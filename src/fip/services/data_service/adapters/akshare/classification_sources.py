"""Pure source conversion. No classification, persistence, or implicit collection.

Index completeness needs an independently verified total for this exact query/batch.
The installed AKShare first-page request alone cannot provide that guarantee.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from fip.platform.source.port import SourceAdapter, SourceRecord
from fip.services.data_service.adapters.akshare.datasets import DATASETS
from fip.services.data_service.classification.models import Evidence, Source

INDEX_DATASETS = {
    "fund_index_passive": "被动指数型",
    "fund_index_enhanced": "增强指数型",
}
DETAIL_FIELDS = {
    "基金类型": "formal_type",
    "投资策略": "investment_strategy",
    "投资目标": "investment_objective",
    "业绩比较基准": "benchmark",
}
BatchState = Literal["UNVERIFIED", "FAILED", "MALFORMED", "EMPTY", "CAPPED", "COMPLETE"]


@dataclass(frozen=True)
class IndexBatch:
    batch_id: str
    indicator: str
    state: BatchState
    record: SourceRecord | None
    payload_ref: str
    evidence: tuple[Evidence, ...] = ()
    diagnostics: tuple[str, ...] = ()
    verified_total: int | None = None

    @property
    def may_withdraw_prior(self) -> bool:
        return self.state == "COMPLETE"

    @property
    def row_count(self) -> int:
        return self.record.row_count if self.record is not None else 0

    @property
    def source_timestamp(self) -> dt.datetime | None:
        return self.record.ingested_at if self.record is not None else None

    @property
    def published_at(self) -> dt.datetime | None:
        return self.record.published_at if self.record is not None else None

    @property
    def provider_available_at(self) -> dt.datetime | None:
        return self.record.provider_available_at if self.record is not None else None

    @property
    def fund_codes(self) -> tuple[str, ...]:
        return tuple(item.raw_value for item in self.evidence)


@dataclass(frozen=True)
class SnowballDetail:
    state: Literal["VALID", "PARTIAL", "MALFORMED", "IDENTITY_MISMATCH"]
    record: SourceRecord
    payload_ref: str
    field_states: dict[str, str]
    evidence: tuple[Evidence, ...] = ()
    diagnostics: tuple[str, ...] = ()


def _fund_code(value: Any) -> bool:
    # Do not repair integers: the provider's leading zeros are part of identity.
    return isinstance(value, str) and re.fullmatch(r"[0-9]{6}", value) is not None


def _evidence(
    record: SourceRecord,
    *,
    code: str,
    field: str,
    normalized: str,
    value: str,
    row: int,
    payload_ref: str,
    provider: str,
) -> Evidence:
    # Operational timeout is not a semantic request parameter.
    params = {k: v for k, v in record.request_params.items() if k != "timeout"}
    identity = json.dumps(
        {
            "adapter": "AKSHARE",
            "provider": provider,
            "dataset": record.dataset,
            "function": DATASETS[record.dataset].callable_name,
            "params": params,
            "provider_fund_code": code,
            "raw_field": field,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return Evidence(
        source="AGGREGATOR",
        confidence="PUBLIC_AGGREGATOR",
        rule_id="SOURCE",
        classified_at=record.ingested_at,
        raw_field=field,
        normalized_field=normalized,
        raw_value=value,
        payload_ref=payload_ref,
        locator=f"identity:{identity};row:{row}",
    )


def source_identity(evidence: Evidence) -> dict[str, Any]:
    """Stable observation key; excludes payload, collection time, batch and row position."""
    if not evidence.locator or not evidence.locator.startswith("identity:"):
        raise ValueError("Evidence has no classification source identity")
    return dict(json.JSONDecoder().raw_decode(evidence.locator[len("identity:") :])[0])


def source_record_from_payload(payload: Any, *, dataset: str) -> SourceRecord:
    """Reconstruct the source transport envelope for an already persisted payload."""
    return SourceRecord(
        dataset=dataset,
        payload=payload.payload,
        row_count=payload.row_count,
        ingested_at=payload.ingested_at,
        request_params=payload.request_params,
        published_at=payload.published_at,
        provider_available_at=payload.provider_available_at,
    )


def parse_index_batch(
    record: SourceRecord,
    *,
    batch_id: str,
    payload_ref: str,
    verified_total: int | None = None,
) -> IndexBatch:
    indicator = INDEX_DATASETS.get(record.dataset, "")

    def result(
        state: BatchState, *diagnostics: str, evidence: tuple[Evidence, ...] = ()
    ) -> IndexBatch:
        return IndexBatch(
            batch_id,
            indicator,
            state,
            record,
            payload_ref,
            evidence,
            tuple(diagnostics),
            verified_total,
        )

    spec = DATASETS.get(record.dataset)
    if not indicator or not spec or record.request_params != spec.fixed_params:
        return result("MALFORMED", "INDEX_QUERY_SCOPE_MISMATCH")
    try:
        frame = pd.read_parquet(io.BytesIO(record.payload))
    except Exception as exc:
        return result("MALFORMED", f"INVALID_PARQUET:{type(exc).__name__}:{exc}")
    if not frame.columns.is_unique or not spec.required_columns <= set(frame.columns):
        return result("MALFORMED", "INDEX_COLUMNS_MISSING_OR_DUPLICATE")
    if len(frame) != record.row_count:
        return result("MALFORMED", "ROW_COUNT_MISMATCH")
    if frame.empty:
        return result("EMPTY", "UNEXPECTED_EMPTY_INDEX_BATCH")
    codes: set[str] = set()
    evidence: list[Evidence] = []
    for position, row in enumerate(frame.to_dict("records")):
        code = row["基金代码"]
        if (
            not _fund_code(code)
            or code in codes
            or not isinstance(row["跟踪标的"], str)
            or not isinstance(row["跟踪方式"], str)
            or row["跟踪标的"] != "全部"
            or row["跟踪方式"] != indicator
        ):
            return result("MALFORMED", f"INVALID_INDEX_ROW:{position}")
        codes.add(code)
        evidence.append(
            _evidence(
                record,
                code=code,
                field="基金代码",
                normalized="index_membership",
                value=code,
                row=position,
                payload_ref=payload_ref,
                provider="EASTMONEY",
            )
        )
    if len(frame) >= 10000:
        return result("CAPPED", "FIRST_PAGE_LIMIT_REACHED", evidence=tuple(evidence))
    if type(verified_total) is not int or verified_total != len(frame):
        return result("UNVERIFIED", "COVERAGE_NOT_VERIFIED", evidence=tuple(evidence))
    return result("COMPLETE", evidence=tuple(evidence))


def parse_snowball_detail(record: SourceRecord, *, payload_ref: str) -> SnowballDetail:
    states = dict.fromkeys(DETAIL_FIELDS, "ABSENT")

    def invalid(state: Literal["MALFORMED", "IDENTITY_MISMATCH"], reason: str) -> SnowballDetail:
        return SnowballDetail(state, record, payload_ref, dict(states), diagnostics=(reason,))

    if record.dataset != "fund_detail_xq":
        return invalid("MALFORMED", "SNOWBALL_DATASET_MISMATCH")
    try:
        frame = pd.read_parquet(io.BytesIO(record.payload))
    except Exception as exc:
        return invalid("MALFORMED", f"INVALID_PARQUET:{type(exc).__name__}:{exc}")
    if (
        not frame.columns.is_unique
        or not {"item", "value"} <= set(frame.columns)
        or len(frame) != record.row_count
    ):
        return invalid("MALFORMED", "SNOWBALL_COLUMNS_OR_ROW_COUNT_INVALID")
    rows: dict[str, list[tuple[int, str]]] = {}
    for position, row in enumerate(frame.to_dict("records")):
        item, value = row["item"], row["value"]
        if not isinstance(item, str) or not item.strip():
            return invalid("MALFORMED", f"INVALID_ITEM:{position}")
        if item not in DETAIL_FIELDS and item != "基金代码":
            continue
        if not isinstance(value, str):
            # Reject lists/maps/numeric values; scalar null is explicit empty.
            if not pd.api.types.is_scalar(value) or not pd.isna(value):
                return invalid("MALFORMED", f"INVALID_VALUE:{position}")
            value = ""
        rows.setdefault(item, []).append((position, value))
    identities = rows.get("基金代码", [])
    requested = record.request_params.get("symbol")
    if not _fund_code(requested) or len(identities) != 1 or identities[0][1] != requested:
        return invalid("IDENTITY_MISMATCH", "PROVIDER_FUND_CODE_MISMATCH_OR_MISSING")
    evidence = []
    diagnostics = []
    for field, normalized in DETAIL_FIELDS.items():
        matches = rows.get(field, [])
        if not matches:
            diagnostics.append(f"ABSENT_FIELD:{field}")
            continue
        if len(matches) > 1:
            states[field] = "DUPLICATE"
            diagnostics.append(f"DUPLICATE_FIELD:{field}")
            continue
        position, value = matches[0]
        states[field] = "PRESENT" if value.strip() else "EMPTY"
        evidence.append(
            _evidence(
                record,
                code=requested,
                field=field,
                normalized=normalized,
                value=value,
                row=position,
                payload_ref=payload_ref,
                provider="SNOWBALL",
            )
        )
    return SnowballDetail(
        "PARTIAL" if diagnostics else "VALID",
        record,
        payload_ref,
        dict(states),
        tuple(evidence),
        tuple(diagnostics),
    )


def parse_fund_list_observations(
    record: SourceRecord, *, payload_ref: str
) -> dict[str, tuple[Evidence, ...]]:
    """Convert saved fund-name rows into source-identified v3 observations."""
    if record.dataset != "fund_list":
        raise ValueError("fund list dataset mismatch")
    frame = pd.read_parquet(io.BytesIO(record.payload))
    required = DATASETS["fund_list"].required_columns
    if not frame.columns.is_unique or not required <= set(frame.columns):
        raise ValueError("fund list columns missing or duplicated")
    if len(frame) != record.row_count:
        raise ValueError("fund list row count mismatch")
    result: dict[str, tuple[Evidence, ...]] = {}
    for position, row in enumerate(frame.to_dict("records")):
        code = row["基金代码"]
        if not _fund_code(code):
            continue
        values: list[Evidence] = []
        fields: tuple[tuple[str, str, Source], ...] = (
            ("基金类型", "formal_type", "AGGREGATOR"),
            ("基金简称", "name", "NAME"),
        )
        for raw_field, normalized, source in fields:
            value = row.get(raw_field)
            if not isinstance(value, str) or not value.strip():
                continue
            identity = json.dumps(
                {
                    "adapter": "AKSHARE",
                    "provider": "EASTMONEY",
                    "dataset": record.dataset,
                    "function": DATASETS[record.dataset].callable_name,
                    "params": dict(record.request_params),
                    "provider_fund_code": code,
                    "raw_field": raw_field,
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            values.append(
                Evidence(
                    source=source,
                    rule_id="SOURCE",
                    confidence="NAME_HINT" if source == "NAME" else "PUBLIC_AGGREGATOR",
                    classified_at=record.ingested_at,
                    raw_field=raw_field,
                    normalized_field=normalized,
                    raw_value=value.strip(),
                    payload_ref=payload_ref,
                    locator=f"identity:{identity};row:{position}",
                )
            )
        result[code] = tuple(values)
    return result


def parse_fund_overview_observations(
    record: SourceRecord, *, payload_ref: str, symbol: str
) -> tuple[Evidence, ...]:
    """Convert only present classification fields from an overview row."""
    if record.dataset != "fund_overview" or record.request_params.get("symbol") != symbol:
        raise ValueError("fund overview identity mismatch")
    frame = pd.read_parquet(io.BytesIO(record.payload))
    if len(frame) != record.row_count or frame.empty or not frame.columns.is_unique:
        raise ValueError("fund overview row/column contract invalid")
    row = frame.iloc[0]
    mapping = {
        "基金类型": "formal_type",
        "投资策略": "investment_strategy",
        "跟踪标的": "tracking_target",
    }
    evidence: list[Evidence] = []
    for raw_field, normalized in mapping.items():
        if raw_field not in frame.columns:
            continue
        value = row[raw_field]
        if not isinstance(value, str):
            if pd.api.types.is_scalar(value) and pd.isna(value):
                value = ""
            else:
                raise ValueError(f"invalid fund overview value for {raw_field}")
        params = {key: value for key, value in record.request_params.items() if key != "timeout"}
        identity = json.dumps(
            {
                "adapter": "AKSHARE",
                "provider": "EASTMONEY",
                "dataset": record.dataset,
                "function": DATASETS[record.dataset].callable_name,
                "params": params,
                "provider_fund_code": symbol,
                "raw_field": raw_field,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        evidence.append(
            Evidence(
                source="AGGREGATOR",
                rule_id="SOURCE",
                confidence="PUBLIC_AGGREGATOR",
                classified_at=record.ingested_at,
                raw_field=raw_field,
                normalized_field=normalized,
                raw_value=value,
                payload_ref=payload_ref,
                locator=f"identity:{identity};row:0",
            )
        )
    return tuple(evidence)


def collect_index_batches(
    adapter: SourceAdapter,
    *,
    batch_id: str,
    payload_refs: dict[str, str],
    verified_totals: dict[str, int] | None = None,
) -> tuple[IndexBatch, ...]:
    """Explicit centralized collection boundary. Calling this performs two adapter fetches.

    The caller owns payload persistence and must supply independently checked coverage
    totals; no fund loop, classifier or database access occurs here.
    """
    results = []
    for dataset, indicator in INDEX_DATASETS.items():
        payload_ref = payload_refs[indicator]
        try:
            record = adapter.fetch(dataset)
        except Exception as exc:
            results.append(
                IndexBatch(
                    batch_id,
                    indicator,
                    "FAILED",
                    getattr(exc, "record", None),
                    payload_ref,
                    diagnostics=(f"{type(exc).__name__}:{exc}",),
                )
            )
            continue
        try:
            parsed = parse_index_batch(
                record,
                batch_id=batch_id,
                payload_ref=payload_ref,
                verified_total=(verified_totals or {}).get(indicator),
            )
        except Exception as exc:
            parsed = IndexBatch(
                batch_id,
                indicator,
                "MALFORMED",
                record,
                payload_ref,
                diagnostics=(f"{type(exc).__name__}:{exc}",),
                verified_total=(verified_totals or {}).get(indicator),
            )
        results.append(parsed)
    return tuple(results)

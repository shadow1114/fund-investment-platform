"""Verified fund company / manager / AUM normalization and retained-data backfill."""

import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.source.port import SourceRecord
from fip.services.data_service.models.fund import Fund, FundBasicInfoHistory

_PLACEHOLDERS = {"nan", "none", "null", "<na>", "--", "-", "暂无"}
_AUM_UNITS = {"": Decimal(1), "万": Decimal(10_000), "亿": Decimal(100_000_000)}
_AUM_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(万|亿)?元?")
_DETAIL_LABELS = {"基金公司": "company", "基金经理": "manager", "最新规模": "aum"}


def _usable_text(value: Any, *, max_length: int, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) and pd.api.types.is_scalar(value) and pd.isna(value):
        return None
    normalized = str(value).strip()
    if not normalized or normalized.casefold() in _PLACEHOLDERS:
        return None
    if len(normalized) > max_length:
        raise ValueError(f"{label} exceeds {max_length} characters")
    return normalized


def _usable_fund_company(value: Any) -> str | None:
    return _usable_text(value, max_length=128, label="fund management company name")


def parse_fund_aum(value: Any) -> Decimal | None:
    """把雪球「最新规模」（如 29.19亿、2177.53万）换算为以元为单位的纯数字。"""
    text_value = _usable_text(value, max_length=64, label="fund aum")
    if text_value is None:
        return None
    match = _AUM_PATTERN.fullmatch(text_value.replace(",", ""))
    if match is None:
        return None
    try:
        amount = Decimal(match.group(1)) * _AUM_UNITS[match.group(2) or ""]
    except InvalidOperation:
        return None
    return amount.quantize(Decimal("0.01"))


def fund_company_from_fields(
    normalized_fields: dict[str, Any], raw_fields: dict[str, Any]
) -> str | None:
    """Use normalized fund_company or the verified AKShare 基金公司 field."""
    if "fund_company" in normalized_fields:
        candidate = _usable_fund_company(normalized_fields["fund_company"])
        if candidate is not None:
            return candidate
    return _usable_fund_company(raw_fields.get("基金公司"))


def _snowball_lookup(record: SourceRecord, *, symbol: str) -> Callable[[str], Any]:
    """Validate an identity-checked Snowball detail response; return a single-item getter."""
    if (
        record.dataset != "fund_detail_xq"
        or record.request_params.get("symbol") != symbol
        or re.fullmatch(r"[0-9]{6}", symbol) is None
    ):
        raise ValueError("fund detail source identity mismatch")
    try:
        frame = pd.read_parquet(io.BytesIO(record.payload))
    except Exception as exc:
        raise ValueError("fund detail source payload is not valid parquet") from exc
    if (
        not frame.columns.is_unique
        or not {"item", "value"} <= set(frame.columns)
        or len(frame) != record.row_count
    ):
        raise ValueError("fund detail source columns or row count are invalid")

    def values_for(item: str) -> list[Any]:
        return cast(list[Any], frame.loc[frame["item"] == item, "value"].tolist())

    identities = values_for("基金代码")
    if len(identities) != 1 or identities[0] != symbol:
        raise ValueError("fund detail source fund code does not match request")

    def single(item: str) -> Any:
        values = values_for(item)
        if len(values) > 1:
            label = _DETAIL_LABELS.get(item, item)
            raise ValueError(f"fund detail source has duplicate {label} values")
        return values[0] if values else None

    return single


def raw_fund_company_from_record(record: SourceRecord, *, symbol: str) -> str | None:
    """Extract only 基金公司 from an identity-checked Snowball detail response."""
    value = _snowball_lookup(record, symbol=symbol)("基金公司")
    if value is None:
        return None
    if not isinstance(value, str):
        if pd.api.types.is_scalar(value) and pd.isna(value):
            return None
        raise ValueError("fund company source value must be text")
    _usable_fund_company(value)
    return value


@dataclass(frozen=True)
class SnowballFundDetail:
    fund_company: str | None
    fund_manager: str | None
    fund_aum: Decimal | None


def fund_detail_from_record(record: SourceRecord, *, symbol: str) -> SnowballFundDetail:
    """Extract 基金公司 / 基金经理 / 最新规模 from a Snowball detail response."""
    single = _snowball_lookup(record, symbol=symbol)
    return SnowballFundDetail(
        fund_company=_usable_fund_company(single("基金公司")),
        fund_manager=_usable_text(single("基金经理"), max_length=256, label="fund manager"),
        fund_aum=parse_fund_aum(single("最新规模")),
    )


@dataclass(frozen=True)
class CompanyBackfillReport:
    scanned: int
    candidates: int
    updated: int


def backfill_fund_companies(
    session: Session, *, dry_run: bool = True, batch_size: int = 500
) -> CompanyBackfillReport:
    """Fill NULL projections from immutable local snapshots; caller owns transaction."""
    if batch_size <= 0 or batch_size > 5000:
        raise ValueError("batch_size must be between 1 and 5000")

    last_id = 0
    scanned = candidates = updated = 0
    while True:
        query = (
            select(Fund)
            .where(Fund.id > last_id, Fund.fund_company.is_(None))
            .order_by(Fund.id)
            .limit(batch_size)
        )
        if not dry_run:
            query = query.execution_options(populate_existing=True).with_for_update()
        funds = session.scalars(query).all()
        if not funds:
            break
        scanned += len(funds)
        last_id = funds[-1].id
        fund_ids = [fund.id for fund in funds]
        histories = session.scalars(
            select(FundBasicInfoHistory)
            .where(FundBasicInfoHistory.fund_id.in_(fund_ids))
            .order_by(
                FundBasicInfoHistory.fund_id,
                FundBasicInfoHistory.available_at.desc(),
                FundBasicInfoHistory.version.desc(),
            )
        ).all()
        by_fund: dict[int, list[FundBasicInfoHistory]] = {}
        for history in histories:
            by_fund.setdefault(history.fund_id, []).append(history)
        for fund in funds:
            candidate = next(
                (
                    value
                    for history in by_fund.get(fund.id, [])
                    if (
                        value := fund_company_from_fields(
                            history.normalized_fields, history.raw_fields
                        )
                    )
                    is not None
                ),
                None,
            )
            if candidate is None:
                continue
            candidates += 1
            if not dry_run:
                # The fund row is locked, so a concurrent/operator-set value wins.
                if fund.fund_company is None:
                    fund.fund_company = candidate
                    updated += 1
        if not dry_run:
            session.flush()
    return CompanyBackfillReport(
        scanned=scanned,
        candidates=candidates,
        updated=0 if dry_run else updated,
    )

"""Verified fund management company normalization and retained-data backfill."""

import io
import re
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.source.port import SourceRecord
from fip.services.data_service.models.fund import Fund, FundBasicInfoHistory


def _usable_company_name(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized or normalized.casefold() in {"nan", "none", "null", "<na>"}:
        return None
    if len(normalized) > 128:
        raise ValueError("fund management company name exceeds 128 characters")
    return normalized


def company_name_from_fields(
    normalized_fields: dict[str, Any], raw_fields: dict[str, Any]
) -> str | None:
    """Use normalized company_name or the verified AKShare 基金公司 field."""
    if "company_name" in normalized_fields:
        candidate = _usable_company_name(normalized_fields["company_name"])
        if candidate is not None:
            return candidate
    return _usable_company_name(raw_fields.get("基金公司"))


def raw_fund_company_from_record(record: SourceRecord, *, symbol: str) -> str | None:
    """Extract only 基金公司 from an identity-checked Snowball detail response."""
    if (
        record.dataset != "fund_detail_xq"
        or record.request_params.get("symbol") != symbol
        or re.fullmatch(r"[0-9]{6}", symbol) is None
    ):
        raise ValueError("fund company source identity mismatch")
    try:
        frame = pd.read_parquet(io.BytesIO(record.payload))
    except Exception as exc:
        raise ValueError("fund company source payload is not valid parquet") from exc
    if (
        not frame.columns.is_unique
        or not {"item", "value"} <= set(frame.columns)
        or len(frame) != record.row_count
    ):
        raise ValueError("fund company source columns or row count are invalid")

    def values_for(item: str) -> list[Any]:
        return cast(list[Any], frame.loc[frame["item"] == item, "value"].tolist())

    identities = values_for("基金代码")
    if len(identities) != 1 or identities[0] != symbol:
        raise ValueError("fund company source fund code does not match request")
    company_values = values_for("基金公司")
    if len(company_values) > 1:
        raise ValueError("fund company source has duplicate company values")
    if not company_values:
        return None
    value = company_values[0]
    if not isinstance(value, str):
        if pd.api.types.is_scalar(value) and pd.isna(value):
            return None
        raise ValueError("fund company source value must be text")
    _usable_company_name(value)
    return value


@dataclass(frozen=True)
class CompanyBackfillReport:
    scanned: int
    candidates: int
    updated: int


def backfill_fund_company_names(
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
            .where(Fund.id > last_id, Fund.company_name.is_(None))
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
                        value := company_name_from_fields(
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
                if fund.company_name is None:
                    fund.company_name = candidate
                    updated += 1
        if not dry_run:
            session.flush()
    return CompanyBackfillReport(
        scanned=scanned,
        candidates=candidates,
        updated=0 if dry_run else updated,
    )

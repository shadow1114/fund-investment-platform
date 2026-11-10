from __future__ import annotations

import calendar
from builtins import list as builtin_list
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import and_, case, column, func, literal, or_, select, true
from sqlalchemy import cast as sa_cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from fip.api.errors import InvalidQueryError, NotFoundError
from fip.platform.decision_data.pit import RiskFreeRatePoint, resolve_visible_until
from fip.services.data_service.models.fund import (
    Fund,
    FundBasicInfoHistory,
    FundClassificationHistory,
    FundClassificationRevision,
    FundManagerAssignment,
    FundShareClass,
    FundStatusHistory,
    InvestmentEligibility,
    ProviderFundIdentity,
)
from fip.services.data_service.models.governance import AuditLog, DataProvider
from fip.services.data_service.models.market import FundNav
from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable
from fip.services.data_service.repositories.benchmark import SqlBenchmarkPitRepository
from fip.services.data_service.repositories.classification import SqlClassificationPitRepository
from fip.services.data_service.repositories.fee import SqlFeePitRepository
from fip.services.data_service.repositories.nav import SqlNavPitRepository
from fip.services.data_service.repositories.risk_free_rate import SqlRiskFreeRatePitRepository
from fip.services.factor_service.calculation import _returns_from_levels
from fip.services.factor_service.live_analysis import FACTOR_CATALOG, calculate_period_factor_values
from fip.services.factor_service.models import FactorRun, FactorValue
from fip.services.fund_service.models import (
    FundEvaluation,
    FundRanking,
    FundScore,
    FundScoreAttribution,
    FundTier,
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupMember,
    PeerGroupSnapshot,
    SelectionConditionRecord,
)
from fip.services.portfolio_service.models import (
    BacktestRecord,
    DecisionRecord,
    OptimizationRecord,
    PortfolioRecord,
)
from fip.strategy_library.factor_types import ReturnObservation
from fip.strategy_library.rates import TenorRate, interpolate_rate

_TENOR_DAYS = {
    "ON": 1,
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "2Y": 730,
    "3Y": 1095,
    "5Y": 1825,
    "7Y": 2555,
    "10Y": 3650,
    "30Y": 10950,
}
_TARGET_TENOR_DAYS = {
    tenor: _TENOR_DAYS[tenor] for tenor in ("1M", "3M", "6M", "1Y", "3Y", "5Y")
}


def _resolve_risk_free_curve(
    points: tuple[RiskFreeRatePoint, ...], target_days: int, currency: str
) -> tuple[tuple[date, Decimal, str], ...]:
    by_date: dict[date, list[RiskFreeRatePoint]] = {}
    for point in points:
        if point.tenor in _TENOR_DAYS:
            by_date.setdefault(point.effective_at, []).append(point)

    resolved: list[tuple[date, Decimal, str]] = []
    for effective_at, curve in sorted(by_date.items()):
        exact = next((point for point in curve if _TENOR_DAYS[point.tenor] == target_days), None)
        if exact is not None:
            resolved.append((effective_at, exact.rate, "EXACT"))
            continue
        lower = [point for point in curve if _TENOR_DAYS[point.tenor] < target_days]
        upper = [point for point in curve if _TENOR_DAYS[point.tenor] > target_days]
        if not lower or not upper:
            continue
        lower_point = max(lower, key=lambda point: _TENOR_DAYS[point.tenor])
        upper_point = min(upper, key=lambda point: _TENOR_DAYS[point.tenor])
        rate = interpolate_rate(
            TenorRate(currency, _TENOR_DAYS[lower_point.tenor], lower_point.rate),
            TenorRate(currency, _TENOR_DAYS[upper_point.tenor], upper_point.rate),
            target_days,
        )
        resolved.append((effective_at, rate, "INTERPOLATED"))
    return tuple(resolved)


class RepositoryAdapter:
    """Small, deterministic boundary shared by the API resource adapters.

    Domain-specific query implementations can replace the protected loading
    hooks without changing the HTTP-facing repository contract.
    """

    def __init__(self, session: object, resource: str) -> None:
        self.session = session
        self.resource = resource

    def _list_rows(self, **_: object) -> list[Mapping[str, object]]:
        return []

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        return next(
            (row for row in self._list_rows() if row.get("id") == identifier),
            None,
        )

    def list(self, **filters: object) -> list[dict[str, object]]:
        rows = (dict(row) for row in self._list_rows(**filters))
        return sorted(rows, key=lambda row: (str(row.get("name", "")), str(row.get("id", ""))))

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        sort: str | None,
        order: str,
        **filters: object,
    ) -> tuple[builtin_list[dict[str, object]], int]:
        """Compatibility boundary for seeded adapters; SQL repositories override it."""
        _ = sort, order
        rows = self.list(**filters)
        offset = (page - 1) * page_size
        return rows[offset : offset + page_size], len(rows)

    def get(self, identifier: str) -> Mapping[str, object]:
        row = self._get_row(identifier)
        if row is None:
            raise NotFoundError(self.resource, identifier)
        return dict(row)


class FundRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "fund")

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        sort: str | None,
        order: str,
        **filters: object,
    ) -> tuple[list[dict[str, object]], int]:
        """Filter, count, sort, and page unique share classes in PostgreSQL.

        The request-scoped API session is new when this method is entered. Set
        its connection isolation before the first statement so the page query
        and the compatibility projection below see one MVCC snapshot.
        """
        if page < 1 or page_size < 1:
            raise InvalidQueryError("page and page_size must be positive")
        if not isinstance(self.session, Session):
            return super().list_page(
                page=page, page_size=page_size, sort=sort, order=order, **filters
            )
        session = self._session()
        if filters.get("management_company_id") is not None:
            raise InvalidQueryError("management_company_id is unavailable for the current data set")
        if filters.get("aum_min") is not None or filters.get("aum_max") is not None:
            raise InvalidQueryError("aum filters are unavailable for the current data set")

        # Request sessions are created in dependencies._new_session and have
        # not begun a DB transaction yet. Direct repository callers may have
        # an outer transaction already (for example, a test fixture), in which
        # case the caller owns its isolation level.
        if not session.in_transaction():
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})

        view_date = _query_date(filters.get("as_of_date")) or date.today()
        visible_until = resolve_visible_until(view_date)
        revision_id = (
            select(FundClassificationRevision.id)
            .where(
                FundClassificationRevision.fund_id == Fund.id,
                FundClassificationRevision.scheme == "FIP_CLASSIFICATION",
                FundClassificationRevision.available_at <= visible_until,
            )
            .order_by(FundClassificationRevision.version.desc())
            .limit(1)
            .correlate(Fund)
            .scalar_subquery()
        )
        classification_row = (
            select(FundClassificationHistory.classification_result)
            .where(
                FundClassificationHistory.revision_id == revision_id,
                FundClassificationHistory.valid_from <= view_date,
                FundClassificationHistory.valid_to.is_(None)
                | (FundClassificationHistory.valid_to > view_date),
            )
            .limit(1)
            .correlate(Fund)
            .scalar_subquery()
        )
        classification = classification_row
        legacy_code = self._legacy_classification_code(
            revision_id, classification, visible_until, view_date
        )
        fund_company = self._fund_company_expression(
            view_date if filters.get("as_of_date") else None, visible_until
        )
        akshare_code = (
            select(ProviderFundIdentity.provider_fund_id)
            .join(DataProvider, DataProvider.id == ProviderFundIdentity.provider_id)
            .where(
                ProviderFundIdentity.share_class_id == FundShareClass.id,
                DataProvider.provider_code == "AKSHARE",
                ProviderFundIdentity.provider_fund_id.op("~")(r"^[0-9]{6}$"),
                ProviderFundIdentity.available_at <= visible_until,
                ProviderFundIdentity.valid_from <= view_date,
                ProviderFundIdentity.valid_to.is_(None)
                | (ProviderFundIdentity.valid_to > view_date),
            )
            .order_by(
                ProviderFundIdentity.valid_from.desc(),
                ProviderFundIdentity.available_at.desc(),
                ProviderFundIdentity.id.desc(),
            )
            .limit(1)
            .correlate(FundShareClass)
            .scalar_subquery()
        )

        predicates: list[ColumnElement[bool]] = []
        fund_name = filters.get("fund_name")
        if isinstance(fund_name, str) and fund_name.strip():
            escaped = (
                fund_name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            predicates.append(Fund.product_name.ilike(f"%{escaped}%", escape="\\"))
        fund_code = filters.get("fund_code")
        if isinstance(fund_code, str) and fund_code.strip():
            normalized_code = fund_code.strip()
            if len(normalized_code) != 6 or any(
                char < "0" or char > "9" for char in normalized_code
            ):
                raise InvalidQueryError("fund_code must contain exactly six ASCII digits")
            predicates.append(akshare_code == normalized_code)
        requested_company = filters.get("fund_company")
        if isinstance(requested_company, str) and requested_company.strip():
            predicates.append(fund_company == requested_company.strip())
        sub_status = filters.get("sub_status")
        if sub_status not in (None, "", "开放"):
            raise InvalidQueryError("sub_status only supports 开放")
        if sub_status == "开放":
            predicates.append(literal("开放") == sub_status)

        manager_id = filters.get("manager_id")
        if manager_id is not None:
            try:
                manager_pk = int(str(manager_id))
            except ValueError as exc:
                raise InvalidQueryError("manager_id must be a numeric manager identifier") from exc
            predicates.append(
                select(1)
                .select_from(FundManagerAssignment)
                .where(
                    FundManagerAssignment.fund_id == Fund.id,
                    FundManagerAssignment.manager_id == manager_pk,
                    FundManagerAssignment.available_at <= visible_until,
                    FundManagerAssignment.valid_from <= view_date,
                    FundManagerAssignment.valid_to.is_(None)
                    | (FundManagerAssignment.valid_to > view_date),
                )
                .exists()
            )
        fund_types = filters.get("fund_type")
        if fund_types:
            predicates.append(legacy_code.in_(tuple(cast(Sequence[str], fund_types))))

        for dimension in (
            "asset_class",
            "strategy",
            "geography",
            "product_structure",
            "market_attributes",
        ):
            choices = filters.get(dimension)
            if choices:
                predicates.append(
                    self._classification_dimension_predicate(
                        classification, dimension, cast(Sequence[str], choices)
                    )
                )
        tags = filters.get("strategy_tags")
        if tags:
            predicates.append(
                self._strategy_tag_predicate(classification, cast(Sequence[str], tags))
            )
        statuses = filters.get("classification_status")
        if statuses:
            predicates.append(
                self._classification_status_predicate(classification, cast(Sequence[str], statuses))
            )

        lifecycle = filters.get("lifecycle_status")
        if lifecycle:
            status = (
                select(FundStatusHistory.lifecycle_status)
                .where(
                    FundStatusHistory.share_class_id == FundShareClass.id,
                    FundStatusHistory.available_at <= visible_until,
                    FundStatusHistory.valid_from <= view_date,
                    FundStatusHistory.valid_to.is_(None) | (FundStatusHistory.valid_to > view_date),
                )
                .order_by(
                    FundStatusHistory.valid_from.desc(),
                    FundStatusHistory.available_at.desc(),
                    FundStatusHistory.id.desc(),
                )
                .limit(1)
                .correlate(FundShareClass)
                .scalar_subquery()
            )
            predicates.append(
                func.coalesce(status, "UNKNOWN").in_(tuple(cast(Sequence[str], lifecycle)))
            )
        eligibility_choices = filters.get("investment_eligibility")
        if eligibility_choices:
            eligibility = (
                select(InvestmentEligibility.eligibility_status)
                .where(
                    InvestmentEligibility.share_class_id == FundShareClass.id,
                    InvestmentEligibility.effective_at <= view_date,
                    InvestmentEligibility.available_at <= visible_until,
                )
                .order_by(
                    InvestmentEligibility.effective_at.desc(),
                    InvestmentEligibility.version.desc(),
                )
                .limit(1)
                .correlate(FundShareClass)
                .scalar_subquery()
            )
            predicates.append(
                func.coalesce(eligibility, "UNKNOWN").in_(
                    tuple(cast(Sequence[str], eligibility_choices))
                )
            )
        inception_from = _query_date(filters.get("inception_date_from"))
        inception_to = _query_date(filters.get("inception_date_to"))
        if inception_from:
            predicates.append(FundShareClass.inception_date >= inception_from)
        if inception_to:
            predicates.append(FundShareClass.inception_date <= inception_to)

        filtered = (
            select(
                Fund.id.label("fund_pk"),
                Fund.fund_code.label("fund_id"),
                Fund.product_name.label("fund_name"),
                Fund.fund_company.label("fund_company_current"),
                fund_company.label("fund_company"),
                FundShareClass.id.label("share_class_pk"),
                FundShareClass.share_class_code.label("share_class"),
                FundShareClass.inception_date.label("inception_date"),
                akshare_code.label("fund_code"),
                literal("开放").label("sub_status"),
                literal(None).label("aum"),
            )
            .select_from(Fund)
            .join(FundShareClass, FundShareClass.fund_id == Fund.id)
            .where(*predicates)
            .cte("filtered_fund_share_classes")
        )
        sort_field = (
            sort
            if sort
            in {
                "fund_code",
                "fund_name",
                "fund_company",
                "sub_status",
                "inception_date",
                "aum",
            }
            else "fund_name"
        )
        sort_expr = {
            "fund_code": filtered.c.fund_code,
            "fund_name": filtered.c.fund_name,
            "fund_company": filtered.c.fund_company,
            "sub_status": filtered.c.sub_status,
            "inception_date": filtered.c.inception_date,
            "aum": filtered.c.aum,
        }[sort_field]
        direction = (
            sort_expr.desc().nulls_last() if order == "desc" else sort_expr.asc().nulls_last()
        )
        page_rows = (
            select(filtered)
            .order_by(direction, filtered.c.fund_id.asc(), filtered.c.share_class_pk.asc())
            .limit(page_size)
            .offset((page - 1) * page_size)
            .cte("fund_share_class_page")
        )
        total = (
            select(func.count().label("total_items")).select_from(filtered).cte("fund_page_total")
        )
        outer_sort_expr = getattr(page_rows.c, sort_field)
        outer_direction = (
            outer_sort_expr.desc().nulls_last()
            if order == "desc"
            else outer_sort_expr.asc().nulls_last()
        )
        statement = (
            select(
                Fund,
                FundShareClass,
                page_rows.c.fund_code,
                page_rows.c.fund_company,
                page_rows.c.sub_status,
                total.c.total_items,
            )
            .select_from(total.outerjoin(page_rows, true()))
            .outerjoin(Fund, Fund.id == page_rows.c.fund_pk)
            .outerjoin(FundShareClass, FundShareClass.id == page_rows.c.share_class_pk)
            .order_by(
                outer_direction,
                page_rows.c.fund_id.asc(),
                page_rows.c.share_class_pk.asc(),
            )
        )
        fetched = session.execute(statement).all()
        if not fetched:
            return [], 0
        total_items = int(fetched[0].total_items)
        result: list[dict[str, object]] = []
        for fund, share_class, code, company, status, _ in fetched:
            if fund is None or share_class is None:
                continue
            row = self._summary(fund, share_class, view_date)
            row.update(
                {
                    "fund_id": fund.fund_code,
                    "fund_code": code,
                    "fund_name": fund.product_name,
                    "fund_company": company,
                    "asset_type": fund.asset_type,
                    "fund_manager": fund.fund_manager,
                    "fund_aum": fund.fund_aum,
                    "fund_management_fee": fund.fund_management_fee,
                    "fund_custody_fee": fund.fund_custody_fee,
                    "sub_status": status,
                    "share_class_id": str(share_class.id),
                    "share_class": share_class.share_class_code,
                    "inception_date": (
                        share_class.inception_date.isoformat()
                        if share_class.inception_date
                        else None
                    ),
                }
            )
            # No source-backed company entity ID exists for the list projection.
            row["management_company_id"] = None
            result.append(row)
        return result, total_items

    def list_management_companies(self, *, as_of_date: str | None = None) -> list[str]:
        session = self._session()
        if not session.in_transaction():
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        effective_date = _query_date(as_of_date)
        visible_until = resolve_visible_until(effective_date or date.today())
        company = self._fund_company_expression(effective_date, visible_until)
        values = session.scalars(
            select(company)
            .select_from(Fund)
            .where(company.is_not(None))
            .distinct()
            .order_by(company.asc())
        )
        return [str(value) for value in values if value]

    def _fund_company_expression(
        self, effective_date: date | None, visible_until: datetime
    ) -> ColumnElement[Any]:
        if effective_date is None:
            return func.nullif(func.btrim(Fund.fund_company), "")
        normalized = func.nullif(
            func.btrim(FundBasicInfoHistory.normalized_fields["fund_company"].as_string()), ""
        )
        raw = func.nullif(func.btrim(FundBasicInfoHistory.raw_fields["基金公司"].as_string()), "")
        invalid_names = ("nan", "none", "null", "<na>")
        normalized_usable = and_(
            normalized.is_not(None),
            func.lower(normalized).not_in(invalid_names),
            func.length(normalized) <= 128,
        )
        raw_usable = and_(
            raw.is_not(None),
            func.lower(raw).not_in(invalid_names),
            func.length(raw) <= 128,
        )
        value = case(
            (normalized_usable, normalized),
            (raw_usable, raw),
            else_=None,
        )
        usable = and_(
            FundBasicInfoHistory.fund_id == Fund.id,
            FundBasicInfoHistory.available_at <= visible_until,
            value.is_not(None),
        )
        return (
            select(value)
            .where(usable)
            .order_by(
                FundBasicInfoHistory.available_at.desc(),
                FundBasicInfoHistory.version.desc(),
                FundBasicInfoHistory.id.desc(),
            )
            .limit(1)
            .correlate(Fund)
            .scalar_subquery()
        )

    def _classification_dimension_predicate(
        self,
        classification: ColumnElement[Any],
        dimension: str,
        choices: Sequence[str],
    ) -> ColumnElement[bool]:
        result = classification[dimension]
        status = result["status"].as_string()
        value = result["value"]
        evaluation = result["evaluation_state"].as_string()
        options = []
        if "UNKNOWN" in choices:
            options.append(
                or_(
                    classification.is_(None),
                    and_(
                        status == "UNKNOWN",
                        evaluation == "EVALUATED",
                    ),
                )
            )
        confirmed = [choice for choice in choices if choice != "UNKNOWN"]
        if confirmed:
            value_matches = [
                or_(value.as_string() == choice, value.contains([choice])) for choice in confirmed
            ]
            options.append(
                and_(
                    status == "CONFIRMED",
                    evaluation == "EVALUATED",
                    or_(*value_matches),
                )
            )
        return or_(*options)

    def _classification_status_predicate(
        self, classification: ColumnElement[Any], statuses: Sequence[str]
    ) -> ColumnElement[bool]:
        values = []
        for dimension in ("asset_class", "strategy"):
            result = classification[dimension]
            evaluation = result["evaluation_state"].as_string()
            status = result["status"].as_string()
            values.append(
                and_(
                    or_(evaluation.is_(None), ~evaluation.in_(("PAUSED", "NOT_EVALUATED"))),
                    status.in_(tuple(statuses)),
                )
            )
        if "UNKNOWN" in statuses:
            values.append(classification.is_(None))
        return or_(*values)

    def _strategy_tag_predicate(
        self, classification: ColumnElement[Any], tags: Sequence[str]
    ) -> ColumnElement[bool]:
        choices = []
        for tag in tags:
            result = classification["strategy_tag_results"][tag]
            choices.append(
                and_(
                    result["status"].as_string() == "CONFIRMED",
                    result["value"].as_string() == tag,
                    result["evaluation_state"].as_string() == "EVALUATED",
                    func.jsonb_array_length(func.coalesce(result["evidence"], sa_cast("[]", JSONB)))
                    > 0,
                )
            )
        return and_(classification.is_not(None), or_(*choices))

    def _legacy_classification_code(
        self,
        revision_id: ColumnElement[Any],
        classification: ColumnElement[Any],
        visible_until: datetime,
        view_date: date,
    ) -> ColumnElement[Any]:
        from fip.services.data_service.models.fund import FundClassificationHistory

        legacy = (
            select(FundClassificationHistory.classification_code)
            .where(
                FundClassificationHistory.fund_id == Fund.id,
                FundClassificationHistory.classification_scheme == "FIP_INTERNAL_L2",
                FundClassificationHistory.revision_id.is_(None),
                FundClassificationHistory.available_at <= visible_until,
                FundClassificationHistory.valid_from <= view_date,
                FundClassificationHistory.valid_to.is_(None)
                | (FundClassificationHistory.valid_to > view_date),
            )
            .order_by(
                FundClassificationHistory.valid_from.desc(),
                FundClassificationHistory.available_at.desc(),
                FundClassificationHistory.id.desc(),
            )
            .limit(1)
            .correlate(Fund)
            .scalar_subquery()
        )
        asset = classification["asset_class"]
        strategy = classification["strategy"]
        tag = classification["strategy_tag_results"]["QUANTITATIVE"]
        tag_evidence = (
            func.jsonb_array_elements(func.coalesce(tag["evidence"], sa_cast("[]", JSONB)))
            .table_valued(column("value", JSONB))
            .alias("tag_evidence")
        )
        evidence_value = tag_evidence.c.value
        invalid_negative_evidence = or_(
            evidence_value["rule_id"].as_string().is_distinct_from("TAG_QUANTITATIVE"),
            evidence_value["rationale"].as_string().is_(None),
            ~evidence_value["rationale"].as_string().contains("polarity=NEGATIVE"),
            func.jsonb_array_length(
                func.coalesce(evidence_value["required_observations"], sa_cast("[]", JSONB))
            )
            == 0,
        )
        has_invalid_negative_evidence = (
            select(1)
            .select_from(tag_evidence)
            .where(invalid_negative_evidence)
            .correlate(Fund)
            .exists()
        )
        negative_evidence = and_(
            func.jsonb_array_length(func.coalesce(tag["evidence"], sa_cast("[]", JSONB))) > 0,
            ~has_invalid_negative_evidence,
        )
        manual_rejection = self._verified_manual_tag_rejection(
            revision_id, classification, tag, visible_until, view_date
        )
        tag_admitted = and_(
            tag["status"].as_string() == "UNKNOWN",
            tag["evaluation_state"].as_string() == "EVALUATED",
            or_(negative_evidence, manual_rejection),
        )
        projected = case(
            (Fund.grouping_status != "CONFIRMED", None),
            (classification.is_(None), None),
            (asset["status"].as_string() != "CONFIRMED", None),
            (strategy["status"].as_string() == "CONFLICT", None),
            (
                and_(
                    classification["scheme"].as_string() == "FIP_CLASSIFICATION",
                    strategy["status"].as_string() != "CONFIRMED",
                ),
                None,
            ),
            (asset["value"].as_string() == "BOND", "BOND"),
            (asset["value"].as_string() == "MIXED", "HYBRID"),
            (
                and_(
                    asset["value"].as_string() == "EQUITY",
                    strategy["status"].as_string() == "CONFIRMED",
                    strategy["value"].as_string() == "ACTIVE",
                    tag_admitted,
                ),
                "ACTIVE_EQUITY",
            ),
            (
                and_(
                    asset["value"].as_string() == "EQUITY",
                    strategy["status"].as_string() == "CONFIRMED",
                    strategy["value"].as_string() == "PASSIVE_INDEX",
                ),
                "PASSIVE_EQUITY",
            ),
            else_=None,
        )
        return case((revision_id.is_not(None), projected), else_=legacy)

    def _verified_manual_tag_rejection(
        self,
        revision_id: ColumnElement[Any],
        classification: ColumnElement[Any],
        tag: ColumnElement[Any],
        visible_until: datetime,
        view_date: date,
    ) -> ColumnElement[bool]:
        from fip.services.data_service.models.fund import FundClassificationReviewCase

        history = FundClassificationHistory
        audit = AuditLog
        review_case = FundClassificationReviewCase
        detail = audit.detail
        scope_start = detail["valid_from"].as_string()
        scope_end = detail["valid_to"].as_string()
        interval_start = (
            select(history.valid_from)
            .where(
                history.revision_id == revision_id,
                history.valid_from <= view_date,
                history.valid_to.is_(None) | (history.valid_to > view_date),
            )
            .limit(1)
            .correlate(Fund)
            .scalar_subquery()
        )
        interval_end = (
            select(history.valid_to)
            .where(
                history.revision_id == revision_id,
                history.valid_from <= view_date,
                history.valid_to.is_(None) | (history.valid_to > view_date),
            )
            .limit(1)
            .correlate(Fund)
            .scalar_subquery()
        )
        decision = detail["tag_decisions"]["QUANTITATIVE"]
        return (
            select(1)
            .select_from(
                audit.__table__.join(
                    review_case.__table__,
                    review_case.id == sa_cast(detail["case_id"].as_string(), review_case.id.type),
                )
            )
            .where(
                audit.resource_type == "fund_classification",
                audit.resource_id == sa_cast(Fund.id, audit.resource_id.type),
                audit.action == "REVIEW",
                audit.created_at <= visible_until,
                func.btrim(audit.operator) != "",
                audit.detail["revision_id"].as_string()
                == sa_cast(revision_id, audit.resource_id.type),
                tag["manual_action"].as_string() == "REJECT",
                tag["evaluation_state"].as_string() == "EVALUATED",
                audit.detail["expected_revision"].as_string()
                == sa_cast(review_case.revision_id, audit.resource_id.type),
                review_case.fund_id == Fund.id,
                review_case.revision_id
                == sa_cast(
                    audit.detail["expected_revision"].as_string(), review_case.revision_id.type
                ),
                select(1)
                .select_from(FundClassificationRevision)
                .where(
                    FundClassificationRevision.id == revision_id,
                    FundClassificationRevision.reviewed.is_(True),
                    FundClassificationRevision.available_at <= visible_until,
                    FundClassificationRevision.scheme == "FIP_CLASSIFICATION",
                )
                .exists(),
                func.btrim(detail["reason"].as_string()) != "",
                decision["action"].as_string() == "REJECT",
                func.jsonb_array_length(func.coalesce(decision["evidence"], sa_cast("[]", JSONB)))
                > 0,
                detail["result_tag_results"]["QUANTITATIVE"] == tag,
                scope_start <= sa_cast(interval_start, scope_start.type),
                or_(
                    scope_end.is_(None),
                    and_(
                        interval_end.is_not(None),
                        sa_cast(interval_end, scope_end.type) <= scope_end,
                    ),
                ),
            )
            .correlate(Fund)
            .exists()
        )

    def _list_rows(self, **filters: object) -> list[Mapping[str, object]]:
        if not isinstance(self.session, Session):
            return super()._list_rows(**filters)
        as_of = _query_date(filters.get("as_of_date")) or date.today()
        pairs = cast(
            list[tuple[Fund, FundShareClass]],
            self.session.execute(select(Fund, FundShareClass).join(FundShareClass)).tuples().all(),
        )
        return [self._summary(fund, share_class, as_of) for fund, share_class in pairs]

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if not isinstance(self.session, Session):
            return super()._get_row(identifier)
        pair = self._share_class(identifier)
        if pair is None:
            return None
        fund, share_class = pair
        return self._summary(fund, share_class, date.today())

    def read_detail(self, identifier: str, *, as_of_date: str | None) -> Mapping[str, object]:
        if not isinstance(self.session, Session):
            return self.get(identifier)
        pair = self._required_share_class(identifier)
        fund, share_class = pair
        view_date = _query_date(as_of_date) or date.today()
        summary = self._summary(fund, share_class, view_date)
        classification = SqlClassificationPitRepository(
            self._session(), resolve_visible_until(view_date)
        ).current(fund.id)
        benchmark = SqlBenchmarkPitRepository(
            self._session(), resolve_visible_until(view_date)
        ).resolve(
            share_class.id, classification.classification_code if classification else "UNKNOWN"
        )
        fees = SqlFeePitRepository(self._session(), resolve_visible_until(view_date)).current(
            share_class.id
        )
        return {
            **summary,
            "classification_version": (
                classification.valid_from.isoformat() if classification is not None else "UNKNOWN"
            ),
            "manager_ids": self._manager_ids(fund.id, view_date),
            "benchmark": {
                "benchmark_id": str(benchmark.benchmark_id)
                if benchmark.benchmark_id is not None
                else "UNKNOWN",
                "benchmark_name": "UNKNOWN",
                "benchmark_type": "UNKNOWN",
                "mapping_version": benchmark.mapping_version or "UNKNOWN",
                "components": [
                    {"benchmark_id": str(item.index_id), "weight": item.weight}
                    for item in benchmark.components
                ],
                "status": benchmark.status,
            },
            "fee_structure": [
                {
                    "expense_type": fee.fee_type,
                    "expense_rate": fee.rate,
                    "included_in_nav": "UNKNOWN",
                    "included_in_backtest": False,
                    "inclusion_source": "NOT_DECLARED",
                }
                for fee in fees
            ],
        }

    def read_nav_series(
        self,
        identifier: str,
        *,
        date_from: str | None,
        date_to: str | None,
        frequency: str,
        nav_type: str,
        as_of_date: str | None,
    ) -> Mapping[str, object]:
        _ = frequency
        _fund, share_class = self._required_share_class(identifier)
        view_date = _query_date(as_of_date) or date.today()
        visible_until = resolve_visible_until(view_date)
        start = (
            _query_date(date_from)
            or share_class.inception_date
            # Many ingested share classes lack an inception date; fall back to the
            # first visible NAV instead of collapsing the range to the view date.
            or self._session().scalar(
                select(func.min(FundNav.effective_at)).where(
                    FundNav.share_class_id == share_class.id,
                    FundNav.available_at <= visible_until,
                )
            )
            or view_date
        )
        end = _query_date(date_to) or view_date
        if end < start:
            raise InvalidQueryError("date_from must not be after date_to")
        data: list[dict[str, object]]
        if nav_type == "ADJUSTED":
            try:
                points = SqlNavPitRepository(self._session(), visible_until).adjusted_nav_series(
                    share_class.id, start, end
                )
            except AdjustedNavUnavailable:
                unavailable_dates = (
                    self._session()
                    .execute(
                        select(FundNav.effective_at)
                        .where(
                            FundNav.share_class_id == share_class.id,
                            FundNav.available_at <= visible_until,
                            FundNav.effective_at.between(start, end),
                        )
                        .distinct()
                        .order_by(FundNav.effective_at)
                    )
                    .scalars()
                )
                data = [
                    {
                        "date": point_date.isoformat(),
                        "nav": None,
                        "nav_status": "UNAVAILABLE",
                        "nav_reason": "ADJUSTED_NAV_UNAVAILABLE",
                    }
                    for point_date in unavailable_dates
                ]
            else:
                data = [
                    {
                        "date": point.effective_at.isoformat(),
                        "nav": float(point.adjusted_nav),
                        "nav_status": "VALID",
                        "nav_reason": None,
                    }
                    for point in points
                ]
        else:
            rows = (
                self._session()
                .execute(
                    select(FundNav)
                    .where(
                        FundNav.share_class_id == share_class.id,
                        FundNav.available_at <= visible_until,
                        FundNav.effective_at.between(start, end),
                    )
                    .order_by(FundNav.effective_at, FundNav.version.desc())
                )
                .scalars()
            )
            latest: dict[date, FundNav] = {}
            for row in rows:
                latest.setdefault(row.effective_at, row)
            data = [
                {
                    "date": point_date.isoformat(),
                    "nav": float(row.unit_nav),
                    "nav_status": "VALID",
                    "nav_reason": None,
                }
                for point_date, row in sorted(latest.items())
            ]
        if frequency != "DAILY":
            buckets: dict[tuple[int, int], dict[str, object]] = {}
            for point in data:
                point_date = date.fromisoformat(str(point["date"]))
                key = (
                    (point_date.isocalendar().year, point_date.isocalendar().week)
                    if frequency == "WEEKLY"
                    else (point_date.year, point_date.month)
                )
                buckets[key] = point
            data = list(buckets.values())
        return {
            "data": {"fund_id": identifier, "points": data},
            "meta": {
                "adjustment_rule_version": "UNKNOWN",
                "unavailable_count": sum(1 for point in data if point["nav"] is None),
            },
        }

    def read_live_factor_analysis(
        self,
        identifier: str,
        *,
        evaluation_period: str,
        as_of_date: str | None,
    ) -> Mapping[str, object]:
        """Calculate display factors from PIT inputs without persisting factor values."""
        from fip.platform.decision_data.context import RuntimeMode
        from fip.services.fund_service.policy import load_evaluation_policy

        periods_months = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36, "5Y": 60}
        view_date = _query_date(as_of_date) or date.today()
        visible_until = resolve_visible_until(view_date)
        session = self._session()
        fund, share_class = self._required_share_class(identifier)
        if evaluation_period == "ALL":
            start = (
                share_class.inception_date
                or session.scalar(
                    select(func.min(FundNav.effective_at)).where(
                        FundNav.share_class_id == share_class.id,
                        FundNav.available_at <= visible_until,
                    )
                )
                or view_date
            )
            span_days = max((view_date - start).days, 1)
            months = max(1, round(span_days / 30.4375))
            # Match the risk-free tenor to the actual span, capped at the longest tenor.
            risk_free_target_days = min(span_days, _TENOR_DAYS["30Y"])
        else:
            months = periods_months[evaluation_period]
            year, month_index = divmod(view_date.year * 12 + view_date.month - 1 - months, 12)
            target_month = month_index + 1
            start = date(
                year, target_month, min(view_date.day, calendar.monthrange(year, target_month)[1])
            )
            risk_free_target_days = _TARGET_TENOR_DAYS[evaluation_period]

        # Read one prior week so the return at the selected period's first date has
        # a valid preceding NAV. Adjusted NAV itself is recalculated under PIT.
        load_from = start - timedelta(days=7)
        nav_quality: str | None = None
        try:
            nav_points = SqlNavPitRepository(session, visible_until).adjusted_nav_series(
                share_class.id, load_from, view_date
            )
        except AdjustedNavUnavailable:
            nav_points = []
            nav_quality = "ADJUSTED_NAV_UNAVAILABLE"
        fund_returns = tuple(
            point
            for point in _returns_from_levels(
                tuple((item.effective_at, item.adjusted_nav) for item in nav_points)
            )
            if point.effective_at > start
        )

        classification = SqlClassificationPitRepository(session, visible_until).current(fund.id)
        classification_code = classification.classification_code if classification else "UNKNOWN"
        benchmark_repository = SqlBenchmarkPitRepository(session, visible_until)
        benchmark_resolution = benchmark_repository.resolve(share_class.id, classification_code)
        benchmark_returns: tuple[ReturnObservation, ...] = ()
        if benchmark_resolution.status == "AVAILABLE":
            benchmark_levels = benchmark_repository.composite_series(
                benchmark_resolution, load_from, view_date
            )
            benchmark_returns = tuple(
                point
                for point in _returns_from_levels(
                    tuple((day, value) for day, value, _quality in benchmark_levels)
                )
                if point.effective_at > start
            )

        # Resolve the selected currency curve exactly, then interpolate between
        # adjacent tenors when the policy tenor is absent on a curve date.
        risk_free_curve = SqlRiskFreeRatePitRepository(session, visible_until).curve_series(
            share_class.base_currency, start, view_date
        )
        resolved_rates = _resolve_risk_free_curve(
            risk_free_curve, risk_free_target_days, share_class.base_currency
        )
        latest_rate = float(resolved_rates[-1][1]) if resolved_rates else None
        rates_by_date = {effective_at: float(rate) for effective_at, rate, _ in resolved_rates}
        risk_free_quality = (
            "INTERPOLATED"
            if any(quality == "INTERPOLATED" for _, _, quality in resolved_rates)
            else "EXACT"
            if resolved_rates
            else "UNAVAILABLE"
        )
        risk_free_returns: list[ReturnObservation] = []
        rate_dates = sorted(rates_by_date)
        active_rate: float | None = None
        cursor = 0
        for point in fund_returns:
            while cursor < len(rate_dates) and rate_dates[cursor] <= point.effective_at:
                active_rate = rates_by_date[rate_dates[cursor]]
                cursor += 1
            if active_rate is not None:
                risk_free_returns.append(ReturnObservation(point.effective_at, active_rate / 252))

        policy_path = Path(__file__).parents[3] / "config/policy/evaluation/v1.yaml"
        evaluation_policy = load_evaluation_policy(policy_path, RuntimeMode.LIVE)
        results = calculate_period_factor_values(
            fund_returns=fund_returns,
            benchmark_returns=benchmark_returns,
            risk_free_returns=risk_free_returns,
            annualized_risk_free=latest_rate,
            annualized_mar=float(evaluation_policy.mar),
            annualization=252,
            minimum_observations=max(2, round(months * 21 * 0.9)),
        )
        if nav_quality:
            for item in results:
                item["raw_value"] = None
                item["status"] = "UNAVAILABLE"
                item["reason_code"] = nav_quality
        categories = [
            {
                "category": category,
                "name": category_name,
                "factors": [item for item in results if item["category"] == category],
            }
            for category, category_name in (
                ("RET", "收益表现"),
                ("RISK", "风险指标"),
                ("RAP", "风险调整收益"),
                ("STAB", "稳定性"),
                ("REL", "相对表现"),
            )
        ]
        return {
            "data": {
                "fund_id": identifier,
                "evaluation_period": evaluation_period,
                "as_of_date": view_date.isoformat(),
                "factor_categories": categories,
            },
            "meta": {
                "as_of_date": view_date.isoformat(),
                "data_version": "on-demand-factor-analysis",
                "calculation_mode": "ON_DEMAND",
                "is_point_in_time": True,
                "availability_quality_distribution": {
                    quality: sum(1 for item in nav_points if item.availability_quality == quality)
                    / max(len(nav_points), 1)
                    for quality in ("EXACT", "DERIVED", "INFERRED")
                },
                "versions": {
                    "factor_catalog": "v1",
                    "evaluation_policy": evaluation_policy.version,
                    "benchmark_mapping": benchmark_resolution.mapping_version or "UNKNOWN",
                },
                "factor_count": len(FACTOR_CATALOG),
                "nav_versions": [
                    {"effective_at": item.effective_at.isoformat(), "version": item.version}
                    for item in nav_points
                ],
                "nav_status": nav_quality or "AVAILABLE",
                "benchmark_status": benchmark_resolution.status,
                "benchmark_mapping_version": benchmark_resolution.mapping_version or "UNKNOWN",
                "risk_free_tenor": evaluation_period,
                "risk_free_status": "AVAILABLE" if resolved_rates else "UNAVAILABLE",
                "risk_free_quality": risk_free_quality,
            },
        }

    def read_evaluation(
        self, identifier: str, *, evaluation_period: str | None, as_of_date: str | None
    ) -> Mapping[str, object]:
        _fund, share_class = self._required_share_class(identifier)
        view_date = _query_date(as_of_date) or date.today()
        evaluation = self._evaluation_for(share_class.id, view_date)
        if evaluation is None:
            raise NotFoundError("fund evaluation", identifier)
        values = self._factor_values(
            evaluation.factor_run_id, share_class.id, evaluation_period, view_date
        )
        if evaluation_period is not None and not values:
            raise NotFoundError("fund evaluation", identifier)
        factor_run = self._session().get(FactorRun, evaluation.factor_run_id)
        peer_group = self._session().get(PeerGroupSnapshot, evaluation.peer_group_snapshot_id)
        period = evaluation_period or (values[0].window if values else "UNKNOWN")
        return {
            "data": {
                "fund_id": identifier,
                "evaluation_period": period,
                "as_of_date": view_date.isoformat(),
                "evaluation_status": "COMPLETED",
                "evaluation_profile": "UNKNOWN",
                "data_completeness": {"available": len(values), "expected": len(values)},
                "factor_results": [
                    {
                        "factor_id": str(value.factor_version_id),
                        "window": value.window,
                        "raw_value": value.raw_value,
                        "normalized_value": value.normalized_value,
                        "status": value.status,
                        "reason_code": value.reason_code,
                        "direction": "UNKNOWN",
                    }
                    for value in values
                ],
            },
            "meta": {
                "peer_group_id": str(evaluation.peer_group_snapshot_id),
                "peer_group_version": str(peer_group.policy_version_id)
                if peer_group
                else "UNKNOWN",
                "evaluation_policy_version": str(evaluation.policy_version_id),
                "factor_version": str(factor_run.metric_version_id) if factor_run else "UNKNOWN",
                "data_version": str(factor_run.metric_version_id) if factor_run else "UNKNOWN",
            },
        }

    def read_scores(
        self, identifier: str, *, evaluation_period: str | None, as_of_date: str | None
    ) -> Mapping[str, object]:
        _fund, share_class = self._required_share_class(identifier)
        view_date = _query_date(as_of_date) or date.today()
        evaluation = self._evaluation_for(share_class.id, view_date)
        if evaluation is None:
            raise NotFoundError("fund score", identifier)
        values = self._factor_values(
            evaluation.factor_run_id, share_class.id, evaluation_period, view_date
        )
        if evaluation_period is not None and not values:
            raise NotFoundError("fund score", identifier)
        score = (
            self._session()
            .execute(
                select(FundScore).where(
                    FundScore.evaluation_id == evaluation.id,
                    FundScore.share_class_id == share_class.id,
                )
            )
            .scalar_one_or_none()
        )
        if score is None:
            raise NotFoundError("fund score", identifier)
        attribution = (
            self._session()
            .execute(
                select(FundScoreAttribution)
                .where(FundScoreAttribution.fund_score_id == score.id)
                .order_by(FundScoreAttribution.metric_id)
            )
            .scalars()
        )
        return {
            "data": {
                "fund_id": identifier,
                "evaluation_period": evaluation_period
                or (values[0].window if values else "UNKNOWN"),
                "as_of_date": view_date.isoformat(),
                "total_score": score.value,
                "total_score_status": score.status,
                "total_score_reason": score.reason_code,
                "attribution": [dict(item.detail) for item in attribution],
                "sub_scores": {
                    field: value
                    for group in (
                        ("return",),
                        ("risk",),
                        ("risk_adjusted",),
                        ("stability",),
                        ("relative_performance",),
                    )
                    for field, value in (
                        (f"{group[0]}_score", None),
                        (f"{group[0]}_score_status", "UNKNOWN"),
                        (f"{group[0]}_score_reason", "NOT_DECLARED"),
                    )
                },
                "data_completeness": {
                    "available": sum(
                        1
                        for value in values
                        if value.status in {"VALID", "COMPLETED"} and value.raw_value is not None
                    ),
                    "expected": len(values),
                },
                "score_status": score.status,
            },
            "meta": {
                "peer_group_id": str(evaluation.peer_group_snapshot_id),
                "peer_group_version": "UNKNOWN",
                "scoring_policy_version": str(evaluation.policy_version_id),
                "evaluation_policy_version": str(evaluation.policy_version_id),
                "factor_version": "UNKNOWN",
                "data_version": str(evaluation.policy_version_id),
            },
        }

    def _summary(
        self, fund: Fund, share_class: FundShareClass, view_date: date
    ) -> dict[str, object]:
        visible_until = resolve_visible_until(view_date)
        classification = SqlClassificationPitRepository(self._session(), visible_until).current(
            fund.id
        )
        status = self._interval_row(
            FundStatusHistory, FundStatusHistory.share_class_id, share_class.id, view_date
        )
        eligibility = self._eligibility(share_class.id, view_date)
        return {
            "fund_id": fund.fund_code,
            "fund_name": fund.product_name,
            "share_class": share_class.share_class_code,
            "classification": SqlClassificationPitRepository(
                self._session(), visible_until
            ).snapshot(fund.id),
            "fund_classification": classification.classification_code
            if classification
            else "UNKNOWN",
            "management_company_id": "UNKNOWN",
            "manager_ids": self._manager_ids(fund.id, view_date),
            "inception_date": share_class.inception_date.isoformat()
            if share_class.inception_date
            else None,
            "lifecycle_status": status.lifecycle_status if status else "UNKNOWN",
            "investment_eligibility": eligibility.eligibility_status if eligibility else "UNKNOWN",
        }

    def _share_class(self, identifier: str) -> tuple[Fund, FundShareClass] | None:
        pairs = cast(
            list[tuple[Fund, FundShareClass]],
            self._session()
            .execute(select(Fund, FundShareClass).join(FundShareClass))
            .tuples()
            .all(),
        )
        return next(
            (
                pair
                for pair in pairs
                if pair[0].fund_code == identifier or str(pair[1].id) == identifier
            ),
            None,
        )

    def _required_share_class(self, identifier: str) -> tuple[Fund, FundShareClass]:
        pair = self._share_class(identifier)
        if pair is None:
            raise NotFoundError("fund", identifier)
        return pair

    def _session(self) -> Session:
        if not isinstance(self.session, Session):
            raise NotFoundError("fund", "repository session")
        return self.session

    def _interval_row(self, model: Any, column: Any, identifier: int, view_date: date) -> Any:
        return (
            self._session()
            .execute(
                select(model)
                .where(
                    column == identifier,
                    model.available_at <= resolve_visible_until(view_date),
                    model.valid_from <= view_date,
                    (model.valid_to.is_(None) | (model.valid_to > view_date)),
                )
                .order_by(model.valid_from.desc(), model.available_at.desc(), model.id.desc())
            )
            .scalar_one_or_none()
        )

    def _eligibility(self, share_class_id: int, view_date: date) -> InvestmentEligibility | None:
        return (
            self._session()
            .execute(
                select(InvestmentEligibility)
                .where(
                    InvestmentEligibility.share_class_id == share_class_id,
                    InvestmentEligibility.effective_at <= view_date,
                    InvestmentEligibility.available_at <= resolve_visible_until(view_date),
                )
                .order_by(
                    InvestmentEligibility.effective_at.desc(), InvestmentEligibility.version.desc()
                )
            )
            .scalar_one_or_none()
        )

    def _manager_ids(self, fund_id: int, view_date: date) -> list[str]:
        rows = (
            self._session()
            .execute(
                select(FundManagerAssignment.manager_id)
                .where(
                    FundManagerAssignment.fund_id == fund_id,
                    FundManagerAssignment.available_at <= resolve_visible_until(view_date),
                    FundManagerAssignment.valid_from <= view_date,
                    (
                        FundManagerAssignment.valid_to.is_(None)
                        | (FundManagerAssignment.valid_to > view_date)
                    ),
                )
                .order_by(FundManagerAssignment.manager_id)
            )
            .scalars()
        )
        return [str(identifier) for identifier in rows]

    def _evaluation_for(self, share_class_id: int, view_date: date) -> FundEvaluation | None:
        return (
            self._session()
            .execute(
                select(FundEvaluation)
                .join(
                    PeerGroupSnapshot, PeerGroupSnapshot.id == FundEvaluation.peer_group_snapshot_id
                )
                .join(PeerGroupMember, PeerGroupMember.snapshot_id == PeerGroupSnapshot.id)
                .where(
                    PeerGroupMember.share_class_id == share_class_id,
                    PeerGroupSnapshot.decision_at <= view_date,
                )
                .order_by(PeerGroupSnapshot.decision_at.desc(), FundEvaluation.id.desc())
            )
            .scalar_one_or_none()
        )

    def _factor_values(
        self, factor_run_id: int, share_class_id: int, period: str | None, view_date: date
    ) -> list[FactorValue]:
        statement = (
            select(FactorValue)
            .join(FactorRun, FactorRun.id == FactorValue.factor_run_id)
            .where(
                FactorValue.factor_run_id == factor_run_id,
                FactorValue.share_class_id == share_class_id,
                FactorValue.effective_at <= view_date,
                FactorRun.created_at <= resolve_visible_until(view_date),
            )
        )
        if period is not None:
            statement = statement.where(FactorValue.window == period)
        rows = (
            self._session()
            .execute(
                statement.order_by(
                    FactorValue.factor_version_id,
                    FactorValue.effective_at.desc(),
                    FactorValue.version.desc(),
                )
            )
            .scalars()
        )
        latest: dict[int, FactorValue] = {}
        for row in rows:
            latest.setdefault(row.factor_version_id, row)
        return [latest[key] for key in sorted(latest)]


class UniverseRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "fund universe")

    def _list_rows(self, **_: object) -> list[Mapping[str, object]]:
        if not isinstance(self.session, Session):
            return super()._list_rows()
        snapshots = self.session.execute(select(FundUniverseSnapshot)).scalars()
        return [self._summary(snapshot) for snapshot in snapshots]

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if not isinstance(self.session, Session):
            return super()._get_row(identifier)
        snapshot = self.session.get(FundUniverseSnapshot, _integer_identifier(identifier))
        return self._summary(snapshot) if snapshot is not None else None

    def read_members(self, identifier: str) -> Mapping[str, object]:
        snapshot = self._snapshot(identifier)
        members = (
            self._session()
            .execute(
                select(FundUniverseMember)
                .where(FundUniverseMember.snapshot_id == snapshot.id)
                .order_by(FundUniverseMember.status.desc(), FundUniverseMember.share_class_id)
            )
            .scalars()
        )
        selected: list[dict[str, object]] = []
        rejected: list[dict[str, object]] = []
        for member in members:
            rendered = self._member(snapshot.evaluation_id, member)
            (selected if member.status == "SELECTED" else rejected).append(rendered)
        summary = self._summary(snapshot)
        return {
            "members": selected,
            "excluded": rejected,
            "meta": {
                "eligibility_rules_version": summary["eligibility_rules_version"],
                "scoring_policy_version": summary["scoring_policy_version"],
            },
        }

    def _summary(self, snapshot: FundUniverseSnapshot) -> dict[str, object]:
        evaluation = self._session().get(FundEvaluation, snapshot.evaluation_id)
        peer_group = self._session().get(
            PeerGroupSnapshot, evaluation.peer_group_snapshot_id if evaluation else None
        )
        count = (
            self._session()
            .execute(
                select(FundUniverseMember).where(FundUniverseMember.snapshot_id == snapshot.id)
            )
            .scalars()
        )
        return {
            "universe_id": str(snapshot.id),
            "strategy_id": snapshot.decision_id,
            "decision_at": peer_group.decision_at.isoformat() if peer_group else None,
            "universe_strategy": "UNKNOWN",
            "member_count": len(list(count)),
            "eligibility_rules_version": str(snapshot.policy_version_id),
            "scoring_policy_version": str(evaluation.policy_version_id) if evaluation else None,
        }

    def _member(self, evaluation_id: int, member: FundUniverseMember) -> dict[str, object]:
        fund = (
            self._session()
            .execute(
                select(Fund)
                .join(FundShareClass, FundShareClass.fund_id == Fund.id)
                .where(FundShareClass.id == member.share_class_id)
            )
            .scalar_one_or_none()
        )
        score = (
            self._session()
            .execute(
                select(FundScore).where(
                    FundScore.evaluation_id == evaluation_id,
                    FundScore.share_class_id == member.share_class_id,
                )
            )
            .scalar_one_or_none()
        )
        ranking = (
            self._session()
            .execute(
                select(FundRanking).where(
                    FundRanking.evaluation_id == evaluation_id,
                    FundRanking.share_class_id == member.share_class_id,
                )
            )
            .scalar_one_or_none()
        )
        tier = (
            self._session()
            .execute(
                select(FundTier).where(
                    FundTier.evaluation_id == evaluation_id,
                    FundTier.share_class_id == member.share_class_id,
                )
            )
            .scalar_one_or_none()
        )
        conditions = (
            self._session()
            .execute(
                select(SelectionConditionRecord)
                .where(SelectionConditionRecord.universe_member_id == member.id)
                .order_by(SelectionConditionRecord.condition_id)
            )
            .scalars()
        )
        passed: list[dict[str, object]] = []
        failed: list[dict[str, object]] = []
        for condition in conditions:
            item: dict[str, object] = {
                "condition": condition.condition_id,
                "actual": None,
                "result": "PASS"
                if condition.passed
                else "FAIL"
                if condition.passed is False
                else "UNKNOWN",
            }
            (passed if condition.passed else failed).append(item)
        return {
            "fund_id": fund.fund_code if fund is not None else str(member.share_class_id),
            "selection_status": member.status,
            "total_score": score.value if score else None,
            "total_score_status": score.status if score else "UNKNOWN",
            "total_score_reason": score.reason_code if score else None,
            "rank": ranking.rank if ranking else None,
            "rank_status": ranking.status if ranking else "UNKNOWN",
            "rank_reason": None,
            "percentile": None,
            "percentile_status": "UNKNOWN",
            "percentile_reason": None,
            "fund_tier": tier.tier if tier else None,
            "investment_eligibility": "UNKNOWN",
            "passed_conditions": passed,
            "failed_conditions": failed,
        }

    def _snapshot(self, identifier: str) -> FundUniverseSnapshot:
        snapshot = self._session().get(FundUniverseSnapshot, _integer_identifier(identifier))
        if snapshot is None:
            raise NotFoundError("fund universe", identifier)
        return snapshot

    def _session(self) -> Session:
        if not isinstance(self.session, Session):
            raise NotFoundError("fund universe", "repository session")
        return self.session


def _query_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError("Expected ISO date")


def _integer_identifier(identifier: str) -> int:
    try:
        return int(identifier)
    except ValueError as error:
        raise NotFoundError("fund universe", identifier) from error


class PortfolioRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "portfolio")

    def _list_rows(self, **_: object) -> list[Mapping[str, object]]:
        if not isinstance(self.session, Session):
            return super()._list_rows()
        return [self._row(item) for item in self.session.execute(select(PortfolioRecord)).scalars()]

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if not isinstance(self.session, Session):
            return super()._get_row(identifier)
        item = self.session.get(PortfolioRecord, identifier)
        return self._row(item) if item is not None else None

    @staticmethod
    def _row(item: PortfolioRecord) -> dict[str, object]:
        return {
            "portfolio_id": item.id,
            "portfolio_name": item.name,
            "portfolio_type": item.portfolio_type,
            "status": item.status,
            "base_currency": item.base_currency,
            "portfolio_version": item.portfolio_version,
            "risk_profile": item.risk_profile,
            "portfolio_benchmark": item.benchmark,
            "portfolio_rule_version": item.portfolio_rule_version,
            "owner_user_id": item.owner_user_id,
            "viewer_user_ids": item.viewer_user_ids,
        }


class OptimizationRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "optimization")

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if not isinstance(self.session, Session):
            return super()._get_row(identifier)
        item = self.session.get(OptimizationRecord, identifier)
        if item is None:
            return None
        return {"optimization_id": item.id, **item.payload, "portfolio_id": item.portfolio_id}


class DecisionRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "decision")

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if not isinstance(self.session, Session):
            return super()._get_row(identifier)
        item = self.session.get(DecisionRecord, identifier)
        if item is None:
            return None
        return {
            "decision_id": item.id,
            **item.payload,
            "portfolio_id": item.portfolio_id,
            "optimization_id": item.optimization_id,
        }


class BacktestRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "backtest")

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        if not isinstance(self.session, Session):
            return super()._get_row(identifier)
        item = self.session.get(BacktestRecord, identifier)
        if item is None:
            return None
        return {"backtest_id": item.id, "status": item.status, **item.payload}


@dataclass(frozen=True, slots=True)
class ApiRepositories:
    """The complete request-scoped set of API read adapters."""

    funds: FundRepository
    universes: UniverseRepository
    portfolios: PortfolioRepository
    optimizations: OptimizationRepository
    decisions: DecisionRepository
    backtests: BacktestRepository

    @classmethod
    def from_session(cls, session: object) -> ApiRepositories:
        return cls(
            funds=FundRepository(session),
            universes=UniverseRepository(session),
            portfolios=PortfolioRepository(session),
            optimizations=OptimizationRepository(session),
            decisions=DecisionRepository(session),
            backtests=BacktestRepository(session),
        )

    def list_funds(self, **filters: object) -> list[dict[str, object]]:
        return self.funds.list(**filters)

    def list_universes(self, **filters: object) -> list[dict[str, object]]:
        return self.universes.list(**filters)

    def list_portfolios(self, **filters: object) -> list[dict[str, object]]:
        return self.portfolios.list(**filters)

    def list(self, resource: str, **filters: object) -> list[dict[str, object]]:
        return self._adapter(resource).list(**filters)

    def get(self, resource: str, identifier: str) -> Mapping[str, object]:
        return self._adapter(resource).get(identifier)

    def _adapter(self, resource: str) -> RepositoryAdapter:
        repository = {
            "fund": self.funds,
            "fund universe": self.universes,
            "portfolio": self.portfolios,
            "optimization": self.optimizations,
            "decision": self.decisions,
            "backtest": self.backtests,
        }.get(resource)
        if repository is None:
            raise NotFoundError(resource, resource)
        return repository


# Compatibility name for consumers that imported the initial read seam.  It is
# an alias, not a second adapter implementation.
ReadRepository = ApiRepositories

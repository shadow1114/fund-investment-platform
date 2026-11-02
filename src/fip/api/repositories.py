from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.api.errors import InvalidQueryError, NotFoundError
from fip.platform.decision_data.pit import RiskFreeRatePoint, resolve_visible_until
from fip.services.data_service.models.fund import (
    Fund,
    FundManagerAssignment,
    FundShareClass,
    FundStatusHistory,
    InvestmentEligibility,
)
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
_TARGET_TENOR_DAYS = {tenor: _TENOR_DAYS[tenor] for tenor in ("1M", "6M", "1Y", "3Y", "5Y")}


def _resolve_risk_free_curve(
    points: tuple[RiskFreeRatePoint, ...], target_tenor: str, currency: str
) -> tuple[tuple[date, Decimal, str], ...]:
    target_days = _TARGET_TENOR_DAYS[target_tenor]
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

    def get(self, identifier: str) -> Mapping[str, object]:
        row = self._get_row(identifier)
        if row is None:
            raise NotFoundError(self.resource, identifier)
        return dict(row)


class FundRepository(RepositoryAdapter):
    def __init__(self, session: object) -> None:
        super().__init__(session, "fund")

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
        start = _query_date(date_from) or share_class.inception_date or view_date
        end = _query_date(date_to) or view_date
        if end < start:
            raise InvalidQueryError("date_from must not be after date_to")
        visible_until = resolve_visible_until(view_date)
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
        from fip.services.factor_service.policy import load_evaluation_policy

        periods_months = {"1M": 1, "6M": 6, "1Y": 12, "3Y": 36, "5Y": 60}
        months = periods_months[evaluation_period]
        view_date = _query_date(as_of_date) or date.today()
        year, month_index = divmod(view_date.year * 12 + view_date.month - 1 - months, 12)
        target_month = month_index + 1
        start = date(
            year, target_month, min(view_date.day, calendar.monthrange(year, target_month)[1])
        )
        visible_until = resolve_visible_until(view_date)
        session = self._session()
        fund, share_class = self._required_share_class(identifier)

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
            risk_free_curve, evaluation_period, share_class.base_currency
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

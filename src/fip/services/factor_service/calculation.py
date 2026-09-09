import datetime as dt
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.decision_data.pit import PitDataContext
from fip.services.factor_service.repositories import FactorRepository
from fip.services.fund_service.models import PeerGroupMember, PeerGroupSnapshot
from fip.strategy_library.factor_types import FactorResult, ReturnObservation
from fip.strategy_library.normalization import normalize_factor
from fip.strategy_library.relative import calculate_relative_factors
from fip.strategy_library.returns import annualized_return, cumulative_return
from fip.strategy_library.risk import downside_volatility, maximum_drawdown, volatility
from fip.strategy_library.risk_adjusted import calmar, sharpe, sortino
from fip.strategy_library.stability import positive_return_ratio, rolling_sharpe


@dataclass(frozen=True, slots=True)
class FactorMetricParameters:
    annualization: int
    minimum_observations: int
    regression_minimum_observations: int
    rolling_window: int
    rolling_minimum_valid_points: int


@dataclass(frozen=True, slots=True)
class FactorCalculationInput:
    share_class_id: int
    window: str
    fund_returns: Sequence[ReturnObservation]
    benchmark_returns: Sequence[ReturnObservation]
    risk_free_returns: Sequence[ReturnObservation]
    annualized_risk_free: float | None
    daily_mar: float | None
    adjustment_policy_version: str
    input_quality_summary: Mapping[str, object]


class FactorInputProvider(Protocol):
    def load(
        self, context: DecisionExecutionContext, peer_group_snapshot_id: int
    ) -> Sequence[FactorCalculationInput]: ...


def _returns_from_levels(
    levels: Sequence[tuple[dt.date, Decimal | float | None]],
) -> tuple[ReturnObservation, ...]:
    returns: list[ReturnObservation] = []
    previous: tuple[dt.date, Decimal | float] | None = None
    for effective_at, value in levels:
        if value is None:
            previous = None
            continue
        if previous is not None:
            previous_date, previous_value = previous
            current = float(value)
            prior = float(previous_value)
            if prior <= 0:
                previous = (effective_at, value)
                continue
            returns.append(ReturnObservation(effective_at, current / prior - 1))
        previous = (effective_at, value)
    return tuple(returns)


class PitFactorInputProvider:
    def __init__(
        self,
        session: Session,
        *,
        window: str,
        lookback_calendar_days: int,
        risk_free_tenor: str,
        annualization: int,
        daily_mar: float | None,
        adjustment_policy_version: str,
    ) -> None:
        self._session = session
        self._window = window
        self._lookback_calendar_days = lookback_calendar_days
        self._risk_free_tenor = risk_free_tenor
        self._annualization = annualization
        self._daily_mar = daily_mar
        self._adjustment_policy_version = adjustment_policy_version

    def load(
        self, context: DecisionExecutionContext, peer_group_snapshot_id: int
    ) -> Sequence[FactorCalculationInput]:
        snapshot = self._session.get(PeerGroupSnapshot, peer_group_snapshot_id)
        if snapshot is None:
            raise ValueError(f"peer group snapshot {peer_group_snapshot_id} not found")
        share_class_ids = self._session.execute(
            select(PeerGroupMember.share_class_id)
            .where(PeerGroupMember.snapshot_id == peer_group_snapshot_id)
            .order_by(PeerGroupMember.share_class_id)
        ).scalars()
        pit = PitDataContext(context, self._session)
        date_from = context.decision_at - dt.timedelta(days=self._lookback_calendar_days)
        rate_points = pit.risk_free_rates().series(
            snapshot.base_currency,
            self._risk_free_tenor,
            date_from,
            context.decision_at,
        )
        risk_free_returns = tuple(
            ReturnObservation(point.effective_at, float(point.rate) / self._annualization)
            for point in rate_points
        )
        annualized_risk_free = float(rate_points[-1].rate) if rate_points else None
        inputs: list[FactorCalculationInput] = []
        benchmarks = pit.benchmarks()
        for share_class_id in share_class_ids:
            nav_points = pit.navs().adjusted_nav_series(
                share_class_id,
                date_from,
                context.decision_at,
            )
            fund_returns = _returns_from_levels(
                tuple((point.effective_at, point.adjusted_nav) for point in nav_points)
            )
            resolution = benchmarks.resolve(share_class_id, snapshot.classification_code)
            benchmark_levels = (
                benchmarks.composite_series(resolution, date_from, context.decision_at)
                if resolution.status == "AVAILABLE"
                else ()
            )
            benchmark_returns = _returns_from_levels(
                tuple((day, value) for day, value, _quality in benchmark_levels)
            )
            index_versions = {
                str(component.index_id): [
                    {"effective_at": day.isoformat(), "version": version}
                    for day, _value, version, _quality in benchmarks.index_series(
                        component.index_id,
                        date_from,
                        context.decision_at,
                    )
                ]
                for component in resolution.components
            }
            inputs.append(
                FactorCalculationInput(
                    share_class_id=share_class_id,
                    window=self._window,
                    fund_returns=fund_returns,
                    benchmark_returns=benchmark_returns,
                    risk_free_returns=risk_free_returns,
                    annualized_risk_free=annualized_risk_free,
                    daily_mar=self._daily_mar,
                    adjustment_policy_version=self._adjustment_policy_version,
                    input_quality_summary={
                        "nav_versions": [
                            {
                                "effective_at": point.effective_at.isoformat(),
                                "version": point.version,
                                "availability_quality": point.availability_quality,
                            }
                            for point in nav_points
                        ],
                        "nav_chain_quality": sorted(
                            {point.chain_availability_quality for point in nav_points}
                        ),
                        "benchmark_status": resolution.status,
                        "benchmark_id": resolution.benchmark_id,
                        "benchmark_mapping_source": resolution.mapping_source,
                        "benchmark_mapping_version": resolution.mapping_version,
                        "benchmark_components": [
                            {
                                "index_id": component.index_id,
                                "weight": str(component.weight),
                            }
                            for component in resolution.components
                        ],
                        "benchmark_index_versions": index_versions,
                        "risk_free_versions": [
                            {
                                "effective_at": point.effective_at.isoformat(),
                                "version": point.version,
                                "availability_quality": point.availability_quality,
                            }
                            for point in rate_points
                        ],
                    },
                )
            )
        return tuple(inputs)


@dataclass(frozen=True, slots=True)
class CalculatedFactorValue:
    share_class_id: int
    window: str
    factor: FactorResult
    adjustment_policy_version: str
    input_quality_summary: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class FactorRunResult:
    decision_id: str
    peer_group_snapshot_id: int
    metric_version_id: int
    input_quality_summary: Mapping[str, object]
    values: tuple[CalculatedFactorValue, ...]


@dataclass(frozen=True, slots=True)
class PersistedFactorValue:
    factor_value_id: int
    share_class_id: int
    factor_id: str
    window: str
    raw_value: float | None
    normalized_value: float | None
    status: str
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class PersistedFactorRun:
    factor_run_id: int
    peer_group_snapshot_id: int
    values: tuple[PersistedFactorValue, ...]


def _calculate_input(
    item: FactorCalculationInput, parameters: FactorMetricParameters
) -> tuple[CalculatedFactorValue, ...]:
    minimum = parameters.minimum_observations
    absolute = (
        annualized_return(
            item.fund_returns,
            parameters.annualization,
            minimum_observations=minimum,
        ),
        cumulative_return(item.fund_returns, minimum_observations=minimum),
        volatility(
            item.fund_returns,
            parameters.annualization,
            minimum_observations=minimum,
        ),
        downside_volatility(
            item.fund_returns,
            parameters.annualization,
            item.daily_mar,
            minimum_observations=minimum,
        ),
        maximum_drawdown(item.fund_returns, minimum_observations=minimum),
        sharpe(
            item.fund_returns,
            parameters.annualization,
            item.annualized_risk_free,
            minimum_observations=minimum,
        ),
        sortino(
            item.fund_returns,
            parameters.annualization,
            item.daily_mar,
            minimum_observations=minimum,
        ),
        calmar(
            item.fund_returns,
            parameters.annualization,
            minimum_observations=minimum,
        ),
        positive_return_ratio(item.fund_returns, minimum_observations=minimum),
        rolling_sharpe(
            item.fund_returns,
            parameters.annualization,
            item.annualized_risk_free,
            parameters.rolling_window,
            parameters.rolling_minimum_valid_points,
            minimum_observations=minimum,
        ),
    )
    relative = calculate_relative_factors(
        item.fund_returns,
        item.benchmark_returns,
        item.risk_free_returns,
        parameters.annualization,
        parameters.regression_minimum_observations,
    )
    return tuple(
        CalculatedFactorValue(
            share_class_id=item.share_class_id,
            window=item.window,
            factor=factor,
            adjustment_policy_version=item.adjustment_policy_version,
            input_quality_summary=item.input_quality_summary,
        )
        for factor in (*absolute, *relative)
    )


def calculate_factor_run(
    context: DecisionExecutionContext,
    peer_group_snapshot_id: int,
    input_provider: FactorInputProvider,
    metric_version_id: int,
    parameters: FactorMetricParameters,
) -> FactorRunResult:
    inputs = tuple(input_provider.load(context, peer_group_snapshot_id))
    values = tuple(
        value
        for item in inputs
        for value in _calculate_input(item, parameters)
    )
    return FactorRunResult(
        decision_id=context.decision_id,
        peer_group_snapshot_id=peer_group_snapshot_id,
        metric_version_id=metric_version_id,
        input_quality_summary={
            "share_classes": {
                str(item.share_class_id): dict(item.input_quality_summary) for item in inputs
            }
        },
        values=values,
    )


def calculate_and_save_factor_run(
    session: Session,
    context: DecisionExecutionContext,
    *,
    peer_group_snapshot_id: int,
    input_provider: FactorInputProvider,
    metric_version_id: int,
    evaluation_policy_version_id: int,
    factor_version_ids: Mapping[str, int],
    normalization_directions: Mapping[str, str],
    minimum_peer_sample: int,
    parameters: FactorMetricParameters,
    value_version: int = 1,
    beta_target_range: tuple[float, float] | None = None,
) -> PersistedFactorRun:
    result = calculate_factor_run(
        context,
        peer_group_snapshot_id,
        input_provider,
        metric_version_id,
        parameters,
    )
    repository = FactorRepository(session)
    run_id = repository.save_run(
        decision_id=context.decision_id,
        peer_group_snapshot_id=peer_group_snapshot_id,
        metric_version_id=metric_version_id,
        evaluation_policy_version_id=evaluation_policy_version_id,
        input_quality_summary=dict(result.input_quality_summary),
    )
    grouped: dict[tuple[str, str], list[CalculatedFactorValue]] = defaultdict(list)
    for value in result.values:
        grouped[(value.factor.factor_id, value.window)].append(value)
    normalized: dict[tuple[int, str, str], tuple[float | None, str, str | None]] = {}
    for (factor_id, window), values in grouped.items():
        available = tuple(
            (value.share_class_id, value.factor.value)
            for value in values
            if value.factor.value is not None and value.factor.status == "AVAILABLE"
        )
        normalized_values = normalize_factor(
            available,
            "TARGET_RANGE" if factor_id == "F-REL-003" else normalization_directions[factor_id],
            minimum_peer_sample,
            target_range=beta_target_range if factor_id == "F-REL-003" else None,
        )
        normalized.update(
            {
                (item.share_class_id, factor_id, window): (
                    item.normalized_value,
                    item.status,
                    item.reason_code,
                )
                for item in normalized_values
            }
        )
    persisted: list[PersistedFactorValue] = []
    for value in result.values:
        factor_id = value.factor.factor_id
        normalized_value, status, reason_code = normalized.get(
            (value.share_class_id, factor_id, value.window),
            (None, value.factor.status, value.factor.reason),
        )
        value_id = repository.save_value(
            factor_run_id=run_id,
            share_class_id=value.share_class_id,
            factor_version_id=factor_version_ids[factor_id],
            window=value.window,
            effective_at=context.decision_at,
            version=value_version,
            status=status,
            reason_code=reason_code,
            raw_value=value.factor.value,
            normalized_value=normalized_value,
            evaluation_policy_version_id=evaluation_policy_version_id,
            input_lineage=dict(value.input_quality_summary),
            adjustment_policy_version=value.adjustment_policy_version,
        )
        persisted.append(
            PersistedFactorValue(
                value_id,
                value.share_class_id,
                factor_id,
                value.window,
                value.factor.value,
                normalized_value,
                status,
                reason_code,
            )
        )
    return PersistedFactorRun(run_id, peer_group_snapshot_id, tuple(persisted))
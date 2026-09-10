"""Point-in-time input assembly for return and risk estimation."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from typing import Any, Protocol

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.decision_data.pit import (
    BenchmarkPitRepository,
    BenchmarkResolutionSegment,
    ClassificationPoint,
    NavPoint,
    PitDataContext,
)
from fip.services.data_service.models.fund import FundShareClass
from fip.services.fund_service.universe import UniverseRepository
from fip.services.portfolio_service.estimation.policy import EstimationPolicy
from fip.strategy_library.estimation.encoding import canonical_checksum
from fip.strategy_library.estimation.types import DatedReturn, FactorRiskObservation

_INSUFFICIENT_VALID_RETURNS = "INSUFFICIENT_VALID_RETURNS"
_CLASSIFICATION_UNAVAILABLE = "CLASSIFICATION_UNAVAILABLE"
_BENCHMARK_UNAVAILABLE = "BENCHMARK_UNAVAILABLE"


class FactorRiskCrossCheckProvider(Protocol):
    """Read-only boundary for comparable Factor risk observations."""

    def load_candidates(
        self, share_class_id: int, decision_id: str
    ) -> tuple[FactorRiskObservation, ...]: ...


@dataclass(frozen=True, slots=True)
class EstimationBasisInput:
    return_basis: str
    matrix: np.ndarray  # type: ignore[type-arg]
    instrument_order: tuple[int, ...]
    observation_dates: tuple[dt.date, ...]
    excluded_instruments: tuple[tuple[int, str], ...]
    dropped_dates: tuple[dt.date, ...]
    lineage: dict[str, Any]
    observation_fingerprint: str
    basis_fingerprint: str


@dataclass(frozen=True, slots=True)
class _InstrumentInput:
    share_class_id: int
    fund_id: int
    nav_points: tuple[NavPoint, ...]
    absolute_returns: tuple[DatedReturn, ...]
    classification: dict[str, object] | None
    excess_returns: tuple[DatedReturn, ...]
    benchmark_segments: tuple[dict[str, object], ...]
    benchmark_switch_dates: tuple[dt.date, ...]
    excess_exclusion_reason: str | None


@dataclass(frozen=True, slots=True)
class _AlignedBasis:
    instrument_order: tuple[int, ...]
    observation_dates: tuple[dt.date, ...]
    matrix: np.ndarray  # type: ignore[type-arg]
    excluded_instruments: tuple[tuple[int, str], ...]
    dropped_dates: tuple[dt.date, ...]


def _decimal_text(value: Decimal) -> str:
    return str(value)


def _nav_is_available(point: NavPoint) -> bool:
    return (
        point.adjusted_nav is not None
        and point.availability_quality != "UNAVAILABLE"
        and point.chain_availability_quality != "UNAVAILABLE"
    )


def _simple_returns_from_nav(points: tuple[NavPoint, ...]) -> tuple[DatedReturn, ...]:
    levels = tuple(
        (
            point.effective_at,
            point.adjusted_nav if _nav_is_available(point) else None,
        )
        for point in points
    )
    return _simple_returns_from_levels(levels)


def _simple_returns_from_levels(
    levels: tuple[tuple[dt.date, Decimal | None], ...],
) -> tuple[DatedReturn, ...]:
    result: list[DatedReturn] = []
    previous: Decimal | None = None
    previous_date: dt.date | None = None
    for effective_at, value in levels:
        if previous_date is not None and effective_at <= previous_date:
            raise ValueError("level observations must be ordered by unique dates")
        previous_date = effective_at
        if value is None:
            previous = None
            continue
        if value <= 0:
            previous = None
            continue
        if previous is not None:
            result.append(DatedReturn(effective_at, float(value / previous - Decimal(1))))
        previous = value
    return tuple(result)


def _nav_lineage(share_class_id: int, point: NavPoint) -> dict[str, object]:
    return {
        "share_class_id": share_class_id,
        "effective_at": point.effective_at.isoformat(),
        "value": _decimal_text(point.adjusted_nav),
        "version": point.version,
        "availability_quality": point.availability_quality,
        "chain_availability_quality": point.chain_availability_quality,
    }


def _classification_lineage(point: ClassificationPoint) -> dict[str, object]:
    return {
        "classification_code": point.classification_code,
        "valid_from": point.valid_from.isoformat(),
        "availability_quality": point.availability_quality,
    }


def _align(
    series: dict[int, tuple[DatedReturn, ...]],
    candidate_order: tuple[int, ...],
    exclusion_reasons: dict[int, str],
) -> _AlignedBasis:
    included: list[tuple[int, dict[dt.date, float]]] = []
    excluded: list[tuple[int, str]] = []
    for share_class_id in candidate_order:
        observations = series.get(share_class_id, ())
        by_date: dict[dt.date, float] = {}
        for observation in observations:
            value = float(observation.value)
            if not isfinite(value):
                raise ValueError("return observations must be finite")
            if observation.effective_at in by_date:
                raise ValueError("return observations must not contain duplicate dates")
            by_date[observation.effective_at] = value
        if len(by_date) < 2:
            excluded.append(
                (
                    share_class_id,
                    exclusion_reasons.get(share_class_id, _INSUFFICIENT_VALID_RETURNS),
                )
            )
            continue
        included.append((share_class_id, by_date))

    if not included:
        return _AlignedBasis(
            instrument_order=(),
            observation_dates=(),
            matrix=np.empty((0, 0), dtype=np.float64),
            excluded_instruments=tuple(excluded),
            dropped_dates=(),
        )

    all_dates = set.union(*(set(observations) for _, observations in included))
    common_dates = set.intersection(*(set(observations) for _, observations in included))
    observation_dates = tuple(sorted(common_dates))
    instrument_order = tuple(share_class_id for share_class_id, _ in included)
    matrix = np.asarray(
        [
            [observations[day] for _, observations in included]
            for day in observation_dates
        ],
        dtype=np.float64,
    ).reshape((len(observation_dates), len(instrument_order)))
    return _AlignedBasis(
        instrument_order=instrument_order,
        observation_dates=observation_dates,
        matrix=matrix,
        excluded_instruments=tuple(excluded),
        dropped_dates=tuple(sorted(all_dates - common_dates)),
    )


class EstimationInputAssembler:
    """Build independently aligned ABSOLUTE and EXCESS estimation inputs."""

    def __init__(
        self,
        session: Session,
        *,
        adjustment_policy_version: str,
    ) -> None:
        self._session = session
        self._adjustment_policy_version = adjustment_policy_version

    def load(
        self,
        context: DecisionExecutionContext,
        snapshot_id: int,
        policy: EstimationPolicy,
    ) -> tuple[EstimationBasisInput, ...]:
        candidate_order = UniverseRepository(self._session).load_selected_members_ordered(
            snapshot_id
        )
        fund_ids = self._load_fund_ids(candidate_order)
        pit = PitDataContext(context, self._session)
        navs = pit.navs()
        classifications = pit.classifications()
        benchmarks = pit.benchmarks()
        instruments: list[_InstrumentInput] = []

        for share_class_id in candidate_order:
            all_nav_points = tuple(
                navs.adjusted_nav_series(
                    share_class_id,
                    dt.date.min,
                    context.decision_at,
                )
            )
            nav_points = all_nav_points[-(policy.lookback_trading_days + 1) :]
            absolute_returns = _simple_returns_from_nav(nav_points)
            classification_point = classifications.current(fund_ids[share_class_id])
            classification = (
                _classification_lineage(classification_point)
                if classification_point is not None
                else None
            )
            excess_returns: tuple[DatedReturn, ...] = ()
            segment_lineage: tuple[dict[str, object], ...] = ()
            switch_dates: tuple[dt.date, ...] = ()
            exclusion_reason: str | None = None
            if classification_point is None:
                exclusion_reason = _CLASSIFICATION_UNAVAILABLE
            elif nav_points:
                segments = benchmarks.resolve_history(
                    share_class_id,
                    classification_point.classification_code,
                    nav_points[0].effective_at,
                    nav_points[-1].effective_at,
                )
                benchmark_returns, segment_lineage, switch_dates = self._benchmark_returns(
                    benchmarks, segments
                )
                benchmark_by_date = {
                    observation.effective_at: observation.value
                    for observation in benchmark_returns
                }
                excess_returns = tuple(
                    DatedReturn(
                        observation.effective_at,
                        observation.value - benchmark_by_date[observation.effective_at],
                    )
                    for observation in absolute_returns
                    if observation.effective_at in benchmark_by_date
                )
                if not segments or not any(segment.status == "AVAILABLE" for segment in segments):
                    exclusion_reason = _BENCHMARK_UNAVAILABLE
            else:
                exclusion_reason = _INSUFFICIENT_VALID_RETURNS

            instruments.append(
                _InstrumentInput(
                    share_class_id=share_class_id,
                    fund_id=fund_ids[share_class_id],
                    nav_points=tuple(nav_points),
                    absolute_returns=absolute_returns,
                    classification=classification,
                    excess_returns=excess_returns,
                    benchmark_segments=segment_lineage,
                    benchmark_switch_dates=switch_dates,
                    excess_exclusion_reason=exclusion_reason,
                )
            )

        absolute = self._assemble_basis(
            "ABSOLUTE", snapshot_id, policy, candidate_order, tuple(instruments)
        )
        excess = self._assemble_basis(
            "EXCESS", snapshot_id, policy, candidate_order, tuple(instruments)
        )
        return (absolute, excess)

    def _load_fund_ids(self, candidate_order: tuple[int, ...]) -> dict[int, int]:
        if not candidate_order:
            return {}
        rows = self._session.execute(
            select(FundShareClass.id, FundShareClass.fund_id).where(
                FundShareClass.id.in_(candidate_order)
            )
        ).all()
        result = {share_class_id: fund_id for share_class_id, fund_id in rows}
        missing = set(candidate_order) - set(result)
        if missing:
            raise ValueError(f"unknown share classes in universe snapshot: {sorted(missing)}")
        return result

    def _benchmark_returns(
        self,
        benchmarks: BenchmarkPitRepository,
        segments: tuple[BenchmarkResolutionSegment, ...],
    ) -> tuple[
        tuple[DatedReturn, ...],
        tuple[dict[str, object], ...],
        tuple[dt.date, ...],
    ]:
        result: list[DatedReturn] = []
        lineage: list[dict[str, object]] = []
        switch_dates = tuple(segment.effective_from for segment in segments[1:])
        for segment in segments:
            component_series: dict[int, dict[dt.date, Decimal]] = {}
            index_lineage: list[dict[str, object]] = []
            for component in segment.components:
                observations = benchmarks.index_series(
                    component.index_id,
                    segment.effective_from,
                    segment.effective_to - dt.timedelta(days=1),
                )
                component_series[component.index_id] = {
                    day: value for day, value, _version, _quality in observations
                }
                index_lineage.append(
                    {
                        "index_id": component.index_id,
                        "observations": [
                            {
                                "effective_at": day.isoformat(),
                                "value": _decimal_text(value),
                                "version": version,
                                "availability_quality": quality,
                            }
                            for day, value, version, quality in observations
                        ],
                    }
                )

            dates = sorted(
                {day for values in component_series.values() for day in values}
            )
            levels: list[tuple[dt.date, Decimal | None]] = []
            for day in dates:
                if segment.status != "AVAILABLE" or any(
                    day not in component_series[component.index_id]
                    for component in segment.components
                ):
                    levels.append((day, None))
                    continue
                composite = sum(
                    (
                        component_series[component.index_id][day] * component.weight
                        for component in segment.components
                    ),
                    Decimal(0),
                )
                levels.append((day, composite))
            result.extend(_simple_returns_from_levels(tuple(levels)))
            lineage.append(
                {
                    "effective_from": segment.effective_from.isoformat(),
                    "effective_to": segment.effective_to.isoformat(),
                    "benchmark_id": segment.benchmark_id,
                    "mapping_source": segment.mapping_source,
                    "mapping_version": segment.mapping_version,
                    "status": segment.status,
                    "components": [
                        {
                            "index_id": component.index_id,
                            "weight": _decimal_text(component.weight),
                        }
                        for component in segment.components
                    ],
                    "index_observations": index_lineage,
                }
            )
        return tuple(result), tuple(lineage), switch_dates

    def _assemble_basis(
        self,
        return_basis: str,
        snapshot_id: int,
        policy: EstimationPolicy,
        candidate_order: tuple[int, ...],
        instruments: tuple[_InstrumentInput, ...],
    ) -> EstimationBasisInput:
        if return_basis == "ABSOLUTE":
            series = {item.share_class_id: item.absolute_returns for item in instruments}
            exclusion_reasons: dict[int, str] = {}
        else:
            series = {item.share_class_id: item.excess_returns for item in instruments}
            exclusion_reasons = {
                item.share_class_id: item.excess_exclusion_reason
                for item in instruments
                if item.excess_exclusion_reason is not None
            }
        aligned = _align(series, tuple(list(candidate_order)), exclusion_reasons)
        observation_dates = tuple(list(aligned.observation_dates))
        observation_fingerprint = canonical_checksum(
            {"observation_dates": [day.isoformat() for day in observation_dates]}
        )
        instrument_lineage: dict[str, object] = {}
        for item in instruments:
            details: dict[str, object] = {
                "fund_id": item.fund_id,
                "nav_observations": [
                    _nav_lineage(item.share_class_id, point) for point in item.nav_points
                ],
            }
            if return_basis == "EXCESS":
                details["classification"] = item.classification
                details["benchmark_segments"] = list(item.benchmark_segments)
            instrument_lineage[str(item.share_class_id)] = details
        switch_dates = (
            sorted(
                {
                    day
                    for item in instruments
                    for day in item.benchmark_switch_dates
                }
            )
            if return_basis == "EXCESS"
            else []
        )
        lineage: dict[str, Any] = {
            "universe_snapshot_id": snapshot_id,
            "instrument_order": list(aligned.instrument_order),
            "adjustment_policy_version": self._adjustment_policy_version,
            "window": {
                "lookback_trading_days": policy.lookback_trading_days,
                "type": policy.window_type,
            },
            "forecast_horizon": policy.forecast_horizon,
            "return_basis": return_basis,
            "numeric_scale": policy.numeric_scale,
            "excluded_instruments": [
                {"share_class_id": share_class_id, "reason": reason}
                for share_class_id, reason in aligned.excluded_instruments
            ],
            "observation_dates": [day.isoformat() for day in observation_dates],
            "dropped_dates": [day.isoformat() for day in aligned.dropped_dates],
            "data_completeness": {
                "candidate_count": len(candidate_order),
                "included_count": len(aligned.instrument_order),
                "observation_count": len(observation_dates),
                "dropped_dates_count": len(aligned.dropped_dates),
                "aligned_from": observation_dates[0].isoformat() if observation_dates else None,
                "aligned_to": observation_dates[-1].isoformat() if observation_dates else None,
                "valid_return_counts": {
                    str(share_class_id): len(series[share_class_id])
                    for share_class_id in candidate_order
                },
            },
            "instruments": instrument_lineage,
        }
        if return_basis == "EXCESS":
            lineage["benchmark_switch_dates"] = [day.isoformat() for day in switch_dates]
        basis_fingerprint = canonical_checksum(lineage)
        return EstimationBasisInput(
            return_basis=return_basis,
            matrix=aligned.matrix.copy(),
            instrument_order=tuple(list(aligned.instrument_order)),
            observation_dates=observation_dates,
            excluded_instruments=tuple(list(aligned.excluded_instruments)),
            dropped_dates=tuple(list(aligned.dropped_dates)),
            lineage=lineage,
            observation_fingerprint=observation_fingerprint,
            basis_fingerprint=basis_fingerprint,
        )

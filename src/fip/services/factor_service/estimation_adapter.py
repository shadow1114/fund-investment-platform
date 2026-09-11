"""Factor-owned SQL adapter for estimation risk cross-check candidates."""

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.factor_service.models import (
    FactorDefinition,
    FactorRun,
    FactorValue,
    FactorVersion,
)
from fip.strategy_library.estimation.encoding import canonical_checksum
from fip.strategy_library.estimation.types import FactorRiskObservation

_RISK_FACTOR_ID = "F-RISK-001"


def _lineage_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _observation_fingerprint(lineage: dict[str, Any]) -> str | None:
    fingerprint = _lineage_string(lineage, "observation_fingerprint")
    if fingerprint is None:
        return None
    dates = lineage.get("observation_dates")
    if not isinstance(dates, list) or not dates:
        return None
    if any(not isinstance(value, str) for value in dates):
        return None
    try:
        parsed = tuple(dt.date.fromisoformat(value) for value in dates)
    except ValueError:
        return None
    if tuple(sorted(parsed)) != parsed or len(set(parsed)) != len(parsed):
        return None
    canonical = canonical_checksum({"observation_dates": dates})
    return fingerprint if fingerprint == canonical else None


def _lineage_string(lineage: dict[str, Any], field: str) -> str | None:
    value = lineage.get(field)
    return value if isinstance(value, str) and value else None


def _lineage_positive_int(lineage: dict[str, Any], field: str) -> int | None:
    value = lineage.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return value


class SqlFactorRiskCrossCheckProvider:
    """Read every decision-scoped volatility Factor candidate in stable ID order."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load_candidates(
        self, share_class_id: int, decision_id: str
    ) -> tuple[FactorRiskObservation, ...]:
        rows = self._session.execute(
            select(FactorRun.id, FactorValue)
            .join(FactorValue, FactorValue.factor_run_id == FactorRun.id)
            .join(FactorVersion, FactorValue.factor_version_id == FactorVersion.id)
            .join(FactorDefinition, FactorVersion.factor_definition_id == FactorDefinition.id)
            .where(
                FactorRun.decision_id == decision_id,
                FactorValue.share_class_id == share_class_id,
                FactorDefinition.factor_id == _RISK_FACTOR_ID,
            )
            .order_by(FactorValue.id)
        ).all()
        return tuple(
            _observation_from_row(factor_run_id, value) for factor_run_id, value in rows
        )


def _observation_from_row(factor_run_id: int, value: FactorValue) -> FactorRiskObservation:
    lineage = _lineage_mapping(value.input_lineage)
    return FactorRiskObservation(
        factor_run_id=factor_run_id,
        factor_value_id=value.id,
        factor_version_id=value.factor_version_id,
        volatility=None if value.raw_value is None else float(value.raw_value),
        window=value.window,
        observation_fingerprint=_observation_fingerprint(lineage),
        return_type=_lineage_string(lineage, "return_type"),
        ddof=_lineage_positive_int(lineage, "ddof"),
        annualization=_lineage_positive_int(lineage, "annualization"),
        status=value.status,
    )

import datetime as dt
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.factor_service.models import FactorRun, FactorValue


class FactorRunConflict(ValueError):
    pass


class FactorValueConflict(ValueError):
    pass


def _same_number(actual: float | None, expected: float | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-10)


class FactorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_run(
        self,
        *,
        decision_id: str,
        peer_group_snapshot_id: int,
        metric_version_id: int,
        evaluation_policy_version_id: int | None,
        input_quality_summary: dict[str, object],
    ) -> int:
        existing = self._session.execute(
            select(FactorRun).where(
                FactorRun.decision_id == decision_id,
                FactorRun.peer_group_snapshot_id == peer_group_snapshot_id,
                FactorRun.metric_version_id == metric_version_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.input_quality_summary != input_quality_summary:
                raise FactorRunConflict("factor run idempotency key conflicts with different input")
            return existing.id
        row = FactorRun(
            decision_id=decision_id,
            peer_group_snapshot_id=peer_group_snapshot_id,
            metric_version_id=metric_version_id,
            evaluation_policy_version_id=evaluation_policy_version_id,
            input_quality_summary=input_quality_summary,
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def save_value(
        self,
        *,
        factor_run_id: int,
        share_class_id: int,
        factor_version_id: int,
        window: str,
        effective_at: dt.date,
        version: int,
        status: str,
        reason_code: str | None,
        raw_value: float | None,
        normalized_value: float | None,
        evaluation_policy_version_id: int | None,
        input_lineage: dict[str, object],
        adjustment_policy_version: str,
    ) -> int:
        existing = self._session.execute(
            select(FactorValue).where(
                FactorValue.share_class_id == share_class_id,
                FactorValue.factor_version_id == factor_version_id,
                FactorValue.window == window,
                FactorValue.effective_at == effective_at,
                FactorValue.version == version,
                FactorValue.evaluation_policy_version_id == evaluation_policy_version_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing_raw = None if existing.raw_value is None else float(existing.raw_value)
            existing_normalized = (
                None if existing.normalized_value is None else float(existing.normalized_value)
            )
            exact_match = (
                existing.factor_run_id == factor_run_id
                and existing.status == status
                and existing.reason_code == reason_code
                and existing.input_lineage == input_lineage
                and existing.adjustment_policy_version == adjustment_policy_version
            )
            numeric_match = _same_number(existing_raw, raw_value) and _same_number(
                existing_normalized, normalized_value
            )
            if not exact_match or not numeric_match:
                raise FactorValueConflict("factor value key conflicts with different result")
            return existing.id
        row = FactorValue(
            factor_run_id=factor_run_id,
            share_class_id=share_class_id,
            factor_version_id=factor_version_id,
            window=window,
            effective_at=effective_at,
            version=version,
            status=status,
            reason_code=reason_code,
            raw_value=raw_value,
            normalized_value=normalized_value,
            input_lineage=input_lineage,
            adjustment_policy_version=adjustment_policy_version,
            evaluation_policy_version_id=evaluation_policy_version_id,
        )
        self._session.add(row)
        self._session.flush()
        return row.id

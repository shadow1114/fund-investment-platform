"""Transactional persistence and approved reads for estimation results."""

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fip.services.portfolio_service.estimation.models import (
    FINAL_BUSINESS_STATUSES,
    RETURN_BASES,
    CovarianceEstimate,
    EstimationRun,
    EstimationValidationResult,
    ReturnEstimate,
    RiskEstimate,
)
from fip.strategy_library.estimation.encoding import (
    canonical_checksum,
    decode_lower_triangle,
    encode_float64,
    encode_lower_triangle,
)
from fip.strategy_library.estimation.types import (
    CovarianceEstimateResult,
    ReturnEstimateResult,
)
from fip.strategy_library.estimation.validation import ValidationResult

NUMERIC_ENCODING_VERSION = "FLOAT64_SHORTEST_ROUNDTRIP_V1"


class EstimationRunConflict(ValueError):
    """The same run identity resolved to different immutable input lineage."""


class EstimationIntegrityError(ValueError):
    """A result bundle is incomplete, misaligned, or corrupt."""


class EstimationStateError(ValueError):
    """A requested run transition is not legal from the persisted state."""


@dataclass(frozen=True, slots=True)
class EstimationRunIdentity:
    decision_id: str
    universe_snapshot_id: int
    estimation_method_version_id: int
    estimation_parameter_version_id: int
    estimation_policy_version_id: int
    validation_policy_version_id: int
    code_version: str


@dataclass(frozen=True, slots=True)
class StartRunResult:
    run_id: int
    status: str
    should_execute: bool


@dataclass(frozen=True, slots=True)
class EstimationRunResult:
    run_id: int
    status: str
    approved_for_optimization: bool
    input_lineage_fingerprint: str | None


@dataclass(frozen=True, slots=True)
class EstimationResultBundle:
    return_basis: str
    instrument_order: tuple[int, ...]
    return_estimate: ReturnEstimateResult
    covariance_estimate: CovarianceEstimateResult
    observation_count: int
    dropped_dates_count: int
    excluded_instruments: tuple[tuple[int, str], ...]
    input_lineage: dict[str, Any]
    input_fingerprint: str
    validations: tuple[ValidationResult, ...]


@dataclass(frozen=True, slots=True)
class EstimationBasisRejection:
    return_basis: str
    reason_code: str
    input_lineage: dict[str, Any]
    input_fingerprint: str
    observation_count: int
    dropped_dates_count: int
    excluded_instruments: tuple[tuple[int, str], ...]


@dataclass(frozen=True, slots=True)
class ApprovedEstimation:
    run_id: int
    return_basis: str
    instrument_order: tuple[int, ...]
    mu: np.ndarray  # type: ignore[type-arg]
    covariance: np.ndarray  # type: ignore[type-arg]
    estimation_method_version_id: int
    estimation_parameter_version_id: int
    estimation_policy_version_id: int
    validation_policy_version_id: int
    code_version: str
    input_lineage_fingerprint: str


def _identity_predicates(identity: EstimationRunIdentity) -> tuple[Any, ...]:
    return (
        EstimationRun.decision_id == identity.decision_id,
        EstimationRun.universe_snapshot_id == identity.universe_snapshot_id,
        EstimationRun.estimation_method_version_id == identity.estimation_method_version_id,
        EstimationRun.estimation_parameter_version_id == identity.estimation_parameter_version_id,
        EstimationRun.estimation_policy_version_id == identity.estimation_policy_version_id,
        EstimationRun.validation_policy_version_id == identity.validation_policy_version_id,
        EstimationRun.code_version == identity.code_version,
    )


def _run_result(row: EstimationRun) -> EstimationRunResult:
    return EstimationRunResult(
        run_id=row.id,
        status=row.status,
        approved_for_optimization=row.approved_for_optimization,
        input_lineage_fingerprint=row.input_lineage_fingerprint,
    )


def _validate_fingerprint(value: str, field: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise EstimationIntegrityError(f"{field} must be a lowercase SHA-256 digest")


def aggregate_input_lineage_fingerprint(basis_fingerprints: dict[str, str]) -> str:
    """Aggregate canonical per-basis fingerprints into the immutable run digest."""
    if not basis_fingerprints:
        raise EstimationIntegrityError("run fingerprint requires at least one basis outcome")
    if any(basis not in RETURN_BASES for basis in basis_fingerprints):
        raise EstimationIntegrityError("run fingerprint contains an unsupported return basis")
    for basis, fingerprint in basis_fingerprints.items():
        _validate_fingerprint(fingerprint, f"{basis} input_fingerprint")
    return canonical_checksum(dict(sorted(basis_fingerprints.items())))


def _shape(value: object) -> tuple[int, ...]:
    return tuple(np.asarray(value).shape)


def _require_finite(value: object, field: str) -> None:
    try:
        finite = bool(np.isfinite(np.asarray(value, dtype=np.float64)).all())
    except (TypeError, ValueError) as exc:
        raise EstimationIntegrityError(f"{field} must contain float64 values") from exc
    if not finite:
        raise EstimationIntegrityError(f"{field} must contain only finite values")


def _decode_canonical_float64(value: object, field: str) -> float:
    if not isinstance(value, str):
        raise EstimationIntegrityError(f"{field} must be a canonical float64 string")
    try:
        decoded = float(value)
        canonical = encode_float64(decoded)
    except (TypeError, ValueError) as exc:
        raise EstimationIntegrityError(f"{field} is not a finite float64 string") from exc
    if canonical != value:
        raise EstimationIntegrityError(f"{field} is not shortest-roundtrip float64 encoding")
    return decoded


def _validate_bundle(bundle: EstimationResultBundle) -> None:
    if bundle.return_basis not in RETURN_BASES:
        raise EstimationIntegrityError(f"unsupported return basis: {bundle.return_basis}")
    order = bundle.instrument_order
    if not order or len(set(order)) != len(order):
        raise EstimationIntegrityError("instrument_order must contain unique members")
    if any(not isinstance(item, int) or isinstance(item, bool) for item in order):
        raise EstimationIntegrityError("instrument_order members must be integer IDs")
    lineage_order = bundle.input_lineage.get("instrument_order")
    if lineage_order != list(order):
        raise EstimationIntegrityError("input lineage instrument order does not match bundle")
    if bundle.input_lineage.get("numeric_scale") != "ANNUALIZED":
        raise EstimationIntegrityError("result bundle numeric scale must be ANNUALIZED")
    _validate_fingerprint(bundle.input_fingerprint, "input_fingerprint")
    try:
        lineage_fingerprint = canonical_checksum(bundle.input_lineage)
    except (TypeError, ValueError) as exc:
        raise EstimationIntegrityError("input lineage is not canonical JSON") from exc
    if lineage_fingerprint != bundle.input_fingerprint:
        raise EstimationIntegrityError("input fingerprint does not match canonical lineage")
    if bundle.observation_count < 0 or bundle.dropped_dates_count < 0:
        raise EstimationIntegrityError("result counts must be non-negative")

    size = len(order)
    returns = bundle.return_estimate
    covariance = bundle.covariance_estimate
    expected_vector = (size,)
    expected_matrix = (size, size)
    vector_fields = {
        "sample_mean_daily": returns.sample_mean_daily,
        "shrunk_mu_annualized": returns.shrunk_mu_annualized,
        "annualized_mu": returns.annualized_mu,
        "clipped": returns.clipped,
        "variance": covariance.variance,
        "volatility": covariance.volatility,
    }
    matrix_fields = {
        "sample_covariance_daily": covariance.sample_covariance_daily,
        "target_covariance_daily": covariance.target_covariance_daily,
        "covariance": covariance.covariance,
        "correlation": covariance.correlation,
    }
    for field, value in vector_fields.items():
        if _shape(value) != expected_vector:
            raise EstimationIntegrityError(
                f"{field} shape {_shape(value)} does not match instrument order {expected_vector}"
            )
    for field, value in matrix_fields.items():
        if _shape(value) != expected_matrix:
            raise EstimationIntegrityError(
                f"{field} shape {_shape(value)} does not match instrument order {expected_matrix}"
            )
    for field, value in {**vector_fields, **matrix_fields}.items():
        _require_finite(value, field)
    scalar_fields = {
        "return target": returns.target_daily,
        "return shrinkage": returns.shrinkage_intensity,
        "covariance shrinkage": covariance.shrinkage_intensity,
        "sample minimum eigenvalue": covariance.sample_min_eigenvalue,
        "sample maximum eigenvalue": covariance.sample_max_eigenvalue,
        "sample condition number": covariance.sample_condition_number,
        "final minimum eigenvalue": covariance.final_min_eigenvalue,
        "final maximum eigenvalue": covariance.final_max_eigenvalue,
        "final condition number": covariance.final_condition_number,
    }
    for field, scalar_value in scalar_fields.items():
        try:
            finite = math.isfinite(float(scalar_value))
        except (TypeError, ValueError) as exc:
            raise EstimationIntegrityError(f"{field} must be a finite float64") from exc
        if not finite:
            raise EstimationIntegrityError(f"{field} must be finite")
    if np.asarray(returns.clipped).dtype.kind != "b":
        raise EstimationIntegrityError("clipped must be a boolean vector")
    codes = tuple(result.code for result in bundle.validations)
    if len(set(codes)) != len(codes):
        raise EstimationIntegrityError("validation codes must be unique within a basis")


def _validate_basis_rejection(rejection: EstimationBasisRejection) -> None:
    if rejection.return_basis not in RETURN_BASES:
        raise EstimationIntegrityError(f"unsupported return basis: {rejection.return_basis}")
    if not rejection.reason_code or len(rejection.reason_code) > 64:
        raise EstimationIntegrityError("basis rejection reason_code must contain 1-64 characters")
    if rejection.observation_count < 0 or rejection.dropped_dates_count < 0:
        raise EstimationIntegrityError("basis rejection counts must be non-negative")
    order = rejection.input_lineage.get("instrument_order")
    if (
        not isinstance(order, list)
        or any(not isinstance(item, int) or isinstance(item, bool) for item in order)
        or len(set(order)) != len(order)
    ):
        raise EstimationIntegrityError("basis rejection lineage instrument order is invalid")
    _validate_fingerprint(rejection.input_fingerprint, "input_fingerprint")
    try:
        lineage_fingerprint = canonical_checksum(rejection.input_lineage)
    except (TypeError, ValueError) as exc:
        raise EstimationIntegrityError("basis rejection lineage is not canonical JSON") from exc
    if lineage_fingerprint != rejection.input_fingerprint:
        raise EstimationIntegrityError(
            "basis rejection fingerprint does not match canonical lineage"
        )
    excluded_ids = tuple(item for item, _reason in rejection.excluded_instruments)
    if len(set(excluded_ids)) != len(excluded_ids):
        raise EstimationIntegrityError("basis rejection exclusions must contain unique members")


def _matrix_payload(matrix: object, order: tuple[int, ...]) -> dict[str, object]:
    core: dict[str, object] = {
        "shape": [len(order), len(order)],
        "instrument_order": list(order),
        "lower_triangle": list(encode_lower_triangle(np.asarray(matrix, dtype=np.float64))),
        "numeric_encoding_version": NUMERIC_ENCODING_VERSION,
    }
    return {**core, "checksum": canonical_checksum(core)}


class EstimationRunRepository:
    """Write-once result repository with row-locked lifecycle transitions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def start(self, identity: EstimationRunIdentity) -> StartRunResult:
        existing = self._session.execute(
            select(EstimationRun).where(*_identity_predicates(identity)).with_for_update()
        ).scalar_one_or_none()
        if existing is not None:
            return StartRunResult(existing.id, existing.status, False)

        row = EstimationRun(
            decision_id=identity.decision_id,
            universe_snapshot_id=identity.universe_snapshot_id,
            estimation_method_version_id=identity.estimation_method_version_id,
            estimation_parameter_version_id=identity.estimation_parameter_version_id,
            estimation_policy_version_id=identity.estimation_policy_version_id,
            validation_policy_version_id=identity.validation_policy_version_id,
            code_version=identity.code_version,
            status="RUNNING",
            approved_for_optimization=False,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(EstimationRun).where(*_identity_predicates(identity)).with_for_update()
            ).scalar_one_or_none()
            if existing is None:
                raise
            return StartRunResult(existing.id, existing.status, False)
        return StartRunResult(row.id, row.status, True)

    def retry_failed(self, run_id: int) -> StartRunResult:
        row = self._locked_run(run_id)
        if row.status != "FAILED":
            raise EstimationStateError(f"run {run_id} cannot retry from {row.status}")
        if self._has_results(run_id):
            raise EstimationIntegrityError("a failed run must not contain business results")
        row.status = "RUNNING"
        row.approved_for_optimization = False
        row.input_lineage_fingerprint = None
        row.error_code = None
        row.completed_at = None
        self._session.flush()
        return StartRunResult(row.id, row.status, True)

    def complete(
        self,
        run_id: int,
        bundles: tuple[EstimationResultBundle, ...],
        fingerprint: str,
        *,
        basis_rejections: tuple[EstimationBasisRejection, ...] = (),
    ) -> EstimationRunResult:
        return self._finalize(
            run_id,
            bundles,
            fingerprint,
            basis_rejections=basis_rejections,
        )

    def reject(
        self,
        run_id: int,
        bundles: tuple[EstimationResultBundle, ...],
        fingerprint: str,
        *,
        basis_rejections: tuple[EstimationBasisRejection, ...] = (),
    ) -> EstimationRunResult:
        return self._finalize(
            run_id,
            bundles,
            fingerprint,
            basis_rejections=basis_rejections,
        )

    def fail(self, run_id: int, error_code: str) -> EstimationRunResult:
        row = self._locked_run(run_id)
        if row.status != "RUNNING":
            raise EstimationStateError(f"run {run_id} cannot fail from {row.status}")
        if self._has_results(run_id):
            raise EstimationIntegrityError(
                "cannot fail a run with partial results; roll back the result transaction first"
            )
        if not error_code or len(error_code) > 64:
            raise ValueError("error_code must contain between 1 and 64 characters")
        row.status = "FAILED"
        row.approved_for_optimization = False
        row.input_lineage_fingerprint = None
        row.error_code = error_code
        row.completed_at = dt.datetime.now(dt.UTC)
        self._session.flush()
        return _run_result(row)

    def _finalize(
        self,
        run_id: int,
        bundles: tuple[EstimationResultBundle, ...],
        fingerprint: str,
        *,
        basis_rejections: tuple[EstimationBasisRejection, ...],
    ) -> EstimationRunResult:
        _validate_fingerprint(fingerprint, "input_lineage_fingerprint")
        if not bundles and not basis_rejections:
            raise EstimationIntegrityError(
                "a final business run must contain a result or rejected-basis audit"
            )
        bases = tuple(bundle.return_basis for bundle in bundles)
        if len(set(bases)) != len(bases):
            raise EstimationIntegrityError("each return basis may appear only once")
        rejected_bases = tuple(rejection.return_basis for rejection in basis_rejections)
        if len(set(rejected_bases)) != len(rejected_bases):
            raise EstimationIntegrityError("each rejected return basis may appear only once")
        if set(bases) & set(rejected_bases):
            raise EstimationIntegrityError("a return basis cannot be both estimated and rejected")
        if "ABSOLUTE" not in {*bases, *rejected_bases}:
            raise EstimationIntegrityError("a final run requires an ABSOLUTE basis outcome")
        for bundle in bundles:
            _validate_bundle(bundle)
        for rejection in basis_rejections:
            _validate_basis_rejection(rejection)
        status, approved = self._derive_outcome(bundles, basis_rejections)
        basis_fingerprints = {bundle.return_basis: bundle.input_fingerprint for bundle in bundles}
        basis_fingerprints.update(
            {rejection.return_basis: rejection.input_fingerprint for rejection in basis_rejections}
        )
        expected_fingerprint = aggregate_input_lineage_fingerprint(basis_fingerprints)
        if fingerprint != expected_fingerprint:
            raise EstimationIntegrityError(
                "run input fingerprint does not match persisted basis fingerprints"
            )

        row = self._locked_run(run_id)
        if row.status in FINAL_BUSINESS_STATUSES:
            if row.input_lineage_fingerprint != fingerprint:
                raise EstimationRunConflict(
                    f"run {run_id} identity conflicts with different input lineage"
                )
            return _run_result(row)
        if row.status != "RUNNING":
            raise EstimationStateError(f"run {run_id} cannot finalize from {row.status}")

        for bundle in bundles:
            self._save_bundle(run_id, bundle)
        for rejection in basis_rejections:
            self._save_basis_rejection(run_id, rejection)
        row.status = status
        row.approved_for_optimization = approved
        row.input_lineage_fingerprint = fingerprint
        row.error_code = None
        row.completed_at = dt.datetime.now(dt.UTC)
        self._session.flush()
        return _run_result(row)

    @staticmethod
    def _derive_outcome(
        bundles: tuple[EstimationResultBundle, ...],
        basis_rejections: tuple[EstimationBasisRejection, ...],
    ) -> tuple[str, bool]:
        rejected_bases = {rejection.return_basis for rejection in basis_rejections}
        by_basis = {bundle.return_basis: bundle for bundle in bundles}
        absolute = by_basis.get("ABSOLUTE")
        absolute_reject_failed = absolute is not None and any(
            result.severity == "REJECT" and result.status == "FAILED"
            for result in absolute.validations
        )
        if "ABSOLUTE" in rejected_bases or absolute_reject_failed:
            return "REJECTED", False

        any_failed_validation = any(
            result.status == "FAILED" for bundle in bundles for result in bundle.validations
        )
        has_excess_rejection = "EXCESS" in rejected_bases
        if any_failed_validation or has_excess_rejection:
            return "COMPLETED_WITH_WARNING", True
        return "COMPLETED", True

    def _save_bundle(self, run_id: int, bundle: EstimationResultBundle) -> None:
        order = bundle.instrument_order
        returns = bundle.return_estimate
        risk = bundle.covariance_estimate
        for index, share_class_id in enumerate(order):
            self._session.add(
                ReturnEstimate(
                    run_id=run_id,
                    return_basis=bundle.return_basis,
                    share_class_id=share_class_id,
                    sample_mean=encode_float64(returns.sample_mean_daily[index]),
                    shrinkage_target=encode_float64(returns.target_daily),
                    shrinkage_intensity=encode_float64(returns.shrinkage_intensity),
                    mu_before_clip=encode_float64(returns.shrunk_mu_annualized[index]),
                    mu=encode_float64(returns.annualized_mu[index]),
                    mu_clipped=bool(returns.clipped[index]),
                    numeric_encoding_version=NUMERIC_ENCODING_VERSION,
                )
            )
            self._session.add(
                RiskEstimate(
                    run_id=run_id,
                    return_basis=bundle.return_basis,
                    share_class_id=share_class_id,
                    variance=encode_float64(risk.variance[index]),
                    volatility=encode_float64(risk.volatility[index]),
                    numeric_encoding_version=NUMERIC_ENCODING_VERSION,
                )
            )
        self._session.add(
            CovarianceEstimate(
                run_id=run_id,
                return_basis=bundle.return_basis,
                covariance_payload=_matrix_payload(risk.covariance, order),
                correlation_payload=_matrix_payload(risk.correlation, order),
                shrinkage_intensity=encode_float64(risk.shrinkage_intensity),
                sample_min_eigenvalue=encode_float64(risk.sample_min_eigenvalue),
                sample_max_eigenvalue=encode_float64(risk.sample_max_eigenvalue),
                sample_condition_number=encode_float64(risk.sample_condition_number),
                final_min_eigenvalue=encode_float64(risk.final_min_eigenvalue),
                final_max_eigenvalue=encode_float64(risk.final_max_eigenvalue),
                final_condition_number=encode_float64(risk.final_condition_number),
                observation_count=bundle.observation_count,
                instrument_count=len(order),
                dropped_dates_count=bundle.dropped_dates_count,
                excluded_instruments=[
                    {"share_class_id": item, "reason": reason}
                    for item, reason in bundle.excluded_instruments
                ],
                input_lineage=bundle.input_lineage,
                input_fingerprint=bundle.input_fingerprint,
            )
        )
        self._session.add_all(
            EstimationValidationResult(
                run_id=run_id,
                return_basis=bundle.return_basis,
                code=result.code,
                severity=result.severity,
                status=result.status,
                detail={"message": result.detail},
            )
            for result in bundle.validations
        )

    def _save_basis_rejection(self, run_id: int, rejection: EstimationBasisRejection) -> None:
        self._session.add(
            EstimationValidationResult(
                run_id=run_id,
                return_basis=rejection.return_basis,
                code="BASIS_INPUT_REJECTED",
                severity="REJECT",
                status="FAILED",
                detail={
                    "reason_code": rejection.reason_code,
                    "input_lineage": rejection.input_lineage,
                    "input_fingerprint": rejection.input_fingerprint,
                    "observation_count": rejection.observation_count,
                    "dropped_dates_count": rejection.dropped_dates_count,
                    "excluded_instruments": [
                        {"share_class_id": item, "reason": reason}
                        for item, reason in rejection.excluded_instruments
                    ],
                },
            )
        )

    def _locked_run(self, run_id: int) -> EstimationRun:
        row = self._session.execute(
            select(EstimationRun).where(EstimationRun.id == run_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise EstimationStateError(f"estimation run {run_id} does not exist")
        return row

    def _has_results(self, run_id: int) -> bool:
        result_models = (
            ReturnEstimate,
            RiskEstimate,
            CovarianceEstimate,
            EstimationValidationResult,
        )
        return any(
            bool(
                self._session.scalar(
                    select(func.count()).select_from(model).where(model.run_id == run_id)
                )
            )
            for model in result_models
        )


class ApprovedEstimationProvider:
    """Read only a checksum-valid, final, approved ABSOLUTE result package."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self, run_id: int) -> ApprovedEstimation:
        run = self._session.execute(
            select(EstimationRun).where(
                EstimationRun.id == run_id,
                EstimationRun.status.in_(FINAL_BUSINESS_STATUSES),
                EstimationRun.approved_for_optimization.is_(True),
            )
        ).scalar_one_or_none()
        if run is None or run.input_lineage_fingerprint is None:
            raise EstimationIntegrityError(f"run {run_id} is not a final approved estimation")

        all_covariance_rows = (
            self._session.execute(
                select(CovarianceEstimate).where(CovarianceEstimate.run_id == run_id)
            )
            .scalars()
            .all()
        )
        rejection_rows = (
            self._session.execute(
                select(EstimationValidationResult).where(
                    EstimationValidationResult.run_id == run_id,
                    EstimationValidationResult.code == "BASIS_INPUT_REJECTED",
                )
            )
            .scalars()
            .all()
        )
        basis_fingerprints: dict[str, str] = {}
        for covariance_result in all_covariance_rows:
            self._add_verified_basis_fingerprint(
                basis_fingerprints,
                covariance_result.return_basis,
                covariance_result.input_lineage,
                covariance_result.input_fingerprint,
            )
        for rejection in rejection_rows:
            detail = rejection.detail
            lineage = detail.get("input_lineage")
            basis_fingerprint = detail.get("input_fingerprint")
            if (
                rejection.return_basis is None
                or not isinstance(lineage, dict)
                or not isinstance(basis_fingerprint, str)
            ):
                raise EstimationIntegrityError("rejected basis lineage payload is invalid")
            self._add_verified_basis_fingerprint(
                basis_fingerprints,
                rejection.return_basis,
                lineage,
                basis_fingerprint,
            )
        expected_run_fingerprint = aggregate_input_lineage_fingerprint(basis_fingerprints)
        if run.input_lineage_fingerprint != expected_run_fingerprint:
            raise EstimationIntegrityError(
                "run input fingerprint does not match persisted basis lineage"
            )

        covariance_rows = [row for row in all_covariance_rows if row.return_basis == "ABSOLUTE"]
        if len(covariance_rows) != 1:
            raise EstimationIntegrityError(
                "approved run must contain exactly one ABSOLUTE covariance result"
            )
        covariance_row = covariance_rows[0]
        covariance, order = self._decode_payload(covariance_row.covariance_payload)
        correlation, correlation_order = self._decode_payload(covariance_row.correlation_payload)
        if correlation_order != order or correlation.shape != covariance.shape:
            raise EstimationIntegrityError(
                "covariance and correlation instrument order or dimensions differ"
            )

        return_rows = (
            self._session.execute(
                select(ReturnEstimate).where(
                    ReturnEstimate.run_id == run_id,
                    ReturnEstimate.return_basis == "ABSOLUTE",
                )
            )
            .scalars()
            .all()
        )
        risk_rows = (
            self._session.execute(
                select(RiskEstimate).where(
                    RiskEstimate.run_id == run_id,
                    RiskEstimate.return_basis == "ABSOLUTE",
                )
            )
            .scalars()
            .all()
        )
        return_by_member = {row.share_class_id: row for row in return_rows}
        risk_by_member = {row.share_class_id: row for row in risk_rows}
        if set(return_by_member) != set(order) or set(risk_by_member) != set(order):
            raise EstimationIntegrityError(
                "approved Return/Risk members differ from covariance instrument order"
            )
        if covariance_row.instrument_count != len(order):
            raise EstimationIntegrityError(
                "covariance instrument_count differs from instrument order"
            )
        if covariance_row.input_lineage.get("instrument_order") != list(order):
            raise EstimationIntegrityError(
                "covariance lineage instrument order differs from payload"
            )
        if covariance_row.input_lineage.get("numeric_scale") != "ANNUALIZED":
            raise EstimationIntegrityError("approved result numeric scale is not ANNUALIZED")
        _validate_fingerprint(covariance_row.input_fingerprint, "input_fingerprint")
        try:
            stored_lineage_fingerprint = canonical_checksum(covariance_row.input_lineage)
        except (TypeError, ValueError) as exc:
            raise EstimationIntegrityError("approved input lineage is not canonical JSON") from exc
        if stored_lineage_fingerprint != covariance_row.input_fingerprint:
            raise EstimationIntegrityError(
                "approved input fingerprint does not match canonical lineage"
            )
        return_encoding_mismatch = any(
            row.numeric_encoding_version != NUMERIC_ENCODING_VERSION for row in return_rows
        )
        risk_encoding_mismatch = any(
            row.numeric_encoding_version != NUMERIC_ENCODING_VERSION for row in risk_rows
        )
        if return_encoding_mismatch or risk_encoding_mismatch:
            raise EstimationIntegrityError("result numeric encoding versions differ")

        for return_result in return_rows:
            for field in (
                "sample_mean",
                "shrinkage_target",
                "shrinkage_intensity",
                "mu_before_clip",
                "mu",
            ):
                _decode_canonical_float64(getattr(return_result, field), f"ReturnEstimate.{field}")
        for risk_result in risk_rows:
            for field in ("variance", "volatility"):
                _decode_canonical_float64(getattr(risk_result, field), f"RiskEstimate.{field}")
        for field in (
            "shrinkage_intensity",
            "sample_min_eigenvalue",
            "sample_max_eigenvalue",
            "sample_condition_number",
            "final_min_eigenvalue",
            "final_max_eigenvalue",
            "final_condition_number",
        ):
            _decode_canonical_float64(getattr(covariance_row, field), f"CovarianceEstimate.{field}")

        try:
            mu = np.asarray(
                [
                    _decode_canonical_float64(return_by_member[member].mu, "ReturnEstimate.mu")
                    for member in order
                ],
                dtype=np.float64,
            )
            variance = np.asarray(
                [
                    _decode_canonical_float64(
                        risk_by_member[member].variance, "RiskEstimate.variance"
                    )
                    for member in order
                ],
                dtype=np.float64,
            )
            volatility = np.asarray(
                [
                    _decode_canonical_float64(
                        risk_by_member[member].volatility, "RiskEstimate.volatility"
                    )
                    for member in order
                ],
                dtype=np.float64,
            )
        except (TypeError, ValueError, EstimationIntegrityError) as exc:
            raise EstimationIntegrityError("approved vector payload cannot be decoded") from exc
        if not all(np.isfinite(value).all() for value in (mu, variance, volatility)):
            raise EstimationIntegrityError("approved vector payload contains non-finite values")
        if not np.array_equal(variance, np.diag(covariance)) or not np.array_equal(
            volatility, np.sqrt(variance)
        ):
            raise EstimationIntegrityError(
                "approved Risk rows do not match the covariance diagonal"
            )

        return ApprovedEstimation(
            run_id=run.id,
            return_basis="ABSOLUTE",
            instrument_order=order,
            mu=mu,
            covariance=covariance,
            estimation_method_version_id=run.estimation_method_version_id,
            estimation_parameter_version_id=run.estimation_parameter_version_id,
            estimation_policy_version_id=run.estimation_policy_version_id,
            validation_policy_version_id=run.validation_policy_version_id,
            code_version=run.code_version,
            input_lineage_fingerprint=run.input_lineage_fingerprint,
        )

    @staticmethod
    def _add_verified_basis_fingerprint(
        collected: dict[str, str],
        basis: str,
        lineage: dict[str, Any],
        fingerprint: str,
    ) -> None:
        if basis in collected:
            raise EstimationIntegrityError(f"duplicate persisted {basis} basis outcome")
        _validate_fingerprint(fingerprint, "input_fingerprint")
        try:
            expected = canonical_checksum(lineage)
        except (TypeError, ValueError) as exc:
            raise EstimationIntegrityError("persisted basis lineage is not canonical JSON") from exc
        if fingerprint != expected:
            raise EstimationIntegrityError(
                f"persisted {basis} fingerprint does not match canonical lineage"
            )
        collected[basis] = fingerprint

    @staticmethod
    def _decode_payload(payload: object) -> tuple[np.ndarray[Any, Any], tuple[int, ...]]:
        if not isinstance(payload, dict):
            raise EstimationIntegrityError("matrix payload must be an object")
        required = {
            "shape",
            "instrument_order",
            "lower_triangle",
            "numeric_encoding_version",
            "checksum",
        }
        if set(payload) != required:
            raise EstimationIntegrityError("matrix payload keys do not match the contract")
        checksum = payload.get("checksum")
        core = {key: value for key, value in payload.items() if key != "checksum"}
        if not isinstance(checksum, str) or canonical_checksum(core) != checksum:
            raise EstimationIntegrityError("matrix payload checksum does not match")
        if payload.get("numeric_encoding_version") != NUMERIC_ENCODING_VERSION:
            raise EstimationIntegrityError("matrix numeric encoding version is unsupported")
        order_value = payload.get("instrument_order")
        shape_value = payload.get("shape")
        triangle_value = payload.get("lower_triangle")
        if (
            not isinstance(order_value, list)
            or not order_value
            or any(not isinstance(item, int) or isinstance(item, bool) for item in order_value)
            or len(set(order_value)) != len(order_value)
        ):
            raise EstimationIntegrityError("matrix instrument order is invalid")
        size = len(order_value)
        if shape_value != [size, size] or not isinstance(triangle_value, list):
            raise EstimationIntegrityError("matrix shape does not match instrument order")
        for index, value in enumerate(triangle_value):
            _decode_canonical_float64(value, f"matrix lower_triangle[{index}]")
        try:
            lower = decode_lower_triangle(tuple(cast(list[str], triangle_value)), size)
        except (TypeError, ValueError) as exc:
            raise EstimationIntegrityError("matrix lower triangle cannot be decoded") from exc
        matrix = lower + np.tril(lower, -1).T
        return matrix, tuple(order_value)

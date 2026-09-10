"""Pure, audit-complete validation for annualized estimation bundles."""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal, Protocol, cast

import numpy as np

from .types import FactorRiskObservation

Severity = Literal["REJECT", "WARNING"]
Status = Literal["PASSED", "FAILED"]
type Array = np.ndarray[Any, Any]


class ValidationPolicy(Protocol):
    """Threshold-only policy view required by the pure validation gate."""

    minimum_t_over_n: int
    warning_t_over_n: int
    psd_relative_tolerance: float
    symmetry_tolerance: float
    correlation_tolerance: float
    condition_warning: float
    condition_reject: float
    relative_tolerance: float


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """One deterministic audit result emitted by :func:`validate_bundle`."""

    code: str
    severity: Severity
    status: Status
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationBundle:
    """Pure inputs and outputs required to audit one estimation result bundle.

    ``factor_volatility`` is the optional risk value for the currently scoped
    share class.  The caller supplies one such context per share class when a
    Factor risk cross-check is available; it does not replace ``volatility``,
    which remains the covariance-derived vector for the whole bundle.
    """

    matrix: np.ndarray  # type: ignore[type-arg]
    mu: np.ndarray  # type: ignore[type-arg]
    covariance: np.ndarray  # type: ignore[type-arg]
    correlation: np.ndarray  # type: ignore[type-arg]
    variance: np.ndarray  # type: ignore[type-arg]
    volatility: np.ndarray  # type: ignore[type-arg]
    condition_number: float
    factor_volatility: float | None
    window: str
    observation_fingerprint: str | None
    return_type: str
    ddof: int
    annualization: int


def validate_bundle(
    bundle: ValidationBundle,
    policy: ValidationPolicy,
    factor_observations: tuple[FactorRiskObservation, ...],
) -> tuple[ValidationResult, ...]:
    """Validate every current-observable rule without short-circuiting.

    The function intentionally performs no persistence or candidate lookup.
    Every returned rule has a status, including rules that pass, so callers can
    persist a complete and reproducible audit trail.
    """
    matrix = _as_float_array(bundle.matrix)
    mu = _as_float_array(bundle.mu)
    covariance = _as_float_array(bundle.covariance)
    correlation = _as_float_array(bundle.correlation)
    variance = _as_float_array(bundle.variance)
    volatility = _as_float_array(bundle.volatility)

    time_count, instrument_count = _matrix_shape(matrix)
    dimensions_valid = _dimensions_are_valid(
        matrix, mu, covariance, correlation, variance, volatility, instrument_count
    )
    factor_matches = _matching_factor_observations(bundle, factor_observations)
    finite_inputs = all(
        _array_is_finite(value)
        for value in (matrix, mu, covariance, correlation, variance, volatility)
    ) and (
        _float_is_finite(bundle.condition_number)
        and _optional_float_is_finite(bundle.factor_volatility)
        and (len(factor_matches) != 1 or _optional_float_is_finite(factor_matches[0].volatility))
    )

    results = [
        _result(
            "MIN_T_OVER_N",
            "REJECT",
            time_count >= policy.minimum_t_over_n * instrument_count and instrument_count > 0,
            f"T={time_count}, N={instrument_count}, minimum={policy.minimum_t_over_n}N",
        ),
        _result(
            "WARNING_T_OVER_N",
            "WARNING",
            not (
                instrument_count > 0
                and policy.minimum_t_over_n * instrument_count
                <= time_count
                < policy.warning_t_over_n * instrument_count
            ),
            f"T={time_count}, N={instrument_count}, warning={policy.warning_t_over_n}N",
        ),
        _result(
            "NON_FINITE",
            "REJECT",
            finite_inputs,
            "all matrix, estimate, risk, and condition-number values must be finite",
        ),
        _result(
            "DIMENSION_MISMATCH",
            "REJECT",
            dimensions_valid,
            _dimension_detail(matrix, mu, covariance, correlation, variance, volatility),
        ),
        _symmetric_result("SIGMA_NOT_SYMMETRIC", covariance, policy.symmetry_tolerance),
        _positive_variance_result(covariance),
        _psd_result(covariance, policy.psd_relative_tolerance),
        _symmetric_result("CORRELATION_NOT_SYMMETRIC", correlation, policy.symmetry_tolerance),
        _correlation_diagonal_result(correlation, policy.correlation_tolerance),
        _correlation_range_result(correlation, policy.correlation_tolerance),
        _risk_identity_result(covariance, variance, volatility),
        _condition_result(bundle.condition_number, policy),
        _factor_cross_check_result(bundle, policy, factor_matches),
    ]
    return tuple(results)


def _result(code: str, severity: Severity, passed: bool, detail: str) -> ValidationResult:
    return ValidationResult(code, severity, "PASSED" if passed else "FAILED", detail)


def _as_float_array(value: object) -> Array:
    try:
        return np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError):
        return np.asarray([np.nan], dtype=np.float64)


def _matrix_shape(matrix: Array) -> tuple[int, int]:
    if matrix.ndim != 2:
        return 0, 0
    return int(matrix.shape[0]), int(matrix.shape[1])


def _dimensions_are_valid(
    matrix: Array,
    mu: Array,
    covariance: Array,
    correlation: Array,
    variance: Array,
    volatility: Array,
    instrument_count: int,
) -> bool:
    return (
        matrix.ndim == 2
        and instrument_count > 0
        and mu.shape == (instrument_count,)
        and covariance.shape == (instrument_count, instrument_count)
        and correlation.shape == (instrument_count, instrument_count)
        and variance.shape == (instrument_count,)
        and volatility.shape == (instrument_count,)
    )


def _dimension_detail(
    matrix: Array,
    mu: Array,
    covariance: Array,
    correlation: Array,
    variance: Array,
    volatility: Array,
) -> str:
    return (
        f"matrix={matrix.shape}, mu={mu.shape}, covariance={covariance.shape}, "
        f"correlation={correlation.shape}, variance={variance.shape}, volatility={volatility.shape}"
    )


def _array_is_finite(value: Array) -> bool:
    return bool(np.isfinite(value).all())


def _float_is_finite(value: object) -> bool:
    return _finite_float(value) is not None


def _optional_float_is_finite(value: float | None) -> bool:
    return value is None or _float_is_finite(value)


def _finite_float(value: object) -> float | None:
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) else None


def _is_square_finite(matrix: Array) -> bool:
    return (
        matrix.ndim == 2
        and matrix.shape[0] > 0
        and matrix.shape[0] == matrix.shape[1]
        and _array_is_finite(matrix)
    )


def _symmetric_result(code: str, matrix: Array, tolerance: float) -> ValidationResult:
    passed = _is_square_finite(matrix) and bool(
        np.allclose(matrix, matrix.T, atol=tolerance, rtol=0.0)
    )
    return _result(code, "REJECT", passed, f"tolerance={tolerance}")


def _positive_variance_result(covariance: Array) -> ValidationResult:
    passed = _is_square_finite(covariance) and bool(np.all(np.diag(covariance) > 0.0))
    return _result(
        "NON_POSITIVE_VARIANCE",
        "REJECT",
        passed,
        "covariance diagonal must be strictly positive",
    )


def _psd_result(covariance: Array, relative_tolerance: float) -> ValidationResult:
    if not _is_square_finite(covariance):
        return _result("SIGMA_NOT_PSD", "REJECT", False, "covariance must be finite and square")
    eigenvalues = np.linalg.eigvalsh(covariance)
    minimum, maximum = float(eigenvalues[0]), float(eigenvalues[-1])
    floor = -relative_tolerance * max(maximum, 1.0e-16)
    return _result(
        "SIGMA_NOT_PSD",
        "REJECT",
        minimum >= floor,
        f"min_eigenvalue={minimum}, floor={floor}",
    )


def _correlation_diagonal_result(correlation: Array, tolerance: float) -> ValidationResult:
    passed = _is_square_finite(correlation) and bool(
        np.all(np.abs(np.diag(correlation) - 1.0) <= tolerance)
    )
    return _result(
        "CORRELATION_DIAGONAL_INVALID",
        "REJECT",
        passed,
        f"diagonal must equal one within {tolerance}",
    )


def _correlation_range_result(correlation: Array, tolerance: float) -> ValidationResult:
    passed = _is_square_finite(correlation) and bool(
        np.all(correlation >= -1.0 - tolerance) and np.all(correlation <= 1.0 + tolerance)
    )
    return _result(
        "CORRELATION_OUT_OF_RANGE", "REJECT", passed, f"range=[-1, 1], tolerance={tolerance}"
    )


def _risk_identity_result(
    covariance: Array, variance: Array, volatility: Array
) -> ValidationResult:
    passed = (
        _is_square_finite(covariance)
        and variance.shape == (covariance.shape[0],)
        and volatility.shape == (covariance.shape[0],)
        and _array_is_finite(variance)
        and _array_is_finite(volatility)
        and np.array_equal(variance, np.diag(covariance))
        and np.array_equal(volatility, np.sqrt(np.diag(covariance)))
    )
    return _result(
        "RISK_IDENTITY_MISMATCH",
        "REJECT",
        bool(passed),
        "variance must equal diag(covariance); volatility must equal sqrt(variance)",
    )


def _condition_result(condition_number: object, policy: ValidationPolicy) -> ValidationResult:
    if not _float_is_finite(condition_number):
        return _result("CONDITION_NUMBER", "REJECT", False, "condition number must be finite")
    value = _finite_float(condition_number)
    assert value is not None
    if value > policy.condition_reject:
        return _result(
            "CONDITION_NUMBER",
            "REJECT",
            False,
            f"condition_number={value}, reject={policy.condition_reject}",
        )
    if value > policy.condition_warning:
        return _result(
            "CONDITION_NUMBER",
            "WARNING",
            False,
            f"condition_number={value}, warning={policy.condition_warning}",
        )
    return _result("CONDITION_NUMBER", "REJECT", True, f"condition_number={value}")


def _factor_cross_check_result(
    bundle: ValidationBundle,
    policy: ValidationPolicy,
    matches: tuple[FactorRiskObservation, ...],
) -> ValidationResult:
    if len(matches) != 1 or bundle.factor_volatility is None:
        ids = ",".join(
            str(item.factor_value_id)
            for item in sorted(matches, key=lambda item: item.factor_value_id)
        )
        return _result(
            "NOT_COMPARABLE",
            "WARNING",
            False,
            f"matching_factor_value_ids=[{ids}], "
            f"factor_volatility_available={bundle.factor_volatility is not None}",
        )

    observation = matches[0]
    if (
        observation.volatility is None
        or not _float_is_finite(observation.volatility)
        or not _float_is_finite(bundle.factor_volatility)
    ):
        return _result(
            "FACTOR_RISK_CROSS_CHECK",
            "REJECT",
            False,
            f"factor_value_id={observation.factor_value_id}, volatility values must be finite",
        )
    candidate_volatility = float(observation.volatility)
    bundle_volatility = float(bundle.factor_volatility)
    relative_error = abs(candidate_volatility - bundle_volatility) / max(
        abs(candidate_volatility), abs(bundle_volatility), 1.0e-16
    )
    return _result(
        "FACTOR_RISK_CROSS_CHECK",
        "REJECT",
        relative_error <= policy.relative_tolerance,
        f"factor_value_id={observation.factor_value_id}, relative_error={relative_error}, "
        f"tolerance={policy.relative_tolerance}",
    )


def _matching_factor_observations(
    bundle: ValidationBundle,
    observations: tuple[FactorRiskObservation, ...],
) -> tuple[FactorRiskObservation, ...]:
    if bundle.observation_fingerprint is None:
        return ()
    return tuple(
        observation
        for observation in observations
        if observation.status == "AVAILABLE"
        and observation.window == bundle.window
        and observation.observation_fingerprint is not None
        and observation.observation_fingerprint == bundle.observation_fingerprint
        and observation.return_type == bundle.return_type
        and observation.ddof == bundle.ddof
        and observation.annualization == bundle.annualization
    )

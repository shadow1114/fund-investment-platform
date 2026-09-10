from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from fip.services.portfolio_service.estimation.policy import EstimationValidationPolicy
from fip.strategy_library.estimation.types import FactorRiskObservation
from fip.strategy_library.estimation.validation import (
    ValidationBundle,
    ValidationResult,
    validate_bundle,
)

POLICY = EstimationValidationPolicy(
    version="test-v1",
    minimum_t_over_n=3,
    warning_t_over_n=5,
    psd_relative_tolerance=1.0e-8,
    symmetry_tolerance=1.0e-12,
    correlation_tolerance=1.0e-12,
    condition_warning=1.0e4,
    condition_reject=1.0e6,
    relative_tolerance=1.0e-6,
    provisional_parameters=(),
)


@pytest.fixture
def valid_bundle() -> ValidationBundle:
    covariance = np.array([[1.0, 0.2, 0.1], [0.2, 4.0, -0.4], [0.1, -0.4, 9.0]], dtype=np.float64)
    variance = np.diag(covariance).copy()
    volatility = np.sqrt(variance)
    return ValidationBundle(
        matrix=np.arange(45, dtype=np.float64).reshape(15, 3),
        mu=np.array([0.04, 0.05, 0.06]),
        covariance=covariance,
        correlation=covariance / np.outer(volatility, volatility),
        variance=variance,
        volatility=volatility,
        condition_number=12.0,
        factor_volatility=1.0,
        window="756D",
        observation_fingerprint="window-fingerprint",
        return_type="SIMPLE",
        ddof=1,
        annualization=252,
    )


def matching_observation(
    volatility: float = 1.0, factor_value_id: int = 7
) -> FactorRiskObservation:
    return FactorRiskObservation(
        factor_run_id=3,
        factor_value_id=factor_value_id,
        factor_version_id=5,
        volatility=volatility,
        window="756D",
        observation_fingerprint="window-fingerprint",
        return_type="SIMPLE",
        ddof=1,
        annualization=252,
        status="AVAILABLE",
    )


def result_for(
    bundle: ValidationBundle, code: str, observations: tuple[FactorRiskObservation, ...] = ()
) -> ValidationResult:
    return next(
        result for result in validate_bundle(bundle, POLICY, observations) if result.code == code
    )


def failed_codes(
    bundle: ValidationBundle, observations: tuple[FactorRiskObservation, ...] = ()
) -> set[str]:
    return {
        result.code
        for result in validate_bundle(bundle, POLICY, observations)
        if result.status == "FAILED"
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("too_few_rows", "MIN_T_OVER_N"),
        ("nan", "NON_FINITE"),
        ("asymmetric", "SIGMA_NOT_SYMMETRIC"),
        ("zero_variance", "NON_POSITIVE_VARIANCE"),
        ("negative_eigenvalue", "SIGMA_NOT_PSD"),
        ("bad_correlation", "CORRELATION_OUT_OF_RANGE"),
    ],
)
def test_gate_rejects_each_blocking_bundle_violation(
    valid_bundle: ValidationBundle, mutation: str, code: str
):
    covariance = valid_bundle.covariance.copy()
    correlation = valid_bundle.correlation.copy()
    kwargs: dict[str, object] = {}
    if mutation == "too_few_rows":
        kwargs["matrix"] = valid_bundle.matrix[:8]
    elif mutation == "nan":
        kwargs["mu"] = np.array([np.nan, 0.05, 0.06])
    elif mutation == "asymmetric":
        covariance[0, 1] = 0.3
        kwargs["covariance"] = covariance
    elif mutation == "zero_variance":
        covariance[1, 1] = 0.0
        kwargs["covariance"] = covariance
    elif mutation == "negative_eigenvalue":
        kwargs["covariance"] = np.diag([1.0, 1.0, -0.01])
    elif mutation == "bad_correlation":
        correlation[0, 1] = correlation[1, 0] = 1.1
        kwargs["correlation"] = correlation

    assert code in failed_codes(replace(valid_bundle, **kwargs))


def test_gate_returns_passing_results_for_every_audited_rule(valid_bundle: ValidationBundle):
    results = validate_bundle(valid_bundle, POLICY, (matching_observation(),))

    assert all(result.status == "PASSED" for result in results)
    assert {result.code for result in results} >= {
        "MIN_T_OVER_N",
        "WARNING_T_OVER_N",
        "NON_FINITE",
        "DIMENSION_MISMATCH",
        "SIGMA_NOT_SYMMETRIC",
        "NON_POSITIVE_VARIANCE",
        "SIGMA_NOT_PSD",
        "CORRELATION_OUT_OF_RANGE",
        "RISK_IDENTITY_MISMATCH",
        "CONDITION_NUMBER",
        "FACTOR_RISK_CROSS_CHECK",
    }


def test_validation_bundle_is_an_immutable_public_value_object(valid_bundle: ValidationBundle):
    with pytest.raises(FrozenInstanceError):
        valid_bundle.window = "504D"  # type: ignore[misc]


def test_gate_warns_when_sample_size_is_between_policy_thresholds(valid_bundle: ValidationBundle):
    bundle = replace(valid_bundle, matrix=valid_bundle.matrix[:12])

    warning = result_for(bundle, "WARNING_T_OVER_N")

    assert warning.severity == "WARNING"
    assert warning.status == "FAILED"
    assert result_for(bundle, "MIN_T_OVER_N").status == "PASSED"


def test_gate_accepts_exact_minimum_t_over_n_boundary(valid_bundle: ValidationBundle):
    bundle = replace(valid_bundle, matrix=valid_bundle.matrix[:9])

    assert result_for(bundle, "MIN_T_OVER_N").status == "PASSED"
    assert result_for(bundle, "WARNING_T_OVER_N").status == "FAILED"


@pytest.mark.parametrize(
    ("condition", "severity", "status"),
    [
        (1.0e4, "REJECT", "PASSED"),
        (1.0e4 + 1.0, "WARNING", "FAILED"),
        (1.0e6, "WARNING", "FAILED"),
        (1.0e6 + 1.0, "REJECT", "FAILED"),
        (np.inf, "REJECT", "FAILED"),
    ],
)
def test_gate_applies_condition_number_thresholds(
    valid_bundle: ValidationBundle, condition: float, severity: str, status: str
):
    result = result_for(replace(valid_bundle, condition_number=condition), "CONDITION_NUMBER")

    assert (result.severity, result.status) == (severity, status)


def test_gate_rejects_bad_dimensions_symmetric_correlation_and_risk_identity(
    valid_bundle: ValidationBundle,
):
    correlation = valid_bundle.correlation.copy()
    correlation[0, 1] = 0.15
    covariance = valid_bundle.covariance.copy()
    variance = valid_bundle.variance.copy()
    variance[2] = 10.0
    bundle = replace(
        valid_bundle,
        mu=np.array([0.04, 0.05]),
        correlation=correlation,
        covariance=covariance,
        variance=variance,
    )

    assert {
        "DIMENSION_MISMATCH",
        "CORRELATION_NOT_SYMMETRIC",
        "RISK_IDENTITY_MISMATCH",
    } <= failed_codes(bundle)


def test_gate_audits_zero_sized_square_matrices_without_aborting(valid_bundle: ValidationBundle):
    empty = np.empty((0, 0))
    bundle = replace(
        valid_bundle,
        matrix=empty,
        mu=np.empty(0),
        covariance=empty,
        correlation=empty,
        variance=np.empty(0),
        volatility=np.empty(0),
    )

    results = validate_bundle(bundle, POLICY, ())

    assert result_for(bundle, "DIMENSION_MISMATCH").status == "FAILED"
    assert {result.code for result in results} >= {"SIGMA_NOT_PSD", "NOT_COMPARABLE"}


def test_gate_allows_relative_psd_roundoff_but_rejects_material_negative_eigenvalue(
    valid_bundle: ValidationBundle,
):
    tolerated = replace(valid_bundle, covariance=np.diag([1.0, 1.0, -0.5e-8]))
    rejected = replace(valid_bundle, covariance=np.diag([1.0, 1.0, -1.1e-8]))

    assert result_for(tolerated, "SIGMA_NOT_PSD").status == "PASSED"
    assert result_for(rejected, "SIGMA_NOT_PSD").status == "FAILED"


def test_gate_rejects_correlation_diagonal_outside_policy_tolerance(
    valid_bundle: ValidationBundle,
):
    correlation = valid_bundle.correlation.copy()
    correlation[1, 1] = 1.0 - 2.0e-12

    assert "CORRELATION_DIAGONAL_INVALID" in failed_codes(
        replace(valid_bundle, correlation=correlation)
    )


def test_factor_cross_check_rejects_one_matching_candidate_outside_relative_tolerance(
    valid_bundle: ValidationBundle,
):
    result = result_for(
        valid_bundle,
        "FACTOR_RISK_CROSS_CHECK",
        (matching_observation(volatility=1.00001),),
    )

    assert result.severity == "REJECT"
    assert result.status == "FAILED"
    assert "factor_value_id=7" in result.detail


@pytest.mark.parametrize(
    "observations",
    [(), (matching_observation(), matching_observation(factor_value_id=8))],
)
def test_factor_cross_check_warns_when_zero_or_multiple_candidates_match(
    valid_bundle: ValidationBundle, observations: tuple[FactorRiskObservation, ...]
):
    result = result_for(valid_bundle, "NOT_COMPARABLE", observations)

    assert (result.severity, result.status) == ("WARNING", "FAILED")


def test_factor_cross_check_ignores_unavailable_or_lineage_mismatched_candidates(
    valid_bundle: ValidationBundle,
):
    unavailable = replace(matching_observation(), status="UNAVAILABLE")
    different_window = replace(matching_observation(), window="504D")

    result = result_for(valid_bundle, "NOT_COMPARABLE", (unavailable, different_window))

    assert result.status == "FAILED"


@pytest.mark.parametrize(
    "mutation",
    [
        {"observation_fingerprint": "different-fingerprint"},
        {"return_type": "LOG"},
        {"ddof": 0},
        {"annualization": 365},
    ],
)
def test_factor_cross_check_requires_each_lineage_field(
    valid_bundle: ValidationBundle, mutation: dict[str, object]
):
    observation = replace(matching_observation(), **mutation)

    result = result_for(valid_bundle, "NOT_COMPARABLE", (observation,))

    assert (result.severity, result.status) == ("WARNING", "FAILED")


@pytest.mark.parametrize(
    ("bundle_fingerprint", "candidate_fingerprint"),
    [(None, "window-fingerprint"), ("window-fingerprint", None)],
)
def test_factor_cross_check_requires_non_null_observation_fingerprints(
    valid_bundle: ValidationBundle,
    bundle_fingerprint: str | None,
    candidate_fingerprint: str | None,
):
    bundle = replace(valid_bundle, observation_fingerprint=bundle_fingerprint)
    observation = replace(matching_observation(), observation_fingerprint=candidate_fingerprint)

    result = result_for(bundle, "NOT_COMPARABLE", (observation,))

    assert (result.severity, result.status) == ("WARNING", "FAILED")


@pytest.mark.parametrize(
    "unrelated",
    [
        replace(matching_observation(factor_value_id=8), volatility=np.nan, window="504D"),
        replace(matching_observation(factor_value_id=8), volatility=np.nan, status="UNAVAILABLE"),
    ],
)
def test_nonfinite_unselected_factor_candidate_does_not_reject_valid_cross_check(
    valid_bundle: ValidationBundle, unrelated: FactorRiskObservation
):
    results = validate_bundle(valid_bundle, POLICY, (matching_observation(), unrelated))

    assert (
        result_for(valid_bundle, "NON_FINITE", (matching_observation(), unrelated)).status
        == "PASSED"
    )
    assert (
        next(result for result in results if result.code == "FACTOR_RISK_CROSS_CHECK").status
        == "PASSED"
    )


@pytest.mark.parametrize(
    "bundle,observations",
    [
        (None, (matching_observation(volatility=np.nan),)),
        (np.nan, (matching_observation(),)),
    ],
)
def test_gate_rejects_nonfinite_factor_cross_check_values(
    valid_bundle: ValidationBundle,
    bundle: float | None,
    observations: tuple[FactorRiskObservation, ...],
):
    candidate = valid_bundle if bundle is None else replace(valid_bundle, factor_volatility=bundle)

    assert "NON_FINITE" in failed_codes(candidate, observations)

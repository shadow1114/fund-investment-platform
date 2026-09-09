import pytest

from fip.strategy_library.validation import (
    EffectivenessThresholds,
    validate_effectiveness,
    validate_effectiveness_series,
)


def test_validation_is_pending_without_out_of_sample_observations():
    result = validate_effectiveness((), minimum_observations=3)
    assert result.verdict == "VALIDATION_PENDING"


def test_validation_uses_time_ordered_rank_ic():
    result = validate_effectiveness(((1.0, 1.0), (2.0, 2.0), (3.0, 3.0)), minimum_observations=3)
    assert result.verdict == "VALID"
    assert result.ic == 1.0


@pytest.fixture()
def thresholds():
    return EffectivenessThresholds(
        ic_mean_min=0.02,
        icir_abs_min=0.3,
        minimum_cross_sections=3,
        ic_std_ddof=1,
        redundancy_threshold=0.8,
    )


def test_effectiveness_series_requires_enough_cross_sections(thresholds):
    result = validate_effectiveness_series(
        (0.1, 0.2),
        layer_returns=(0.01, 0.02, 0.03),
        expected_direction="POSITIVE",
        thresholds=thresholds,
    )

    assert result.verdict == "VALIDATION_PENDING"
    assert result.reason_code == "INSUFFICIENT_OOS_CROSS_SECTIONS"


def test_effectiveness_series_calculates_icir_and_monotonicity(thresholds):
    result = validate_effectiveness_series(
        (0.1, 0.2, 0.3),
        layer_returns=(0.01, 0.02, 0.03, 0.04, 0.05),
        expected_direction="POSITIVE",
        thresholds=thresholds,
    )

    assert result.verdict == "VALID"
    assert result.ic == pytest.approx(0.2)
    assert result.icir == pytest.approx(2.0)
    assert result.monotonic is True


@pytest.mark.parametrize(
    ("ic_series", "layers", "redundant_with", "reason"),
    [
        ((0.03, 0.03, 0.03), (0.01, 0.02, 0.03), None, "ZERO_IC_DISPERSION"),
        ((0.01, 0.02, 0.03), (0.01, 0.03, 0.02), None, "NON_MONOTONIC_LAYERS"),
        ((0.1, 0.2, 0.3), (0.01, 0.02, 0.03), ("F-RAP-001", 0.9), "REDUNDANT_FACTOR"),
    ],
)
def test_effectiveness_series_fails_closed(
    thresholds, ic_series, layers, redundant_with, reason
):
    result = validate_effectiveness_series(
        ic_series,
        layer_returns=layers,
        expected_direction="POSITIVE",
        thresholds=thresholds,
        redundant_with=redundant_with,
    )

    assert result.verdict == "INVALID"
    assert result.reason_code == reason

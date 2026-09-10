import numpy as np
import pytest

from fip.strategy_library.estimation.covariance import estimate_covariance


def test_constant_correlation_matches_frozen_reference():
    matrix = np.array(
        [
            [0.01, 0.02, 0.00],
            [0.02, 0.01, 0.01],
            [0.00, 0.03, 0.02],
            [0.01, 0.02, 0.01],
            [0.03, 0.00, 0.02],
            [0.02, 0.01, 0.03],
        ]
    )

    result = estimate_covariance(matrix, annualization=252)

    expected = np.array(
        [
            [0.02772, -0.0226754594594595, 0.0029740540540541],
            [-0.0226754594594595, 0.02772, -0.0080185945945946],
            [0.0029740540540541, -0.0080185945945946, 0.02772],
        ]
    )
    assert result.shrinkage_intensity == pytest.approx(0.2729729729729731)
    assert result.covariance == pytest.approx(expected, abs=1e-8)
    assert np.diag(result.covariance) == pytest.approx(result.variance)


def test_zero_variance_is_rejected():
    constant_column = np.array([[0.01, 0.02], [0.01, 0.03], [0.01, 0.04]])

    with pytest.raises(ValueError, match="positive sample variance"):
        estimate_covariance(constant_column, annualization=252)


def test_target_uses_constant_correlation_with_unequal_variances():
    matrix = np.array(
        [[1.0, 10.0, 0.0], [2.0, 12.0, 4.0], [4.0, 9.0, 3.0], [3.0, 14.0, 1.0], [6.0, 11.0, 8.0]]
    )

    result = estimate_covariance(matrix)

    expected_target = np.array(
        [
            [3.7, 0.805829409254992, 1.3047524417936918],
            [0.805829409254992, 3.7, 1.3047524417936915],
            [1.3047524417936918, 1.3047524417936915, 9.7],
        ]
    )
    assert result.target_covariance_daily == pytest.approx(expected_target)
    assert np.diag(result.target_covariance_daily) == pytest.approx(
        np.diag(result.sample_covariance_daily)
    )


@pytest.mark.parametrize(
    ("matrix", "message"),
    [
        (np.array([[1.0, np.nan], [2.0, 3.0]]), "finite"),
        (np.array([[1.0, np.inf], [2.0, 3.0]]), "finite"),
        (np.array([[1.0, 2.0]]), "at least two observations"),
        (np.array([[1.0], [2.0]]), "at least two instruments"),
    ],
)
def test_rejects_nonfinite_or_undersized_matrix(matrix, message):
    with pytest.raises(ValueError, match=message):
        estimate_covariance(matrix)


def test_gamma_zero_uses_full_shrinkage():
    matrix = np.array([[-2.0, 2.0], [-1.0, 1.0], [1.0, -1.0], [2.0, -2.0]])

    result = estimate_covariance(matrix)

    assert result.shrinkage_intensity == 1.0
    assert result.covariance == pytest.approx(result.target_covariance_daily * 252)


@pytest.mark.parametrize(
    ("matrix", "expected_shrinkage"),
    [
        (
            np.array(
                [
                    [-0.4873283943594556, -0.7380834593130157, 0.4299655236448123],
                    [-1.332664383714051, -0.3250717537309279, 0.2818759140322155],
                    [0.3021319779596807, 0.7572511457075964, 0.1965531123458838],
                    [1.328859668657728, 0.5742472264539621, 0.28733264529273833],
                ]
            ),
            0.0,
        ),
        (
            np.array(
                [
                    [-0.8585843288930456, 1.5630605759787024, -1.1881238871988966],
                    [-0.16310181600629972, -2.098991754346891, 0.5230383423923788],
                    [-0.7097654504509944, 0.35712906188313437, 1.579150173372161],
                ]
            ),
            1.0,
        ),
    ],
)
def test_shrinkage_intensity_clamps_to_endpoint(matrix, expected_shrinkage):
    # Independent moment evaluation gives unclamped values -0.04002853178271989
    # and 2.671873855394062 respectively.
    result = estimate_covariance(matrix)

    assert result.shrinkage_intensity == expected_shrinkage


def test_final_derived_outputs_come_from_annual_covariance():
    matrix = np.array(
        [[1.0, 10.0, 0.0], [2.0, 12.0, 4.0], [4.0, 9.0, 3.0], [3.0, 14.0, 1.0], [6.0, 11.0, 8.0]]
    )

    result = estimate_covariance(matrix, annualization=12)

    expected_variance = np.diag(result.covariance)
    expected_volatility = np.sqrt(expected_variance)
    expected_correlation = result.covariance / np.outer(expected_volatility, expected_volatility)
    assert result.variance == pytest.approx(expected_variance)
    assert result.volatility == pytest.approx(expected_volatility)
    assert result.correlation == pytest.approx(expected_correlation)

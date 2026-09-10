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

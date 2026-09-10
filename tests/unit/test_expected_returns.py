import numpy as np
import pytest

from fip.strategy_library.estimation.returns import estimate_expected_returns


def test_james_stein_matches_positive_part_formula():
    matrix = np.array(
        [
            [0.01, 0.02, 0.00, 0.03],
            [0.02, 0.01, 0.01, 0.04],
            [0.00, 0.03, 0.02, 0.02],
            [0.01, 0.02, 0.01, 0.03],
            [0.03, 0.00, 0.02, 0.05],
        ]
    )

    result = estimate_expected_returns(matrix, annualization=252)

    assert result.sample_mean_daily == pytest.approx([0.014, 0.016, 0.012, 0.034])
    assert result.target_daily == pytest.approx(0.019)
    assert result.shrinkage_intensity == pytest.approx(0.07467532467532466)
    assert result.shrunk_mu_annualized == pytest.approx(
        [3.62209091, 4.08845455, 3.15572727, 8.28572727]
    )
    assert result.annualized_mu == pytest.approx(
        [3.62209091, 4.08845455, 3.15572727, 8.28572727]
    )
    assert not result.clipped.any()


def test_james_stein_uses_stable_full_shrinkage_for_equal_means():
    matrix = np.array(
        [
            [0.01, 0.01, 0.01, 0.01],
            [0.03, 0.03, 0.03, 0.03],
        ]
    )

    result = estimate_expected_returns(matrix)

    assert result.shrinkage_intensity == 1.0
    assert result.target_daily == pytest.approx(0.02)
    assert result.shrunk_mu_annualized == pytest.approx([5.04, 5.04, 5.04, 5.04])
    assert result.annualized_mu == pytest.approx([5.04, 5.04, 5.04, 5.04])
    assert not result.clipped.any()


def test_james_stein_rejects_zero_variance_when_asset_means_differ():
    matrix = np.array(
        [
            [0.01, 0.02, 0.03, 0.04],
            [0.01, 0.02, 0.03, 0.04],
        ]
    )

    with pytest.raises(ValueError, match="positive mean variance"):
        estimate_expected_returns(matrix)


def test_james_stein_clips_an_outlying_annualized_expected_return():
    matrix = np.array(
        [
            [-0.000001, -0.000001, -0.000001, -0.000001, -0.000001, 0.099999],
            [0.000001, 0.000001, 0.000001, 0.000001, 0.000001, 0.100001],
        ]
    )

    result = estimate_expected_returns(matrix)

    assert result.shrunk_mu_annualized[-1] == pytest.approx(25.2)
    assert result.clipped.tolist() == [False, False, False, False, False, True]
    assert result.annualized_mu == pytest.approx(
        [0.000000001512, 0.000000001512, 0.000000001512, 0.000000001512,
         0.000000001512, 24.7757138]
    )
    assert result.annualized_mu[-1] < result.shrunk_mu_annualized[-1]


@pytest.mark.parametrize(
    "matrix",
    [
        np.ones((2, 3)),
        np.ones((1, 4)),
        np.array([[0.01, 0.02, 0.03, np.inf], [0.02, 0.03, 0.04, 0.05]]),
    ],
)
def test_james_stein_rejects_invalid_matrix_shape_and_values(matrix):
    with pytest.raises(ValueError):
        estimate_expected_returns(matrix)

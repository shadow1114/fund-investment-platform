"""Positive-part James-Stein expected-return estimation."""

from typing import Any

import numpy as np

from .types import ReturnEstimateResult


def estimate_expected_returns(
    matrix: np.ndarray[Any, Any], annualization: int = 252
) -> ReturnEstimateResult:
    """Estimate annual expected returns by grand-mean James-Stein shrinkage."""
    observations = np.asarray(matrix, dtype=np.float64)
    if observations.ndim != 2:
        raise ValueError("matrix must have shape (T, N)")
    time_count, instrument_count = observations.shape
    if instrument_count < 4:
        raise ValueError("matrix must contain at least four instruments")
    if time_count < 2:
        raise ValueError("matrix must contain at least two observations")
    if not np.isfinite(observations).all():
        raise ValueError("matrix must contain only finite values")
    if not isinstance(annualization, int) or isinstance(annualization, bool) or annualization <= 0:
        raise ValueError("annualization must be a positive integer")

    sample_mean_daily = observations.mean(axis=0, dtype=np.float64)
    sample_covariance_daily = np.cov(observations, rowvar=False, ddof=1)
    target_daily = float(sample_mean_daily.mean(dtype=np.float64))
    mean_variance = float(np.trace(sample_covariance_daily) / (instrument_count * time_count))
    dispersion = float(np.sum((sample_mean_daily - target_daily) ** 2, dtype=np.float64))
    if not np.isfinite(sample_covariance_daily).all():
        raise ValueError("sample covariance must be finite")
    if not np.isfinite(dispersion) or dispersion < 0:
        raise ValueError("sample mean dispersion must be finite and non-negative")

    if dispersion == 0.0:
        shrinkage_intensity = 1.0
    else:
        if not np.isfinite(mean_variance) or mean_variance <= 0.0:
            raise ValueError("sample covariance must produce positive mean variance")
        shrinkage_intensity = float(
            np.clip(
                (instrument_count - 3) * mean_variance / dispersion,
                0.0,
                1.0,
            )
        )
        if not np.isfinite(shrinkage_intensity):
            raise ValueError("James-Stein shrinkage intensity must be finite")

    shrunk_mu_daily = (
        (1.0 - shrinkage_intensity) * sample_mean_daily + shrinkage_intensity * target_daily
    )
    shrunk_mu_annualized = shrunk_mu_daily * annualization
    cross_section_mean = float(shrunk_mu_annualized.mean(dtype=np.float64))
    cross_section_std = float(shrunk_mu_annualized.std(ddof=1, dtype=np.float64))
    if not np.isfinite(cross_section_mean) or not np.isfinite(cross_section_std):
        raise ValueError("annualized expected returns must have finite dispersion")
    lower_bound = cross_section_mean - 2.0 * cross_section_std
    upper_bound = cross_section_mean + 2.0 * cross_section_std
    clipped = (shrunk_mu_annualized < lower_bound) | (shrunk_mu_annualized > upper_bound)
    annualized_mu = np.clip(shrunk_mu_annualized, lower_bound, upper_bound)
    return ReturnEstimateResult(
        sample_mean_daily=sample_mean_daily,
        target_daily=target_daily,
        shrinkage_intensity=shrinkage_intensity,
        shrunk_mu_annualized=shrunk_mu_annualized,
        annualized_mu=annualized_mu,
        clipped=clipped,
    )

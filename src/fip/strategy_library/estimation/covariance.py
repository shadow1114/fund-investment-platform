"""Constant-correlation Ledoit-Wolf covariance shrinkage."""

from typing import Any

import numpy as np

from .types import CovarianceEstimateResult


def estimate_covariance(
    matrix: np.ndarray[Any, Any], annualization: int = 252
) -> CovarianceEstimateResult:
    """Estimate an annualized covariance matrix with a constant-correlation target.

    The daily sample covariance uses the unbiased ``ddof=1`` convention.  The
    Ledoit-Wolf moment estimators consequently use the effective sample size
    ``T - 1`` after demeaning.
    """
    observations = np.asarray(matrix, dtype=np.float64)
    if observations.ndim != 2:
        raise ValueError("matrix must have shape (T, N)")
    time_count, instrument_count = observations.shape
    if time_count < 2:
        raise ValueError("matrix must contain at least two observations")
    if instrument_count < 2:
        raise ValueError("matrix must contain at least two instruments")
    if not np.isfinite(observations).all():
        raise ValueError("matrix must contain only finite values")
    if not isinstance(annualization, int) or isinstance(annualization, bool) or annualization <= 0:
        raise ValueError("annualization must be a positive integer")

    centered = observations - observations.mean(axis=0, keepdims=True, dtype=np.float64)
    effective_count = time_count - 1
    sample = centered.T @ centered / effective_count
    sample_variance = np.diag(sample)
    if not np.isfinite(sample).all() or not np.all(sample_variance > 0.0):
        raise ValueError("sample covariance must have positive sample variance")

    standard_deviation = np.sqrt(sample_variance)
    correlation_scale = np.outer(standard_deviation, standard_deviation)
    average_correlation = float(
        (np.sum(sample / correlation_scale, dtype=np.float64) - instrument_count)
        / (instrument_count * (instrument_count - 1))
    )
    if not np.isfinite(average_correlation):
        raise ValueError("sample average correlation must be finite")

    target = average_correlation * correlation_scale
    np.fill_diagonal(target, sample_variance)

    squared = centered**2
    pi_matrix = squared.T @ squared / effective_count - sample**2
    pi_hat = float(np.sum(pi_matrix, dtype=np.float64))

    cubic_cross_products = (centered**3).T @ centered / effective_count
    theta_matrix = cubic_cross_products - sample_variance[:, np.newaxis] * sample
    np.fill_diagonal(theta_matrix, 0.0)
    rho_hat = float(
        np.trace(pi_matrix)
        + average_correlation
        * np.sum(np.outer(1.0 / standard_deviation, standard_deviation) * theta_matrix)
    )
    gamma_hat = float(np.sum((sample - target) ** 2, dtype=np.float64))
    if not np.isfinite(pi_hat) or not np.isfinite(rho_hat) or not np.isfinite(gamma_hat):
        raise ValueError("Ledoit-Wolf moments must be finite")

    if gamma_hat == 0.0:
        shrinkage_intensity = 1.0
    else:
        shrinkage_intensity = float(
            np.clip((pi_hat - rho_hat) / (gamma_hat * effective_count), 0.0, 1.0)
        )

    final_daily = shrinkage_intensity * target + (1.0 - shrinkage_intensity) * sample
    covariance = final_daily * annualization
    variance = np.diag(covariance).copy()
    volatility = np.sqrt(variance)
    final_standard_deviation = np.sqrt(variance)
    correlation = covariance / np.outer(final_standard_deviation, final_standard_deviation)

    sample_eigenvalues = np.linalg.eigvalsh(sample)
    final_eigenvalues = np.linalg.eigvalsh(covariance)
    return CovarianceEstimateResult(
        sample_covariance_daily=sample,
        target_covariance_daily=target,
        covariance=covariance,
        correlation=correlation,
        variance=variance,
        volatility=volatility,
        shrinkage_intensity=shrinkage_intensity,
        sample_min_eigenvalue=float(sample_eigenvalues[0]),
        sample_max_eigenvalue=float(sample_eigenvalues[-1]),
        sample_condition_number=float(np.linalg.cond(sample)),
        final_min_eigenvalue=float(final_eigenvalues[0]),
        final_max_eigenvalue=float(final_eigenvalues[-1]),
        final_condition_number=float(np.linalg.cond(covariance)),
    )

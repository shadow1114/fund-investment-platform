"""Immutable data-transfer objects shared by estimation components."""

import datetime as dt
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class DatedReturn:
    effective_at: dt.date
    value: float


@dataclass(frozen=True, slots=True)
class AlignedReturns:
    instrument_order: tuple[int, ...]
    observation_dates: tuple[dt.date, ...]
    matrix: np.ndarray  # type: ignore[type-arg]
    excluded_instruments: tuple[tuple[int, str], ...]
    dropped_dates: tuple[dt.date, ...]


@dataclass(frozen=True, slots=True)
class ReturnEstimateResult:
    sample_mean_daily: np.ndarray  # type: ignore[type-arg]
    target_daily: float
    shrinkage_intensity: float
    shrunk_mu_annualized: np.ndarray  # type: ignore[type-arg]
    annualized_mu: np.ndarray  # type: ignore[type-arg]
    clipped: np.ndarray  # type: ignore[type-arg]


@dataclass(frozen=True, slots=True)
class CovarianceEstimateResult:
    sample_covariance_daily: np.ndarray  # type: ignore[type-arg]
    target_covariance_daily: np.ndarray  # type: ignore[type-arg]
    covariance: np.ndarray  # type: ignore[type-arg]
    correlation: np.ndarray  # type: ignore[type-arg]
    variance: np.ndarray  # type: ignore[type-arg]
    volatility: np.ndarray  # type: ignore[type-arg]
    shrinkage_intensity: float
    sample_min_eigenvalue: float
    sample_max_eigenvalue: float
    sample_condition_number: float
    final_min_eigenvalue: float
    final_max_eigenvalue: float
    final_condition_number: float


@dataclass(frozen=True, slots=True)
class FactorRiskObservation:
    factor_run_id: int
    factor_value_id: int
    factor_version_id: int
    volatility: float | None
    window: str
    observation_fingerprint: str | None
    return_type: str | None
    ddof: int | None
    annualization: int | None
    status: str

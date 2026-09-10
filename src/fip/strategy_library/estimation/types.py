"""Immutable data-transfer objects shared by estimation components."""

import datetime as dt
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class DatedReturn:
    effective_at: dt.date
    value: float


@dataclass(frozen=True, slots=True)
class AlignedReturns:
    instrument_order: tuple[int, ...]
    observation_dates: tuple[dt.date, ...]
    matrix: np.ndarray[Any, Any]
    excluded_instruments: tuple[tuple[int, str], ...]
    dropped_dates: tuple[dt.date, ...]


@dataclass(frozen=True, slots=True)
class ReturnEstimateResult:
    sample_mean_daily: np.ndarray[Any, Any]
    target_daily: float
    shrinkage_intensity: float
    shrunk_mu_annualized: np.ndarray[Any, Any]
    annualized_mu: np.ndarray[Any, Any]
    clipped: np.ndarray[Any, Any]


@dataclass(frozen=True, slots=True)
class CovarianceEstimateResult:
    sample_covariance_daily: np.ndarray[Any, Any]
    target_covariance_daily: np.ndarray[Any, Any]
    covariance: np.ndarray[Any, Any]
    correlation: np.ndarray[Any, Any]
    variance: np.ndarray[Any, Any]
    volatility: np.ndarray[Any, Any]
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

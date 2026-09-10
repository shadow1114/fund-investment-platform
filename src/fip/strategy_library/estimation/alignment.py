"""Deterministic complete-case alignment for daily return observations."""

import datetime as dt
from collections.abc import Mapping, Sequence
from math import isfinite

import numpy as np

from .types import AlignedReturns, DatedReturn

_INSUFFICIENT_VALID_RETURNS = "INSUFFICIENT_VALID_RETURNS"


def complete_case_alignment(
    series: Mapping[int, Sequence[DatedReturn]], instrument_order: tuple[int, ...]
) -> AlignedReturns:
    """Align eligible series once on their full common date intersection.

    Instruments are considered exactly once in the supplied frozen order.  A
    series with fewer than two observations is excluded, while all other
    missing dates are handled only by the single complete-case intersection.
    """
    if len(set(instrument_order)) != len(instrument_order):
        raise ValueError("instrument_order must not contain duplicates")

    included: list[tuple[int, dict[dt.date, float]]] = []
    excluded: list[tuple[int, str]] = []
    for instrument_id in instrument_order:
        observations = series.get(instrument_id, ())
        by_date: dict[dt.date, float] = {}
        for observation in observations:
            value = float(observation.value)
            if not isfinite(value):
                raise ValueError("return observations must be finite")
            if observation.effective_at in by_date:
                raise ValueError("return observations must not contain duplicate dates")
            by_date[observation.effective_at] = value
        if len(by_date) < 2:
            excluded.append((instrument_id, _INSUFFICIENT_VALID_RETURNS))
        else:
            included.append((instrument_id, by_date))

    if not included:
        raise ValueError("at least one instrument must have two valid returns")

    date_sets = [set(values) for _, values in included]
    common_dates = set.intersection(*date_sets)
    if not common_dates:
        raise ValueError("eligible return series have no common observation dates")
    observation_dates = tuple(sorted(common_dates))
    all_dates = set.union(*date_sets)
    dropped_dates = tuple(sorted(all_dates - common_dates))
    matrix = np.asarray(
        [
            [observations[observation_date] for _, observations in included]
            for observation_date in observation_dates
        ],
        dtype=np.float64,
    )
    return AlignedReturns(
        instrument_order=tuple(instrument_id for instrument_id, _ in included),
        observation_dates=observation_dates,
        matrix=matrix,
        excluded_instruments=tuple(excluded),
        dropped_dates=dropped_dates,
    )

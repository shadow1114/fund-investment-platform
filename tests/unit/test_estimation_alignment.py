import datetime as dt

import numpy as np
import pytest

from fip.strategy_library.estimation.alignment import complete_case_alignment
from fip.strategy_library.estimation.types import DatedReturn


def test_complete_case_uses_intersection_without_fill():
    series = {
        10: (
            DatedReturn(dt.date(2026, 1, 1), 0.01),
            DatedReturn(dt.date(2026, 1, 2), 0.02),
            DatedReturn(dt.date(2026, 1, 3), 0.03),
        ),
        20: (
            DatedReturn(dt.date(2026, 1, 1), 0.04),
            DatedReturn(dt.date(2026, 1, 3), 0.06),
        ),
    }

    result = complete_case_alignment(series, (10, 20))

    assert result.instrument_order == (10, 20)
    assert result.observation_dates == (dt.date(2026, 1, 1), dt.date(2026, 1, 3))
    assert result.matrix.shape == (2, 2)
    assert np.array_equal(result.matrix, np.array([[0.01, 0.04], [0.03, 0.06]]))
    assert not np.isnan(result.matrix).any()
    assert result.excluded_instruments == ()
    assert result.dropped_dates == (dt.date(2026, 1, 2),)


def test_complete_case_excludes_only_series_with_fewer_than_two_valid_returns():
    series = {
        10: (
            DatedReturn(dt.date(2026, 1, 1), 0.01),
            DatedReturn(dt.date(2026, 1, 2), 0.02),
        ),
        20: (DatedReturn(dt.date(2026, 1, 1), 0.03),),
        30: (
            DatedReturn(dt.date(2026, 1, 1), 0.04),
            DatedReturn(dt.date(2026, 1, 2), 0.05),
        ),
    }

    result = complete_case_alignment(series, (10, 20, 30))

    assert result.instrument_order == (10, 30)
    assert result.excluded_instruments == ((20, "INSUFFICIENT_VALID_RETURNS"),)
    assert np.array_equal(result.matrix, np.array([[0.01, 0.04], [0.02, 0.05]]))


def test_complete_case_rejects_non_finite_and_duplicate_observations():
    non_finite = {
        10: (
            DatedReturn(dt.date(2026, 1, 1), 0.01),
            DatedReturn(dt.date(2026, 1, 2), float("nan")),
        )
    }
    duplicate = {
        10: (
            DatedReturn(dt.date(2026, 1, 1), 0.01),
            DatedReturn(dt.date(2026, 1, 1), 0.02),
        )
    }

    with pytest.raises(ValueError, match="finite"):
        complete_case_alignment(non_finite, (10,))
    with pytest.raises(ValueError, match="duplicate"):
        complete_case_alignment(duplicate, (10,))

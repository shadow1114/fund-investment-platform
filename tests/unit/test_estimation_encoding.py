import dataclasses
import datetime as dt
import hashlib
import json

import numpy as np
import pytest

from fip.strategy_library.estimation.encoding import (
    canonical_checksum,
    decode_lower_triangle,
    encode_float64,
    encode_lower_triangle,
)
from fip.strategy_library.estimation.types import (
    AlignedReturns,
    CovarianceEstimateResult,
    DatedReturn,
    FactorRiskObservation,
    ReturnEstimateResult,
)


def test_lower_triangle_round_trips_float64_exactly():
    matrix = np.array([[0.1, -0.0], [-0.0, np.nextafter(0.2, 1.0)]])
    encoded = encode_lower_triangle(matrix)
    assert encoded == (repr(0.1), repr(-0.0), repr(float(np.nextafter(0.2, 1.0))))
    decoded = decode_lower_triangle(encoded, 2)
    assert np.array_equal(decoded, matrix)
    assert np.signbit(decoded[1, 0])


def test_canonical_checksum_uses_sorted_compact_json_sha256():
    payload = {"b": 1, "a": [True, "x"]}
    expected = hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    assert canonical_checksum(payload) == expected
    assert canonical_checksum({"a": [True, "x"], "b": 1}) == expected


def test_encode_float64_rejects_non_finite_values():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            encode_float64(value)


def test_lower_triangle_requires_square_matrix_and_matching_size():
    with pytest.raises(ValueError):
        encode_lower_triangle(np.ones((2, 3)))
    with pytest.raises(ValueError):
        decode_lower_triangle(("0.0",), 2)


def test_estimation_dtos_are_frozen_and_slotted():
    classes = (
        DatedReturn,
        AlignedReturns,
        ReturnEstimateResult,
        CovarianceEstimateResult,
        FactorRiskObservation,
    )
    for cls in classes:
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen
        assert hasattr(cls, "__slots__")

    dated = DatedReturn(dt.date(2024, 1, 1), 0.1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        dated.value = 0.2

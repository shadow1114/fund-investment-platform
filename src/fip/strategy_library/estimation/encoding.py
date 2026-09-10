"""Deterministic, dependency-light encodings used by estimation artifacts."""

import hashlib
import json
import math
from typing import Any

import numpy as np


def encode_float64(value: float) -> str:
    """Encode a finite value using Python's shortest round-trip float format."""
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("float64 encoding only accepts finite values")
    return repr(converted)


def encode_lower_triangle(matrix: np.ndarray[Any, Any]) -> tuple[str, ...]:
    """Encode a square matrix's lower triangle in row-major order."""
    array = np.asarray(matrix)
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        raise ValueError("matrix must be square")
    return tuple(
        encode_float64(array[row, column])
        for row in range(array.shape[0])
        for column in range(row + 1)
    )


def decode_lower_triangle(values: tuple[str, ...], size: int) -> np.ndarray[Any, Any]:
    """Decode a row-major lower triangle into a float64 square matrix."""
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError("size must be a non-negative integer")
    expected = size * (size + 1) // 2
    if len(values) != expected:
        raise ValueError(f"expected {expected} lower-triangle values, got {len(values)}")
    matrix = np.zeros((size, size), dtype=np.float64)
    index = 0
    for row in range(size):
        for column in range(row + 1):
            value = float(values[index])
            if not math.isfinite(value):
                raise ValueError("float64 decoding only accepts finite values")
            matrix[row, column] = value
            index += 1
    return matrix


def canonical_checksum(payload: Any) -> str:
    """Return the SHA-256 checksum of compact, sorted-key canonical JSON."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

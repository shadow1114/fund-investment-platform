"""Disposable bounded classification-source calls with existing HTTP capture semantics."""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Callable
from numbers import Number
from typing import Any

import pandas as pd

from fip.services.data_service.adapters.akshare.overview_worker import capture_overview

FUNCTIONS = frozenset({"fund_info_index_em", "fund_individual_basic_info_xq"})


def normalize_snowball_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    """Encode only numeric size metadata as text for the item/value parquet column.

    Local AKShare leaves 最新规模 numeric alongside text values. Classification
    fields and provider identity are never coerced; invalid values still fail with
    the original HTTP response captured by the worker.
    """
    if not frame.columns.is_unique or not {"item", "value"} <= set(frame.columns):
        return frame
    result = frame.copy()
    values = list(result["value"])
    for position, (item, value) in enumerate(zip(result["item"], values, strict=True)):
        if (
            isinstance(item, str)
            and item == "最新规模"
            and isinstance(value, Number)
            and not pd.isna(value)
        ):
            values[position] = str(value)
    result["value"] = values
    return result


def _provider_call(function: str, **params: Any) -> pd.DataFrame:
    import akshare

    result: pd.DataFrame = getattr(akshare, function)(**params)
    return result


def capture_source(
    function: str,
    params: dict[str, Any],
    *,
    caller: Callable[..., pd.DataFrame] | None = None,
) -> dict[str, Any]:
    if function not in FUNCTIONS:
        raise ValueError(f"Unsupported isolated source function: {function}")

    def call(symbol: str) -> pd.DataFrame:
        if caller is not None:
            frame = caller(**params)
        else:
            frame = _provider_call(function, **params)
        if function == "fund_individual_basic_info_xq":
            return normalize_snowball_metadata(frame)
        return frame

    # Shared capture records raw bytes before parsing and structured retryable statuses.
    # Outer process timeout also bounds functions whose signature offers no timeout.
    return capture_overview(
        str(params.get("symbol", "")),
        caller=call,
        request_timeout=float(params.get("timeout", 20)),
    )


if __name__ == "__main__":
    # Some AKShare versions print progress; reserve stdout for the JSON envelope.
    with contextlib.redirect_stdout(sys.stderr):
        result = capture_source(sys.argv[1], json.loads(sys.argv[2]))
    sys.stdout.write(json.dumps(result))

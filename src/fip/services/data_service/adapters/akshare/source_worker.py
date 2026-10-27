"""Disposable bounded classification-source calls with existing HTTP capture semantics."""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Callable
from typing import Any

import pandas as pd

from fip.services.data_service.adapters.akshare.overview_worker import capture_overview

FUNCTIONS = frozenset({"fund_info_index_em", "fund_individual_basic_info_xq"})


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
            return caller(**params)
        return _provider_call(function, **params)

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

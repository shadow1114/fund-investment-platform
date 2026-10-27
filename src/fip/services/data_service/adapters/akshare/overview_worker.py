"""Disposable AKShare call: capture HTTP bytes before its HTML parser runs."""

from __future__ import annotations

import base64
import io
import json
import sys
from collections.abc import Callable
from typing import Any

import pandas as pd
import requests


def capture_overview(
    symbol: str,
    *,
    caller: Callable[..., pd.DataFrame] | None = None,
    request_timeout: float = 20,
) -> dict[str, Any]:
    original_get = requests.get
    raw = b""
    status: int | None = None

    def captured_get(*args: Any, **kwargs: Any) -> requests.Response:
        nonlocal raw, status
        kwargs["timeout"] = request_timeout
        response = original_get(*args, **kwargs)
        raw, status = response.content, response.status_code
        response.raise_for_status()
        return response

    requests.get = captured_get
    try:
        if caller is None:
            import akshare

            caller = akshare.fund_overview_em
        frame = caller(symbol=symbol)
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        return {
            "kind": "ok",
            "parquet": base64.b64encode(buffer.getvalue()).decode(),
            "raw": base64.b64encode(raw).decode(),
            "retryable": False,
            "http_status": status,
        }
    except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
        return {
            "kind": "network",
            "retryable": status is None or status in {429, 502, 503, 504},
            "raw": base64.b64encode(raw).decode(),
            "http_status": status,
            "error": f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            "kind": "parse",
            "retryable": False,
            "raw": base64.b64encode(raw).decode(),
            "http_status": status,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        requests.get = original_get


if __name__ == "__main__":
    sys.stdout.write(json.dumps(capture_overview(sys.argv[1])))

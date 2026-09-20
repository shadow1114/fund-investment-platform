from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from time import perf_counter
from typing import Any


@dataclass(frozen=True)
class RequestEvent:
    method: str
    route: str
    status_code: int
    duration_ms: float
    request_id: str | None
    principal_id: str | None


class MetricsRegistry:
    def __init__(self) -> None:
        self._http_requests: Counter[tuple[str, str, int]] = Counter()
        self._http_errors: Counter[tuple[str, str, int]] = Counter()

    def record(self, event: RequestEvent) -> None:
        key = (event.method, event.route, event.status_code)
        self._http_requests[key] += 1
        if event.status_code >= 400:
            self._http_errors[key] += 1

    def render(self) -> str:
        lines = [
            "# TYPE fip_http_requests_total counter",
            "# TYPE fip_http_errors_total counter",
        ]
        for (method, route, status), count in sorted(self._http_requests.items()):
            labels = f'method="{method}",route="{route}",status="{status}"'
            lines.append(f"fip_http_requests_total{{{labels}}} {count}")
            errors = self._http_errors.get((method, route, status), 0)
            if errors:
                lines.append(f"fip_http_errors_total{{{labels}}} {errors}")
        return "\n".join(lines) + "\n"


class RequestEventSink:
    def __init__(self, metrics: MetricsRegistry, logger: logging.Logger | None = None) -> None:
        self.metrics = metrics
        self.logger = logger or logging.getLogger("fip.api")

    def emit(self, event: RequestEvent) -> None:
        self.metrics.record(event)
        self.logger.info(json.dumps({"event": "http_request", **event.__dict__}, sort_keys=True))


def event_for(request: Any, response: Any, started_at: float) -> RequestEvent:
    principal = getattr(getattr(request, "state", None), "principal", None)
    return RequestEvent(
        method=request.method,
        route=request.url.path,
        status_code=response.status_code,
        duration_ms=round((perf_counter() - started_at) * 1000, 3),
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        principal_id=getattr(principal, "user_id", None),
    )

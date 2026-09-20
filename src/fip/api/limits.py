from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class LocalRateLimiter:
    """Bounded process-local limiter for development and single-process use."""

    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def with_limit(self, limit_per_minute: int) -> LocalRateLimiter:
        return LocalRateLimiter(limit_per_minute)

    def allow(
        self, principal_key: str, route_key: str, now: float | None = None
    ) -> RateLimitDecision:
        current = monotonic() if now is None else now
        key = f"{principal_key}:{route_key}"
        events = self._events[key]
        while events and events[0] <= current - 60:
            events.popleft()
        if len(events) >= self.limit_per_minute:
            return RateLimitDecision(False, max(1, int(events[0] + 60 - current)))
        events.append(current)
        return RateLimitDecision(True)

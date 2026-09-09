import datetime as dt
from dataclasses import dataclass
from enum import StrEnum


class FactorStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class FactorResult:
    factor_id: str
    value: float | None
    status: FactorStatus | str
    reason: str | None
    observations: int


@dataclass(frozen=True, slots=True)
class ReturnObservation:
    effective_at: dt.date
    value: float


def unavailable(factor_id: str, reason: str, observations: int = 0) -> FactorResult:
    return FactorResult(factor_id, None, FactorStatus.UNAVAILABLE, reason, observations)

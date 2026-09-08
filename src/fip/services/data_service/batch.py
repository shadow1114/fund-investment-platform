from dataclasses import dataclass
from enum import StrEnum


class BatchItemStatus(StrEnum):
    SUCCESS = "SUCCESS"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class FundIngestSubject:
    share_class_id: int
    provider_fund_id: str


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    subject_id: int
    status: BatchItemStatus
    error: str | None


@dataclass(frozen=True, slots=True)
class BatchIngestResult:
    items: tuple[BatchItemResult, ...]

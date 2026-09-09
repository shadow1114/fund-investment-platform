from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PeerGroupKey:
    classification_code: str
    base_currency: str


@dataclass(frozen=True, slots=True)
class PeerGroupCandidate:
    share_class_id: int
    key: PeerGroupKey | None
    grouping_status: str
    status: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PeerGroupDraft:
    key: PeerGroupKey
    member_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PeerGroupExclusion:
    share_class_id: int
    status: str
    reason: str

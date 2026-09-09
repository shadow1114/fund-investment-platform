from collections.abc import Mapping, Sequence

from fip.services.fund_service.peer_group.models import (
    PeerGroupCandidate,
    PeerGroupDraft,
    PeerGroupKey,
)


def build_peer_groups(
    candidates: Sequence[PeerGroupCandidate], supported_profiles: Mapping[str, str]
) -> tuple[PeerGroupDraft, ...]:
    grouped: dict[tuple[str, str], list[int]] = {}
    for candidate in candidates:
        if candidate.grouping_status == "UNCONFIRMED" or candidate.key is None:
            continue
        if candidate.key.classification_code not in supported_profiles:
            continue
        grouped.setdefault(
            (candidate.key.classification_code, candidate.key.base_currency), []
        ).append(candidate.share_class_id)
    return tuple(
        PeerGroupDraft(PeerGroupKey(code, currency), tuple(sorted(ids)))
        for (code, currency), ids in sorted(grouped.items())
    )

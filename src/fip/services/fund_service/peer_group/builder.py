from collections.abc import Mapping, Sequence

from fip.services.fund_service.peer_group.models import (
    PeerGroupCandidate,
    PeerGroupDraft,
    PeerGroupExclusion,
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


def excluded_candidates(
    candidates: Sequence[PeerGroupCandidate], supported_profiles: Mapping[str, str]
) -> tuple[PeerGroupExclusion, ...]:
    """Return auditable non-members without changing the pure group output."""
    exclusions: list[PeerGroupExclusion] = []
    for candidate in candidates:
        if candidate.grouping_status == "UNCONFIRMED":
            exclusions.append(
                PeerGroupExclusion(
                    candidate.share_class_id, "GROUPING_UNCONFIRMED", "GROUPING_UNCONFIRMED"
                )
            )
        elif candidate.key is None or candidate.key.classification_code not in supported_profiles:
            exclusions.append(
                PeerGroupExclusion(
                    candidate.share_class_id,
                    "UNSUPPORTED_CLASSIFICATION",
                    "UNSUPPORTED_CLASSIFICATION",
                )
            )
    return tuple(sorted(exclusions, key=lambda item: item.share_class_id))

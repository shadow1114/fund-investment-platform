from fip.services.fund_service.peer_group import (
    PeerGroupCandidate,
    PeerGroupKey,
    build_peer_groups,
    excluded_candidates,
)


def test_peer_groups_are_deterministic_and_exclude_unconfirmed_or_unknown():
    candidates = [
        PeerGroupCandidate(2, PeerGroupKey("BOND", "CNY"), "CONFIRMED"),
        PeerGroupCandidate(1, PeerGroupKey("BOND", "CNY"), "CONFIRMED"),
        PeerGroupCandidate(3, PeerGroupKey("UNKNOWN", "CNY"), "CONFIRMED"),
        PeerGroupCandidate(4, PeerGroupKey("BOND", "CNY"), "UNCONFIRMED"),
    ]
    groups = build_peer_groups(candidates, {"BOND": "Bond"})
    assert groups[0].member_ids == (1, 2)
    assert [
        (item.share_class_id, item.status)
        for item in excluded_candidates(candidates, {"BOND": "Bond"})
    ] == [(3, "UNSUPPORTED_CLASSIFICATION"), (4, "GROUPING_UNCONFIRMED")]

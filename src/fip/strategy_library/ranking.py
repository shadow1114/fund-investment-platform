from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankingResult:
    share_class_id: int
    rank: float | None
    status: str


def rank_peer_group(
    scores: Sequence[tuple[int, float | None]], minimum_sample: int
) -> tuple[RankingResult, ...]:
    available = [(identifier, value) for identifier, value in scores if value is not None]
    if len(available) < minimum_sample:
        return tuple(RankingResult(identifier, None, "UNAVAILABLE") for identifier, _ in scores)
    ranked = sorted(available, key=lambda item: (-item[1], item[0]))
    ranks: dict[int, float] = {}
    start = 0
    while start < len(ranked):
        end = start + 1
        while end < len(ranked) and ranked[end][1] == ranked[start][1]:
            end += 1
        rank = (start + 1 + end) / 2
        for identifier, _ in ranked[start:end]:
            ranks[identifier] = rank
        start = end
    return tuple(
        RankingResult(
            identifier, ranks.get(identifier), "AVAILABLE" if identifier in ranks else "UNAVAILABLE"
        )
        for identifier, _ in sorted(scores)
    )

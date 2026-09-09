from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FundTierResult:
    tier: str | None
    status: str
    n_effective: int


def classify_tier(*, rank: float | None, n_effective: int, minimum_sample: int) -> FundTierResult:
    if rank is None or n_effective < minimum_sample:
        return FundTierResult(None, "UNAVAILABLE", n_effective)
    percentile = rank / n_effective
    if percentile <= 0.2:
        return FundTierResult("A", "AVAILABLE", n_effective)
    if percentile <= 0.5:
        return FundTierResult("B", "AVAILABLE", n_effective)
    if percentile <= 0.8:
        return FundTierResult("C", "AVAILABLE", n_effective)
    return FundTierResult("D", "AVAILABLE", n_effective)

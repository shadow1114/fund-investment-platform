from fip.strategy_library.tier import classify_tier


def test_tier_is_unavailable_below_minimum_sample():
    result = classify_tier(rank=1, n_effective=2, minimum_sample=3)
    assert result.status == "UNAVAILABLE"


def test_tier_uses_rank_percentile_thresholds():
    assert classify_tier(rank=1, n_effective=10, minimum_sample=3).tier == "A"
    assert classify_tier(rank=10, n_effective=10, minimum_sample=3).tier == "D"

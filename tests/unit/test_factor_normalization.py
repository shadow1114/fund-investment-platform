from fip.strategy_library.normalization import normalize_factor


def test_normalization_returns_unavailable_below_minimum_sample():
    values = normalize_factor(((1, 1.0), (2, 2.0)), "HIGHER_IS_BETTER", 3)
    assert {value.status for value in values} == {"UNAVAILABLE"}


def test_normalization_uses_average_rank_for_ties():
    values = normalize_factor(((1, 1.0), (2, 1.0), (3, 3.0)), "HIGHER_IS_BETTER", 3)
    assert [value.normalized_value for value in values] == [25.0, 25.0, 100.0]

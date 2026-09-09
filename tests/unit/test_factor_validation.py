from fip.strategy_library.validation import validate_effectiveness


def test_validation_is_pending_without_out_of_sample_observations():
    result = validate_effectiveness((), minimum_observations=3)
    assert result.verdict == "VALIDATION_PENDING"


def test_validation_uses_time_ordered_rank_ic():
    result = validate_effectiveness(((1.0, 1.0), (2.0, 2.0), (3.0, 3.0)), minimum_observations=3)
    assert result.verdict == "VALID"
    assert result.ic == 1.0

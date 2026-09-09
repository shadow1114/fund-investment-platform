from fip.strategy_library.scoring import ScoringItem, calculate_score


def test_score_renormalizes_available_fixed_weights():
    result = calculate_score(
        (
            ScoringItem("alpha", 80.0, 0.6, "VALID"),
            ScoringItem("beta", None, 0.4, "VALID"),
        ),
        minimum_factors=1,
        minimum_completeness=0.5,
    )
    assert result.status == "AVAILABLE"
    assert result.value == 80.0


def test_score_is_validation_pending_without_oos_verdict():
    result = calculate_score(
        (ScoringItem("alpha", 80.0, 1.0, "VALIDATION_PENDING"),),
        minimum_factors=1,
        minimum_completeness=0.0,
    )
    assert result.status == "VALIDATION_PENDING"

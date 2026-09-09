from fip.strategy_library.universe import SelectionCondition, evaluate_candidate


def test_universe_retains_all_condition_results_for_rejected_candidate():
    result = evaluate_candidate(
        (
            SelectionCondition("eligible", "AVAILABLE", True),
            SelectionCondition("score", "UNAVAILABLE", None),
        )
    )
    assert result.status == "REJECTED"
    assert len(result.conditions) == 2

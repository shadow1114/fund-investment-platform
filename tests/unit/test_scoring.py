from fip.strategy_library.scoring import (
    ScoringItem,
    TrackingErrorInput,
    calculate_score,
    calculate_tracking_error_scores,
)


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


def test_active_tracking_error_uses_reward_penalty_and_neutral_branches():
    results = calculate_tracking_error_scores(
        (
            TrackingErrorInput(1, 0.02, 20.0, information_ratio=0.8),
            TrackingErrorInput(2, 0.01, 80.0, information_ratio=-0.2),
            TrackingErrorInput(3, 0.03, 40.0, information_ratio=0.3),
        ),
        profile="active_equity",
        minimum_sample=2,
    )

    assert [item.interaction_value for item in results] == [100.0, 0.0, 50.0]


def test_hybrid_tracking_error_uses_sharpe_gate():
    results = calculate_tracking_error_scores(
        (
            TrackingErrorInput(1, 0.02, 20.0, sharpe=1.2),
            TrackingErrorInput(2, 0.01, 80.0, sharpe=0.8),
        ),
        profile="hybrid",
        minimum_sample=2,
    )

    assert [item.interaction_value for item in results] == [100.0, 0.0]


def test_passive_and_bond_tracking_error_rules():
    candidates = (
        TrackingErrorInput(1, 0.01, 80.0),
        TrackingErrorInput(2, 0.02, 20.0),
    )

    passive = calculate_tracking_error_scores(
        candidates, profile="passive_equity", minimum_sample=2
    )
    bond = calculate_tracking_error_scores(candidates, profile="bond", minimum_sample=2)

    assert [item.interaction_value for item in passive] == [80.0, 20.0]
    assert [item.interaction_value for item in bond] == [80.0, 0.0]

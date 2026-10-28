"""Pure smoke checks for the single current classification ruleset."""

from datetime import UTC, datetime

from fip.services.data_service.classification import classify, normalize_evidence
from fip.services.data_service.classification.policy import load_policy
from fip.services.data_service.classification.rules import DEFAULT_POLICY

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def ev(field: str, value: str, source: str = "OFFICIAL"):
    return normalize_evidence(
        source=source,
        field=field,
        value=value,
        classified_at=NOW,
        payload_ref="raw:123",
        locator="p.2",
    )


def test_current_policy_is_the_only_classifier_policy():
    assert load_policy() == DEFAULT_POLICY
    assert DEFAULT_POLICY.scheme == "FIP_CLASSIFICATION"
    assert DEFAULT_POLICY.active_dimensions == ("asset_class", "strategy")


def test_active_asset_dimension_is_classified_and_paused_dimensions_are_not_recomputed():
    snapshot = classify([ev("formal_type", "股票型")], classified_at=NOW)

    assert snapshot.scheme == "FIP_CLASSIFICATION"
    assert snapshot.asset_class.value == "EQUITY"
    assert snapshot.asset_class.evaluation_state == "EVALUATED"
    assert snapshot.strategy.value == "UNKNOWN"
    assert snapshot.geography.evaluation_state == "NOT_EVALUATED"
    assert snapshot.product_structure.evaluation_state == "NOT_EVALUATED"
    assert snapshot.market_attributes.evaluation_state == "NOT_EVALUATED"
    assert snapshot.strategy_tag_results["QUANTITATIVE"].evaluation_state == "NOT_EVALUATED"


def test_classifier_serialization_has_no_rule_or_enum_release_labels():
    snapshot = classify([ev("formal_type", "债券型")], classified_at=NOW)
    data = snapshot.to_dict()

    assert data["asset_class"]["value"] == "BOND"
    assert "rule_version" not in data
    assert "enum_version" not in data


def test_unknown_formal_type_does_not_fall_back_to_an_asset_class():
    snapshot = classify([ev("formal_type", "新奇型")], classified_at=NOW)

    assert snapshot.asset_class.status == "UNKNOWN"
    assert snapshot.asset_class.value == "UNKNOWN"

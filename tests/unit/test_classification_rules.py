"""Pure classification contract: no persistence or source availability required."""

from datetime import UTC, datetime

import pytest

from fip.services.data_service.classification import classify, normalize_evidence
from fip.services.data_service.classification.policy import load_policy

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def ev(field: str, value: str, source: str = "OFFICIAL"):
    return normalize_evidence(
        source=source,
        field=field,
        value=value,
        classified_at=NOW,
        payload_ref="raw:123",
        locator="p.2",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("股票型", "EQUITY"),
        ("债券型", "BOND"),
        ("混合型", "MIXED"),
        ("货币型", "MONEY_MARKET"),
        ("FOF", "FOF"),
        ("REIT", "REIT"),
        ("商品型", "COMMODITY"),
        ("指数型", "UNKNOWN"),
        ("新奇型", "UNKNOWN"),
    ],
)
def test_formal_asset_matrix(raw, expected):
    result = classify([ev("formal_type", raw)], classified_at=NOW)
    assert result.asset_class.value == expected
    assert result.asset_class.evidence[0].raw_value == raw


@pytest.mark.parametrize(
    ("values", "expected", "status"),
    [
        (["ENHANCED_INDEX", "PASSIVE_INDEX"], "ENHANCED_INDEX", "CONFIRMED"),
        (["QUANTITATIVE", "PASSIVE_INDEX"], "PASSIVE_INDEX", "CONFIRMED"),
        (["TARGET_DATE", "QUANTITATIVE"], "TARGET_DATE", "CONFIRMED"),
        (["TARGET_DATE", "TARGET_RISK"], "UNKNOWN", "CONFLICT"),
        (["ACTIVE", "PASSIVE_INDEX"], "UNKNOWN", "CONFLICT"),
        (["ACTIVE", "ENHANCED_INDEX"], "ENHANCED_INDEX", "CONFIRMED"),
        ([], "UNKNOWN", "UNKNOWN"),
    ],
)
def test_strategy_matrix(values, expected, status):
    result = classify([ev("strategy_hint", value) for value in values], classified_at=NOW)
    assert (result.strategy.value, result.strategy.status) == (expected, status)


def test_benchmark_is_not_tracking_and_names_are_candidates():
    result = classify(
        [ev("benchmark", "PASSIVE_INDEX"), ev("name", "美国商品ETF联接A", "NAME")],
        classified_at=NOW,
    )
    assert result.strategy.value == "UNKNOWN"
    assert result.product_structure.value == "UNKNOWN"
    assert result.product_structure.candidates == ("ETF_LINKED",)
    assert result.asset_class.status == "CANDIDATE"


def test_multivalue_and_qdii_do_not_infer_us():
    result = classify(
        [
            ev("market_attributes", "QDII"),
            ev("geography", "JP"),
            ev("geography", "HK"),
            ev("geography", "JP"),
        ],
        classified_at=NOW,
    )
    assert result.geography.value == ("HK", "JP", "MULTI_REGION")
    assert result.market_attributes.value == ("CROSS_BORDER", "QDII")


def test_conflict_is_local_and_all_sources_retained():
    result = classify(
        [
            ev("formal_type", "股票型"),
            ev("formal_type", "债券型", "AGGREGATOR"),
            ev("product_structure", "ETF_LINKED"),
        ],
        classified_at=NOW,
    )
    assert result.asset_class.status == "CONFLICT"
    assert len(result.asset_class.evidence) == 2
    assert all(item.conflict_reason for item in result.asset_class.evidence)
    assert result.product_structure.value == "ETF_LINKED"
    assert len(result.review_items) == len(set(result.review_items))


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("geography", ["GLOBAL", "DOMESTIC"]),
        ("market_attributes", ["DOMESTIC", "CROSS_BORDER"]),
        ("product_structure", ["ETF", "ETF_LINKED"]),
    ],
)
def test_incompatible_evidence_conflicts(field, values):
    result = classify([ev(field, value) for value in values], classified_at=NOW)
    assert getattr(result, field).status == "CONFLICT"


def test_snapshot_is_json_and_stable_and_unknown_exclusive():
    result = classify([ev("geography", "UNKNOWN"), ev("geography", "US")], classified_at=NOW)
    data = result.to_dict()
    assert data["scheme"] == "FIP_CLASSIFICATION_V1"
    assert data["rule_version"] == data["enum_version"] == "1.0.0"
    assert data["geography"]["value"] == ["US"]
    assert data["geography"]["evidence"][0]["payload_ref"] == "raw:123"
    assert data["geography"]["evidence"][0]["classified_at"].endswith(("Z", "+00:00"))


def test_separate_versioned_policy_loader():
    assert load_policy().rule_version == "1.0.0"


def test_explicit_passive_and_enhanced_contradiction():
    result = classify(
        [ev("strategy", "ENHANCED_INDEX"), ev("strategy", "PASSIVE_INDEX")], classified_at=NOW
    )
    assert result.strategy.status == "CONFLICT"


def test_policy_file_matches_pure_default():
    from fip.services.data_service.classification.rules import DEFAULT_POLICY

    assert load_policy() == DEFAULT_POLICY


def test_naive_time_rejected():
    with pytest.raises(ValueError, match="timezone"):
        normalize_evidence(
            source="OFFICIAL",
            field="formal_type",
            value="股票型",
            classified_at=datetime(2026, 1, 1),
        )


@pytest.mark.parametrize(
    ("asset", "strategy", "expected"),
    [
        ("股票型", "ACTIVE", "ACTIVE_EQUITY"),
        ("股票型", "PASSIVE_INDEX", "PASSIVE_EQUITY"),
        ("债券型", None, "BOND"),
        ("混合型", None, "HYBRID"),
        ("股票型", "ENHANCED_INDEX", None),
        ("股票型", "QUANTITATIVE", None),
    ],
)
def test_legacy_projection(asset, strategy, expected):
    from fip.services.data_service.classification import project_legacy

    evidence = [ev("formal_type", asset)]
    if strategy:
        evidence.append(ev("strategy", strategy))
    result = project_legacy(classify(evidence, classified_at=NOW), grouping_confirmed=True)
    assert result.value == expected
    assert (result.reason is None) == (expected is not None)


def test_legacy_requires_product_grouping_and_retains_benchmark_evidence():
    from fip.services.data_service.classification import project_legacy

    snapshot = classify(
        [ev("formal_type", "债券型"), ev("benchmark", "PASSIVE_INDEX")], classified_at=NOW
    )
    assert project_legacy(snapshot, grouping_confirmed=False).value is None
    assert snapshot.strategy.evidence[0].raw_field == "benchmark"


def test_formal_underlying_not_generic_index_confirms_commodity():
    result = classify(
        [ev("formal_type", "指数型"), ev("underlying_asset", "COMMODITY")], classified_at=NOW
    )
    assert result.asset_class.value == "COMMODITY"


def test_name_does_not_change_official_structure():
    result = classify(
        [ev("name", "ETF", "NAME"), ev("product_structure", "ETF_LINKED")], classified_at=NOW
    )
    assert result.product_structure.value == "ETF_LINKED"
    assert result.product_structure.candidates == ("ETF",)


def test_normalization_preserves_native_field_and_value():
    result = classify([ev("基金类型", "股票型")], classified_at=NOW)
    assert result.asset_class.value == "EQUITY"
    assert result.asset_class.evidence[0].raw_field == "基金类型"


def test_exclusive_unknown_multivalue_is_stable():
    result = classify([], classified_at=NOW)
    assert result.geography.value == ("UNKNOWN",)
    assert result.market_attributes.value == ("UNKNOWN",)


def test_explicit_passive_is_not_overridden_by_enhanced_hint():
    result = classify(
        [ev("strategy", "PASSIVE_INDEX"), ev("strategy_hint", "ENHANCED_INDEX")], classified_at=NOW
    )
    assert result.strategy.status == "CONFLICT"


def test_explicit_global_and_multi_region_conflict():
    result = classify(
        [ev("geography", "GLOBAL"), ev("geography", "MULTI_REGION")], classified_at=NOW
    )
    assert result.geography.status == "CONFLICT"


def test_other_requires_recognized_formal_type_rule():
    result = classify([ev("asset_class", "OTHER")], classified_at=NOW)
    assert result.asset_class.status == "UNKNOWN"


def test_invalid_policy_fails_before_classifier_can_drop_strategy():
    from pydantic import ValidationError

    from fip.services.data_service.classification.policy import ClassificationPolicy

    content = load_policy().model_dump()
    content["strategy_priority"] = ("ACTIVE",)
    with pytest.raises(ValidationError):
        ClassificationPolicy.model_validate(content)

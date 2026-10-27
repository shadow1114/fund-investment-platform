"""Offline asset regression matrix for the explicitly selected v3 policy."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from fip.services.data_service.classification import classify, normalize_evidence
from fip.services.data_service.classification.policy import ClassificationPolicy, load_policy

NOW = datetime(2026, 10, 27, tzinfo=UTC)


def ev(field, value, source="OFFICIAL"):
    return normalize_evidence(
        source=source,
        field=field,
        value=value,
        classified_at=NOW,
        payload_ref="raw:asset-fixture",
        locator="p.3",
    )


def classify_v3(evidence):
    return classify(evidence, classified_at=NOW, policy=load_policy(rule_version="3.0.0"))


def test_paused_dimensions_emit_no_automatic_assertions_or_review_items():
    result = classify_v3(
        [
            ev("formal_type", "股票型"),
            ev("geography", "US"),
            ev("market_attributes", "QDII"),
            ev("product_structure", "ETF"),
            ev("name", "美国商品QDII ETF", "NAME"),
        ]
    )
    assert result.asset_class.value == "EQUITY"
    for dimension in ("geography", "product_structure", "market_attributes"):
        paused = getattr(result, dimension)
        assert paused.status == "UNKNOWN"
        assert paused.value in ("UNKNOWN", ("UNKNOWN",))
        assert paused.evaluation_state == "NOT_EVALUATED"
        assert paused.evidence == paused.candidates == ()
        assert not any(item.startswith(f"{dimension}:") for item in result.review_items)
    assert result.asset_class.evaluation_state == "EVALUATED"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("QDII-混合灵活", "MIXED"),
        ("QDII-普通股票", "EQUITY"),
        ("QDII-商品", "COMMODITY"),
        ("QDII-纯债", "BOND"),
        ("指数型-其他", "UNKNOWN"),
        ("债券型-混合一级", "BOND"),
        ("FOF-均衡型", "FOF"),
        ("混合型-偏股", "MIXED"),
        ("指数型-股票", "EQUITY"),
        ("QDII-混合债", "UNKNOWN"),
        ("债券型-长债", "BOND"),
        ("FOF-稳健型", "FOF"),
        ("QDII-FOF", "FOF"),
        ("混合型-绝对收益", "MIXED"),
        ("债券型-混合二级", "BOND"),
        ("货币型-浮动净值", "MONEY_MARKET"),
        ("混合型-灵活", "MIXED"),
        ("FOF-进取型", "FOF"),
        ("债券型-中短债", "BOND"),
        ("QDII-混合偏股", "MIXED"),
        ("QDII-REITs", "UNKNOWN"),
        ("QDII-混合平衡", "MIXED"),
        ("指数型-海外股票", "EQUITY"),
        ("混合型-平衡", "MIXED"),
        ("指数型-固收", "BOND"),
        ("货币型-普通货币", "MONEY_MARKET"),
        ("混合型-偏债", "MIXED"),
    ],
)
def test_exact_formal_type_allowlist(raw, expected):
    result = classify_v3([ev("formal_type", raw)])
    assert result.asset_class.value == expected
    assert result.asset_class.status == ("UNKNOWN" if expected == "UNKNOWN" else "CONFIRMED")
    assert result.asset_class.evidence[0].raw_value == raw
    if expected == "UNKNOWN":
        assert "asset_class:UNRECOGNIZED" in result.review_items


@pytest.mark.parametrize("raw", ["指数型", "股票型-未登记", "债券型-新产品", "QDII-REITs"])
def test_unmapped_formal_types_preserve_raw_and_review_after_other_source_confirms(raw):
    unknown = ev("formal_type", raw, "AGGREGATOR")
    reliable = ev("underlying_asset", "EQUITY")
    result = classify_v3([unknown, unknown, reliable])
    assert (result.asset_class.status, result.asset_class.value) == ("CONFIRMED", "EQUITY")
    assert unknown in result.asset_class.evidence
    assert result.review_items.count("asset_class:UNRECOGNIZED") == 1
    assert result.review_items == classify_v3([reliable, unknown]).review_items


@pytest.mark.parametrize(
    ("target", "expected", "provider"),
    [
        ("沪深300指数", "EQUITY", "CSI"),
        ("中证全债指数", "BOND", "CSI"),
        ("彭博商品指数", "COMMODITY", "BLOOMBERG"),
    ],
)
def test_exact_tracking_index_uses_traceable_curated_directory(target, expected, provider):
    raw = ev("tracking_target", target, "AGGREGATOR")
    result = classify_v3([raw])
    assert (result.asset_class.status, result.asset_class.value) == ("CONFIRMED", expected)
    derived = result.asset_class.evidence[0]
    assert derived.rule_id == "ASSET_INDEX_EXACT"
    assert derived.raw_value == target
    assert derived.payload_ref == raw.payload_ref
    assert derived.locator == raw.locator
    assert derived.required_observations == (raw,)
    assert derived.assertion_status == "CONFIRMED"
    assert "CURATED_NOT_LIVE_VERIFIED" in derived.rationale
    assert "2026-10-27.1" in derived.rationale
    assert provider in derived.rationale
    assert "https://" in derived.rationale


@pytest.mark.parametrize(
    "target",
    [
        "沪深300",
        "沪深300指数收益率",
        "沪深300指数+中证全债指数",
        "沪深300指数*80%+银行活期存款*20%",
        "综合指数",
        "未知债券指数",
        "全部",
        "股票指数",
        "债券指数",
        " 沪深300指数 ",
    ],
)
def test_unlisted_ambiguous_and_compound_tracking_targets_remain_reviewable(target):
    raw = ev("tracking_target", target)
    result = classify_v3([raw])
    assert (result.asset_class.status, result.asset_class.value) == ("UNKNOWN", "UNKNOWN")
    assert raw in result.asset_class.evidence
    assert "asset_class:UNRECOGNIZED" in result.review_items


@pytest.mark.parametrize("field", ["benchmark", "investment_scope", "investment_objective"])
def test_auxiliary_fields_cannot_establish_tracking_asset(field):
    result = classify_v3([ev(field, "沪深300指数")])
    assert (result.asset_class.status, result.asset_class.value) == ("UNKNOWN", "UNKNOWN")


def test_name_clue_is_only_candidate_and_does_not_conflict_with_reliable_asset():
    name = ev("name", "商品债券基金", "NAME")
    result = classify_v3([name])
    assert (result.asset_class.status, result.asset_class.value) == ("CANDIDATE", "UNKNOWN")
    assert result.asset_class.candidates == ("BOND", "COMMODITY")
    confirmed = classify_v3([name, ev("formal_type", "股票型")])
    assert (confirmed.asset_class.status, confirmed.asset_class.value) == ("CONFIRMED", "EQUITY")
    assert confirmed.asset_class.candidates == ("BOND", "COMMODITY")


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_formal_and_tracking_assets_retain_both_sources(reverse):
    evidence = [ev("formal_type", "债券型"), ev("tracking_target", "沪深300指数", "AGGREGATOR")]
    result = classify_v3(list(reversed(evidence)) if reverse else evidence)
    assert (result.asset_class.status, result.asset_class.value) == ("CONFLICT", "UNKNOWN")
    assert result.asset_class.candidates == ("BOND", "EQUITY")
    assert len(result.asset_class.evidence) == 2
    assert {item.raw_value for item in result.asset_class.evidence} == {"债券型", "沪深300指数"}
    assert all(item.conflict_reason for item in result.asset_class.evidence)
    assert "asset_class:CONFLICT" in result.review_items


def test_same_asset_from_formal_and_tracking_is_not_conflict():
    result = classify_v3([ev("formal_type", "股票型"), ev("tracking_target", "沪深300指数")])
    assert (result.asset_class.status, result.asset_class.value) == ("CONFIRMED", "EQUITY")
    assert len(result.asset_class.evidence) == 2


def test_unknown_formal_type_does_not_block_reliable_tracking_index():
    result = classify_v3([ev("formal_type", "QDII-REITs"), ev("tracking_target", "中证全债指数")])
    assert (result.asset_class.status, result.asset_class.value) == ("CONFIRMED", "BOND")
    assert "asset_class:UNRECOGNIZED" in result.review_items


@pytest.mark.parametrize(
    "locator",
    [
        'identity:{"function":"fund_info_index_em","dataset":"fund_index_passive"};row:0',
        'identity:{"function":"fund_info_index_em","dataset":"fund_index_enhanced"};row:0',
        "dataset:fund_index_passive;params:{'symbol': '全部'}",
        "dataset:fund_index_enhanced;params:{'symbol': '全部'}",
    ],
)
def test_index_query_context_never_becomes_tracking_asset_even_if_mislabeled(locator):
    raw = ev("tracking_target", "沪深300指数", "AGGREGATOR").model_copy(
        update={"locator": locator, "raw_field": "跟踪标的"}
    )
    result = classify_v3([raw])
    assert (result.asset_class.status, result.asset_class.value) == ("UNKNOWN", "UNKNOWN")
    assert "asset_class:INDEX_QUERY_CONTEXT" in result.review_items


def test_index_membership_is_not_tracking_asset():
    result = classify_v3([ev("index_membership", "000001", "AGGREGATOR")])
    assert result.asset_class.status == "UNKNOWN"
    assert result.asset_class.evidence == ()


def test_other_requires_an_explicit_controlled_mapping():
    assert classify_v3([ev("asset_class", "OTHER")]).asset_class.status == "UNKNOWN"
    raw = load_policy(rule_version="3.0.0").model_dump()
    raw["formal_types"]["受控其他类型"] = "OTHER"
    result = classify(
        [ev("formal_type", "受控其他类型")],
        classified_at=NOW,
        policy=ClassificationPolicy.model_validate(raw),
    )
    assert (result.asset_class.status, result.asset_class.value) == ("CONFIRMED", "OTHER")


@pytest.mark.parametrize("invalid", ["version", "provider", "reference", "verification", "asset"])
def test_index_directory_rejects_missing_provenance_or_invalid_assets(invalid):
    raw = load_policy(rule_version="3.0.0").model_dump()
    raw["index_asset_mapping_version"] = "2026-10-27.1"
    entry = {
        "asset_class": "EQUITY",
        "provider": "CSI",
        "reference": "https://www.csindex.com.cn/",
        "verification": "CURATED_NOT_LIVE_VERIFIED",
    }
    raw["index_assets"] = {"沪深300指数": entry}
    if invalid == "version":
        raw["index_asset_mapping_version"] = None
    elif invalid == "asset":
        entry["asset_class"] = "MADE_UP"
    else:
        entry.pop(invalid)
    with pytest.raises(ValidationError):
        ClassificationPolicy.model_validate(raw)

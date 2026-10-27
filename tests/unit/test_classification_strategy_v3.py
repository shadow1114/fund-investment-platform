"""Offline joint-strategy and independent quantitative-tag behavior."""

import json
from datetime import UTC, datetime

import pytest

from fip.services.data_service.classification import classify, normalize_evidence
from fip.services.data_service.classification.policy import load_policy

NOW = datetime(2026, 10, 27, tzinfo=UTC)


def ev(field, value, source="OFFICIAL"):
    return normalize_evidence(
        source=source,
        field=field,
        value=value,
        classified_at=NOW,
        payload_ref="raw:strategy-fixture",
        locator=f"field:{field}",
    )


def member(dataset="fund_index_enhanced", **changes):
    indicator = "增强指数型" if dataset == "fund_index_enhanced" else "被动指数型"
    identity = {
        "adapter": "AKSHARE",
        "provider": "EASTMONEY",
        "dataset": dataset,
        "function": "fund_info_index_em",
        "params": {"symbol": "全部", "indicator": indicator},
        "provider_fund_code": "000001",
        "raw_field": "基金代码",
    }
    identity.update(changes)
    return ev("index_membership", "000001", "AGGREGATOR").model_copy(
        update={
            "raw_field": "基金代码",
            "locator": "identity:" + json.dumps(identity) + ";row:0",
        }
    )


def v3(items, policy=None):
    return classify(items, classified_at=NOW, policy=policy or load_policy(rule_version="3.0.0"))


@pytest.mark.parametrize(
    ("dataset", "value", "rule"),
    [
        ("fund_index_enhanced", "ENHANCED_INDEX", "STR001"),
        ("fund_index_passive", "PASSIVE_INDEX", "STR002"),
    ],
)
def test_valid_membership_is_positive_with_original_observation(dataset, value, rule):
    raw = member(dataset)
    result = v3([raw]).strategy
    assert (result.status, result.value) == ("CONFIRMED", value)
    assertion = next(e for e in result.evidence if e.rule_id == rule)
    assert assertion.required_observations == (raw,)
    assert assertion.assertion_status == "CONFIRMED"
    assert "3.0.0" in assertion.rationale


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "UNKNOWN"},
        {"function": "other"},
        {"provider_fund_code": "000002"},
        {"params": {"symbol": "股票型", "indicator": "增强指数型"}},
        {"params": {"symbol": "全部", "indicator": "被动指数型"}},
    ],
)
def test_malformed_membership_does_not_assert_index_strategy(changes):
    assert v3([member(**changes)]).strategy.status == "UNKNOWN"


def test_unproven_membership_and_tracking_or_hint_are_not_index_assertions():
    result = v3(
        [
            ev("index_membership", "000001"),
            ev("tracking_target", "沪深300指数"),
            ev("strategy_hint", "PASSIVE_INDEX"),
            ev("benchmark", "ENHANCED_INDEX"),
        ]
    )
    assert result.strategy.status == "UNKNOWN"
    assert any(e.rule_id == "STR999" for e in result.strategy.evidence)


def test_dual_membership_conflicts_and_priority_is_only_a_review_suggestion():
    inputs = [member(), member("fund_index_passive")]
    result = v3(inputs)
    assert (result.strategy.status, result.strategy.value) == ("CONFLICT", "UNKNOWN")
    assert result.strategy.candidates == ("ENHANCED_INDEX", "PASSIVE_INDEX")
    assert all(e.assertion_status == "CONFLICT" for e in result.strategy.evidence)
    assert all("suggested_strategy=ENHANCED_INDEX" in e.rationale for e in result.strategy.evidence)
    assert {e.required_observations[0] for e in result.strategy.evidence} == set(inputs)
    assert "strategy:CONFLICT" in result.review_items


@pytest.mark.parametrize(
    ("field", "text", "expected", "rule"),
    [
        ("formal_type", "目标日期基金", "TARGET_DATE", "STR010"),
        ("investment_strategy", "本基金采用目标日期策略。", "TARGET_DATE", "STR010"),
        ("investment_objective", "本基金采用目标风险策略配置资产。", "TARGET_RISK", "STR020"),
        ("investment_strategy", "本基金采用完全复制法跟踪沪深300指数。", "PASSIVE_INDEX", "STR002"),
        ("investment_strategy", "本基金采用指数增强策略。", "ENHANCED_INDEX", "STR001"),
    ],
)
def test_explicit_official_declarations(field, text, expected, rule):
    raw = ev(field, text, "AGGREGATOR")
    result = v3([raw]).strategy
    assert (result.status, result.value) == ("CONFIRMED", expected)
    assertion = next(e for e in result.evidence if e.rule_id == rule)
    assert assertion.required_observations == (raw,)
    assert text.rstrip("。") in assertion.rationale


@pytest.mark.parametrize(
    "text",
    [
        "本基金不采用目标日期策略。",
        "本基金可采用目标风险策略。",
        "其他基金使用目标风险策略。",
        "资料称：‘本基金采用目标日期策略’。",
        "本基金介绍“目标风险策略”概念。",
        "若条件成熟，本基金将采用目标日期策略。",
        "本基金为养老2035基金，稳健运作，控制风险并匹配风险收益。",
        "本基金采用完全复制法构建某组合。",
    ],
)
def test_ambiguous_negated_conditional_and_quoted_declarations_do_not_confirm(text):
    assert v3([ev("investment_strategy", text)]).strategy.status == "UNKNOWN"


def test_registered_target_risk_mechanism_requires_explicit_adoption():
    raw = load_policy(rule_version="3.0.0").model_dump()
    raw["target_risk_mechanisms"] = ("恒定风险预算机制",)
    policy = type(load_policy()).model_validate(raw)
    assert (
        v3([ev("investment_strategy", "本基金采用恒定风险预算机制。")], policy).strategy.value
        == "TARGET_RISK"
    )
    assert (
        v3([ev("investment_strategy", "本基金可采用恒定风险预算机制。")], policy).strategy.status
        == "UNKNOWN"
    )
    assert (
        v3([ev("investment_strategy", "本基金采用恒定风险预算机制。")]).strategy.status == "UNKNOWN"
    )


def test_active_requires_controlled_type_and_explicit_fund_level_strategy():
    inputs = (
        ev("formal_type", "混合型-偏股"),
        ev("investment_strategy", "本基金采用主动管理策略。"),
    )
    result = v3(inputs).strategy
    assert (result.status, result.value) == ("CONFIRMED", "ACTIVE")
    assertion = next(e for e in result.evidence if e.rule_id == "STR030")
    assert assertion.required_observations == inputs
    assert assertion.payload_ref == inputs[1].payload_ref
    assert assertion.locator == inputs[1].locator


@pytest.mark.parametrize("formal", [None, "UNKNOWN", "指数型", "指数型-股票", "新类型"])
def test_unknown_or_index_type_does_not_complete_active_gate(formal):
    inputs = [ev("investment_strategy", "本基金采用主动管理策略。")]
    if formal:
        inputs.append(ev("formal_type", formal))
    assert v3(inputs).strategy.status == "UNKNOWN"


@pytest.mark.parametrize("formal", ["债券型", "货币型", "混合型", "FOF"])
@pytest.mark.parametrize(
    "text",
    [
        "",
        "精选优选基本面研究，自上而下与自下而上。",
        "不采用被动投资。",
        "无跟踪标的。",
        "本基金可采用主动管理。",
    ],
)
def test_non_index_type_and_forbidden_shortcuts_do_not_prove_active(formal, text):
    assert (
        v3([ev("formal_type", formal), ev("investment_strategy", text)]).strategy.status
        == "UNKNOWN"
    )


@pytest.mark.parametrize(
    "exclusive",
    [member(), member("fund_index_passive"), ev("investment_strategy", "本基金采用目标风险策略。")],
)
def test_independent_exclusive_declarations_conflict_with_joint_active(exclusive):
    result = v3(
        [
            exclusive,
            ev("formal_type", "混合型"),
            ev("investment_strategy", "本基金采用主动管理策略。"),
        ]
    )
    assert result.strategy.status == "CONFLICT"
    assert "ACTIVE" in result.strategy.candidates
    active = next(e for e in result.strategy.evidence if e.rule_id == "STR030")
    assert len(active.required_observations) == 2


def test_membership_and_official_target_strategy_conflict():
    result = v3([member(), ev("investment_objective", "本基金采用目标日期策略。")])
    assert result.strategy.status == "CONFLICT"
    assert result.strategy.candidates == ("ENHANCED_INDEX", "TARGET_DATE")


def test_name_hint_never_conflicts_with_reliable_membership():
    result = v3([member(), ev("name", "目标日期量化指数基金", "NAME")])
    assert (result.strategy.status, result.strategy.value) == ("CONFIRMED", "ENHANCED_INDEX")
    assert "TARGET_DATE" in result.strategy.candidates
    assert result.strategy_tag_results["QUANTITATIVE"].status == "CANDIDATE"
    assert result.strategy_tags == ()


def test_same_sentence_index_copy_and_active_enhancement_is_one_strategy():
    result = v3(
        [
            ev("formal_type", "混合型"),
            ev("investment_strategy", "本基金通过复制沪深300指数并主动增强获取超额收益。"),
        ]
    )
    assert (result.strategy.status, result.strategy.value) == ("CONFIRMED", "ENHANCED_INDEX")


def test_separate_copy_and_enhancement_declarations_are_conflict():
    result = v3(
        [ev("investment_strategy", "本基金采用完全复制法跟踪沪深300指数。本基金采用指数增强策略。")]
    )
    assert result.strategy.status == "CONFLICT"


def test_local_cash_management_and_target_underlying_active_are_not_main_active():
    for exclusive, text in [
        (member("fund_index_passive"), "本基金对现金头寸进行主动管理。"),
        (ev("investment_strategy", "本基金采用目标日期策略。"), "底层基金采用主动管理策略。"),
    ]:
        result = v3([exclusive, ev("formal_type", "混合型"), ev("investment_strategy", text)])
        assert result.strategy.status == "CONFIRMED"
        assert "ACTIVE" not in result.strategy.candidates


@pytest.mark.parametrize(
    "main",
    [
        [ev("formal_type", "股票型"), ev("investment_strategy", "本基金采用主动管理策略。")],
        [member()],
        [member("fund_index_passive")],
        [ev("investment_strategy", "本基金采用目标日期策略。")],
        [],
    ],
)
@pytest.mark.parametrize(
    "method", ["量化模型", "多因子模型", "因子模型", "数量化方法", "模型驱动方法"]
)
def test_quantitative_tag_is_independent_of_any_main_strategy(main, method):
    raw = ev("investment_strategy", f"本基金采用{method}进行投资。")
    result = v3([*main, raw])
    assert result.strategy_tags == ("QUANTITATIVE",)
    tag = result.strategy_tag_results["QUANTITATIVE"]
    assert (tag.status, tag.value, tag.evaluation_state) == (
        "CONFIRMED",
        "QUANTITATIVE",
        "EVALUATED",
    )
    assert tag.evidence[0].required_observations == (raw,)
    if not main:
        assert result.strategy.status == "UNKNOWN"


@pytest.mark.parametrize(
    "text",
    [
        "本基金不采用量化模型。",
        "本基金可采用多因子模型。",
        "其他基金采用因子模型。",
        "若条件满足，本基金采用数量化方法。",
        "本基金引用‘采用量化模型’的报告。",
    ],
)
def test_quantitative_negation_optional_and_citation_do_not_confirm(text):
    result = v3([ev("investment_strategy", text)])
    assert result.strategy_tags == ()
    assert result.strategy_tag_results["QUANTITATIVE"].status == "UNKNOWN"
    assert result.strategy_tag_results["QUANTITATIVE"].evaluation_state == "EVALUATED"


def test_quantitative_positive_and_negative_conflict_with_review_and_both_inputs():
    inputs = (
        ev("investment_strategy", "本基金采用量化模型。"),
        ev("investment_strategy", "本基金不采用量化方法。", "AGGREGATOR"),
    )
    result = v3(inputs)
    tag = result.strategy_tag_results["QUANTITATIVE"]
    assert tag.status == "CONFLICT"
    assert tag.candidates == ("QUANTITATIVE",)
    assert result.strategy_tags == ()
    assert {e.required_observations[0] for e in tag.evidence} == set(inputs)
    assert "strategy_tags:QUANTITATIVE:CONFLICT" in result.review_items


def test_tag_empty_evaluation_distinguishes_absent_data_from_evaluated_strategy():
    missing = v3([member(), ev("benchmark", "本基金采用量化模型。")])
    evaluated = v3([ev("investment_strategy", "本基金精选优质证券。")])
    assert missing.strategy_tag_results["QUANTITATIVE"].evaluation_state == "NOT_EVALUATED"
    assert evaluated.strategy_tag_results["QUANTITATIVE"].evaluation_state == "EVALUATED"
    assert missing.strategy_tags == evaluated.strategy_tags == ()


def test_legacy_default_remains_quantitative_main_strategy_without_tag_extension():
    snapshot = classify([ev("investment_strategy", "QUANTITATIVE")], classified_at=NOW)
    assert snapshot.strategy.value == "QUANTITATIVE"
    assert snapshot.strategy_tag_results is None
    assert "strategy_tags" not in snapshot.to_dict()


@pytest.mark.parametrize(
    ("field", "text"),
    [
        ("formal_type", "非目标日期基金"),
        ("formal_type", "非目标风险基金"),
        ("investment_strategy", "本基金未实施主动管理策略。"),
        ("investment_strategy", "本基金未使用量化模型。"),
        ("investment_strategy", "本基金研究目标日期策略，实际采用基本面投资方法。"),
        ("investment_strategy", "本基金研究量化模型，实际采用基本面投资方法。"),
        ("investment_strategy", "本基金研究指数增强策略，实际采用基本面投资方法。"),
    ],
)
def test_mention_is_not_adoption_and_unadopted_methods_are_not_confirmed(field, text):
    result = v3([ev("formal_type", "股票型"), ev(field, text)])
    assert result.strategy.status == "UNKNOWN"
    assert result.strategy_tags == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("本基金为目标日期基金。", "TARGET_DATE"),
        ("本基金是目标风险基金。", "TARGET_RISK"),
    ],
)
def test_explicit_fund_identity_declaration_is_sufficient(text, expected):
    assert v3([ev("investment_objective", text)]).strategy.value == expected


@pytest.mark.parametrize(
    "text",
    [
        "本基金对现金头寸采用主动管理策略。",
        "本基金采用主动管理现金头寸的方法。",
        "本基金通过主动管理增强指数投资组合。",
    ],
)
def test_local_active_wording_does_not_create_conflict_with_enhanced_member(text):
    result = v3([member(), ev("formal_type", "股票型"), ev("investment_strategy", text)])
    assert (result.strategy.status, result.strategy.value) == ("CONFIRMED", "ENHANCED_INDEX")


def test_quote_filter_does_not_hide_independent_unquoted_positive_declaration():
    text = "资料中“本基金采用目标日期策略。”为引用。本基金采用目标风险策略。"
    assert v3([ev("investment_strategy", text)]).strategy.value == "TARGET_RISK"


def test_same_sentence_multiple_independent_adoptions_retain_real_conflict():
    text = "本基金采用完全复制法跟踪沪深300指数，并采用指数增强策略。"
    result = v3([ev("investment_strategy", text)])
    assert result.strategy.status == "CONFLICT"
    assert result.strategy.candidates == ("ENHANCED_INDEX", "PASSIVE_INDEX")


def test_default_v3_controlled_type_gate_excludes_unknown_and_index_types():
    policy = load_policy(rule_version="3.0.0")
    raw = policy.model_dump()
    for invalid in [("指数型-股票",), ("新类型",), ("股票型", "股票型")]:
        raw["active_non_index_types"] = invalid
        with pytest.raises(ValueError):
            type(policy).model_validate(raw)


@pytest.mark.parametrize("raw_field", ["benchmark", "业绩比较基准", "name", "投资范围"])
@pytest.mark.parametrize("field", ["investment_strategy", "investment_objective", "formal_type"])
def test_misnormalized_helper_fields_cannot_assert_strategy_or_tag(raw_field, field):
    raw = ev(field, "本基金采用目标风险策略和量化模型。其正式类型为目标日期基金。")
    raw = raw.model_copy(update={"raw_field": raw_field})
    result = v3([raw])
    assert result.strategy.status == "UNKNOWN"
    assert result.strategy_tags == ()
    assert result.strategy_tag_results["QUANTITATIVE"].evaluation_state == "NOT_EVALUATED"


def test_misnormalized_benchmark_cannot_complete_active_type_gate():
    bad_type = ev("formal_type", "股票型").model_copy(update={"raw_field": "benchmark"})
    result = v3([bad_type, ev("investment_strategy", "本基金采用主动管理策略。")])
    assert result.strategy.status == "UNKNOWN"


@pytest.mark.parametrize(
    "text",
    [
        "本基金采用主动管理策略并采用指数增强策略。",
        "本基金采用完全复制法跟踪沪深300指数并采用指数增强策略。",
    ],
)
def test_independent_adoptions_without_comma_preserve_conflict(text):
    result = v3([ev("formal_type", "股票型"), ev("investment_strategy", text)])
    assert result.strategy.status == "CONFLICT"


@pytest.mark.parametrize(
    "text",
    [
        "本基金采用非量化投资方法。",
        "本基金可以通过量化模型进行投资。",
        "本基金拒绝采用量化模型。",
    ],
)
def test_negative_or_optional_quantitative_method_is_not_adopted(text):
    result = v3([ev("investment_strategy", text)])
    assert result.strategy_tags == ()
    assert result.strategy_tag_results["QUANTITATIVE"].status == "UNKNOWN"


def test_explicit_target_date_and_risk_cannot_be_resolved_by_priority():
    result = v3(
        [
            ev("investment_strategy", "本基金采用目标日期策略。"),
            ev("investment_objective", "本基金采用目标风险策略。"),
        ]
    )
    assert (result.strategy.status, result.strategy.value) == ("CONFLICT", "UNKNOWN")
    assert result.strategy.candidates == ("TARGET_DATE", "TARGET_RISK")


@pytest.mark.parametrize(
    ("dataset", "text"),
    [
        ("fund_index_enhanced", "本基金采用完全复制法跟踪沪深300指数。"),
        ("fund_index_passive", "本基金采用指数增强策略。"),
    ],
)
def test_index_list_and_incompatible_official_index_declaration_conflict(dataset, text):
    result = v3([member(dataset), ev("investment_strategy", text)])
    assert (result.strategy.status, result.strategy.value) == ("CONFLICT", "UNKNOWN")
    assert result.strategy.candidates == ("ENHANCED_INDEX", "PASSIVE_INDEX")


@pytest.mark.parametrize(
    "prefix",
    [
        "本基金不采用目标日期策略，而",
        "其他基金采用目标日期策略，本基金",
        "本基金可采用目标日期策略，但本基金",
        "资料引用‘采用目标日期策略’，而本基金",
    ],
)
def test_review_independent_target_clause_keeps_its_own_context(prefix):
    raw = ev("investment_strategy", prefix + "采用目标风险策略。")
    result = v3([raw]).strategy
    assert (result.status, result.value) == ("CONFIRMED", "TARGET_RISK")
    assertion = next(e for e in result.evidence if e.rule_id == "STR020")
    assert assertion.required_observations == (raw,)
    assert "matched=" in assertion.rationale


@pytest.mark.parametrize("separator", ["，但", "，而", "，同时", "但"])
def test_review_tag_positive_and_negative_clauses_conflict(separator):
    raw = ev("investment_strategy", f"本基金采用量化模型{separator}不采用多因子模型。")
    result = v3([raw])
    tag = result.strategy_tag_results["QUANTITATIVE"]
    assert tag.status == "CONFLICT"
    assert result.strategy_tags == ()
    assert len(tag.evidence) == 2
    assert all(e.required_observations == (raw,) for e in tag.evidence)
    assert any("polarity=POSITIVE" in e.rationale for e in tag.evidence)
    assert any("polarity=NEGATIVE" in e.rationale for e in tag.evidence)
    assert "strategy_tags:QUANTITATIVE:CONFLICT" in result.review_items


@pytest.mark.parametrize(
    "prefix",
    [
        "其他基金采用多因子模型，本基金",
        "本基金可采用多因子模型，但本基金",
        "资料引用‘采用多因子模型’，而本基金",
    ],
)
def test_review_tag_positive_clause_is_independent_of_unrelated_context(prefix):
    result = v3([ev("investment_strategy", prefix + "采用量化模型。")])
    assert result.strategy_tags == ("QUANTITATIVE",)


@pytest.mark.parametrize(
    "text",
    [
        "本基金采用完全复制法跟踪沪深300指数，增强风险管理能力。",
        "本基金采用完全复制法跟踪沪深300指数并增强风险管理能力。",
        "本基金采用完全复制法跟踪沪深300指数，增强流动性管理。",
        "本基金采用完全复制法跟踪沪深300指数并主动增强客户服务能力。",
    ],
)
def test_review_unrelated_enhancement_does_not_change_passive_strategy(text):
    result = v3([ev("investment_strategy", text)]).strategy
    assert (result.status, result.value) == ("CONFIRMED", "PASSIVE_INDEX")
    assert "ENHANCED_INDEX" not in result.candidates


@pytest.mark.parametrize(
    "text",
    [
        "本基金通过复制沪深300指数，并主动增强获取超额收益。",
        "本基金通过复制沪深300指数并主动增强获取超额收益。",
        "本基金通过主动管理增强指数投资组合。",
    ],
)
def test_review_index_investment_enhancement_still_is_enhanced(text):
    result = v3([ev("investment_strategy", text)]).strategy
    assert (result.status, result.value) == ("CONFIRMED", "ENHANCED_INDEX")

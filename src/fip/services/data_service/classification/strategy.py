"""Conservative v3 joint strategy rules and independent quantitative tags.

Only saved Evidence is consumed here. Source adapters own membership validation,
identity resolution and freshness; this engine never fetches or withdraws facts.
"""

import json
import re
from collections.abc import Sequence

from .models import DimensionResult, Evidence, Status, StrategyTagResult
from .policy import ClassificationPolicy

RULES = {
    "ENHANCED_INDEX": ("STR001", 100),
    "PASSIVE_INDEX": ("STR002", 90),
    "TARGET_DATE": ("STR010", 80),
    "TARGET_RISK": ("STR020", 70),
    "ACTIVE": ("STR030", 60),
    "UNKNOWN": ("STR999", 0),
}
FORMAL_FIELDS = {"formal_type", "基金类型"}
STRATEGY_FIELDS = {"investment_strategy", "strategy", "投资策略"}
OBJECTIVE_FIELDS = {"investment_objective", "投资目标"}
DECLARATION_FIELDS = FORMAL_FIELDS | STRATEGY_FIELDS | OBJECTIVE_FIELDS
CONTEXT_FIELDS = DECLARATION_FIELDS | {
    "index_membership",
    "tracking_target",
    "benchmark",
    "strategy_hint",
}
QUANT_METHOD = re.compile(r"量化(?:模型|方法|投资|策略)?|多因子|因子模型|数量化|模型驱动")
ADOPTION = re.compile(r"采用|运用|使用|实施|坚持|通过|采取|进行")
NEGATION = re.compile(
    r"(?:不|未|没有|拒绝)(?:再|会|予以)?(?:采用|运用|使用|实施|进行|采取)"
    r"|并非|不是|不属于|^非|非(?:量化|多因子|目标日期|目标风险|指数|主动)"
)
OPTIONAL = re.compile(
    r"可(?:以|能)?(?:采用|运用|使用|实施|通过|进行|采取)"
    r"|可能|视情况|拟采用|计划采用|将考虑|若|如果|必要时|条件"
)
FOREIGN_SUBJECT = re.compile(
    r"其他基金|其它基金|别的基金|例如|举例|引用|据称|资料称|底层基金|现金头寸|现金管理|局部|部分资产"
)
QUOTED = re.compile(r'“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』|"[^"\n]*"|\'[^\'\n]*\'')


def _field(item: Evidence) -> str:
    return item.normalized_field or item.raw_field


def _disclosed_field(item: Evidence) -> bool:
    """A normalized label cannot promote a benchmark/name/scope into a disclosure."""
    return any(
        _field(item) in fields and item.raw_field in fields
        for fields in (FORMAL_FIELDS, STRATEGY_FIELDS, OBJECTIVE_FIELDS)
    )


def _sentences(text: str) -> list[str]:
    # Remove quotations before splitting: a quoted full stop cannot escape its quote.
    return [
        part.strip() for part in re.split(r"[。！？!?；;\n]", QUOTED.sub("", text)) if part.strip()
    ]


def _context(sentence: str) -> str:
    if OPTIONAL.search(sentence) or FOREIGN_SUBJECT.search(sentence):
        return "IGNORED"
    return "NEGATIVE" if NEGATION.search(sentence) else "POSITIVE"


def _adopts(sentence: str, method: str | re.Pattern[str]) -> bool:
    """Require the adoption verb to govern this method rather than another clause."""
    for match in re.finditer(method, sentence):
        verbs = list(ADOPTION.finditer(sentence[: match.start()]))
        if verbs:
            between = sentence[verbs[-1].end() : match.start()]
            if len(between) <= 40 and not re.search(
                r"[，,]|研究|关注|介绍|参考|探讨|了解|提及", between
            ):
                return True
    return False


def _membership(item: Evidence) -> str | None:
    """Accept only the positive, exact-scope identities emitted by the saved converter.

    Batch completeness is deliberately irrelevant to an observed positive member;
    it governs withdrawal outside this classifier. Inputs must already be scoped to
    the fund/share under classification by the caller.
    """
    if (
        _field(item) != "index_membership"
        or item.source != "AGGREGATOR"
        or item.raw_field != "基金代码"
        or not item.payload_ref
        or not re.fullmatch(r"[0-9]{6}", item.raw_value)
        or not item.locator
        or not item.locator.startswith("identity:")
    ):
        return None
    try:
        identity, _ = json.JSONDecoder().raw_decode(item.locator[len("identity:") :])
    except ValueError:
        return None
    if not isinstance(identity, dict):
        return None
    datasets = {
        "fund_index_enhanced": ("增强指数型", "ENHANCED_INDEX"),
        "fund_index_passive": ("被动指数型", "PASSIVE_INDEX"),
    }
    dataset = identity.get("dataset")
    if not isinstance(dataset, str) or dataset not in datasets:
        return None
    indicator, value = datasets[dataset]
    if (
        identity.get("adapter") != "AKSHARE"
        or identity.get("provider") != "EASTMONEY"
        or identity.get("function") != "fund_info_index_em"
        or identity.get("params") != {"symbol": "全部", "indicator": indicator}
        or identity.get("provider_fund_code") != item.raw_value
        or identity.get("raw_field") != item.raw_field
    ):
        return None
    return value


def _assertion(
    item: Evidence,
    *,
    rule: str,
    observations: tuple[Evidence, ...],
    rationale: str,
    status: Status = "CONFIRMED",
) -> Evidence:
    return item.model_copy(
        update={
            "rule_id": rule,
            "required_observations": observations,
            "assertion_status": status,
            "rationale": f"rule_version=3.0.0;enum_version=3.0.0;{rationale}",
        }
    )


def _declarations(item: Evidence, policy: ClassificationPolicy) -> list[tuple[str, str]]:
    """Keep sentence boundaries so separate exclusive declarations still conflict."""
    results = []
    field = _field(item)
    clauses = []
    for sentence in _sentences(item.raw_value):
        if _context(sentence) == "IGNORED":
            continue
        # A new adoption clause is independent; an index-copy clause followed by
        # local "并主动增强" stays together as one enhanced implementation.
        clauses.extend(
            re.split(
                r"[，,](?=(?:并|实际|本基金)*(?:采用|运用|使用|实施|采取))"
                r"|(?=并(?:采用|实施|运用)(?:指数增强策略|主动管理策略|主动投资策略))",
                sentence,
            )
        )
    for sentence in clauses:
        if _context(sentence) != "POSITIVE":
            continue
        formal = field in FORMAL_FIELDS
        if "目标日期" in sentence and (
            formal
            or _adopts(sentence, r"目标日期(?:策略|基金)")
            or re.search(r"本基金(?:为|是|属于)目标日期基金", sentence)
        ):
            results.append(("TARGET_DATE", sentence))
        if (
            "目标风险" in sentence
            and (
                formal
                or _adopts(sentence, r"目标风险(?:策略|基金)")
                or re.search(r"本基金(?:为|是|属于)目标风险基金", sentence)
            )
            or any(
                _adopts(sentence, re.escape(mechanism))
                for mechanism in policy.target_risk_mechanisms
            )
        ):
            results.append(("TARGET_RISK", sentence))
        if field not in STRATEGY_FIELDS:
            continue
        index_context = "指数" in sentence
        enhanced = index_context and "增强" in sentence and _adopts(sentence, r"指数|复制")
        if enhanced:
            results.append(("ENHANCED_INDEX", sentence))
        elif index_context and _adopts(sentence, r"复制|被动跟踪|被动投资"):
            results.append(("PASSIVE_INDEX", sentence))
        # Local enhancement is implementation, not a second fund-level ACTIVE assertion.
        if not enhanced and _adopts(sentence, r"主动管理|主动投资"):
            results.append(("ACTIVE", sentence))
    return results


def classify_strategy(
    evidence: Sequence[Evidence],
    policy: ClassificationPolicy,
) -> tuple[DimensionResult, set[str]]:
    assertions: list[tuple[str, Evidence]] = []
    hints: set[str] = set()
    hint_evidence = []
    relevant = []
    types = tuple(
        item
        for item in evidence
        if item.source != "NAME"
        and _disclosed_field(item)
        and _field(item) in FORMAL_FIELDS
        and item.raw_value in policy.active_non_index_types
    )
    for item in evidence:
        field = _field(item)
        if item.source == "NAME" or field == "name":
            values = {
                value
                for token, value in {
                    "指数": "PASSIVE_INDEX",
                    "增强": "ENHANCED_INDEX",
                    "目标日期": "TARGET_DATE",
                    "目标风险": "TARGET_RISK",
                }.items()
                if token in item.raw_value
            }
            if values:
                hints.update(values)
                hint_evidence.append(
                    _assertion(
                        item,
                        rule="NAME_STRATEGY",
                        observations=(item,),
                        status="CANDIDATE",
                        rationale="Name hint only; no factual contradiction or confirmed strategy",
                    )
                )
            continue
        if field not in CONTEXT_FIELDS:
            continue
        relevant.append(item)
        member = _membership(item)
        declarations = [(member, "valid positive index-list membership")] if member else []
        if _disclosed_field(item):
            declarations.extend(_declarations(item, policy))
        for value, snippet in declarations:
            observations: tuple[Evidence, ...] = (item,)
            if value == "ACTIVE":
                if not types:
                    continue
                observations = (*types, item)
            rule, priority = RULES[value]
            assertions.append(
                (
                    value,
                    _assertion(
                        item,
                        rule=rule,
                        observations=observations,
                        rationale=f"priority={priority};value={value};matched={snippet}",
                    ),
                )
            )
    values = {value for value, _ in assertions}
    conflict = len(values) > 1
    status: Status = (
        "CONFLICT" if conflict else "CONFIRMED" if values else "CANDIDATE" if hints else "UNKNOWN"
    )
    used = []
    for _, assertion in assertions:
        if conflict:
            suggested = next(value for value in policy.strategy_priority if value in values)
            assertion = assertion.model_copy(
                update={
                    "assertion_status": "CONFLICT",
                    "conflict_reason": "INCOMPATIBLE_EVIDENCE",
                    "rationale": (
                        f"{assertion.rationale};suggested_strategy={suggested};"
                        "priority is suggestion only"
                    ),
                }
            )
        used.append(assertion)
    used.extend(hint_evidence)
    # Helper/insufficient evidence remains traceable without inventing a source on empty input.
    covered = tuple(
        observation for assertion in used for observation in assertion.required_observations or ()
    )
    for item in relevant:
        if item not in covered:
            used.append(
                _assertion(
                    item,
                    rule="STR999",
                    observations=(item,),
                    status="UNKNOWN",
                    rationale=(
                        "priority=0;insufficient positive strategy evidence;"
                        "benchmark and hints are helpers only"
                    ),
                )
            )
    return DimensionResult(
        status=status,
        value=next(iter(values)) if len(values) == 1 else "UNKNOWN",
        candidates=tuple(sorted(hints | (values if conflict else set()))),
        evidence=tuple(used),
        evaluation_state="EVALUATED",
    ), ({f"strategy:{status}"} if status != "CONFIRMED" else set())


def classify_tags(
    evidence: Sequence[Evidence],
    policy: ClassificationPolicy,
) -> tuple[dict[str, StrategyTagResult], set[str]]:
    # The policy validates the versioned catalog; unknown methods never invent new tags.
    tags: dict[str, StrategyTagResult] = {}
    review = set()
    for tag in policy.strategy_tag_catalog:
        positive: list[Evidence] = []
        negative: list[Evidence] = []
        candidates: list[Evidence] = []
        evaluated = False
        for item in evidence:
            if item.source == "NAME" or _field(item) == "name":
                if "量化" in item.raw_value:
                    candidates.append(
                        _assertion(
                            item,
                            rule="TAG_QUANTITATIVE_NAME",
                            observations=(item,),
                            status="CANDIDATE",
                            rationale="Name hint only;tag_catalog_version=3.0.0",
                        )
                    )
                continue
            if (
                _field(item) not in STRATEGY_FIELDS
                or not _disclosed_field(item)
                or not item.raw_value.strip()
            ):
                continue
            evaluated = True
            for sentence in _sentences(item.raw_value):
                if not _adopts(sentence, QUANT_METHOD):
                    continue
                context = _context(sentence)
                if context == "IGNORED":
                    continue
                assertion = _assertion(
                    item,
                    rule="TAG_QUANTITATIVE",
                    observations=(item,),
                    status="CONFIRMED" if context == "POSITIVE" else "UNKNOWN",
                    rationale=f"tag_catalog_version=3.0.0;polarity={context};matched={sentence}",
                )
                (positive if context == "POSITIVE" else negative).append(assertion)
        conflict = bool(positive and negative)
        status: Status = (
            "CONFLICT"
            if conflict
            else "CONFIRMED"
            if positive
            else "CANDIDATE"
            if candidates
            else "UNKNOWN"
        )
        used = positive + negative + candidates
        if conflict:
            used = [
                item.model_copy(
                    update={
                        "assertion_status": "CONFLICT",
                        "conflict_reason": "INCOMPATIBLE_TAG_EVIDENCE",
                    }
                )
                for item in used
            ]
        tags[tag] = StrategyTagResult(
            status=status,
            value=tag if status == "CONFIRMED" else "UNKNOWN",
            candidates=(tag,) if status in {"CONFLICT", "CANDIDATE"} else (),
            evidence=tuple(used),
            evaluation_state="EVALUATED" if evaluated or candidates else "NOT_EVALUATED",
        )
        if status in {"CONFLICT", "CANDIDATE"}:
            review.add(f"strategy_tags:{tag}:{status}")
    return tags, review

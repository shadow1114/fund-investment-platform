"""Pure R1–R6 classification. No grouping, network, database or score access."""

import json
from collections.abc import Sequence
from datetime import datetime

from .models import DIMENSIONS, ClassificationSnapshot, DimensionResult, Evidence, Source, Status
from .policy import ClassificationPolicy

CATALOG = {
    "asset_class": (
        "EQUITY",
        "BOND",
        "MIXED",
        "MONEY_MARKET",
        "FOF",
        "REIT",
        "COMMODITY",
        "OTHER",
        "UNKNOWN",
    ),
    "strategy": (
        "TARGET_DATE",
        "TARGET_RISK",
        "ENHANCED_INDEX",
        "PASSIVE_INDEX",
        "QUANTITATIVE",
        "ACTIVE",
        "UNKNOWN",
    ),
    "geography": ("DOMESTIC", "US", "HK", "JP", "EUROPE", "GLOBAL", "MULTI_REGION", "UNKNOWN"),
    "product_structure": ("ETF", "ETF_LINKED", "LOF", "ORDINARY", "UNKNOWN"),
    "market_attributes": ("DOMESTIC", "CROSS_BORDER", "QDII", "UNKNOWN"),
}
DEFAULT_POLICY = ClassificationPolicy(
    catalog=CATALOG,
    formal_types={
        "股票型": "EQUITY",
        "债券型": "BOND",
        "混合型": "MIXED",
        "货币型": "MONEY_MARKET",
        "FOF": "FOF",
        "REIT": "REIT",
        "商品型": "COMMODITY",
    },
    strategy_priority=CATALOG["strategy"][:-1],
)
FIELD_DIMENSION = {
    "formal_type": "asset_class",
    "基金类型": "asset_class",
    "underlying_asset": "asset_class",
    "tracking_target": "strategy",
    "benchmark": "strategy",
    "strategy_hint": "strategy",
    "investment_strategy": "strategy",
    "investment_geography": "geography",
    **{d: d for d in DIMENSIONS},
}
RULE_IDS = {
    "asset_class": "R1",
    "strategy": "R2",
    "geography": "R3",
    "product_structure": "R4",
    "market_attributes": "R5",
}


def normalize_evidence(
    *,
    source: Source,
    field: str,
    value: str,
    classified_at: datetime,
    payload_ref: str | None = None,
    locator: str | None = None,
    raw_field: str | None = None,
) -> Evidence:
    if classified_at.utcoffset() is None:
        raise ValueError("classified_at must include timezone")
    return Evidence(
        source=source,
        rule_id="R6" if source == "NAME" else RULE_IDS.get(FIELD_DIMENSION.get(field, ""), "R6"),
        confidence=(
            "OFFICIAL_DOCUMENT"
            if source == "OFFICIAL"
            else "PUBLIC_AGGREGATOR"
            if source == "AGGREGATOR"
            else "NAME_HINT"
        ),
        classified_at=classified_at,
        raw_field=raw_field or field,
        normalized_field=field,
        raw_value=value,
        payload_ref=payload_ref,
        locator=locator,
    )


def _name_values(name: str, dimension: str) -> set[str]:
    hints = {
        "asset_class": {
            "股票": "EQUITY",
            "债券": "BOND",
            "混合": "MIXED",
            "货币": "MONEY_MARKET",
            "FOF": "FOF",
            "REIT": "REIT",
            "商品": "COMMODITY",
        },
        "strategy": {
            "增强": "ENHANCED_INDEX",
            "量化": "QUANTITATIVE",
            "指数": "PASSIVE_INDEX",
            "目标日期": "TARGET_DATE",
            "目标风险": "TARGET_RISK",
        },
        "geography": {"美国": "US", "全球": "GLOBAL", "日本": "JP", "港股": "HK"},
        "product_structure": {"ETF联接": "ETF_LINKED", "ETF": "ETF", "LOF": "LOF"},
        "market_attributes": {"QDII": "QDII"},
    }
    values = {v for k, v in hints[dimension].items() if k in name.upper()}
    if "ETF_LINKED" in values:
        values.discard("ETF")
    return values


def _incompatible(dimension: str, values: set[str]) -> bool:
    if dimension in ("asset_class", "product_structure"):
        return len(values) > 1
    if dimension == "strategy":
        # Quantitative is an implementation technique; passive is a generic index clue.
        return bool(
            {"TARGET_DATE", "TARGET_RISK"} <= values
            or {"ACTIVE", "PASSIVE_INDEX"} <= values
            and "ENHANCED_INDEX" not in values
            or values.intersection({"TARGET_DATE", "TARGET_RISK"})
            and values.intersection({"PASSIVE_INDEX", "ENHANCED_INDEX"})
        )
    if dimension == "geography":
        return ("DOMESTIC" in values and bool(values - {"DOMESTIC"})) or {
            "GLOBAL",
            "MULTI_REGION",
        } <= values
    return {"DOMESTIC", "CROSS_BORDER"} <= values


def _index_query_context(item: Evidence) -> bool:
    """Read the saved identity only; never import or call a source adapter."""
    locator = item.locator or ""
    datasets = {"fund_index_passive", "fund_index_enhanced", "fund_info_index_em"}
    if locator.startswith("identity:"):
        try:
            identity, _ = json.JSONDecoder().raw_decode(locator[len("identity:") :])
        except ValueError:
            return False
        return isinstance(identity, dict) and (
            identity.get("function") == "fund_info_index_em" or identity.get("dataset") in datasets
        )
    return any(locator.startswith(f"dataset:{dataset};") for dataset in datasets)


def classify(
    evidence: Sequence[Evidence],
    *,
    classified_at: datetime,
    policy: ClassificationPolicy | None = None,
) -> ClassificationSnapshot:
    if classified_at.utcoffset() is None:
        raise ValueError("classified_at must include timezone")
    policy = policy or DEFAULT_POLICY
    dimensions: dict[str, DimensionResult] = {}
    review: set[str] = set()
    for dimension in DIMENSIONS:
        if dimension not in policy.active_dimensions:
            dimensions[dimension] = DimensionResult(
                status="UNKNOWN",
                value=("UNKNOWN",)
                if dimension in ("geography", "market_attributes")
                else "UNKNOWN",
                evaluation_state="NOT_EVALUATED",
            )
            continue
        values: set[str] = set()
        candidates: set[str] = set()
        used: list[Evidence] = []
        for item in evidence:
            if item.source == "NAME" or (item.normalized_field or item.raw_field) == "name":
                hints = _name_values(item.raw_value, dimension) & set(policy.catalog[dimension])
                candidates.update(hints)
                if hints:
                    used.append(item)
                continue
            if (
                policy.rule_version == "3.0.0"
                and (item.normalized_field or item.raw_field) == "tracking_target"
            ):
                if dimension != "asset_class":
                    continue
                if _index_query_context(item):
                    used.append(item)
                    review.add("asset_class:INDEX_QUERY_CONTEXT")
                    continue
                entry = policy.index_assets.get(item.raw_value)
                if entry is None:
                    used.append(item)
                    review.add("asset_class:UNRECOGNIZED")
                    continue
                values.add(entry.asset_class)
                used.append(
                    item.model_copy(
                        update={
                            "rule_id": "ASSET_INDEX_EXACT",
                            "assertion_status": "CONFIRMED",
                            "required_observations": (item,),
                            "rationale": (
                                f"index_asset_mapping_version={policy.index_asset_mapping_version};"
                                f"provider={entry.provider};reference={entry.reference};"
                                f"verification={entry.verification};asset_class={entry.asset_class}"
                            ),
                        }
                    )
                )
                continue
            if FIELD_DIMENSION.get(item.normalized_field or item.raw_field) != dimension:
                continue
            used.append(item)
            if (item.normalized_field or item.raw_field) == "benchmark":
                continue
            value = (
                policy.formal_types.get(item.raw_value, "UNKNOWN")
                if (item.normalized_field or item.raw_field) in ("formal_type", "基金类型")
                else item.raw_value.strip().upper()
            )
            if value == "OTHER" and (item.normalized_field or item.raw_field) not in (
                "formal_type",
                "基金类型",
            ):
                review.add(f"{dimension}:UNRECOGNIZED")
                continue
            if value in policy.catalog[dimension] and value != "UNKNOWN":
                values.add(value)
            elif value != "UNKNOWN" or item.raw_value != "UNKNOWN":
                review.add(f"{dimension}:UNRECOGNIZED")
        if dimension == "market_attributes" and "QDII" in values:
            values.add("CROSS_BORDER")
        explicit = {
            item.raw_value.strip().upper()
            for item in used
            if (item.normalized_field or item.raw_field) in ("strategy", "investment_strategy")
        }
        exclusive = explicit - {"QUANTITATIVE", "UNKNOWN"}
        conflict = (
            _incompatible(dimension, values)
            or dimension == "strategy"
            and (len(exclusive) > 1 or "PASSIVE_INDEX" in explicit and "ENHANCED_INDEX" in values)
        )
        if conflict:
            used = [
                item.model_copy(update={"conflict_reason": "INCOMPATIBLE_EVIDENCE"})
                for item in used
            ]
            candidates.update(values)
            values.clear()
        elif dimension == "geography" and len(values - {"GLOBAL", "MULTI_REGION"}) > 1:
            if "GLOBAL" not in values:
                values.add("MULTI_REGION")
        status: Status = (
            "CONFLICT"
            if conflict
            else "CONFIRMED"
            if values
            else "CANDIDATE"
            if candidates
            else "UNKNOWN"
        )
        final: str | tuple[str, ...] = "UNKNOWN"
        if dimension in ("geography", "market_attributes"):
            final = tuple(sorted(values)) if values else ("UNKNOWN",)
        elif values:
            final = (
                next(v for v in policy.strategy_priority if v in values)
                if dimension == "strategy"
                else sorted(values)[0]
            )
        if status != "CONFIRMED":
            review.add(f"{dimension}:{status}")
        dimensions[dimension] = DimensionResult(
            status=status,
            value=final,
            candidates=tuple(sorted(candidates)),
            evidence=tuple(used),
            evaluation_state="EVALUATED" if policy.rule_version == "3.0.0" else None,
        )
    return ClassificationSnapshot(
        rule_version=policy.rule_version,
        enum_version=policy.enum_version,
        review_items=tuple(sorted(review)),
        asset_class=dimensions["asset_class"],
        strategy=dimensions["strategy"],
        geography=dimensions["geography"],
        product_structure=dimensions["product_structure"],
        market_attributes=dimensions["market_attributes"],
    )

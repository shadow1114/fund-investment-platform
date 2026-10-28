"""Pure compatibility projection; benchmark and eligibility checks remain downstream."""

from dataclasses import dataclass

from .models import ClassificationSnapshot


@dataclass(frozen=True)
class LegacyProjection:
    value: str | None
    reason: str | None
    scheme: str = "FIP_INTERNAL_L2"
    mapping_version: str = "FIP_CLASSIFICATION_TO_L2_V1"


def project_legacy(
    snapshot: ClassificationSnapshot,
    *,
    grouping_confirmed: bool,
    verified_tag_rejections: frozenset[str] = frozenset(),
) -> LegacyProjection:
    if not grouping_confirmed:
        return LegacyProjection(None, "PRODUCT_GROUPING_UNCONFIRMED")
    if snapshot.asset_class.status != "CONFIRMED":
        return LegacyProjection(None, "ASSET_CLASS_UNCONFIRMED")
    if snapshot.strategy.status == "CONFLICT":
        return LegacyProjection(None, "STRATEGY_CONFLICT")
    if snapshot.rule_version == "3.0.0" and snapshot.strategy.status != "CONFIRMED":
        return LegacyProjection(None, "STRATEGY_UNCONFIRMED")
    asset, strategy = snapshot.asset_class.value, snapshot.strategy.value
    if asset == "BOND":
        return LegacyProjection("BOND", None)
    if asset == "MIXED":
        return LegacyProjection("HYBRID", None)
    if asset == "EQUITY" and snapshot.strategy.status == "CONFIRMED":
        if strategy == "ACTIVE":
            if snapshot.rule_version == "3.0.0":
                tag = (snapshot.strategy_tag_results or {}).get("QUANTITATIVE")
                # UNKNOWN alone includes absence of information. Admission requires
                # an explicit evaluated negative assertion or an audited rejection.
                negative = (
                    tag is not None
                    and tag.evaluation_state == "EVALUATED"
                    and (
                        tag.manual_action == "REJECT"
                        and "QUANTITATIVE" in verified_tag_rejections
                        or bool(tag.evidence)
                        and all(
                            e.rule_id == "TAG_QUANTITATIVE"
                            and "polarity=NEGATIVE" in (e.rationale or "")
                            and bool(e.required_observations)
                            for e in tag.evidence
                        )
                    )
                )
                if not negative or tag is None or tag.status != "UNKNOWN":
                    return LegacyProjection(None, "V3_ACTIVE_TAG_ADMISSION_UNVERIFIED")
            return LegacyProjection("ACTIVE_EQUITY", None)
        if strategy == "PASSIVE_INDEX":
            return LegacyProjection("PASSIVE_EQUITY", None)
    return LegacyProjection(None, "UNSUPPORTED_COMBINATION")

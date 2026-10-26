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
    snapshot: ClassificationSnapshot, *, grouping_confirmed: bool
) -> LegacyProjection:
    if not grouping_confirmed:
        return LegacyProjection(None, "PRODUCT_GROUPING_UNCONFIRMED")
    if snapshot.asset_class.status != "CONFIRMED":
        return LegacyProjection(None, "ASSET_CLASS_UNCONFIRMED")
    if snapshot.strategy.status == "CONFLICT":
        return LegacyProjection(None, "STRATEGY_CONFLICT")
    asset, strategy = snapshot.asset_class.value, snapshot.strategy.value
    if asset == "BOND":
        return LegacyProjection("BOND", None)
    if asset == "MIXED":
        return LegacyProjection("HYBRID", None)
    if asset == "EQUITY" and snapshot.strategy.status == "CONFIRMED":
        if strategy == "ACTIVE":
            return LegacyProjection("ACTIVE_EQUITY", None)
        if strategy == "PASSIVE_INDEX":
            return LegacyProjection("PASSIVE_EQUITY", None)
    return LegacyProjection(None, "UNSUPPORTED_COMBINATION")

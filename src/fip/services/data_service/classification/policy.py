"""Policy I/O is intentionally outside the pure classifier."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import (
    DIMENSIONS,
    CURRENT_ACTIVE_DIMENSIONS,
    CURRENT_CATALOG,
    CURRENT_PAUSED_DIMENSIONS,
    CURRENT_STRATEGY_TAGS,
)

CURRENT_POLICY_PATH = Path("config/policy/classification/current.yaml")


class IndexAssetEntry(BaseModel):
    """Literal target mapping; references identify curation, not a live verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    asset_class: str
    provider: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    verification: Literal["CURATED_NOT_LIVE_VERIFIED"]


class ClassificationPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scheme: str = "FIP_CLASSIFICATION"
    catalog: dict[str, tuple[str, ...]]
    formal_types: dict[str, str]
    strategy_priority: tuple[str, ...]
    active_dimensions: tuple[str, ...] = DIMENSIONS
    paused_dimensions: tuple[str, ...] = ()
    strategy_tag_catalog: tuple[str, ...] = ()
    active_non_index_types: tuple[str, ...] = ()
    target_risk_mechanisms: tuple[str, ...] = ()
    index_asset_mapping_source: str | None = None
    index_assets: dict[str, IndexAssetEntry] = Field(default_factory=dict)

    @model_validator(mode="after")
    def semantic_contract(self) -> "ClassificationPolicy":
        expected = {
            "asset_class",
            "strategy",
            "geography",
            "product_structure",
            "market_attributes",
        }
        if set(self.catalog) != expected or any(
            "UNKNOWN" not in values or len(values) != len(set(values))
            for values in self.catalog.values()
        ):
            raise ValueError("Classification catalog must cover all five dimensions uniquely")
        if not set(self.formal_types.values()) <= set(self.catalog["asset_class"]):
            raise ValueError("Formal type mapping contains an unknown asset value")
        if self.index_assets and (
            not self.index_asset_mapping_source
            or not self.index_asset_mapping_source.strip()
            or any(
                not target.strip()
                or entry.asset_class not in set(self.catalog["asset_class"]) - {"UNKNOWN"}
                or not entry.provider.strip()
                or not entry.reference.strip()
                for target, entry in self.index_assets.items()
            )
        ):
            raise ValueError("Index assets require a mapping source, known assets and provenance")
        if set(self.strategy_priority) != set(self.catalog["strategy"]) - {"UNKNOWN"} or len(
            self.strategy_priority
        ) != len(set(self.strategy_priority)):
            raise ValueError("Strategy priority must cover each known strategy once")
        if any(
            name not in self.formal_types or self.formal_types[name] == "UNKNOWN" or "指数" in name
            for name in self.active_non_index_types
        ) or len(self.active_non_index_types) != len(set(self.active_non_index_types)):
            raise ValueError("Active type gate requires unique controlled non-index formal types")
        if any(not value.strip() for value in self.target_risk_mechanisms) or len(
            self.target_risk_mechanisms
        ) != len(set(self.target_risk_mechanisms)):
            raise ValueError("Target-risk mechanisms must be nonempty unique declarations")
        if self.scheme != "FIP_CLASSIFICATION":
            raise ValueError("Classification policy must use the single current scheme")
        if (
            self.active_dimensions != CURRENT_ACTIVE_DIMENSIONS
            or self.paused_dimensions != CURRENT_PAUSED_DIMENSIONS
        ):
            raise ValueError("Current policy requires the active classification dimensions")
        if self.catalog != CURRENT_CATALOG:
            raise ValueError("Current dimension catalogs do not match the classification contract")
        if self.strategy_tag_catalog != CURRENT_STRATEGY_TAGS:
            raise ValueError("Current strategy tag catalog must contain QUANTITATIVE once")
        return self


def load_policy(path: Path | None = None) -> ClassificationPolicy:
    path = path or CURRENT_POLICY_PATH
    policy = ClassificationPolicy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    return policy

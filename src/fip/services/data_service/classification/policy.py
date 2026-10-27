"""Policy I/O is intentionally outside the pure classifier."""

from pathlib import Path
from types import MappingProxyType

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from .models import (
    DIMENSIONS,
    V3_ACTIVE_DIMENSIONS,
    V3_CATALOG,
    V3_PAUSED_DIMENSIONS,
    V3_STRATEGY_TAGS,
)

# Append-only registrations. Default runtime selection remains v1 until rollout.
POLICY_REGISTRY = MappingProxyType(
    {
        ("FIP_CLASSIFICATION_V1", "1.0.0", "1.0.0"): Path("config/policy/classification/v1.yaml"),
        ("FIP_CLASSIFICATION_V1", "3.0.0", "3.0.0"): Path("config/policy/classification/v3.yaml"),
    }
)


class ClassificationPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scheme: str = "FIP_CLASSIFICATION_V1"
    rule_version: str = "1.0.0"
    enum_version: str = "1.0.0"
    catalog: dict[str, tuple[str, ...]]
    formal_types: dict[str, str]
    strategy_priority: tuple[str, ...]
    active_dimensions: tuple[str, ...] = DIMENSIONS
    paused_dimensions: tuple[str, ...] = ()
    strategy_tag_catalog: tuple[str, ...] = ()

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
        if set(self.strategy_priority) != set(self.catalog["strategy"]) - {"UNKNOWN"} or len(
            self.strategy_priority
        ) != len(set(self.strategy_priority)):
            raise ValueError("Strategy priority must cover each known strategy once")
        if self.rule_version == "3.0.0" or self.enum_version == "3.0.0":
            if (self.scheme, self.rule_version, self.enum_version) != (
                "FIP_CLASSIFICATION_V1",
                "3.0.0",
                "3.0.0",
            ):
                raise ValueError("Invalid v3 scheme or version pair")
            if (
                self.active_dimensions != V3_ACTIVE_DIMENSIONS
                or self.paused_dimensions != V3_PAUSED_DIMENSIONS
            ):
                raise ValueError("V3 requires two active and three paused dimensions")
            if self.catalog != V3_CATALOG:
                raise ValueError("V3 dimension catalogs must match their registered enum version")
            if self.strategy_tag_catalog != V3_STRATEGY_TAGS:
                raise ValueError("V3 strategy tag catalog must contain QUANTITATIVE once")
        return self


def load_policy(
    path: Path | None = None,
    *,
    rule_version: str | None = None,
    enum_version: str | None = None,
) -> ClassificationPolicy:
    requested = (
        "FIP_CLASSIFICATION_V1",
        rule_version or "1.0.0",
        enum_version or rule_version or "1.0.0",
    )
    if path is None:
        if requested not in POLICY_REGISTRY:
            raise ValueError("Unsupported classification policy version")
        path = POLICY_REGISTRY[requested]
    policy = ClassificationPolicy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    identity = (policy.scheme, policy.rule_version, policy.enum_version)
    if identity not in POLICY_REGISTRY or (
        (rule_version is not None or enum_version is not None) and identity != requested
    ):
        raise ValueError("Unsupported classification policy version")
    return policy

"""Policy I/O is intentionally outside the pure classifier."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator


class ClassificationPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scheme: str = "FIP_CLASSIFICATION_V1"
    rule_version: str = "1.0.0"
    enum_version: str = "1.0.0"
    catalog: dict[str, tuple[str, ...]]
    formal_types: dict[str, str]
    strategy_priority: tuple[str, ...]

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
        return self


def load_policy(path: Path = Path("config/policy/classification/v1.yaml")) -> ClassificationPolicy:
    policy = ClassificationPolicy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if (policy.scheme, policy.rule_version, policy.enum_version) != (
        "FIP_CLASSIFICATION_V1",
        "1.0.0",
        "1.0.0",
    ):
        raise ValueError("Unsupported classification policy version")
    return policy

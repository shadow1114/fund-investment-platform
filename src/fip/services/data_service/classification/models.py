"""Versioned JSON contract. Confidence is an evidence grade, never probability."""

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

DIMENSIONS = ("asset_class", "strategy", "geography", "product_structure", "market_attributes")
Status = Literal["CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"]
Source = Literal["OFFICIAL", "AGGREGATOR", "NAME"]
EvaluationState = Literal["NOT_EVALUATED", "EVALUATED", "PAUSED"]
V3_ACTIVE_DIMENSIONS = ("asset_class", "strategy")
V3_PAUSED_DIMENSIONS = ("geography", "product_structure", "market_attributes")
V3_STRATEGIES = (
    "ACTIVE",
    "PASSIVE_INDEX",
    "ENHANCED_INDEX",
    "TARGET_DATE",
    "TARGET_RISK",
    "UNKNOWN",
)
V3_STRATEGY_TAGS = ("QUANTITATIVE",)
V3_CATALOG = MappingProxyType(
    {
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
        "strategy": V3_STRATEGIES,
        "geography": ("DOMESTIC", "US", "HK", "JP", "EUROPE", "GLOBAL", "MULTI_REGION", "UNKNOWN"),
        "product_structure": ("ETF", "ETF_LINKED", "LOF", "ORDINARY", "UNKNOWN"),
        "market_attributes": ("DOMESTIC", "CROSS_BORDER", "QDII", "UNKNOWN"),
    }
)


class _AdditiveContract(BaseModel):
    """Absent new metadata must not change legacy JSON or semantic hashes."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    _optional_metadata: ClassVar[tuple[str, ...]] = ()

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        result: dict[str, object] = handler(self)
        for name in self._optional_metadata:
            if getattr(self, name) is None:
                result.pop(name, None)
        return result


class Evidence(_AdditiveContract):
    _optional_metadata = ("required_observations", "assertion_status", "rationale")
    source: Source
    rule_id: str
    confidence: Literal["OFFICIAL_DOCUMENT", "PUBLIC_AGGREGATOR", "NAME_HINT"]
    classified_at: datetime
    raw_field: str
    normalized_field: str | None = None
    raw_value: str
    payload_ref: str | None = None
    locator: str | None = None
    conflict_reason: str | None = None
    # Joint assertions retain the immutable raw Evidence inputs and all locators.
    # There is no separate observation identity/fact store in the v1 baseline.
    required_observations: tuple["Evidence", ...] | None = None
    assertion_status: Status | None = None
    rationale: str | None = None


class DimensionResult(_AdditiveContract):
    _optional_metadata: ClassVar[tuple[str, ...]] = (
        "evaluation_state",
        "carried_from_revision_id",
        "source_rule_version",
        "source_enum_version",
    )
    status: Status
    value: str | tuple[str, ...] = "UNKNOWN"
    candidates: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    evaluation_state: EvaluationState | None = None
    carried_from_revision_id: int | None = None
    source_rule_version: str | None = None
    source_enum_version: str | None = None

    @model_validator(mode="after")
    def unevaluated_placeholder(self) -> "DimensionResult":
        if self.evaluation_state == "NOT_EVALUATED" and (
            self.status != "UNKNOWN"
            or self.value not in ("UNKNOWN", ("UNKNOWN",), ())
            or self.candidates
            or self.evidence
        ):
            raise ValueError("NOT_EVALUATED results must be empty UNKNOWN placeholders")
        provenance = (
            self.carried_from_revision_id,
            self.source_rule_version,
            self.source_enum_version,
        )
        if self.evaluation_state == "PAUSED" or any(item is not None for item in provenance):
            if (
                self.carried_from_revision_id is None
                or self.carried_from_revision_id <= 0
                or not self.source_rule_version
                or not self.source_enum_version
            ):
                raise ValueError("Historical carry requires a revision and both source versions")
        return self

    @property
    def is_evaluated(self) -> bool:
        """Legacy facts retain their semantics; paused/placeholders are not current UNKNOWNs."""
        return self.evaluation_state in (None, "EVALUATED")


class StrategyTagResult(DimensionResult):
    """Independent tag assertion; a missing legacy result is represented by None."""

    evaluation_state: Literal["NOT_EVALUATED", "EVALUATED"] = "NOT_EVALUATED"
    _optional_metadata: ClassVar[tuple[str, ...]] = (
        *DimensionResult._optional_metadata,
        "manual_action",
    )
    manual_action: Literal["CONFIRM", "REJECT"] | None = None

    @model_validator(mode="after")
    def evidence_bearing_assertion(self) -> "StrategyTagResult":
        if self.status != "UNKNOWN" and not self.evidence:
            raise ValueError("Tag assertions require evidence; absent evidence is UNKNOWN")
        return self


class ClassificationSnapshot(_AdditiveContract):
    _optional_metadata = (
        "strategy_tag_results",
        "strategy_tags",
        "observations",
        "source_diagnostics",
    )
    scheme: Literal["FIP_CLASSIFICATION_V1"] = "FIP_CLASSIFICATION_V1"
    rule_version: str = "1.0.0"
    enum_version: str = "1.0.0"
    asset_class: DimensionResult
    strategy: DimensionResult
    geography: DimensionResult
    product_structure: DimensionResult
    market_attributes: DimensionResult
    review_items: tuple[str, ...] = ()
    strategy_tag_results: Mapping[str, StrategyTagResult] | None = None
    strategy_tags: tuple[str, ...] | None = None
    # Raw observations include explicit empty values, even when no assertion uses them.
    observations: tuple[Evidence, ...] | None = None
    source_diagnostics: tuple[str, ...] | None = None

    @field_validator("strategy_tag_results")
    @classmethod
    def freeze_tag_results(
        cls, value: Mapping[str, StrategyTagResult] | None
    ) -> Mapping[str, StrategyTagResult] | None:
        # Copy before freezing so callers cannot mutate the snapshot through an input alias.
        return MappingProxyType(dict(value)) if value is not None else None

    @field_serializer("strategy_tag_results")
    def serialize_tag_results(
        self, value: Mapping[str, StrategyTagResult] | None
    ) -> dict[str, StrategyTagResult] | None:
        return dict(value) if value is not None else None

    @model_validator(mode="after")
    def versioned_extensions(self) -> "ClassificationSnapshot":
        if "3.0.0" in (self.rule_version, self.enum_version):
            if (self.rule_version, self.enum_version) != ("3.0.0", "3.0.0"):
                raise ValueError("V3 snapshots require the registered 3.0.0 rule/enum version pair")
            for name, catalog in V3_CATALOG.items():
                result = getattr(self, name)
                values = (result.value,) if isinstance(result.value, str) else result.value
                if not set((*values, *result.candidates)) <= set(catalog):
                    raise ValueError(f"Invalid v3 {name} enum values")
            for name in V3_ACTIVE_DIMENSIONS:
                if getattr(self, name).evaluation_state == "PAUSED":
                    raise ValueError("Active dimensions cannot be PAUSED")
            for name in V3_PAUSED_DIMENSIONS:
                if getattr(self, name).evaluation_state not in ("PAUSED", "NOT_EVALUATED"):
                    raise ValueError(
                        "V3 paused dimensions require PAUSED or NOT_EVALUATED metadata"
                    )
            if self.strategy_tag_results is not None and not set(self.strategy_tag_results) <= set(
                V3_STRATEGY_TAGS
            ):
                raise ValueError("Invalid v3 strategy tag catalog")
        if self.strategy_tag_results is None:
            if self.strategy_tags is not None:
                raise ValueError("Strategy tags require evidence-bearing tag results")
            return self
        for tag, result in self.strategy_tag_results.items():
            if result.status == "CONFIRMED" and (
                result.value != tag or not result.evidence or result.evaluation_state != "EVALUATED"
            ):
                raise ValueError("Confirmed tags require matching values and evaluated evidence")
            if result.status != "CONFIRMED" and result.value != "UNKNOWN":
                raise ValueError("Unconfirmed tags cannot contain final values")
            if not set(result.candidates) <= {tag}:
                raise ValueError("Tag candidates must match their catalog entry")
        confirmed = tuple(
            sorted(
                tag
                for tag, result in self.strategy_tag_results.items()
                if result.status == "CONFIRMED"
            )
        )
        if self.strategy_tags is not None and self.strategy_tags != confirmed:
            raise ValueError("Strategy tags must project only CONFIRMED results")
        object.__setattr__(self, "strategy_tags", confirmed)
        return self

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

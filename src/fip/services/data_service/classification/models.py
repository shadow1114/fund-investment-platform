"""Versioned JSON contract. Confidence is an evidence grade, never probability."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DIMENSIONS = ("asset_class", "strategy", "geography", "product_structure", "market_attributes")
Status = Literal["CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"]
Source = Literal["OFFICIAL", "AGGREGATOR", "NAME"]


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
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


class DimensionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Status
    value: str | tuple[str, ...] = "UNKNOWN"
    candidates: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()


class ClassificationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scheme: Literal["FIP_CLASSIFICATION_V1"] = "FIP_CLASSIFICATION_V1"
    rule_version: str = "1.0.0"
    enum_version: str = "1.0.0"
    asset_class: DimensionResult
    strategy: DimensionResult
    geography: DimensionResult
    product_structure: DimensionResult
    market_attributes: DimensionResult
    review_items: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

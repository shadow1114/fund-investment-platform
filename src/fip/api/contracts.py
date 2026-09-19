from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from fip.api.schemas import SuccessEnvelopeModel


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    api_version: str = "v1"
    request_id: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SuccessEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: Any
    meta: ResponseMeta
    error: None = None


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: None = None
    error: ErrorBody
    meta: ResponseMeta


def success(data: Any, *, request_id: str | None = None, **meta: Any) -> dict[str, Any]:
    if meta.get("as_of_date") is None:
        meta["as_of_date"] = date.today().isoformat()
    meta.setdefault("data_version", "api-v1")
    meta.setdefault("versions", {})
    meta.setdefault("is_point_in_time", False)
    meta.setdefault(
        "availability_quality_distribution",
        {"EXACT": 0.0, "DERIVED": 0.0, "INFERRED": 0.0},
    )
    return SuccessEnvelopeModel.model_validate(
        {
            "data": data,
            "meta": ResponseMeta(request_id=request_id, **meta).model_dump(mode="json"),
            "error": None,
        }
    ).model_dump(mode="json")

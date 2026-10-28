"""Canonical snapshot hashing for fund ingestion previews."""

import hashlib
import json
from typing import Any


def snapshot_hash(dataset: str, scope: dict[str, Any], members: list[dict[str, Any]]) -> str:
    canonical_scope = dict(scope)
    if canonical_scope.get("type") == "SELECTED":
        canonical_scope["fund_ids"] = sorted(set(canonical_scope["fund_ids"]))
    filters = canonical_scope.get("filters")
    if isinstance(filters, dict):
        canonical_scope["filters"] = {
            key: sorted(set(value)) if isinstance(value, list) else value
            for key, value in filters.items()
            if value is not None
        }
    canonical_members = sorted(
        json.dumps(member, sort_keys=True, separators=(",", ":")) for member in members
    )
    data = json.dumps(
        [dataset, canonical_scope, canonical_members], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(data.encode()).hexdigest()

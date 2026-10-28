"""Registered API catalogs; selecting a version never changes runtime defaults."""

from functools import lru_cache

from fip.api.errors import InvalidQueryError
from fip.services.data_service.classification.policy import ClassificationPolicy, load_policy


@lru_cache
def get_classification_policy(
    rule_version: str | None = None, enum_version: str | None = None
) -> ClassificationPolicy:
    selected = rule_version or enum_version or "1.0.0"
    try:
        return load_policy(rule_version=selected, enum_version=enum_version or selected)
    except ValueError as exc:
        raise InvalidQueryError(str(exc)) from exc

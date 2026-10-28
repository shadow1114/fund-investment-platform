"""Registered API catalogs; selecting a version never changes runtime defaults."""

from fip.api.errors import InvalidQueryError
from fip.services.data_service.classification.policy import ClassificationPolicy, load_policy


def get_classification_policy() -> ClassificationPolicy:
    try:
        return load_policy()
    except ValueError as exc:
        raise InvalidQueryError(str(exc)) from exc

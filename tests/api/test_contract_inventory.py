from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fip.api.contract_registry import RESPONSE_COMPONENT_REGISTRY


def collect_operation_ids(paths: dict[str, Any], *, include_shared: bool = True) -> set[str]:
    operation_ids = {
        operation["operationId"]
        for path_item in paths.values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
        and "operationId" in operation
    }
    if not include_shared:
        operation_ids -= {"getSession", "getOperation"}
    return operation_ids


def test_every_nested_response_operation_has_a_registered_component() -> None:
    document = yaml.safe_load(
        (Path(__file__).parents[2] / "frontend/openapi/m17.yaml").read_text()
    )
    operation_ids = collect_operation_ids(document["paths"], include_shared=False)
    assert set(RESPONSE_COMPONENT_REGISTRY) == operation_ids
    schemas = document["components"]["schemas"]
    for component in RESPONSE_COMPONENT_REGISTRY.values():
        assert component in schemas


def test_shared_session_and_operation_components_remain_frozen() -> None:
    document = yaml.safe_load(
        (Path(__file__).parents[2] / "frontend/openapi/m17.yaml").read_text()
    )
    schemas = document["components"]["schemas"]
    assert schemas["SessionEnvelope"]["properties"]["data"]["$ref"].endswith("/Session")
    assert schemas["OperationEnvelope"]["properties"]["data"]["$ref"].endswith("/Operation")

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


def test_fund_company_options_contract_and_fund_list_query_fields_are_registered() -> None:
    document = yaml.safe_load(
        (Path(__file__).parents[2] / "frontend/openapi/m17.yaml").read_text()
    )
    operation_ids = collect_operation_ids(document["paths"], include_shared=False)
    assert "listFundManagementCompanies" in operation_ids
    assert RESPONSE_COMPONENT_REGISTRY["listFundManagementCompanies"] == (
        "FundManagementCompaniesEnvelope"
    )

    fund_list = document["paths"]["/api/v1/funds"]["get"]
    parameters = {}
    for item in fund_list["parameters"]:
        if "$ref" in item:
            component = item["$ref"].rsplit("/", 1)[-1]
            item = document["components"]["parameters"][component]
        parameters[item["name"]] = item
    assert {"fund_code", "fund_company", "sub_status", "asset_class", "page_size"} <= set(
        parameters
    )
    assert parameters["sub_status"]["schema"]["enum"] == ["开放"]
    assert parameters["sort"]["schema"]["enum"] == [
        "fund_code",
        "fund_name",
        "fund_company",
        "sub_status",
        "inception_date",
        "aum",
    ]

    schemas = document["components"]["schemas"]
    item = schemas["FundListItem"]
    assert {
        "share_class_id",
        "sub_status",
        "manager_ids",
    } <= set(item["required"])
    assert item["properties"]["fund_company"]["type"] == ["string", "null"]
    assert item["properties"]["fund_code"]["pattern"] == "^[0-9]{6}$"
    assert item["properties"]["sub_status"]["enum"] == ["开放", "UNKNOWN"]
    assert "subscription_status_source" in schemas["FundListMeta"]["required"]
    company_envelope = schemas["FundManagementCompaniesEnvelope"]
    assert (
        company_envelope["properties"]["data"]["items"]["$ref"]
        == "#/components/schemas/FundManagementCompany"
    )

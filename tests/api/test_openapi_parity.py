from pathlib import Path

import yaml
from fastapi.openapi.utils import get_openapi

from fip.api.app import create_app


def test_served_openapi_is_the_frozen_projection() -> None:
    frozen = yaml.safe_load((Path(__file__).parents[2] / "frontend/openapi/m17.yaml").read_text())
    served = create_app().openapi()
    assert served["openapi"] == frozen["openapi"]
    assert served["info"] == frozen["info"]
    assert served["paths"] == frozen["paths"]
    assert served["components"] == frozen["components"]


def test_source_fund_contract_matches_frozen_query_and_payload_projection() -> None:
    app = create_app(strict_contracts=True)
    source = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        routes=app.routes,
    )
    frozen = yaml.safe_load(
        (Path(__file__).parents[2] / "frontend/openapi/m17.yaml").read_text()
    )

    source_params = {
        parameter["name"]: parameter
        for parameter in source["paths"]["/api/v1/funds"]["get"]["parameters"]
    }
    frozen_params = {}
    for parameter in frozen["paths"]["/api/v1/funds"]["get"]["parameters"]:
        if "$ref" in parameter:
            name = parameter["$ref"].rsplit("/", 1)[-1]
            parameter = frozen["components"]["parameters"][name]
        frozen_params[parameter["name"]] = parameter

    assert {"fund_code", "fund_company", "sub_status", "sort"} <= set(source_params)
    assert source_params["fund_code"]["schema"]["anyOf"][0]["pattern"] == "^[0-9]{6}$"
    assert frozen_params["fund_code"]["schema"]["pattern"] == "^[0-9]{6}$"
    assert source_params["sub_status"]["schema"]["anyOf"][0]["const"] == "开放"
    assert frozen_params["sub_status"]["schema"]["enum"] == ["开放"]
    source_sort = source_params["sort"]["schema"]["anyOf"][0]["enum"]
    assert source_sort == frozen_params["sort"]["schema"]["enum"]

    source_company = source["paths"]["/api/v1/fund-management-companies"]["get"]
    frozen_company = frozen["paths"]["/api/v1/fund-management-companies"]["get"]
    assert source_company["operationId"] == frozen_company["operationId"]
    source_item = source["components"]["schemas"]["FundListPayloadModel"]["properties"]
    frozen_item = frozen["components"]["schemas"]["FundListItem"]["properties"]
    assert source_item["share_class_id"]["type"] == frozen_item["share_class_id"]["type"]
    assert source_item["fund_company"]["anyOf"][1]["type"] == "null"
    assert frozen_item["fund_company"]["type"] == ["string", "null"]
    source_sub_status = source_item["sub_status"]
    assert source_sub_status["enum"] == ["开放", "UNKNOWN"]
    assert frozen_item["sub_status"]["enum"] == ["开放", "UNKNOWN"]

    source_read = source["components"]["schemas"]["ReadPayloadModel"]["properties"]
    frozen_read = frozen["components"]["schemas"]["FundSummary"]["properties"]
    for field in ("share_class_id", "fund_code", "fund_company", "sub_status"):
        assert field not in source_read
        assert field not in frozen_read

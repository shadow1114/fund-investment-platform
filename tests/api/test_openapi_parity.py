from pathlib import Path

import yaml

from fip.api.app import create_app


def test_served_openapi_is_the_frozen_projection() -> None:
    frozen = yaml.safe_load((Path(__file__).parents[2] / "frontend/openapi/m17.yaml").read_text())
    served = create_app().openapi()
    assert served["openapi"] == frozen["openapi"]
    assert served["info"] == frozen["info"]
    assert served["paths"] == frozen["paths"]
    assert served["components"] == frozen["components"]

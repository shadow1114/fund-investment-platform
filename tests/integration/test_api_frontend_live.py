from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_generated_frontend_client_uses_runtime_api_base_adapter():
    generated = Path("frontend/src/api/generated/m17.ts").read_text()
    client = Path("frontend/src/api/client.ts").read_text()

    assert 'import { apiFetch } from "../client"' in generated
    assert "VITE_API_BASE_URL" in client
    assert "apiFetch<" in generated

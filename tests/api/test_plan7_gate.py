from pathlib import Path


def test_makefile_exposes_plan7_acceptance_gate() -> None:
    makefile = Path("Makefile").read_text()
    assert "plan7-check:" in makefile
    assert "test_response_contract_postgres.py" in makefile
    assert "frontend-check" in makefile.split("plan7-check:", 1)[1].split("\n\n", 1)[0]

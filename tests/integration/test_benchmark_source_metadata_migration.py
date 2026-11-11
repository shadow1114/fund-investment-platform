import pytest
from sqlalchemy import inspect, text

pytestmark = pytest.mark.integration


def test_0044_adds_request_metadata_and_allows_unfilled_seed_columns(db_engine):
    columns = {
        column["name"]: column
        for column in inspect(db_engine).get_columns("benchmark_index", schema="market")
    }
    for name in ("source", "api", "param"):
        assert name in columns
        assert columns[name]["nullable"] is True
    for name in ("provider_symbol", "currency", "index_type"):
        assert columns[name]["nullable"] is True

    with db_engine.connect() as connection:
        seeded = connection.execute(
            text(
                """
                SELECT display_name, provider_code
                FROM market.benchmark_index
                WHERE display_name IN ('中证医药', '中证800成长')
                """
            )
        ).all()
    assert {(row.display_name, row.provider_code) for row in seeded} == {
        ("中证医药", "000933"),
        ("中证800成长", "H30355"),
    }

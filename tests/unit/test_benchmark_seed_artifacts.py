import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

_ROOT = Path(__file__).parents[2]
_CSV_PATH = _ROOT / "docs/benchmark.csv"
_MIGRATION_PATH = _ROOT / "db/migrations/versions/0044_benchmark_source_request_metadata.py"
_MAPPING_PATH = _ROOT / "config/benchmark/component_provider_codes.yaml"


def _benchmark_rows() -> list[dict[str, str]]:
    with _CSV_PATH.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_csv_resolves_duplicate_lookup_names_to_selected_provider_codes():
    rows = _benchmark_rows()
    by_name: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_name[row["lookup_name"]].add(row["code"])

    assert by_name["中证医药"] == {"000933"}
    assert by_name["中证800成长"] == {"H30355"}
    assert by_name["中证综合债"] == {"H11009"}


def test_generated_seed_and_component_map_match_the_csv():
    rows = _benchmark_rows()
    unique_names: dict[str, dict[str, object]] = {}
    for row in rows:
        params = json.loads(row["query_param"]) if row["query_param"] else None
        current = {
            "provider_code": row["code"],
            "display_name": row["lookup_name"],
            "source": row["Source"],
            "api": row["api"] or None,
            "param": params,
        }
        existing = unique_names.setdefault(row["lookup_name"], current)
        assert existing == current

    migration = _MIGRATION_PATH.read_text(encoding="utf-8")
    match = re.search(r'_BENCHMARK_SEED_JSON = r"""(.*?)"""', migration, re.S)
    assert match is not None
    seed_rows = json.loads(match.group(1))
    assert seed_rows == list(unique_names.values())
    assert "INSERT INTO market.benchmark_index" in migration
    assert "db/seeds/benchmark_index_seed.sql" not in migration

    mapping = yaml.safe_load(_MAPPING_PATH.read_text(encoding="utf-8"))
    expected_mapping = {row["component_name"]: row["code"] for row in rows}
    assert mapping == {"component_to_provider_code": expected_mapping}

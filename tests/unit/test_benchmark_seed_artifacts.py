import csv
import json
import re
import runpy
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


def test_generated_seed_includes_csv_and_database_supplements():
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
    supplements = json.loads(
        (_ROOT / "config/benchmark/supplemental_indexes.json").read_text(encoding="utf-8")
    )
    assert seed_rows == list(unique_names.values()) + supplements
    assert len({row["display_name"] for row in seed_rows}) == len(seed_rows)
    assert "INSERT INTO market.benchmark_index" in migration
    assert "db/seeds/benchmark_index_seed.sql" not in migration

    mapping = yaml.safe_load(_MAPPING_PATH.read_text(encoding="utf-8"))
    actual_mapping = mapping["component_to_provider_code"]
    seed_codes = {row["provider_code"] for row in seed_rows}
    assert set(actual_mapping.values()) <= seed_codes
    assert actual_mapping["中证800ESG基准指数收益率"] == "931650"
    assert actual_mapping["上证国债指数收益率"] == "000012"


def test_generator_includes_manually_inserted_indexes():
    module = runpy.run_path(str(_ROOT / "tools/generate_benchmark_db_artifacts.py"))
    records, _ = module["_read_benchmarks"]()
    supplements = json.loads(
        (_ROOT / "config/benchmark/supplemental_indexes.json").read_text(encoding="utf-8")
    )
    assert len(supplements) == 6
    assert records[-6:] == supplements
    assert module["_build_migration"](records) == _MIGRATION_PATH.read_text(encoding="utf-8")


def test_generator_preserves_manual_additions_and_overrides(tmp_path):
    module = runpy.run_path(str(_ROOT / "tools/generate_benchmark_db_artifacts.py"))
    build = module["_build_mapping_yaml"]
    path = tmp_path / "mapping.yaml"
    path.write_text(
        "component_to_provider_code:\n  手工新增: '000012'\n  已有组成项: '000012'\n",
        encoding="utf-8",
    )
    build.__globals__["_MAPPING_PATH"] = path
    result = yaml.safe_load(build({"已有组成项": "000906", "新增CSV项": "000012"}))
    component_map = result["component_to_provider_code"]
    assert component_map["手工新增"] == "000012"
    assert component_map["已有组成项"] == "000012"
    assert component_map["新增CSV项"] == "000012"

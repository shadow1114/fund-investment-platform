from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_CSV_PATH = _ROOT / "docs/benchmark.csv"
_MIGRATION_PATH = _ROOT / "db/migrations/versions/0044_benchmark_source_request_metadata.py"
_MAPPING_PATH = _ROOT / "config/benchmark/component_provider_codes.yaml"
_CSV_FIELDS = ["component_name", "lookup_name", "code", "Source", "api", "query_param"]


def _read_benchmarks() -> tuple[list[dict[str, Any]], dict[str, str]]:
    with _CSV_PATH.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != _CSV_FIELDS:
            raise ValueError(f"Unexpected benchmark CSV fields: {reader.fieldnames}")
        rows = list(reader)

    by_name: OrderedDict[str, dict[str, Any]] = OrderedDict()
    component_map: OrderedDict[str, str] = OrderedDict()
    for row in rows:
        component_name = row["component_name"].strip()
        display_name = row["lookup_name"].strip()
        provider_code = row["code"].strip()
        source = row["Source"].strip()
        if not component_name or not display_name or not provider_code or not source:
            raise ValueError(f"Required benchmark field is empty: {row}")

        raw_param = row["query_param"].strip()
        param = json.loads(raw_param) if raw_param else None
        if param is not None and not isinstance(param, dict):
            raise ValueError(f"query_param must contain a JSON object: {row}")
        record = {
            "provider_code": provider_code,
            "display_name": display_name,
            "source": source,
            "api": row["api"].strip() or None,
            "param": param,
        }
        existing = by_name.setdefault(display_name, record)
        if existing != record:
            raise ValueError(
                f"lookup_name {display_name!r} maps to conflicting provider data: "
                f"{existing!r} vs {record!r}"
            )
        previous_code = component_map.setdefault(component_name, provider_code)
        if previous_code != provider_code:
            raise ValueError(
                f"component_name {component_name!r} maps to conflicting provider codes"
            )

    seed_codes = {record["provider_code"] for record in by_name.values()}
    missing = sorted(set(component_map.values()) - seed_codes)
    if missing:
        raise ValueError(f"Component mapping points to provider codes absent from seed: {missing}")
    return list(by_name.values()), component_map


def _build_migration(records: list[dict[str, Any]]) -> str:
    seed_json = json.dumps(records, ensure_ascii=False, indent=2)
    return f'''"""Add benchmark request metadata and seed benchmark indexes.

Revision ID: 0044
Revises: 0043
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

_BENCHMARK_SEED_JSON = r"""{seed_json}"""


def upgrade() -> None:
    op.add_column(
        "benchmark_index", sa.Column("source", sa.String(64), nullable=True), schema="market"
    )
    op.add_column("benchmark_index", sa.Column("api", sa.Text(), nullable=True), schema="market")
    op.add_column(
        "benchmark_index",
        sa.Column("param", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="market",
    )
    op.alter_column(
        "benchmark_index",
        "provider_symbol",
        existing_type=sa.String(128),
        nullable=True,
        schema="market",
    )
    op.alter_column(
        "benchmark_index", "currency", existing_type=sa.String(8), nullable=True, schema="market"
    )
    op.alter_column(
        "benchmark_index", "index_type", existing_type=sa.String(32), nullable=True, schema="market"
    )
    op.execute(
        sa.text("""
        WITH seed AS (
            SELECT
                item->>'provider_code' AS provider_code,
                item->>'display_name' AS display_name,
                item->>'source' AS source,
                NULLIF(item->>'api', '') AS api,
                CASE
                    WHEN item->'param' IS NULL OR item->'param' = 'null'::jsonb THEN NULL
                    ELSE item->'param'
                END AS param
            FROM jsonb_array_elements(CAST(:seed_json AS jsonb)) AS seed_data(item)
        )
        INSERT INTO market.benchmark_index (provider_code, display_name, source, api, param)
        SELECT seed.provider_code, seed.display_name, seed.source, seed.api, seed.param
        FROM seed
        WHERE NOT EXISTS (
            SELECT 1 FROM market.benchmark_index AS existing
            WHERE existing.display_name = seed.display_name
        )
    """).bindparams(seed_json=_BENCHMARK_SEED_JSON)
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE market.benchmark_index
        SET provider_symbol = COALESCE(provider_symbol, 'UNASSIGNED-' || id::text),
            currency = COALESCE(currency, 'CNY'),
            index_type = COALESCE(index_type, 'FULL_PRICE')
        WHERE provider_symbol IS NULL OR currency IS NULL OR index_type IS NULL
    """
    )
    op.alter_column(
        "benchmark_index",
        "index_type",
        existing_type=sa.String(32),
        nullable=False,
        schema="market",
    )
    op.alter_column(
        "benchmark_index", "currency", existing_type=sa.String(8), nullable=False, schema="market"
    )
    op.alter_column(
        "benchmark_index",
        "provider_symbol",
        existing_type=sa.String(128),
        nullable=False,
        schema="market",
    )
    op.drop_column("benchmark_index", "param", schema="market")
    op.drop_column("benchmark_index", "api", schema="market")
    op.drop_column("benchmark_index", "source", schema="market")
'''


def _build_mapping_yaml(component_map: dict[str, str]) -> str:
    entries = "\n".join(
        f"  {json.dumps(component_name, ensure_ascii=False)}: "
        f"{json.dumps(provider_code, ensure_ascii=False)}"
        for component_name, provider_code in component_map.items()
    )
    return (
        "# Generated from docs/benchmark.csv; keys are source component descriptions.\n"
        "component_to_provider_code:\n"
        f"{entries}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate benchmark migration and component map.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated artifacts without writing files.",
    )
    args = parser.parse_args()

    records, component_map = _read_benchmarks()
    outputs = {
        _MIGRATION_PATH: _build_migration(records),
        _MAPPING_PATH: _build_mapping_yaml(component_map),
    }
    stale: list[Path] = []
    for path, contents in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != contents:
                stale.append(path.relative_to(_ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8", newline="")

    if stale:
        print("Generated benchmark artifacts are stale:")
        for path in stale:
            print(f"  {path}")
        return 1
    if args.check:
        print(f"Validated {len(records)} seed indexes and {len(component_map)} component mappings.")
    else:
        print(
            f"Generated {len(records)} benchmark indexes and "
            f"{len(component_map)} component mappings."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

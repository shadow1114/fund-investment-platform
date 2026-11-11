from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from fip.services.data_service.models.benchmark import (
    BenchmarkComponent,
    BenchmarkIndex,
    BenchmarkIndexType,
    BenchmarkMapping,
)


def test_benchmark_index_types_are_explicit_and_complete():
    assert set(BenchmarkIndexType) == {
        BenchmarkIndexType.PRICE,
        BenchmarkIndexType.TOTAL_RETURN,
        BenchmarkIndexType.FULL_PRICE,
    }
    constraints = {
        constraint.name
        for constraint in BenchmarkIndex.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert constraints == {"ck_benchmark_index_type"}


def test_benchmark_index_source_metadata_and_seed_fields_allow_nulls():
    columns = BenchmarkIndex.__table__.c
    assert columns.source.nullable is True
    assert columns.api.nullable is True
    assert columns.param.nullable is True
    assert isinstance(columns.param.type, JSONB)
    for name in ("provider_symbol", "currency", "index_type"):
        assert columns[name].nullable is True


def test_components_and_mappings_have_required_contract_constraints():
    component_names = {
        constraint.name
        for constraint in BenchmarkComponent.__table__.constraints
        if isinstance(constraint, CheckConstraint | UniqueConstraint)
    }
    mapping_names = {
        constraint.name
        for constraint in BenchmarkMapping.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {"ck_benchmark_component_weight", "uq_benchmark_component_index"} <= component_names
    assert "ck_benchmark_mapping_scope" in mapping_names

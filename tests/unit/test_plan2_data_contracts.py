from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ExcludeConstraint

from fip.services.data_service.models.fund import (
    FundClassificationHistory,
    FundManagerAssignment,
    FundShareClass,
)
from fip.services.data_service.models.governance import (
    DataProviderDataset,
    DataSourcePriority,
)


def test_share_class_base_currency_is_required_with_m1_default():
    column = FundShareClass.__table__.columns["base_currency"]

    assert column.nullable is False
    assert column.type.length == 8
    assert column.default is not None
    assert column.default.arg == "CNY"


def test_classification_has_one_open_interval_per_scheme():
    index = next(
        index
        for index in FundClassificationHistory.__table__.indexes
        if index.name == "uq_fch_open_interval"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "fund_id",
        "classification_scheme",
    ]
    assert str(index.dialect_options["postgresql"]["where"]) == "valid_to IS NULL"


def test_manager_overlap_constraint_uses_plan2_contract_name():
    names = {
        constraint.name
        for constraint in FundManagerAssignment.__table__.constraints
        if isinstance(constraint, ExcludeConstraint)
    }

    assert names == {"ex_fma_same_manager_non_overlapping"}


def test_disclosure_lag_rule_version_is_unique_per_dataset_and_field():
    constraint = next(
        constraint
        for constraint in DataSourcePriority.__table__.constraints
        if constraint.name == "uq_data_source_priority_rule"
        and isinstance(constraint, UniqueConstraint)
    )

    assert [column.name for column in constraint.columns] == [
        "dataset_id",
        "field_name",
        "rule_version",
    ]


def test_provider_dataset_code_is_unique_within_provider():
    constraint = next(
        constraint
        for constraint in DataProviderDataset.__table__.constraints
        if constraint.name == "uq_data_provider_dataset_code"
        and isinstance(constraint, UniqueConstraint)
    )

    assert [column.name for column in constraint.columns] == [
        "provider_id",
        "dataset_code",
    ]

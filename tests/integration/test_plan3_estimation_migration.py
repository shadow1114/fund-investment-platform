import datetime as dt
from collections.abc import Mapping

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.models import FactorRun
from fip.services.fund_service.models import (
    FundEvaluation,
    FundUniverseSnapshot,
    PeerGroupSnapshot,
)

pytestmark = pytest.mark.integration

PLAN3_TABLES = {
    "estimation_method_version",
    "estimation_parameter_version",
    "estimation_run",
    "return_estimate",
    "risk_estimate",
    "covariance_estimate",
    "estimation_validation_result",
}

RUN_IDENTITY = (
    "decision_id",
    "universe_snapshot_id",
    "estimation_method_version_id",
    "estimation_parameter_version_id",
    "estimation_policy_version_id",
    "validation_policy_version_id",
    "code_version",
)


def _seed_dependencies(db_session, suffix: str = "default") -> Mapping[str, int]:
    short_suffix = suffix[:12]
    policies = {
        kind: PolicyVersion(
            policy_kind=kind,
            version_label=f"{short_suffix}-{index}",
            content={},
        )
        for index, kind in enumerate(("evaluation", "estimation", "estimation_validation"), start=1)
    }
    db_session.add_all(policies.values())
    db_session.flush()

    fund = Fund(
        fund_code=f"plan3-{suffix}",
        product_name=f"Plan 3 {suffix}",
        grouping_status="CONFIRMED",
    )
    db_session.add(fund)
    db_session.flush()
    share_class = FundShareClass(
        fund_id=fund.id,
        share_class_code="A",
        display_name=f"Plan 3 {suffix} A",
    )
    db_session.add(share_class)
    db_session.flush()

    peer_group = PeerGroupSnapshot(
        decision_id=f"decision-{suffix}",
        classification_code="BOND",
        base_currency="CNY",
        policy_version_id=policies["evaluation"].id,
        decision_at=dt.date(2026, 9, 10),
        status="AVAILABLE",
        member_count=1,
    )
    db_session.add(peer_group)
    db_session.flush()
    factor_run = FactorRun(
        decision_id=f"decision-{suffix}",
        peer_group_snapshot_id=peer_group.id,
        metric_version_id=policies["evaluation"].id,
        evaluation_policy_version_id=policies["evaluation"].id,
        input_quality_summary={},
    )
    db_session.add(factor_run)
    db_session.flush()
    evaluation = FundEvaluation(
        decision_id=f"decision-{suffix}",
        peer_group_snapshot_id=peer_group.id,
        factor_run_id=factor_run.id,
        policy_version_id=policies["evaluation"].id,
    )
    db_session.add(evaluation)
    db_session.flush()
    universe = FundUniverseSnapshot(
        decision_id=f"decision-{suffix}",
        evaluation_id=evaluation.id,
        policy_version_id=policies["evaluation"].id,
    )
    db_session.add(universe)
    db_session.flush()

    method_id = db_session.execute(
        text(
            """
            INSERT INTO portfolio.estimation_method_version
                (method_code, version_label, implementation_path, specification)
            VALUES (:method_code, 'v1', 'fip.strategy_library.estimation', '{}'::jsonb)
            RETURNING id
            """
        ),
        {"method_code": f"plan3-{suffix}"},
    ).scalar_one()
    parameter_id = db_session.execute(
        text(
            """
            INSERT INTO portfolio.estimation_parameter_version (version_label, parameters)
            VALUES (:version_label, '{}'::jsonb)
            RETURNING id
            """
        ),
        {"version_label": f"v1-{suffix}"},
    ).scalar_one()
    return {
        "universe_snapshot_id": universe.id,
        "share_class_id": share_class.id,
        "method_id": method_id,
        "parameter_id": parameter_id,
        "estimation_policy_id": policies["estimation"].id,
        "validation_policy_id": policies["estimation_validation"].id,
    }


def _insert_run(
    db_session,
    ids: Mapping[str, int],
    *,
    suffix: str = "default",
    status: str = "PENDING",
    approved: bool = False,
    fingerprint: str | None = None,
) -> int:
    return db_session.execute(
        text(
            """
            INSERT INTO portfolio.estimation_run
                (decision_id, universe_snapshot_id,
                 estimation_method_version_id, estimation_parameter_version_id,
                 estimation_policy_version_id, validation_policy_version_id,
                 code_version, status, approved_for_optimization,
                 input_lineage_fingerprint)
            VALUES
                (:decision_id, :universe_snapshot_id,
                 :method_id, :parameter_id,
                 :estimation_policy_id, :validation_policy_id,
                 'code-v1', :status, :approved, :fingerprint)
            RETURNING id
            """
        ),
        {
            **ids,
            "decision_id": f"decision-{suffix}",
            "status": status,
            "approved": approved,
            "fingerprint": fingerprint,
        },
    ).scalar_one()


def test_plan3_tables_exist(db_session):
    names = inspect(db_session.connection()).get_table_names(schema="portfolio")
    assert PLAN3_TABLES <= set(names)


def test_run_idempotency_is_database_enforced(db_session):
    ids = _seed_dependencies(db_session, "idempotency")
    _insert_run(db_session, ids, suffix="idempotency")
    with pytest.raises(IntegrityError):
        _insert_run(db_session, ids, suffix="idempotency")


def test_run_idempotency_key_contains_every_identity_column(db_session):
    unique_constraints = inspect(db_session.connection()).get_unique_constraints(
        "estimation_run", schema="portfolio"
    )
    keys = {tuple(item["column_names"]) for item in unique_constraints}
    assert RUN_IDENTITY in keys


def test_final_status_requires_lineage_and_matches_approval(db_session):
    ids = _seed_dependencies(db_session, "final-lineage")
    with pytest.raises(IntegrityError):
        _insert_run(
            db_session,
            ids,
            suffix="final-lineage",
            status="COMPLETED",
            approved=True,
            fingerprint=None,
        )


def test_transient_run_may_have_no_lineage(db_session):
    ids = _seed_dependencies(db_session, "transient-lineage")
    assert _insert_run(db_session, ids, suffix="transient-lineage") > 0


@pytest.mark.parametrize("status", ["UNKNOWN", "APPROVED"])
def test_run_rejects_unknown_or_legacy_approved_status(db_session, status):
    ids = _seed_dependencies(db_session, f"status-{status.lower()}")
    with pytest.raises(IntegrityError):
        _insert_run(db_session, ids, suffix=f"status-{status.lower()}", status=status)


def test_result_keys_and_database_delete_actions_are_exact(db_session):
    inspector = inspect(db_session.connection())
    expected_keys = {
        "return_estimate": ("run_id", "return_basis", "share_class_id"),
        "risk_estimate": ("run_id", "return_basis", "share_class_id"),
        "covariance_estimate": ("run_id", "return_basis"),
        "estimation_validation_result": ("run_id", "return_basis", "code"),
    }
    for table_name, expected_key in expected_keys.items():
        uniques = inspector.get_unique_constraints(table_name, schema="portfolio")
        assert expected_key in {tuple(item["column_names"]) for item in uniques}

        foreign_keys = inspector.get_foreign_keys(table_name, schema="portfolio")
        run_fk = next(fk for fk in foreign_keys if fk["constrained_columns"] == ["run_id"])
        assert run_fk["options"]["ondelete"] == "CASCADE"

    run_foreign_keys = inspector.get_foreign_keys("estimation_run", schema="portfolio")
    assert run_foreign_keys
    assert {fk["options"].get("ondelete") for fk in run_foreign_keys} == {"RESTRICT"}


def test_numeric_results_are_text_and_matrix_payloads_are_jsonb(db_session):
    inspector = inspect(db_session.connection())
    expected_text = {
        "return_estimate": {
            "sample_mean",
            "shrinkage_target",
            "shrinkage_intensity",
            "mu_before_clip",
            "mu",
        },
        "risk_estimate": {"variance", "volatility"},
        "covariance_estimate": {
            "shrinkage_intensity",
            "sample_min_eigenvalue",
            "sample_max_eigenvalue",
            "sample_condition_number",
            "final_min_eigenvalue",
            "final_max_eigenvalue",
            "final_condition_number",
        },
    }
    for table_name, expected_names in expected_text.items():
        columns = {
            column["name"]: column for column in inspector.get_columns(table_name, "portfolio")
        }
        assert expected_names <= set(columns)
        assert all(
            columns[name]["type"].__class__.__name__ in {"TEXT", "VARCHAR"}
            for name in expected_names
        )

    covariance_columns = {
        column["name"]: column
        for column in inspector.get_columns("covariance_estimate", schema="portfolio")
    }
    for name in ("covariance_payload", "correlation_payload", "input_lineage"):
        assert covariance_columns[name]["type"].__class__.__name__ == "JSONB"


def test_approved_absolute_lookup_indexes_exist(db_session):
    inspector = inspect(db_session.connection())
    run_indexes = inspector.get_indexes("estimation_run", schema="portfolio")
    assert any(
        index["name"] == "ix_estimation_run_approved_final"
        and "approved_for_optimization" in index["dialect_options"]["postgresql_where"]
        for index in run_indexes
    )
    for table_name in ("return_estimate", "risk_estimate", "covariance_estimate"):
        indexes = inspector.get_indexes(table_name, schema="portfolio")
        assert any(
            "absolute_lookup" in index["name"]
            and "ABSOLUTE" in index["dialect_options"]["postgresql_where"]
            for index in indexes
        )

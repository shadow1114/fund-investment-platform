import datetime as dt
import json
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
from fip.strategy_library.estimation.encoding import encode_float64

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
        fund_code=f"plan3-{short_suffix}",
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
        {"version_label": f"v1-{short_suffix}"},
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


def _matrix_payload(*, checksum: str = "a" * 64) -> dict[str, object]:
    return {
        "shape": [1, 1],
        "instrument_order": [1],
        "lower_triangle": ["0.25"],
        "numeric_encoding_version": "FLOAT64_SHORTEST_ROUNDTRIP_V1",
        "checksum": checksum,
    }


def _insert_return(
    db_session,
    run_id: int,
    share_class_id: int,
    *,
    basis: str = "ABSOLUTE",
    values: tuple[str, str, str, str, str] = ("0.1", "0.2", "0.3", "0.4", "0.5"),
) -> int:
    return db_session.execute(
        text(
            """
            INSERT INTO portfolio.return_estimate
                (run_id, return_basis, share_class_id, sample_mean,
                 shrinkage_target, shrinkage_intensity, mu_before_clip, mu,
                 mu_clipped, numeric_encoding_version)
            VALUES
                (:run_id, :basis, :share_class_id, :sample_mean,
                 :shrinkage_target, :shrinkage_intensity, :mu_before_clip, :mu,
                 false, 'FLOAT64_SHORTEST_ROUNDTRIP_V1')
            RETURNING id
            """
        ),
        {
            "run_id": run_id,
            "basis": basis,
            "share_class_id": share_class_id,
            "sample_mean": values[0],
            "shrinkage_target": values[1],
            "shrinkage_intensity": values[2],
            "mu_before_clip": values[3],
            "mu": values[4],
        },
    ).scalar_one()


def _insert_risk(
    db_session,
    run_id: int,
    share_class_id: int,
    *,
    basis: str = "ABSOLUTE",
) -> int:
    return db_session.execute(
        text(
            """
            INSERT INTO portfolio.risk_estimate
                (run_id, return_basis, share_class_id, variance, volatility,
                 numeric_encoding_version)
            VALUES
                (:run_id, :basis, :share_class_id, '0.25', '0.5',
                 'FLOAT64_SHORTEST_ROUNDTRIP_V1')
            RETURNING id
            """
        ),
        {"run_id": run_id, "basis": basis, "share_class_id": share_class_id},
    ).scalar_one()


def _insert_covariance(
    db_session,
    run_id: int,
    *,
    basis: str = "ABSOLUTE",
    covariance_payload: dict[str, object] | None = None,
    correlation_payload: dict[str, object] | None = None,
    observation_count: int = 20,
    instrument_count: int = 1,
    dropped_dates_count: int = 0,
) -> int:
    covariance_payload = covariance_payload or _matrix_payload()
    correlation_payload = correlation_payload or _matrix_payload(checksum="b" * 64)
    return db_session.execute(
        text(
            """
            INSERT INTO portfolio.covariance_estimate
                (run_id, return_basis, covariance_payload, correlation_payload,
                 shrinkage_intensity, sample_min_eigenvalue,
                 sample_max_eigenvalue, sample_condition_number,
                 final_min_eigenvalue, final_max_eigenvalue,
                 final_condition_number, observation_count, instrument_count,
                 dropped_dates_count, excluded_instruments, input_lineage,
                 input_fingerprint)
            VALUES
                (:run_id, :basis, CAST(:covariance_payload AS jsonb),
                 CAST(:correlation_payload AS jsonb), '0.1', '0.2', '0.3',
                 '1.5', '0.25', '0.25', '1.0', :observation_count,
                 :instrument_count, :dropped_dates_count, '[]'::jsonb,
                 '{}'::jsonb, :input_fingerprint)
            RETURNING id
            """
        ),
        {
            "run_id": run_id,
            "basis": basis,
            "covariance_payload": json.dumps(covariance_payload),
            "correlation_payload": json.dumps(correlation_payload),
            "observation_count": observation_count,
            "instrument_count": instrument_count,
            "dropped_dates_count": dropped_dates_count,
            "input_fingerprint": "c" * 64,
        },
    ).scalar_one()


def _insert_validation(
    db_session,
    run_id: int,
    *,
    basis: str | None = "ABSOLUTE",
    code: str = "MIN_T_OVER_N",
    severity: str = "REJECT",
    status: str = "PASSED",
) -> int:
    return db_session.execute(
        text(
            """
            INSERT INTO portfolio.estimation_validation_result
                (run_id, return_basis, code, severity, status, detail)
            VALUES (:run_id, :basis, :code, :severity, :status, '{}'::jsonb)
            RETURNING id
            """
        ),
        {
            "run_id": run_id,
            "basis": basis,
            "code": code,
            "severity": severity,
            "status": status,
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


@pytest.mark.parametrize("result_kind", ["return", "risk", "covariance"])
def test_duplicate_numeric_result_keys_are_database_rejected(db_session, result_kind):
    ids = _seed_dependencies(db_session, f"duplicate-{result_kind}")
    run_id = _insert_run(db_session, ids, suffix=f"duplicate-{result_kind}")
    insert = {
        "return": lambda: _insert_return(db_session, run_id, ids["share_class_id"]),
        "risk": lambda: _insert_risk(db_session, run_id, ids["share_class_id"]),
        "covariance": lambda: _insert_covariance(db_session, run_id),
    }[result_kind]

    insert()
    with pytest.raises(IntegrityError):
        insert()


def test_duplicate_run_level_validation_code_is_rejected_when_basis_is_null(db_session):
    ids = _seed_dependencies(db_session, "duplicate-validation")
    run_id = _insert_run(db_session, ids, suffix="duplicate-validation")
    _insert_validation(db_session, run_id, basis=None, code="RUN_COMPLETE")

    with pytest.raises(IntegrityError):
        _insert_validation(db_session, run_id, basis=None, code="RUN_COMPLETE")


@pytest.mark.parametrize("result_kind", ["return", "risk", "covariance", "validation"])
def test_result_rows_reject_illegal_return_basis(db_session, result_kind):
    ids = _seed_dependencies(db_session, f"basis-{result_kind}")
    run_id = _insert_run(db_session, ids, suffix=f"basis-{result_kind}")

    with pytest.raises(IntegrityError):
        if result_kind == "return":
            _insert_return(db_session, run_id, ids["share_class_id"], basis="TOTAL")
        elif result_kind == "risk":
            _insert_risk(db_session, run_id, ids["share_class_id"], basis="TOTAL")
        elif result_kind == "covariance":
            _insert_covariance(db_session, run_id, basis="TOTAL")
        else:
            _insert_validation(db_session, run_id, basis="TOTAL")


@pytest.mark.parametrize(
    ("field", "value"),
    [("severity", "INFO"), ("status", "SKIPPED")],
)
def test_validation_rows_reject_illegal_severity_or_status(db_session, field, value):
    ids = _seed_dependencies(db_session, f"validation-{field}")
    run_id = _insert_run(db_session, ids, suffix=f"validation-{field}")
    kwargs = {field: value}

    with pytest.raises(IntegrityError):
        _insert_validation(db_session, run_id, **kwargs)


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("observation_count", {"observation_count": -1}),
        ("instrument_count", {"instrument_count": -1}),
        ("dropped_dates_count", {"dropped_dates_count": -1}),
    ],
)
def test_covariance_rejects_negative_counts(db_session, field, values):
    ids = _seed_dependencies(db_session, f"negative-{field}")
    run_id = _insert_run(db_session, ids, suffix=f"negative-{field}")

    with pytest.raises(IntegrityError):
        _insert_covariance(db_session, run_id, **values)


@pytest.mark.parametrize(
    ("payload_name", "missing_key"),
    [
        ("covariance_payload", "lower_triangle"),
        ("covariance_payload", "checksum"),
        ("correlation_payload", "lower_triangle"),
        ("correlation_payload", "checksum"),
    ],
)
def test_covariance_rejects_matrix_payloads_missing_required_keys(
    db_session, payload_name, missing_key
):
    ids = _seed_dependencies(db_session, f"payload-{payload_name[:3]}-{missing_key[:3]}")
    run_id = _insert_run(
        db_session,
        ids,
        suffix=f"payload-{payload_name[:3]}-{missing_key[:3]}",
    )
    malformed = _matrix_payload()
    del malformed[missing_key]

    with pytest.raises(IntegrityError):
        _insert_covariance(db_session, run_id, **{payload_name: malformed})


@pytest.mark.parametrize(
    ("referenced_table", "id_key"),
    [
        ("portfolio.estimation_method_version", "method_id"),
        ("portfolio.estimation_parameter_version", "parameter_id"),
        ("evaluation.fund_universe_snapshot", "universe_snapshot_id"),
        ("governance.policy_version", "estimation_policy_id"),
        ("governance.policy_version", "validation_policy_id"),
    ],
)
def test_run_restricts_deletion_of_immutable_inputs(db_session, referenced_table, id_key):
    ids = _seed_dependencies(db_session, f"restrict-{id_key[:8]}")
    _insert_run(db_session, ids, suffix=f"restrict-{id_key[:8]}")

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(
                text(f"DELETE FROM {referenced_table} WHERE id = :id"),
                {"id": ids[id_key]},
            )

    assert db_session.execute(text("SELECT 1")).scalar_one() == 1
    assert (
        db_session.execute(
            text(f"SELECT count(*) FROM {referenced_table} WHERE id = :id"),
            {"id": ids[id_key]},
        ).scalar_one()
        == 1
    )


@pytest.mark.parametrize("result_kind", ["return", "risk"])
def test_result_rows_restrict_deletion_of_share_class(db_session, result_kind):
    ids = _seed_dependencies(db_session, f"restrict-share-{result_kind}")
    run_id = _insert_run(db_session, ids, suffix=f"restrict-share-{result_kind}")
    if result_kind == "return":
        _insert_return(db_session, run_id, ids["share_class_id"])
        result_table = "return_estimate"
    else:
        _insert_risk(db_session, run_id, ids["share_class_id"])
        result_table = "risk_estimate"

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(
                text("DELETE FROM fund.fund_share_class WHERE id = :share_class_id"),
                {"share_class_id": ids["share_class_id"]},
            )

    assert db_session.execute(text("SELECT 1")).scalar_one() == 1
    assert (
        db_session.execute(
            text(
                f"SELECT count(*) FROM portfolio.{result_table} "
                "WHERE run_id = :run_id AND share_class_id = :share_class_id"
            ),
            {"run_id": run_id, "share_class_id": ids["share_class_id"]},
        ).scalar_one()
        == 1
    )


def test_deleting_run_cascades_to_all_run_owned_results(db_session):
    ids = _seed_dependencies(db_session, "cascade-results")
    run_id = _insert_run(db_session, ids, suffix="cascade-results")
    _insert_return(db_session, run_id, ids["share_class_id"])
    _insert_risk(db_session, run_id, ids["share_class_id"])
    _insert_covariance(db_session, run_id)
    _insert_validation(db_session, run_id)

    db_session.execute(
        text("DELETE FROM portfolio.estimation_run WHERE id = :run_id"),
        {"run_id": run_id},
    )

    for table_name in (
        "return_estimate",
        "risk_estimate",
        "covariance_estimate",
        "estimation_validation_result",
    ):
        count = db_session.execute(
            text(f"SELECT count(*) FROM portfolio.{table_name} WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).scalar_one()
        assert count == 0


@pytest.mark.parametrize(
    ("status", "approved"),
    [
        ("COMPLETED", True),
        ("COMPLETED_WITH_WARNING", True),
        ("REJECTED", False),
    ],
)
def test_final_status_approval_combinations_are_accepted(db_session, status, approved):
    suffix = f"valid-{status.lower()}"
    ids = _seed_dependencies(db_session, suffix)

    run_id = _insert_run(
        db_session,
        ids,
        suffix=suffix,
        status=status,
        approved=approved,
        fingerprint="f" * 64,
    )

    assert run_id > 0


@pytest.mark.parametrize(
    ("status", "approved"),
    [
        ("COMPLETED", False),
        ("COMPLETED_WITH_WARNING", False),
        ("REJECTED", True),
    ],
)
def test_final_status_approval_mismatches_are_rejected(db_session, status, approved):
    suffix = f"invalid-{status.lower()}"
    ids = _seed_dependencies(db_session, suffix)

    with pytest.raises(IntegrityError):
        _insert_run(
            db_session,
            ids,
            suffix=suffix,
            status=status,
            approved=approved,
            fingerprint="f" * 64,
        )


@pytest.mark.parametrize("status", ["COMPLETED", "COMPLETED_WITH_WARNING", "REJECTED"])
def test_every_final_status_requires_lineage(db_session, status):
    suffix = f"lineage-{status.lower()}"
    ids = _seed_dependencies(db_session, suffix)

    with pytest.raises(IntegrityError):
        _insert_run(
            db_session,
            ids,
            suffix=suffix,
            status=status,
            approved=status != "REJECTED",
            fingerprint=None,
        )


def test_canonical_shortest_roundtrip_numeric_strings_are_persisted_verbatim(db_session):
    ids = _seed_dependencies(db_session, "canonical-numeric")
    run_id = _insert_run(db_session, ids, suffix="canonical-numeric")
    encoded = tuple(
        encode_float64(value)
        for value in (0.1, -0.0, 1.2345678901234567, 5e-324, 1.7976931348623157e308)
    )
    estimate_id = _insert_return(
        db_session,
        run_id,
        ids["share_class_id"],
        values=encoded,
    )

    persisted = db_session.execute(
        text(
            """
            SELECT sample_mean, shrinkage_target, shrinkage_intensity,
                   mu_before_clip, mu
            FROM portfolio.return_estimate
            WHERE id = :estimate_id
            """
        ),
        {"estimate_id": estimate_id},
    ).one()

    assert tuple(persisted) == encoded
    assert tuple(encode_float64(float(value)) for value in persisted) == encoded

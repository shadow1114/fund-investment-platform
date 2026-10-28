import pytest
from pydantic import ValidationError

from fip.api.schemas import FundIngestionPreviewRequest


def test_scope_is_discriminated_and_selected_has_limits():
    payload = FundIngestionPreviewRequest.model_validate(
        {"dataset": "NAV", "scope": {"type": "SELECTED", "fund_ids": ["a", "b"]}}
    )
    assert payload.scope.type == "SELECTED"
    for scope in (
        {"type": "SELECTED", "fund_ids": []},
        {"type": "SELECTED", "fund_ids": ["a"]},
        {"type": "SELECTED", "fund_ids": ["a", "a"]},
        {"type": "SELECTED", "fund_ids": [str(i) for i in range(101)]},
        {"type": "SINGLE", "fund_id": "a", "fund_ids": ["a"]},
        {"type": "ALL", "filters": {"unknown": "value"}},
        {"type": "ALL", "filters": {"manager_id": "x"}},
    ):
        with pytest.raises(ValidationError):
            FundIngestionPreviewRequest.model_validate({"dataset": "NAV", "scope": scope})


def test_snapshot_hash_is_stable_and_changes_with_mapping():
    from fip.platform.jobs.ingestion_scope import snapshot_hash

    scope = {"type": "SELECTED", "fund_ids": ["b", "a"]}
    members = [
        {"fund_id": 2, "share_class_id": 4, "symbol": "B"},
        {"fund_id": 1, "share_class_id": 3, "symbol": "A"},
    ]
    assert snapshot_hash("NAV", scope, members) == snapshot_hash(
        "NAV", {"type": "SELECTED", "fund_ids": ["a", "b"]}, list(reversed(members))
    )
    changed = [dict(member) for member in members]
    changed[0]["symbol"] = "NEW"
    assert snapshot_hash("NAV", scope, members) != snapshot_hash("NAV", scope, changed)


def test_preview_and_item_models_have_persistent_snapshot_and_unique_items():
    from sqlalchemy import UniqueConstraint

    from fip.services.data_service.models.fund_ingestion import (
        FundIngestionPreview,
        FundIngestionRunItem,
    )

    assert {"actor", "dataset", "scope", "members", "scope_hash", "expires_at"} <= set(
        FundIngestionPreview.__table__.columns.keys()
    )
    unique = [
        set(c.columns.keys())
        for c in FundIngestionRunItem.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]
    assert {"operation_id", "fund_id", "share_class_id"} in unique


def test_full_universe_job_read_requires_capability_even_for_manager():
    from types import SimpleNamespace

    from fip.api.context import Principal
    from fip.api.routers.fund_ingestions import _can_read_job

    principal = Principal("alice", ("operations",), False, False, True)
    job = SimpleNamespace(job_payload={"actor": "alice", "scope_type": "ALL"})
    assert not _can_read_job(principal, job)


def test_transient_provider_failure_is_classified_for_manual_retry():
    from fip.platform.jobs.fund_ingestion import _is_transient_result

    assert _is_transient_result({"status": "FAILED", "error": "TimeoutError: timed out"})
    assert not _is_transient_result({"status": "FAILED", "error": "ValueError: bad data"})


def test_scoped_job_denies_other_ingestion_managers():
    from types import SimpleNamespace

    from fip.api.context import Principal
    from fip.api.routers.fund_ingestions import _can_read_job

    actor = Principal("bob", ("operations",), False, False, True, True)
    job = SimpleNamespace(
        job_payload={"actor": "alice", "scope_type": "SINGLE", "scoped_items": True}
    )
    assert not _can_read_job(actor, job)
    legacy = SimpleNamespace(job_payload={"actor": "alice"})
    assert _can_read_job(actor, legacy)


def test_subprocess_timeout_is_retryable():
    from subprocess import TimeoutExpired

    from fip.platform.jobs.fund_ingestion import _is_transient_result

    error = TimeoutExpired(cmd="akshare", timeout=30)
    assert _is_transient_result({"status": "FAILED", "error": f"{type(error).__name__}: {error}"})

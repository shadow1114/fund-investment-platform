"""Offline revision/review/PIT regressions. No engine, fixtures or external sources."""

import datetime as dt
import json

import pytest
from sqlalchemy.orm.evaluator import _EvaluatorCompiler
from sqlalchemy.sql import operators

from fip.services.data_service.classification import classify, load_policy, normalize_evidence
from fip.services.data_service.classification import service as module
from fip.services.data_service.classification.legacy import project_legacy
from fip.services.data_service.classification.models import (
    ClassificationSnapshot,
    StrategyTagResult,
)
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationReviewCase,
    FundClassificationRevision,
)
from fip.services.data_service.models.governance import AuditLog
from fip.services.data_service.repositories.classification import SqlClassificationPitRepository

NOW = dt.datetime(2026, 10, 27, 10, tzinfo=dt.UTC)
LATER = NOW + dt.timedelta(hours=1)
DAY = NOW.date()


class Rows(list):
    def all(self):
        return list(self)


class MemorySession:
    """Replace only ORM storage; evaluate real select predicates and ordering offline."""

    def __init__(self):
        self.rows = [Fund(id=1, fund_code="fixture", grouping_status="CONFIRMED")]
        self.lock_count = 0

    def add(self, row):
        if row.id is None:
            row.id = max((r.id for r in self.rows if type(r) is type(row)), default=0) + 1
        self.rows.append(row)

    def flush(self):
        pass

    def refresh(self, row):
        pass

    def get(self, model, row_id):
        return next((r for r in self.rows if isinstance(r, model) and r.id == row_id), None)

    def scalars(self, query):
        model = query.column_descriptions[0]["entity"]
        rows = [r for r in self.rows if isinstance(r, model)]
        if query._where_criteria:
            predicate = _EvaluatorCompiler().process(*query._where_criteria)
            rows = [r for r in rows if predicate(r)]
        for order in reversed(query._order_by_clauses):
            descending = getattr(order, "modifier", None) is operators.desc_op
            column = getattr(order, "element", order)
            rows.sort(key=lambda r: getattr(r, column.key), reverse=descending)
        if query._limit_clause is not None:
            rows = rows[: query._limit_clause.value]
        if query._for_update_arg is not None:
            self.lock_count += 1
        return Rows(rows)

    def scalar(self, query):
        return next(iter(self.scalars(query)), None)


def ev(field, value, *, code="000001", provider="SNOWBALL", row=0, at=NOW, payload="raw:1"):
    identity = {
        "provider": provider,
        "dataset": "fund_detail_xq",
        "provider_fund_code": code,
        "params": {"symbol": code},
        "raw_field": field,
    }
    return normalize_evidence(
        source="AGGREGATOR",
        field=field,
        value=value,
        classified_at=at,
        locator="identity:" + json.dumps(identity, sort_keys=True) + f";row:{row}",
        payload_ref=payload,
    )


def snap(*evidence, v3=True):
    return classify(
        evidence
        or [ev("formal_type", "股票型"), ev("investment_strategy", "本基金采用主动管理策略。")],
        classified_at=NOW,
        policy=load_policy(rule_version="3.0.0" if v3 else "1.0.0"),
    )


def persist(session, snapshot=None, *, at=NOW, reviewed=False, **kwargs):
    return module.ClassificationService(session).write(
        1,
        snapshot or snap(),
        valid_from=DAY,
        available_at=at,
        actor="fixture",
        reason="offline fixture",
        reviewed=reviewed,
        **kwargs,
    )


def pending(session, revision):
    return next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
        and r.revision_id == revision.id
        and r.status == "PENDING"
    )


def decision(value="ACTIVE"):
    return module.ReviewDecision(
        action="OVERRIDE", value=value, evidence=(ev("investment_strategy", value),)
    )


def test_hash_ignores_storage_timestamps_payload_and_source_row_position():
    a = snap(ev("formal_type", "股票型", row=0))
    b = snap(ev("formal_type", "股票型", row=99, at=LATER, payload="raw:999"))
    assert module._hash([(DAY, None, a, {})]) == module._hash([(DAY, None, b, {})])


def test_hash_retains_share_provider_raw_identity_and_tag_semantics():
    original = snap(ev("formal_type", "股票型"))
    for changed in [
        snap(ev("formal_type", "股票型", code="000002")),
        snap(ev("formal_type", "股票型", provider="OTHER")),
        snap(ev("formal_type", "股票型"), ev("investment_strategy", "本基金采用量化模型。")),
        snap(ev("formal_type", "股票型"), v3=False),
    ]:
        assert module._hash([(DAY, None, original, {})]) != module._hash([(DAY, None, changed, {})])


def test_v3_write_is_immutable_idempotent_and_has_only_active_cases():
    session = MemorySession()
    first = persist(session)
    again = persist(
        session,
        snap(
            *(
                ev(f, v, at=LATER, row=8, payload="raw:9")
                for f, v in [
                    ("formal_type", "股票型"),
                    ("investment_strategy", "本基金采用主动管理策略。"),
                ]
            )
        ),
        at=LATER,
    )
    assert first is again
    assert session.lock_count >= 2
    assert len([r for r in session.rows if isinstance(r, FundClassificationRevision)]) == 1
    assert all(
        r.details.get("dimension") in {"asset_class", "strategy", "strategy_tags.QUANTITATIVE"}
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
    )


@pytest.mark.parametrize("status", ["CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"])
def test_legacy_projection_does_not_admit_quantitative_or_unverified_tags(status):
    evidence = (ev("investment_strategy", "量化"),)
    tag = StrategyTagResult(
        status=status,
        value="QUANTITATIVE" if status == "CONFIRMED" else "UNKNOWN",
        candidates=() if status == "UNKNOWN" else ("QUANTITATIVE",),
        evidence=evidence,
        evaluation_state="EVALUATED",
    )
    snapshot = snap().model_copy(
        update={
            "strategy_tag_results": {"QUANTITATIVE": tag},
            "strategy_tags": ("QUANTITATIVE",) if status == "CONFIRMED" else (),
        }
    )
    assert project_legacy(snapshot, grouping_confirmed=True).value is None


def test_legacy_projection_requires_confirmed_strategy_for_bond_and_mixed():
    for kind in ["债券型-长债", "混合型-偏股"]:
        assert project_legacy(snap(ev("formal_type", kind)), grouping_confirmed=True).value is None


def test_v1_snapshot_remains_exact_and_quant_does_not_become_active():
    old = snap(ev("formal_type", "股票型"), ev("strategy", "QUANTITATIVE"), v3=False)
    data = old.to_dict()
    assert ClassificationSnapshot.model_validate(data).to_dict() == data
    assert "strategy_tag_results" not in data
    assert project_legacy(old, grouping_confirmed=True).value is None


def test_partial_refresh_replaces_only_same_observation_and_explicit_empty_withdraws():
    session = MemorySession()
    service = module.ClassificationService(session)
    persist(
        session,
        snap(
            ev("formal_type", "股票型"),
            ev("investment_strategy", "本基金采用量化模型。"),
            ev("investment_strategy", "本基金采用主动管理策略。", code="000002"),
        ),
    )
    service.refresh_v3(
        1,
        [ev("investment_strategy", "", at=LATER, row=9)],
        available_at=LATER,
        actor="source",
        reason="explicit empty",
    )
    latest = service.intervals(service.latest(1).id)[-1][2]
    assert latest.asset_class.value == "EQUITY"
    assert latest.strategy.value == "ACTIVE"
    assert latest.strategy_tags == ()
    assert any(e.raw_value == "" for e in latest.observations)
    assert any(e.raw_value == "本基金采用主动管理策略。" for e in latest.observations)


def test_failed_source_retains_evidence_and_exposes_diagnostic():
    session = MemorySession()
    service = module.ClassificationService(session)
    persist(session)
    service.refresh_v3(
        1,
        [],
        available_at=LATER,
        actor="source",
        reason="failure",
        diagnostics=("SNOWBALL:FAILED:timeout",),
    )
    latest = service.intervals(service.latest(1).id)[-1][2]
    assert latest.asset_class.value == "EQUITY"
    assert latest.source_diagnostics == ("SNOWBALL:FAILED:timeout",)
    assert all(e.classified_at == NOW for e in latest.observations)


def test_reviewed_baseline_new_tag_or_version_creates_deduplicated_proposal():
    session = MemorySession()
    baseline = persist(session, snap(v3=False), reviewed=True)
    service = module.ClassificationService(session)
    incoming = snap(
        ev("formal_type", "股票型"), ev("investment_strategy", "本基金采用量化模型和主动管理策略。")
    )
    assert persist(session, incoming, at=LATER) is baseline
    persist(session, incoming, at=LATER)
    cases = [
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
        and r.issue_type == "NEW_EVIDENCE_AFTER_REVIEW"
    ]
    assert len(cases) >= 1
    assert any("strategy_tags.QUANTITATIVE" in c.details["changed_scope"] for c in cases)
    assert all(
        c.details["baseline"] == service.intervals(baseline.id)[-1][2].to_dict() for c in cases
    )
    assert len({c.issue_key for c in cases}) == len(cases)


def test_v3_upgrade_requires_explicit_version_two_dimensions_and_changed_tag():
    session = MemorySession()
    baseline = persist(session, snap(v3=False), reviewed=True)
    persist(
        session,
        snap(
            ev("formal_type", "股票型"),
            ev("investment_strategy", "本基金采用量化模型和主动管理策略。"),
        ),
        at=LATER,
    )
    case = next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
        and r.issue_type == "NEW_EVIDENCE_AFTER_REVIEW"
    )
    service = module.ClassificationService(session)
    kwargs = dict(
        expected_revision=baseline.id,
        actor="reviewer",
        reason="upgrade",
        can_review=True,
        reviewed_at=LATER,
    )
    with pytest.raises(ValueError, match="incoming version"):
        service.review(
            case.id, decisions={"asset_class": decision("EQUITY"), "strategy": decision()}, **kwargs
        )
    with pytest.raises(ValueError, match="scope"):
        service.review(
            case.id, decisions={"strategy": decision()}, accept_incoming_version="3.0.0", **kwargs
        )
    result = service.review(
        case.id,
        decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
        tag_decisions={
            "QUANTITATIVE": module.StrategyTagDecision(
                action="REJECT", evidence=(ev("investment_strategy", "reject quant"),)
            )
        },
        accept_incoming_version="3.0.0",
        **kwargs,
    )
    snapshot = service.intervals(result.id)[-1][2]
    assert snapshot.rule_version == "3.0.0"
    assert snapshot.strategy.value == "ACTIVE"
    assert snapshot.strategy_tags == ()
    audit = [r for r in session.rows if isinstance(r, AuditLog) and r.action == "REVIEW"][-1]
    assert audit.detail["baseline"]["rule_version"] == "1.0.0"
    assert audit.detail["incoming"]["rule_version"] == "3.0.0"
    assert audit.detail["tag_decisions"]["QUANTITATIVE"]["action"] == "REJECT"
    assert project_legacy(snapshot, grouping_confirmed=True).value is None
    assert (
        SqlClassificationPitRepository(session, LATER).current(1).classification_code
        == "ACTIVE_EQUITY"
    )
    with pytest.raises(module.ClassificationConflict):
        service.review(case.id, decisions={}, **kwargs)


def test_reject_upgrade_keeps_exact_baseline_and_protects_manual_result():
    session = MemorySession()
    baseline = persist(session, snap(v3=False), reviewed=True)
    old = module.ClassificationService(session).intervals(baseline.id)[-1][2].to_dict()
    persist(session, snap(), at=LATER)
    case = next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
        and r.issue_type == "NEW_EVIDENCE_AFTER_REVIEW"
    )
    result = module.ClassificationService(session).review(
        case.id,
        expected_revision=baseline.id,
        decisions={},
        reject_upgrade=True,
        actor="reviewer",
        reason="keep baseline",
        can_review=True,
        reviewed_at=LATER,
    )
    assert result is baseline
    assert module.ClassificationService(session).intervals(baseline.id)[-1][2].to_dict() == old
    assert case.status == "RESOLVED"


def test_v3_review_rejects_paused_decisions_and_permission():
    session = MemorySession()
    revision = persist(session, snap(ev("formal_type", "股票型")))
    case = pending(session, revision)
    service = module.ClassificationService(session)
    kwargs = dict(
        expected_revision=revision.id, actor="reviewer", reason="review", reviewed_at=LATER
    )
    with pytest.raises(PermissionError):
        service.review(case.id, decisions={}, can_review=False, **kwargs)
    with pytest.raises(ValueError, match="scope"):
        service.review(case.id, decisions={"geography": decision("US")}, can_review=True, **kwargs)


def test_paused_pending_history_survives_upgrade_and_is_hidden_from_active_queue():
    session = MemorySession()
    baseline = persist(session, snap(v3=False))
    historical = next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase) and r.details.get("dimension") == "geography"
    )
    module.ClassificationService(session).refresh_v3(
        1, [], available_at=LATER, actor="source", reason="upgrade"
    )
    assert historical.status == "PENDING"
    assert historical.details["evaluation_state"] == "PAUSED"
    assert historical not in module.ClassificationService(session).active_review_cases()
    current = module.ClassificationService(session).intervals(
        module.ClassificationService(session).latest(1).id
    )[-1][2]
    assert current.geography.carried_from_revision_id == baseline.id


def test_v3_pit_uses_visible_revision_before_interval_and_preserves_source_times():
    session = MemorySession()
    first = persist(session, snap(v3=False))
    source_published = NOW - dt.timedelta(days=1)
    second = persist(
        session,
        at=LATER,
        published_at=source_published,
        provider_available_at=NOW,
        ingested_at=LATER,
        availability_quality="EXACT",
    )
    before = SqlClassificationPitRepository(session, NOW).snapshot(1, effective_at=DAY)
    after = SqlClassificationPitRepository(session, LATER).snapshot(1, effective_at=DAY)
    assert before["revision_id"] == first.id
    assert after["revision_id"] == second.id
    assert after["published_at"] == source_published.isoformat()
    assert after["provider_available_at"] == NOW.isoformat()
    assert after["ingested_at"] == LATER.isoformat()
    # Latest visible revision has a gap: never fall back to an old interval.
    module.ClassificationService(session).replace_intervals(
        1,
        [(DAY + dt.timedelta(days=1), None, snap())],
        available_at=LATER,
        actor="source",
        reason="gap",
    )
    assert SqlClassificationPitRepository(session, LATER).snapshot(1, effective_at=DAY) is None


def test_refresh_cannot_backdate_newly_ingested_evidence():
    session = MemorySession()
    with pytest.raises(ValueError, match="available_at"):
        module.ClassificationService(session).refresh_v3(
            1,
            [ev("formal_type", "股票型", at=LATER)],
            available_at=NOW,
            actor="source",
            reason="incorrect backdate",
        )


def test_explicit_negative_quant_evidence_allows_evaluated_nonquant_legacy_active():
    snapshot = snap(
        ev("formal_type", "股票型"),
        ev("investment_strategy", "本基金采用主动管理策略，不采用量化模型。"),
    )
    assert snapshot.strategy.value == "ACTIVE"
    assert snapshot.strategy_tag_results["QUANTITATIVE"].evaluation_state == "EVALUATED"
    assert project_legacy(snapshot, grouping_confirmed=True).value == "ACTIVE_EQUITY"


def test_missing_or_unevaluated_tag_is_not_nonquant_proof():
    for tag in [None, StrategyTagResult(status="UNKNOWN")]:
        snapshot = snap().model_copy(
            update={
                "strategy_tag_results": {"QUANTITATIVE": tag} if tag else None,
                "strategy_tags": () if tag else None,
            }
        )
        assert project_legacy(snapshot, grouping_confirmed=True).value is None


def test_refresh_v3_semantically_identical_observations_do_not_create_new_revision():
    session = MemorySession()
    service = module.ClassificationService(session)
    evidence = [ev("formal_type", "股票型"), ev("investment_strategy", "本基金采用主动管理策略。")]
    first = service.refresh_v3(1, evidence, available_at=NOW, actor="source", reason="initial")
    repeated = [
        item.model_copy(update={"classified_at": LATER, "payload_ref": "raw:888"})
        for item in evidence
    ]
    assert (
        service.refresh_v3(1, repeated, available_at=LATER, actor="source", reason="repeat")
        is first
    )


def test_pending_partial_observations_survive_next_day_without_overwriting_manual_baseline():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session, reviewed=True)
    tomorrow = LATER + dt.timedelta(days=1)
    service.refresh_v3(
        1,
        [ev("formal_type", "债券型-长债", at=LATER)],
        available_at=LATER,
        actor="source",
        reason="changed type",
    )
    service.refresh_v3(
        1,
        [ev("investment_strategy", "本基金采用量化模型。", at=tomorrow)],
        available_at=tomorrow,
        actor="source",
        reason="changed strategy",
    )
    assert service.latest(1) is baseline
    proposals = [
        r
        for r in service.active_review_cases(1)
        if r.details.get("valid_from") == tomorrow.date().isoformat()
    ]
    assert proposals
    assert all(r.details["intervals"][0][2]["asset_class"]["value"] == "BOND" for r in proposals)


def test_pause_hash_retains_revision_provenance_and_deterministic_collection_order():
    current = snap()
    paused = current.geography.model_copy(
        update={
            "evaluation_state": "PAUSED",
            "carried_from_revision_id": 3,
            "source_rule_version": "1.0.0",
            "source_enum_version": "1.0.0",
        }
    )
    first = current.model_copy(update={"geography": paused})
    second = first.model_copy(
        update={"geography": paused.model_copy(update={"carried_from_revision_id": 4})}
    )
    assert module._hash([(DAY, None, first, {})]) != module._hash([(DAY, None, second, {})])
    reordered = current.model_copy(update={"review_items": tuple(reversed(current.review_items))})
    assert module._hash([(DAY, None, current, {})]) == module._hash([(DAY, None, reordered, {})])


def test_mixed_case_leaves_paused_history_pending_after_active_review():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session, snap(v3=False), reviewed=True)
    persist(session, snap(), at=LATER)
    case = next(
        c for c in service.active_review_cases(1) if c.issue_type == "NEW_EVIDENCE_AFTER_REVIEW"
    )
    case.details = {**case.details, "source_dimensions": ["asset_class", "strategy", "geography"]}
    result = service.review(
        case.id,
        expected_revision=baseline.id,
        decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
        tag_decisions={
            "QUANTITATIVE": module.StrategyTagDecision(
                action="REJECT", evidence=(ev("strategy", "manual"),)
            )
        },
        accept_incoming_version="3.0.0",
        actor="reviewer",
        reason="active only",
        can_review=True,
        reviewed_at=LATER,
    )
    assert result.rule_version == "3.0.0"
    assert case.status == "PENDING"
    assert case.details["evaluation_state"] == "PAUSED"
    assert case not in service.active_review_cases(1)


def test_nonmember_and_empty_membership_do_not_infer_active():
    session = MemorySession()
    service = module.ClassificationService(session)
    revision = service.refresh_v3(
        1,
        [ev("formal_type", "股票型"), ev("index_membership", "")],
        available_at=NOW,
        actor="source",
        reason="not listed",
    )
    assert service.intervals(revision.id)[-1][2].strategy.value == "UNKNOWN"


def test_pit_chooses_highest_visible_version_not_latest_source_timestamp():
    session = MemorySession()
    persist(session, snap(v3=False), at=LATER)
    highest = persist(session, snap(ev("formal_type", "债券型-长债")), at=NOW)
    assert SqlClassificationPitRepository(session, LATER).snapshot(1)["revision_id"] == highest.id


def test_manual_tag_rejection_is_persisted_and_can_admit_evaluated_nonquant_active():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(
        session,
        snap(
            ev("formal_type", "股票型"),
            ev("investment_strategy", "本基金采用量化模型和主动管理策略。"),
        ),
    )
    # A service case may originate from source diagnostics or a controlled re-review.
    case = service._case(
        baseline,
        "manual-tag",
        "TAG_REVIEW",
        {"dimension": "strategy_tags.QUANTITATIVE", "valid_from": DAY.isoformat()},
        NOW,
    )
    revision = service.review(
        case.id,
        expected_revision=baseline.id,
        decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
        tag_decisions={
            "QUANTITATIVE": module.StrategyTagDecision(
                action="REJECT", evidence=(ev("strategy", "reviewed explicit rejection"),)
            )
        },
        actor="reviewer",
        reason="contract disproves tag",
        can_review=True,
        reviewed_at=LATER,
    )
    result = service.intervals(revision.id)[-1][2]
    assert result.strategy_tag_results["QUANTITATIVE"].manual_action == "REJECT"
    assert project_legacy(result, grouping_confirmed=True).value is None
    assert (
        SqlClassificationPitRepository(session, LATER).current(1).classification_code
        == "ACTIVE_EQUITY"
    )
    service.refresh_v3(
        1,
        [ev("investment_strategy", "本基金采用量化模型和主动管理策略。", at=LATER)],
        available_at=LATER,
        actor="source",
        reason="cannot restore rejected tag",
    )
    assert service.latest(1) is revision
    assert service.intervals(revision.id)[-1][2].strategy_tags == ()


def test_direct_v3_write_carries_paused_facts_without_reinterpreting_v1_quant():
    session = MemorySession()
    service = module.ClassificationService(session)
    old = snap(
        ev("formal_type", "股票型"), ev("strategy", "QUANTITATIVE"), ev("geography", "US"), v3=False
    )
    first = persist(session, old)
    second = persist(session, snap(ev("formal_type", "股票型")), at=LATER)
    result = service.intervals(second.id)[-1][2]
    assert result.geography.value == ("US",)
    assert result.geography.evaluation_state == "PAUSED"
    assert result.geography.carried_from_revision_id == first.id
    assert result.strategy.value == "UNKNOWN"
    assert result.strategy_tag_results["QUANTITATIVE"].evaluation_state == "NOT_EVALUATED"
    assert service.intervals(first.id)[-1][2].to_dict() == old.to_dict()


def test_v3_history_preserves_supplied_source_timestamps():
    session = MemorySession()
    persist(
        session,
        published_at=NOW - dt.timedelta(days=1),
        provider_available_at=NOW,
        ingested_at=NOW,
        availability_quality="EXACT",
    )
    row = SqlClassificationPitRepository(session, NOW).history(1)[0]
    assert row["published_at"] == (NOW - dt.timedelta(days=1)).isoformat()
    assert row["provider_available_at"] == NOW.isoformat()
    assert row["ingested_at"] == NOW.isoformat()
    assert row["availability_quality"] == "EXACT"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"published_at": LATER},
        {"ingested_at": NOW - dt.timedelta(hours=1), "provider_available_at": NOW},
        {"availability_quality": "EXACT"},
        {"published_at": NOW.replace(tzinfo=None)},
    ],
)
def test_source_timestamp_inconsistency_is_rejected_before_any_revision_write(kwargs):
    session = MemorySession()
    with pytest.raises(ValueError):
        persist(session, **kwargs)
    assert not any(isinstance(r, FundClassificationRevision) for r in session.rows)


def test_paused_pending_cases_are_hidden_while_reviewed_v3_upgrade_is_still_proposed():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session, snap(v3=False), reviewed=True)
    paused = next(
        c for c in service.active_review_cases(1) if c.details.get("dimension") == "geography"
    )
    persist(session, snap(), at=LATER)
    assert service.latest(1) is baseline
    assert paused.status == "PENDING"
    assert paused.details["evaluation_state"] == "PAUSED"
    assert paused not in service.active_review_cases(1)


def test_mixed_historical_case_is_not_silently_superseded_by_automatic_v3_write():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session, snap(v3=False))
    mixed = service._case(
        baseline,
        "mixed-history",
        "UNKNOWN",
        {"source_dimensions": ["strategy", "geography"], "valid_from": DAY.isoformat()},
        NOW,
    )
    persist(session, snap(), at=LATER)
    assert mixed.status == "PENDING"
    assert mixed.details["evaluation_state"] == "PAUSED"
    assert mixed.details["source_dimensions"] == ["strategy", "geography"]
    assert mixed not in service.active_review_cases(1)


def test_physical_observation_replacement_is_not_split_by_normalizer_metadata():
    session = MemorySession()
    service = module.ClassificationService(session)
    old = ev("formal_type", "股票型")
    service.refresh_v3(1, [old], available_at=NOW, actor="source", reason="initial")
    replacement = old.model_copy(
        update={"normalized_field": "provider_type", "raw_value": "", "classified_at": LATER}
    )
    revision = service.refresh_v3(
        1, [replacement], available_at=LATER, actor="source", reason="empty physical field"
    )
    result = service.intervals(revision.id)[-1][2]
    assert result.asset_class.status == "UNKNOWN"
    assert len(result.observations) == 1


def test_hash_sorts_intervals_but_retains_membership_indicator_and_stable_row_identity():
    snapshot = snap()
    first = (DAY, DAY + dt.timedelta(days=1), snapshot, {})
    second = (DAY + dt.timedelta(days=1), None, snapshot, {})
    assert module._hash([first, second]) == module._hash([second, first])
    raw = ev("formal_type", "股票型")
    for parameter in [
        {"indicator": "被动指数型"},
        {"indicator": "增强指数型"},
        {"stable_row_id": "B"},
    ]:
        identity, _ = json.JSONDecoder().raw_decode(raw.locator[len("identity:") :])
        identity.update(parameter)
        changed = raw.model_copy(update={"locator": "identity:" + json.dumps(identity) + ";row:0"})
        assert module._hash([(DAY, None, snap(raw), {})]) != module._hash(
            [(DAY, None, snap(changed), {})]
        )


def test_v3_direct_write_and_review_do_not_backdate_new_evidence():
    session = MemorySession()
    with pytest.raises(ValueError, match="available_at"):
        persist(session, snap(ev("formal_type", "股票型", at=LATER)))
    baseline = persist(session, snap(ev("formal_type", "股票型")))
    case = pending(session, baseline)
    with pytest.raises(ValueError, match="reviewed_at"):
        module.ClassificationService(session).review(
            case.id,
            expected_revision=baseline.id,
            decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
            actor="reviewer",
            reason="too early",
            can_review=True,
            reviewed_at=NOW - dt.timedelta(days=1),
        )


def test_v3_interval_revision_does_not_create_paused_cases_for_copied_v1_history():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session, snap(v3=False))
    future = service.write(
        1,
        snap(),
        valid_from=DAY + dt.timedelta(days=1),
        available_at=LATER,
        actor="source",
        reason="future v3 effective date",
    )
    assert service.intervals(future.id)[0][2].rule_version == "1.0.0"
    assert service.intervals(baseline.id)[0][2].rule_version == "1.0.0"
    assert not any(
        c.revision_id == future.id
        and c.details.get("dimension") in {"geography", "product_structure", "market_attributes"}
        for c in service.active_review_cases(1)
    )


def test_paused_case_cannot_be_reviewed_directly_with_current_v1_baseline_revision():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session, snap(v3=False), reviewed=True)
    case = next(
        c for c in service.active_review_cases(1) if c.details.get("dimension") == "geography"
    )
    persist(session, snap(), at=LATER)
    before = list(session.rows)
    assert case.details["evaluation_state"] == "PAUSED"
    with pytest.raises(ValueError, match="paused"):
        service.review(
            case.id,
            expected_revision=baseline.id,
            decisions={"geography": decision("US")},
            actor="reviewer",
            reason="must remain historical",
            can_review=True,
            reviewed_at=LATER,
        )
    assert session.rows == before
    assert service.latest(1) is baseline
    assert case.status == "PENDING"
    assert case.resolved_at is None


@pytest.mark.parametrize(
    "locator",
    [
        None,
        "p.2",
        "identity:{};row:0",
        'identity:{"provider":"SNOWBALL","dataset":"fund_detail_xq","provider_fund_code":"","params":{},"raw_field":"formal_type"};row:0',
    ],
)
def test_new_refresh_input_requires_stable_provider_share_identity(locator):
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session)
    unsafe = ev("formal_type", "").model_copy(update={"locator": locator})
    before = list(session.rows)
    with pytest.raises(ValueError, match="identity"):
        service.refresh_v3(1, [unsafe], available_at=LATER, actor="source", reason="unsafe empty")
    assert session.rows == before
    assert service.latest(1) is baseline
    assert service.intervals(baseline.id)[-1][2].asset_class.value == "EQUITY"


def test_incomplete_legacy_observations_are_preserved_separately_during_safe_partial_refresh():
    session = MemorySession()
    service = module.ClassificationService(session)
    share_a = ev("formal_type", "股票型", payload="raw:A").model_copy(update={"locator": None})
    share_b = ev("formal_type", "债券型-长债", payload="raw:B").model_copy(update={"locator": None})
    persist(session, snap(share_a, share_b))
    revision = service.refresh_v3(
        1,
        [ev("investment_strategy", "本基金采用主动管理策略。")],
        available_at=LATER,
        actor="source",
        reason="other physical field",
    )
    result = service.intervals(revision.id)[-1][2]
    assert result.asset_class.status == "CONFLICT"
    assert {e.payload_ref for e in result.observations if e.raw_field == "formal_type"} == {
        "raw:A",
        "raw:B",
    }


def test_ordinary_write_cannot_admit_unaudited_manual_tag_rejection():
    session = MemorySession()
    tag = StrategyTagResult(
        status="UNKNOWN",
        evaluation_state="EVALUATED",
        manual_action="REJECT",
        evidence=(ev("strategy", "unreviewed claim"),),
    )
    snapshot = snap().model_copy(
        update={"strategy_tag_results": {"QUANTITATIVE": tag}, "strategy_tags": ()}
    )
    assert project_legacy(snapshot, grouping_confirmed=True).value is None
    persist(session, snapshot, reviewed=True)
    assert SqlClassificationPitRepository(session, NOW).current(1).classification_code == "UNKNOWN"


def test_audited_review_admits_manual_tag_rejection_only_for_matching_result_tag():
    session = MemorySession()
    service = module.ClassificationService(session)
    baseline = persist(session, snap(ev("formal_type", "股票型")))
    case = pending(session, baseline)
    revision = service.review(
        case.id,
        expected_revision=baseline.id,
        decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
        tag_decisions={
            "QUANTITATIVE": module.StrategyTagDecision(
                action="REJECT", evidence=(ev("strategy", "verified rejection"),)
            )
        },
        actor="reviewer",
        reason="contract rules out quant",
        can_review=True,
        reviewed_at=LATER,
    )
    current = SqlClassificationPitRepository(session, LATER).current(1)
    assert current.classification_code == "ACTIVE_EQUITY"
    audit = next(r for r in session.rows if isinstance(r, AuditLog) and r.action == "REVIEW")
    assert audit.detail["result_tag_results"]["QUANTITATIVE"]["manual_action"] == "REJECT"
    audit.detail = {**audit.detail, "result_tag_results": {}}
    assert (
        SqlClassificationPitRepository(session, LATER).current(1).classification_code == "UNKNOWN"
    )
    assert service.latest(1) is revision


def test_authorized_tag_admission_is_bound_to_exact_reviewed_result_across_intervals():
    from fip.services.data_service.models.fund import FundClassificationHistory

    session = MemorySession()
    service = module.ClassificationService(session)
    forged = StrategyTagResult(
        status="UNKNOWN",
        evaluation_state="EVALUATED",
        manual_action="REJECT",
        evidence=(ev("strategy", "unreviewed historical claim"),),
    )
    historical = snap().model_copy(
        update={"strategy_tag_results": {"QUANTITATIVE": forged}, "strategy_tags": ()}
    )
    tomorrow = DAY + dt.timedelta(days=1)
    baseline = service.replace_intervals(
        1,
        [(DAY, tomorrow, historical), (tomorrow, None, snap(ev("formal_type", "股票型")))],
        available_at=NOW,
        actor="source",
        reason="two intervals",
    )
    case = next(
        c
        for c in service.active_review_cases(1)
        if c.details.get("valid_from") == tomorrow.isoformat()
    )
    reviewed = service.review(
        case.id,
        expected_revision=baseline.id,
        decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
        tag_decisions={
            "QUANTITATIVE": module.StrategyTagDecision(
                action="REJECT", evidence=(ev("strategy", "authorized different result"),)
            )
        },
        actor="reviewer",
        reason="one reviewed interval only",
        can_review=True,
        reviewed_at=LATER,
    )
    old_interval = next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationHistory)
        and r.revision_id == reviewed.id
        and r.valid_from == DAY
    )
    assert old_interval.classification_code == "UNKNOWN"


def bounded_tag_review_fixture():
    """Identical tag JSON exists before, inside, and after the reviewed range."""
    session = MemorySession()
    service = module.ClassificationService(session)
    start = DAY + dt.timedelta(days=1)
    split = DAY + dt.timedelta(days=2)
    end = DAY + dt.timedelta(days=3)
    evidence = ev("strategy", "bounded audited rejection")
    exact_tag = StrategyTagResult(
        status="UNKNOWN", evaluation_state="EVALUATED", manual_action="REJECT", evidence=(evidence,)
    )
    copied = snap().model_copy(
        update={"strategy_tag_results": {"QUANTITATIVE": exact_tag}, "strategy_tags": ()}
    )
    middle = snap(ev("formal_type", "股票型"))
    baseline = service.replace_intervals(
        1,
        [
            (DAY, start, copied),
            (start, split, middle, {"status": "ALLOWED"}),
            (split, end, middle, {"status": "BLOCKED"}),
            (end, None, copied),
        ],
        available_at=NOW,
        actor="source",
        reason="bounded fixture with trading split",
    )
    case = service._case(
        baseline,
        "bounded-review",
        "TAG_REVIEW",
        {
            "dimension": "strategy_tags.QUANTITATIVE",
            "valid_from": start.isoformat(),
            "valid_to": end.isoformat(),
        },
        NOW,
    )
    revision = service.review(
        case.id,
        expected_revision=baseline.id,
        decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
        tag_decisions={
            "QUANTITATIVE": module.StrategyTagDecision(action="REJECT", evidence=(evidence,))
        },
        actor="reviewer",
        reason="bounded review only",
        can_review=True,
        reviewed_at=LATER,
    )
    return session, service, revision, exact_tag, start, split, end


def test_identical_reviewed_tag_is_authorized_only_inside_reviewed_range_in_result_revision():
    from fip.services.data_service.models.fund import FundClassificationHistory

    session, service, revision, exact_tag, start, split, end = bounded_tag_review_fixture()
    rows = {
        r.valid_from: r
        for r in session.rows
        if isinstance(r, FundClassificationHistory) and r.revision_id == revision.id
    }
    assert all(
        r.classification_result["strategy_tag_results"]["QUANTITATIVE"]
        == exact_tag.model_dump(mode="json")
        for r in rows.values()
    )
    assert rows[DAY].classification_code == "UNKNOWN"
    assert rows[start].classification_code == "ACTIVE_EQUITY"
    assert rows[split].classification_code == "ACTIVE_EQUITY"
    assert rows[end].classification_code == "UNKNOWN"
    for day, expected in [
        (DAY, "UNKNOWN"),
        (start, "ACTIVE_EQUITY"),
        (split, "ACTIVE_EQUITY"),
        (end, "UNKNOWN"),
    ]:
        point = SqlClassificationPitRepository(session, LATER + (day - DAY)).current(1)
        assert point.classification_code == expected
    audit = next(r for r in session.rows if isinstance(r, AuditLog) and r.action == "REVIEW")
    assert audit.detail["valid_from"] == start.isoformat()
    assert audit.detail["valid_to"] == end.isoformat()
    assert audit.detail["revision_id"] == revision.id


def test_exact_audited_tag_copy_cannot_inherit_admission_in_an_unrelated_revision():
    from fip.services.data_service.models.fund import FundClassificationHistory

    session, service, reviewed, _, start, _, end = bounded_tag_review_fixture()
    snapshot = next(v[2] for v in service.intervals(reviewed.id) if v[0] == start)
    copied = service.replace_intervals(
        1,
        [
            (start, end, snapshot, {"status": "ALLOWED"}),
            (end, None, snapshot, {"status": "BLOCKED"}),
        ],
        available_at=LATER + dt.timedelta(hours=1),
        actor="source",
        reason="copy without new review",
        reviewed=True,
    )
    assert copied.id != reviewed.id
    assert all(
        r.classification_code == "UNKNOWN"
        for r in session.rows
        if isinstance(r, FundClassificationHistory) and r.revision_id == copied.id
    )
    assert (
        SqlClassificationPitRepository(session, LATER + dt.timedelta(days=1))
        .current(1)
        .classification_code
        == "UNKNOWN"
    )
    assert (
        SqlClassificationPitRepository(session, LATER + dt.timedelta(days=4))
        .current(1)
        .classification_code
        == "UNKNOWN"
    )


def review_identical_snapshot(service, baseline, case):
    """Use the same authorized inputs when preparing and testing boundary copies."""
    return service.review(
        case.id,
        expected_revision=baseline.id,
        decisions={"asset_class": decision("EQUITY"), "strategy": decision()},
        tag_decisions={
            "QUANTITATIVE": module.StrategyTagDecision(
                action="REJECT", evidence=(ev("strategy", "scope-only rejection"),)
            )
        },
        actor="reviewer",
        reason="one bounded interval",
        can_review=True,
        reviewed_at=LATER,
    )


def test_review_boundaries_survive_merging_identical_snapshot_and_trading_rows():
    from fip.services.data_service.models.fund import FundClassificationHistory

    # Prepare the exact full result via real review, including retained evidence
    # and raw observations, rather than guessing the service's serialized result.
    template_session = MemorySession()
    template_service = module.ClassificationService(template_session)
    template = persist(template_session, snap(ev("formal_type", "股票型")))
    template_revision = review_identical_snapshot(
        template_service, template, pending(template_session, template)
    )
    identical = template_service.intervals(template_revision.id)[-1][2]

    session = MemorySession()
    service = module.ClassificationService(session)
    start = DAY + dt.timedelta(days=1)
    end = DAY + dt.timedelta(days=3)
    baseline = service.replace_intervals(
        1,
        [
            (DAY, start, identical),
            (start, end, snap(ev("formal_type", "股票型"))),
            (end, None, identical),
        ],
        available_at=NOW,
        actor="source",
        reason="identical outside copies",
    )
    case = next(
        c
        for c in service.active_review_cases(1)
        if c.details.get("valid_from") == start.isoformat()
    )
    revision = review_identical_snapshot(service, baseline, case)
    rows = sorted(
        (
            r
            for r in session.rows
            if isinstance(r, FundClassificationHistory) and r.revision_id == revision.id
        ),
        key=lambda r: r.valid_from,
    )
    assert [(r.valid_from, r.valid_to) for r in rows] == [(DAY, start), (start, end), (end, None)]
    assert all(r.classification_result == identical.to_dict() for r in rows)
    assert all(r.trading_eligibility == {"status": "UNKNOWN"} for r in rows)
    assert [r.classification_code for r in rows] == ["UNKNOWN", "ACTIVE_EQUITY", "UNKNOWN"]
    for day, expected in [(DAY, "UNKNOWN"), (start, "ACTIVE_EQUITY"), (end, "UNKNOWN")]:
        assert (
            SqlClassificationPitRepository(session, LATER + (day - DAY))
            .current(1)
            .classification_code
            == expected
        )
    # Replaying the identical result must retain its persisted review boundaries;
    # losing those boundaries must not manufacture a new-evidence proposal.
    before = list(service.active_review_cases(1))
    assert (
        service.write(
            1,
            identical,
            valid_from=DAY,
            available_at=LATER + dt.timedelta(hours=1),
            actor="source",
            reason="identical replay",
        )
        is revision
    )
    assert service.active_review_cases(1) == before

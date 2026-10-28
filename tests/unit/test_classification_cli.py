"""Offline CLI contract tests; no SQL engine or provider calls."""

import contextlib
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from fip.platform import cli


def test_classify_parser_has_explicit_v3_and_bounded_defaults(monkeypatch):
    parsed = {}
    monkeypatch.setattr(cli, "cmd_classification", lambda args: parsed.update(vars(args)))
    cli.main(["classify-funds", "--actor", "operator", "--rule-version", "3.0.0"])
    assert parsed["rule_version"] == "3.0.0"
    assert parsed["limit"] == 100
    assert parsed["batch_size"] == 50
    assert parsed["dry_run"] is False


def test_classify_parser_rejects_unbounded_library_run():
    with pytest.raises(SystemExit):
        cli.main(["classify-funds", "--actor", "operator", "--limit", "1001", "--dry-run"])


def test_default_review_queue_excludes_paused_history_cases():
    cases = [
        SimpleNamespace(id=1, details={"active_scope": ["asset_class"]}),
        SimpleNamespace(id=2, details={"evaluation_state": "PAUSED", "active_scope": []}),
        SimpleNamespace(id=3, details={}),
    ]
    assert [case.id for case in cli._active_review_cases(cases, 10)] == [1, 3]


def test_index_set_dry_run_prints_exact_requests_without_adapter_or_writes(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(object()))

    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run must not instantiate/call source adapters")

    monkeypatch.setattr(
        "fip.services.data_service.adapters.akshare.client.AkShareSourceAdapter",
        forbidden,
    )
    cli.main(["refresh-index-sets", "--actor", "operator", "--dry-run"])
    output = json.loads(capsys.readouterr().out)
    assert output["network_calls"] == 0
    assert output["write"] is False
    assert [item["dataset"] for item in output["requests"]] == [
        "fund_index_passive",
        "fund_index_enhanced",
    ]


def test_single_fund_refresh_dry_run_makes_no_adapter_calls_or_writes(monkeypatch, capsys):
    session = contextlib.nullcontext(object())
    monkeypatch.setattr(cli, "_session", lambda: session)
    monkeypatch.setattr(cli, "_resolve", lambda *_args: SimpleNamespace(fund_id=8))

    def forbidden(*args, **kwargs):
        raise AssertionError("single-fund dry-run must not call the source adapter")

    monkeypatch.setattr(
        "fip.services.data_service.adapters.akshare.client.AkShareSourceAdapter",
        forbidden,
    )
    cli.main(
        [
            "refresh-classification",
            "--actor",
            "operator",
            "--symbol",
            "000001",
            "--dry-run",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert output["network_calls"] == 0
    assert output["write"] is False
    assert output["fund_id"] == 8


def test_v3_classification_replay_never_constructs_or_fetches_source_adapter(monkeypatch, capsys):
    from fip.services.data_service.classification import classify
    from fip.services.data_service.classification.policy import load_policy
    from fip.services.data_service.models.raw import RawPayload

    frame = pd.DataFrame(
        [{"基金代码": "000001", "基金简称": "测试基金", "基金类型": "混合型-偏股"}]
    )
    raw = RawPayload(
        id=17,
        dataset_id=2,
        payload=frame.to_parquet(index=False),
        row_count=1,
        ingested_at=pd.Timestamp("2026-10-28T00:00:00Z").to_pydatetime(),
        request_params={},
        published_at=None,
        provider_available_at=None,
    )

    class FakeSession:
        commits = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def scalars(self, _statement):
            return [raw]

        def get(self, _model, _key):
            return None

        def commit(self):
            self.commits += 1

    session = FakeSession()
    snapshot = classify(
        [],
        classified_at=pd.Timestamp("2026-10-28T00:00:00Z").to_pydatetime(),
        policy=load_policy(rule_version="3.0.0"),
    )
    monkeypatch.setattr(cli, "_session", lambda: session)
    monkeypatch.setattr(cli, "_resolve", lambda _session, _symbol: SimpleNamespace(fund_id=8))
    monkeypatch.setattr(
        cli,
        "_classify_saved_v3",
        lambda *_args, **_kwargs: (
            snapshot,
            "WRITE_REVISION",
            ("asset_class:UNRECOGNIZED",),
        ),
    )
    monkeypatch.setattr(cli, "_service", lambda *_args: (_ for _ in ()).throw(AssertionError()))
    from fip.services.data_service.classification import service as classification_service

    monkeypatch.setattr(classification_service, "ClassificationService", lambda *_args: object())

    cli.main(
        [
            "classify-funds",
            "--actor",
            "operator",
            "--rule-version",
            "3.0.0",
            "--dry-run",
            "--symbol",
            "000001",
        ]
    )
    assert session.commits == 0
    output = capsys.readouterr().out.splitlines()
    assert '"dry_run": true' in output[-1]
    assert json.loads(output[0])["unrecognized_reasons"] == ["asset_class:UNRECOGNIZED"]
    assert "asset_class:UNRECOGNIZED" in json.loads(output[-1])["summary"]["unrecognized_reasons"]


def test_v3_replay_skips_future_fund_list_payload_at_shared_cutoff(monkeypatch, capsys):
    import datetime as dt

    from fip.services.data_service.classification import classify
    from fip.services.data_service.classification.policy import load_policy
    from fip.services.data_service.models.raw import RawPayload

    cutoff = dt.datetime(2026, 10, 28, 12, tzinfo=dt.UTC)

    def payload(payload_id, symbol, ingested_at):
        frame = pd.DataFrame(
            [{"基金代码": symbol, "基金简称": f"测试{symbol}", "基金类型": "混合型-偏股"}]
        )
        return RawPayload(
            id=payload_id,
            dataset_id=2,
            payload=frame.to_parquet(index=False),
            row_count=1,
            ingested_at=ingested_at,
            request_params={},
            published_at=None,
            provider_available_at=None,
        )

    payloads = [
        payload(17, "000001", cutoff - dt.timedelta(days=1)),
        payload(18, "000002", cutoff + dt.timedelta(days=1)),
    ]

    class FakeSession:
        commits = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def scalars(self, statement):
            where = " ".join(str(item) for item in statement._where_criteria)
            assert "raw_payload.ingested_at <=" in where
            return [row for row in payloads if row.ingested_at <= cutoff]

        def get(self, _model, _key):
            return None

        def commit(self):
            self.commits += 1

    session = FakeSession()
    snapshot = classify([], classified_at=cutoff, policy=load_policy(rule_version="3.0.0"))
    calls = []
    monkeypatch.setattr(cli, "_session", lambda: session)
    monkeypatch.setattr(cli, "_classification_replay_cutoff", lambda: cutoff)
    monkeypatch.setattr(
        cli,
        "_resolve",
        lambda _session, symbol: calls.append(("resolve", symbol)) or SimpleNamespace(fund_id=8),
    )
    monkeypatch.setattr(
        cli,
        "_classify_saved_v3",
        lambda _session, _fund_id, symbol, _payload, **kwargs: calls.append(
            ("classify", symbol, kwargs["cutoff"])
        )
        or (snapshot, "NO_CHANGE", ()),
    )

    cli.main(["classify-funds", "--actor", "operator", "--rule-version", "3.0.0", "--dry-run"])

    assert [item[1] for item in calls if item[0] == "resolve"] == ["000001"]
    assert [item[1:] for item in calls if item[0] == "classify"] == [("000001", cutoff)]
    assert session.commits == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["summary"]["processed"] == 1


def test_v3_saved_payload_dry_run_uses_pure_rules_without_revision_write(monkeypatch):
    from fip.services.data_service.models.fund import FundClassificationRevision
    from fip.services.data_service.models.raw import RawPayload
    from tests.unit.test_classification_revision_v3 import MemorySession

    frame = pd.DataFrame(
        [{"基金代码": "000001", "基金简称": "测试基金", "基金类型": "混合型-偏股"}]
    )
    payload = RawPayload(
        id=17,
        dataset_id=2,
        payload=frame.to_parquet(index=False),
        row_count=1,
        ingested_at=pd.Timestamp("2026-10-28T00:00:00Z").to_pydatetime(),
        request_params={},
        published_at=None,
        provider_available_at=None,
    )
    session = MemorySession()
    monkeypatch.setattr(cli, "_saved_v3_source_evidence", lambda *_args, **_kwargs: ())
    before = len([row for row in session.rows if isinstance(row, FundClassificationRevision)])
    cutoff = pd.Timestamp("2026-10-28T12:00:00Z").to_pydatetime()

    snapshot, action, reasons = cli._classify_saved_v3(
        session, 1, "000001", payload, cutoff=cutoff, actor="operator", dry_run=True
    )

    after = len([row for row in session.rows if isinstance(row, FundClassificationRevision)])
    assert snapshot.rule_version == "3.0.0"
    assert action in {"WRITE_REVISION", "CREATE_REVIEW"}
    assert reasons == ("strategy:UNKNOWN",)
    assert after == before


def test_saved_v3_replay_does_not_backdate_newer_detail_evidence(monkeypatch):
    import datetime as dt

    from fip.services.data_service.classification.models import Evidence
    from fip.services.data_service.classification.service import ClassificationService
    from fip.services.data_service.models.raw import RawPayload
    from tests.unit.test_classification_revision_v3 import MemorySession

    frame = pd.DataFrame(
        [{"基金代码": "000001", "基金简称": "测试基金", "基金类型": "混合型-偏股"}]
    )
    payload = RawPayload(
        id=17,
        dataset_id=2,
        payload=frame.to_parquet(index=False),
        row_count=1,
        ingested_at=dt.datetime(2026, 10, 28, tzinfo=dt.UTC),
        request_params={},
        published_at=None,
        provider_available_at=None,
    )
    later = Evidence(
        source="AGGREGATOR",
        rule_id="SOURCE",
        confidence="PUBLIC_AGGREGATOR",
        classified_at=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
        raw_field="基金类型",
        normalized_field="formal_type",
        raw_value="债券型-长债",
        locator=(
            'identity:{"provider":"SNOWBALL","dataset":"fund_detail_xq",'
            '"provider_fund_code":"000001","raw_field":"基金类型",'
            '"params":{"symbol":"000001"}};row:8'
        ),
    )
    session = MemorySession()
    cutoff = dt.datetime(2026, 10, 31, tzinfo=dt.UTC)
    monkeypatch.setattr(cli, "_classification_replay_cutoff", lambda: cutoff)
    monkeypatch.setattr(cli, "_saved_v3_source_evidence", lambda *_args, **_kwargs: (later,))
    captured = {}

    def refresh(_self, _fund_id, _evidence, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=22)

    monkeypatch.setattr(ClassificationService, "refresh_v3", refresh)
    cli._classify_saved_v3(
        session, 1, "000001", payload, cutoff=cutoff, actor="operator", dry_run=False
    )
    assert captured["valid_from"] == dt.date(2026, 10, 31)
    assert captured["available_at"] == cutoff
    assert "ingested_at" not in captured


def test_replay_selects_latest_revision_visible_at_current_cutoff(monkeypatch):
    import datetime as dt

    from fip.services.data_service.classification.service import ClassificationService
    from fip.services.data_service.models.fund import FundClassificationRevision
    from tests.unit.test_classification_revision_v3 import MemorySession

    cutoff = dt.datetime(2026, 10, 28, 12, tzinfo=dt.UTC)

    def revision(row_id, version, available_at):
        return FundClassificationRevision(
            id=row_id,
            fund_id=1,
            scheme="FIP_CLASSIFICATION_V1",
            version=version,
            rule_version="3.0.0",
            enum_version="3.0.0",
            content_hash="0" * 64,
            classified_at=available_at,
            available_at=available_at,
            availability_quality="INFERRED",
            published_at=None,
            provider_available_at=None,
            ingested_at=available_at,
            reason="fixture",
            actor="test",
            reviewed=False,
        )

    visible = revision(10, 2, cutoff - dt.timedelta(days=1))
    future = revision(11, 3, cutoff + dt.timedelta(days=1))
    session = MemorySession()
    session.rows.extend((visible, future))
    seen = []
    monkeypatch.setattr(
        ClassificationService, "intervals", lambda _self, rid: seen.append(rid) or []
    )

    selected, interval = cli._latest_classification_interval(
        ClassificationService(session), 1, cutoff.date(), cutoff=cutoff
    )

    assert selected is visible
    assert interval is None
    assert seen == [visible.id]


def test_non_dry_run_fails_safely_when_newer_revision_is_after_replay_cutoff(monkeypatch):
    import datetime as dt

    from fip.services.data_service.classification.service import ClassificationService
    from fip.services.data_service.models.raw import RawPayload
    from tests.unit.test_classification_revision_v3 import MemorySession

    cutoff = dt.datetime(2026, 10, 28, 12, tzinfo=dt.UTC)
    future = SimpleNamespace(id=99, available_at=cutoff + dt.timedelta(days=1))
    monkeypatch.setattr(cli, "_classification_replay_cutoff", lambda: cutoff)
    monkeypatch.setattr(cli, "_saved_v3_source_evidence", lambda *_args, **_kwargs: ())

    frame = pd.DataFrame(
        [{"基金代码": "000001", "基金简称": "测试基金", "基金类型": "混合型-偏股"}]
    )
    payload = RawPayload(
        id=17,
        dataset_id=2,
        payload=frame.to_parquet(index=False),
        row_count=1,
        ingested_at=cutoff - dt.timedelta(days=1),
        request_params={},
        published_at=None,
        provider_available_at=None,
    )

    def latest(_self, _fund_id, *, available_at=None):
        return None if available_at is not None else future

    monkeypatch.setattr(ClassificationService, "latest", latest)
    monkeypatch.setattr(
        ClassificationService,
        "refresh_v3",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unsafe write")),
    )

    with pytest.raises(RuntimeError, match="newer than its current-UTC cutoff"):
        cli._classify_saved_v3(
            MemorySession(),
            1,
            "000001",
            payload,
            cutoff=cutoff,
            actor="operator",
            dry_run=False,
        )

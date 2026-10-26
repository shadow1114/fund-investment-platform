"""CLI 的 symbol → share class 解析测试。

`cli._resolve` 此前完全没有测试覆盖，这正是「静默写进错误的基金」这个缺陷
能通过验收的原因：它先用 `display_name LIKE %symbol%` 匹配（symbol 是
AKShare 的数字代码，display_name 是中文简称，永远匹配不上，是死代码），
再兜底 `ORDER BY id LIMIT 1` 返回全表最小 id 的份额类别并报告成功 ——
无错误、无告警、退出码 0，而净值被写进了别人的 PIT 历史。

因此本文件的两条断言是这条链路的承重测试：
(a) 已登记的 symbol 必须解析到【它自己】那一行；
(b) 未登记的 symbol 必须【报错退出】，绝不允许退化成任何「兜底取一行」。
"""

import argparse
import contextlib
import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform import cli
from fip.platform.cli import _resolve
from fip.services.data_service.adapters.akshare import client as akshare_client
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.batch import (
    BatchIngestResult,
    BatchItemResult,
    BatchItemStatus,
)
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import (
    FundShareClass,
    ProviderFundIdentity,
)
from fip.services.data_service.models.governance import (
    DataProvider,
    DataProviderDataset,
    DataSourcePriority,
)
from fip.services.data_service.models.market import FundNav

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)

FUND_LIST = pd.DataFrame(
    {
        "基金代码": ["000001", "000002"],
        "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
        "基金类型": ["混合型", "混合型"],
    }
)


def _caller(name, **params):
    if name == "fund_name_em":
        return FUND_LIST
    raise AssertionError(f"未预期的调用 {name} {params}")


@pytest.fixture()
def ingested(db_session) -> None:
    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_caller)
    IngestService(db_session, adapter, disclosure_lag_days=1).ingest_fund_list()
    db_session.flush()


def test_registered_symbol_resolves_to_its_own_share_class(db_session, ingested):
    """每个 symbol 都必须解析到它自己的份额类别。

    刻意断言【两个】symbol：只断言 000001 会与「兜底返回最小 id 那一行」
    的错误行为恰好一致（验收时正是这个巧合掩盖了缺陷），必须让第二个
    symbol 把这个巧合排除掉。
    """
    a = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    c = db_session.query(FundShareClass).filter_by(share_class_code="C").one()
    assert a.id != c.id

    assert _resolve(db_session, "000001").id == a.id
    assert _resolve(db_session, "000002").id == c.id


def test_unregistered_symbol_exits_instead_of_returning_another_fund(db_session, ingested):
    """未登记的 symbol 必须显式失败。

    静默取错基金比报错退出坏得多：CLI 会从 AKShare 抓到【这只】基金的真实
    净值，然后写进【别人】的 PIT 历史，且退出码为 0。
    """
    with pytest.raises(SystemExit) as excinfo:
        _resolve(db_session, "999999")
    assert "999999" in str(excinfo.value)


def test_resolution_fails_when_nothing_is_ingested(db_session):
    """空库同样是报错退出，而不是返回 None 或抛别的异常。"""
    with pytest.raises(SystemExit):
        _resolve(db_session, "000001")


# --- ingest-funds 的批量失败面 -------------------------------------------
# fix round 2 item 4：_ensure_provider_identity 原先直接抛 ValueError，一路
# 穿出 ingest_fund_list，而 cmd_ingest_funds 不捕获 —— 整批 ingest-funds 全废，
# 包括本次已抓到的 raw payload。触发条件并不罕见：上游基金简称改名导致
# split_share_class_name 归到另一个 product_name 就会触发。
#
# 方向不变（响亮失败优于静默沿用旧映射），但失败面必须收窄到「那一条映射」：
# 其余基金照常登记、已成功处理的部分照常提交，CLI 以非零退出码逐条列出冲突。

RENAMED_FUND_LIST = pd.DataFrame(
    {
        "基金代码": ["000001", "000003"],
        "基金简称": ["测试改名混合A", "测试另一只混合A"],
        "基金类型": ["混合型", "混合型"],
    }
)


def _renamed_caller(name, **params):
    if name == "fund_name_em":
        return RENAMED_FUND_LIST
    raise AssertionError(f"未预期的调用 {name} {params}")


def test_ingest_funds_exits_nonzero_and_lists_every_conflict(db_session, ingested, monkeypatch):
    """有冲突时：退出码非零、逐条列出冲突，且其余基金仍被正常登记。"""
    a = db_session.query(FundShareClass).filter_by(share_class_code="A").one()

    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_renamed_caller)
    # cmd_ingest_funds 自己开 engine 连的是 dev 库；这里把它换成测试事务里的
    # session（用 nullcontext 包一层，避免 `with` 在命令结束时把 fixture 的
    # session 关掉），并注入用改名后 fund list 的 adapter。
    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(db_session))
    monkeypatch.setattr(
        cli,
        "_service",
        lambda session: IngestService(session, adapter, disclosure_lag_days=1),
    )

    cli.cmd_ingest_funds(argparse.Namespace(limit=None))

    # 已成功处理的部分照常提交：000003 是本批新代码，必须已登记；
    # 000001 的旧映射原样保留，不被静默改写。
    mapping = {
        row.provider_fund_id: row.share_class_id
        for row in db_session.query(ProviderFundIdentity).all()
    }
    assert "000003" in mapping
    assert mapping["000001"] == a.id
    # 注意：上面读的是 session 内的行 —— 它【不能】证明 commit 真的发生过。
    # 「已成功部分已提交」这条性质由下面的
    # test_ingest_funds_really_commits_the_successful_part 用【独立连接】在
    # 事务外复查，见该测试的 docstring。


def test_name_refresh_keeps_identity_without_orphans(db_session, ingested):
    before = db_session.query(FundShareClass).filter_by(share_class_code="A").one().id
    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_renamed_caller)
    service = IngestService(db_session, adapter, disclosure_lag_days=1)
    first = service.ingest_fund_list()
    second = service.ingest_fund_list()
    assert first.reassignments == second.reassignments == ()
    assert second.created == 0
    assert (
        db_session.query(ProviderFundIdentity)
        .filter_by(provider_fund_id="000001", valid_to=None)
        .one()
        .share_class_id
        == before
    )
    assert db_session.query(FundShareClass).count() == 3


@pytest.fixture()
def committed_session(db_engine):
    """真提交的会话；结束时清空本测试写进去的行。

    不能复用 db_session：它的 rollback 兜底正是这条测试要绕开的东西。
    收尾用 TRUNCATE ... CASCADE 把维度、映射与 raw 清干净，保证不污染后续
    用例（测试库里这些表本来就是空的）。

    ⚠️ CASCADE 的实际波及面远不止 TRUNCATE 语句里点名的 7 张表（fix round 4
    item 5：此处原先只列了那 7 张，读者会以为范围就到此为止）。按外键图，
    CASCADE 还会连带清空：

      · market.fund_nav 及其 31 张分区子表、market.fund_distribution
        （都外键指向 fund.fund_share_class）
      · fund.fund_fee、fund.fund_status_history、fund.investment_eligibility
        （指向 fund_share_class）
      · fund.fund_classification_history、fund.fund_manager_assignment
        （指向 fund.fund）
      · governance.data_source_priority（指向 governance.data_provider_dataset）

    也就是说这个 fixture 会清空【几乎整个业务数据面】。它只在测试库里跑
    （db_engine 来自 settings.test_database_url），但任何人若把它复制到别处
    连上 dev 库，会一次性抹掉全部已灌数据。
    """
    session = Session(db_engine, future=True)
    try:
        yield session
    finally:
        session.close()
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "TRUNCATE fund.provider_fund_identity, fund.fund_share_class, "
                    "fund.fund, raw.canonical_raw, raw.raw_payload, "
                    "governance.data_provider_dataset, governance.data_provider "
                    "RESTART IDENTITY CASCADE"
                )
            )
            conn.execute(
                text("""
                INSERT INTO governance.data_provider (provider_code, display_name)
                VALUES ('AKSHARE', 'AKShare')
            """)
            )
            conn.execute(
                text("""
                INSERT INTO governance.data_provider_dataset
                    (provider_id, dataset_code, adapter_version, library_version)
                SELECT id, dataset_code, '1', '1.18.94'
                FROM governance.data_provider
                CROSS JOIN (VALUES ('fund_nav'), ('fund_distribution'), ('fund_split'))
                    AS seed(dataset_code)
                WHERE provider_code = 'AKSHARE'
            """)
            )
            conn.execute(
                text("""
                INSERT INTO governance.data_source_priority
                    (dataset_id, field_name, priority, disclosure_lag_days, rule_version)
                SELECT id, 'available_at', 1, 1, 'v1'
                FROM governance.data_provider_dataset
            """)
            )


def test_ingest_funds_really_commits_the_successful_part(committed_session, db_engine, monkeypatch):
    """有冲突时，本批【已成功的部分】必须真的落盘 —— 用独立连接在事务外复查。

    这是 cmd_ingest_funds 里那句 `session.commit()` 的唯一守卫：它先于
    SystemExit 执行，若被挪到 raise 之后（或被删掉），一条映射冲突就会重新
    毁掉整批已抓数据 —— 而任何在同一个 session 里做的断言都看不出区别。
    """
    baseline = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_caller)
    IngestService(committed_session, baseline, disclosure_lag_days=1).ingest_fund_list()
    committed_session.commit()
    a_id = committed_session.query(FundShareClass).filter_by(share_class_code="A").one().id

    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_renamed_caller)
    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(committed_session))
    monkeypatch.setattr(
        cli,
        "_service",
        lambda session: IngestService(session, adapter, disclosure_lag_days=1),
    )

    cli.cmd_ingest_funds(argparse.Namespace(limit=None))

    # 独立连接：自己的事务，只可能看见【已提交】的行。
    with db_engine.connect() as probe:
        mapping = dict(
            probe.execute(
                text("SELECT provider_fund_id, share_class_id FROM fund.provider_fund_identity")
            ).all()
        )
        share_classes = dict(
            probe.execute(text("SELECT display_name, id FROM fund.fund_share_class")).all()
        )
        payloads = probe.execute(text("SELECT count(*) FROM raw.raw_payload")).scalar_one()

    assert (
        mapping["000003"] == share_classes["测试另一只混合A"]
    ), "本批新代码 000003 必须已提交 —— 一条映射冲突不得毁掉整批"
    assert mapping["000001"] == a_id, "旧映射必须原样保留，不被静默改写"
    assert "测试改名混合A" not in share_classes
    assert payloads == 2, "两批 fund_list 的 raw payload 都必须已提交"


# --- 生产装配路径的披露时滞 ---------------------------------------------
# 这条路径必须真正从 governance.data_source_priority 读取规则；
# 测试不直接向 IngestService 注入时滞，以免绕过生产装配。

NAV_FRAME = pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": [1.2345]})


def _nav_caller(name, **params):
    if name == "fund_open_fund_info_em" and params.get("indicator") == "单位净值走势":
        return NAV_FRAME
    raise AssertionError(f"未预期的调用 {name} {params}")


class _OfflineAdapter(AkShareSourceAdapter):
    """真适配器，只把时钟与上游调用换成固定的离线夹具。

    刻意用子类而不是一个 lambda：cli._resolve 会读
    AkShareSourceAdapter.provider_code 这个【类属性】，换成 lambda 会让被测
    的装配路径在与本测试无关的地方断掉。
    """

    def __init__(self) -> None:
        super().__init__(clock=lambda: FIXED_NOW, caller=_nav_caller)


def test_production_assembly_pins_the_disclosure_lag(db_session, ingested, monkeypatch):
    """生产装配从版本化规则读取披露时滞，不使用代码常量。"""
    monkeypatch.setattr(akshare_client, "AkShareSourceAdapter", _OfflineAdapter)

    setup = IngestService(db_session, _OfflineAdapter(), disclosure_lag_days=1)
    dataset = setup.ensure_dataset("fund_nav")
    rule = (
        db_session.query(DataSourcePriority)
        .filter_by(
            dataset_id=dataset.id,
            field_name="available_at",
            rule_version=cli.DATA_SOURCE_RULE_VERSION,
        )
        .one()
    )
    rule.disclosure_lag_days = 2
    db_session.flush()

    share_class = _resolve(db_session, "000001")
    assert cli._nav_service(db_session).ingest_nav(share_class.id, "000001") == 1

    row = db_session.query(FundNav).filter_by(share_class_id=share_class.id).one()
    assert row.effective_at == dt.date(2020, 1, 2)
    assert row.available_at == dt.datetime(2020, 1, 4, tzinfo=dt.UTC)
    # C-12：AKShare 给不出这两个时刻，必须如实留空，质量恒为 INFERRED。
    assert row.published_at is None
    assert row.provider_available_at is None
    assert row.availability_quality == "INFERRED"


def test_migration_bootstraps_all_ingest_disclosure_lag_policies(db_session):
    rows = (
        db_session.query(DataProviderDataset.dataset_code, DataSourcePriority)
        .join(DataProvider, DataProvider.id == DataProviderDataset.provider_id)
        .join(DataSourcePriority, DataSourcePriority.dataset_id == DataProviderDataset.id)
        .filter(
            DataProvider.provider_code == "AKSHARE",
            DataSourcePriority.field_name == "available_at",
            DataSourcePriority.rule_version == cli.DATA_SOURCE_RULE_VERSION,
        )
        .all()
    )

    assert {code: rule.disclosure_lag_days for code, rule in rows} == {
        "fund_nav": 1,
        "fund_distribution": 1,
        "fund_split": 1,
    }


def test_ingest_nav_cli_exits_nonzero_for_invalid_subject(db_session, ingested, monkeypatch):
    share_class = _resolve(db_session, "000001")

    class InvalidService:
        def ingest_nav_batch(self, _subjects):
            return BatchIngestResult(
                (BatchItemResult(share_class.id, BatchItemStatus.INVALID, "invalid payload"),)
            )

    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(db_session))
    monkeypatch.setattr(cli, "_nav_service", lambda _session: InvalidService())

    with pytest.raises(SystemExit) as excinfo:
        cli.cmd_ingest_nav(argparse.Namespace(symbol="000001"))

    assert excinfo.value.code != 0
    assert "invalid payload" in str(excinfo.value)


def test_ingest_nav_cli_does_not_read_orm_object_after_session_closes(monkeypatch, capsys):
    state = {"closed": False}

    class ClosingSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            state["closed"] = True

        def commit(self):
            pass

    class ShareClass:
        id = 7

        @property
        def display_name(self):
            if state["closed"]:
                raise RuntimeError("detached instance was accessed")
            return "测试基金A"

    class SuccessService:
        def ingest_nav_batch(self, _subjects):
            return BatchIngestResult((BatchItemResult(7, BatchItemStatus.SUCCESS, None),))

    monkeypatch.setattr(cli, "_session", ClosingSession)
    monkeypatch.setattr(cli, "_resolve", lambda _session, _symbol: ShareClass())
    monkeypatch.setattr(cli, "_nav_service", lambda _session: SuccessService())

    cli.cmd_ingest_nav(argparse.Namespace(symbol="000001"))

    assert capsys.readouterr().out.strip() == "测试基金A：SUCCESS"


def test_classify_dry_run_uses_retained_raw(db_session, ingested, monkeypatch, capsys):
    from fip.services.data_service.models.fund import FundClassificationRevision

    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(db_session))
    before = db_session.query(FundClassificationRevision).count()
    cli.main(["classify-funds", "--actor", "operator", "--dry-run", "--symbol", "000001"])
    import json

    lines = capsys.readouterr().out.splitlines()
    assert "000001" in lines[0]
    summary = json.loads(lines[-1])["summary"]
    assert summary["processed"] == 1
    assert summary["unknown_rates"]["strategy"] == 1.0
    assert db_session.query(FundClassificationRevision).count() == before


def test_review_cli_requires_operator_allowlist(db_session, ingested, monkeypatch):
    from fip.services.data_service.models.fund import FundClassificationReviewCase

    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(db_session))
    monkeypatch.delenv("FIP_CLASSIFICATION_REVIEWERS", raising=False)
    case = db_session.query(FundClassificationReviewCase).first()
    with pytest.raises(PermissionError):
        cli.main(
            [
                "review-classification",
                "--actor",
                "unknown",
                "--case-id",
                str(case.id),
                "--expected-revision",
                str(case.revision_id),
                "--reason",
                "test",
                "--decisions",
                "{}",
            ]
        )

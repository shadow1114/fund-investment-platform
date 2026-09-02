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
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import (
    Fund,
    FundShareClass,
    ProviderFundIdentity,
)
from fip.services.data_service.models.market import FundNav

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)

FUND_LIST = pd.DataFrame({
    "基金代码": ["000001", "000002"],
    "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
    "基金类型": ["混合型", "混合型"],
})


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

RENAMED_FUND_LIST = pd.DataFrame({
    "基金代码": ["000001", "000003"],
    "基金简称": ["测试改名混合A", "测试另一只混合A"],
    "基金类型": ["混合型", "混合型"],
})


def _renamed_caller(name, **params):
    if name == "fund_name_em":
        return RENAMED_FUND_LIST
    raise AssertionError(f"未预期的调用 {name} {params}")


def test_ingest_funds_exits_nonzero_and_lists_every_conflict(
    db_session, ingested, monkeypatch
):
    """有冲突时：退出码非零、逐条列出冲突，且其余基金仍被正常登记。"""
    a = db_session.query(FundShareClass).filter_by(share_class_code="A").one()

    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_renamed_caller)
    # cmd_ingest_funds 自己开 engine 连的是 dev 库；这里把它换成测试事务里的
    # session（用 nullcontext 包一层，避免 `with` 在命令结束时把 fixture 的
    # session 关掉），并注入用改名后 fund list 的 adapter。
    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(db_session))
    monkeypatch.setattr(
        cli, "_service",
        lambda session: IngestService(session, adapter, disclosure_lag_days=1),
    )

    with pytest.raises(SystemExit) as excinfo:
        cli.cmd_ingest_funds(argparse.Namespace(limit=None))

    assert excinfo.value.code != 0, "有冲突必须以非零退出码结束"
    message = str(excinfo.value)
    assert "000001" in message, "必须点名是哪个 provider_fund_id"
    assert str(a.id) in message, "必须写出原指向的份额类别"

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


def test_conflicting_batch_leaves_one_reusable_orphan_dimension_row(
    db_session, ingested, monkeypatch
):
    """钉住冲突批次留下的【孤儿维度行】—— 这是有意的取舍，不是缺陷。

    改名（"测试蓝筹混合A" → "测试改名混合A"）会先按新的 product_name 建出
    Fund + FundShareClass，之后 _ensure_provider_identity 才发现 000001 此前
    指向另一个份额类别、返回冲突而【不写】映射。于是新建的那一对维度行没有
    任何 provider_fund_identity 指向它。

    旧行为（直接抛 ValueError）不会留下孤儿，但代价是整批 ingest-funds 全废。
    换来的这条孤儿此前【没有被任何测试断言】—— 一个无人断言的新行为，下一次
    重构时既没人知道它该在，也没人知道它不该增长。本测试把三条性质钉死：

      1. 孤儿【确实产生】，且不参与任何映射；
      2. 重跑同一批【不增长】（按 product_name 命中已存在的行）；
      3. 人工关闭旧区间后重跑，孤儿【正好被复用】，不会再多建一条。

    完整取舍说明见 IngestService.ingest_fund_list 的 docstring。
    """
    a = db_session.query(FundShareClass).filter_by(share_class_code="A").one()

    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_renamed_caller)
    service = IngestService(db_session, adapter, disclosure_lag_days=1)

    def _orphans():
        """没有任何 provider_fund_identity 指向的份额类别。"""
        mapped = {
            row.share_class_id
            for row in db_session.query(ProviderFundIdentity).all()
        }
        return [
            sc for sc in db_session.query(FundShareClass).all()
            if sc.id not in mapped
        ]

    assert _orphans() == [], "基线批次不应留下任何孤儿"

    # 1. 冲突批次留下【恰好一条】孤儿：改名后的 "测试改名混合" / A。
    first = service.ingest_fund_list()
    db_session.flush()
    assert len(first.reassignments) == 1
    orphans = _orphans()
    assert len(orphans) == 1
    orphan_id = orphans[0].id
    assert orphan_id != a.id
    assert orphans[0].display_name == "测试改名混合A"
    orphan_fund = db_session.query(Fund).filter_by(id=orphans[0].fund_id).one()
    assert orphan_fund.product_name == "测试改名混合"

    # 2. 重跑同一批不增长：Fund 按 product_name、FundShareClass 按
    #    (fund_id, share_class_code) 查找后才新建，第二次全部命中已存在的行。
    second = service.ingest_fund_list()
    db_session.flush()
    assert len(second.reassignments) == 1, "冲突仍应逐次如实上报"
    assert second.created == 0, "重跑不得再建任何份额类别"
    assert [sc.id for sc in _orphans()] == [orphan_id], "孤儿不得增长"

    # 3. 不丢数据：旧份额类别与它的映射原样保留。
    mapping = {
        row.provider_fund_id: row.share_class_id
        for row in db_session.query(ProviderFundIdentity).all()
    }
    assert mapping["000001"] == a.id

    # 4. 人工处置后正好被复用：运维确认归属、关闭旧区间，重跑即把映射登记到
    #    这条已经存在的孤儿上 —— 不再新建第三条份额类别。
    #
    #    重跑刻意用【第二天】的时钟，这不是为了让测试通过而挑的值，而是这条
    #    复用路径本来就有的前提：valid_from 取落库当日（C-12 不得伪造更早的
    #    生效日），而旧映射的 valid_from 也是它自己的落库当日。同一天内关闭
    #    旧区间再重开，两行的 (provider_id, provider_fund_id, valid_from) 完全
    #    相同，会撞上唯一键 uq_pfi_provider_key。现实里人工核对归属不会在同
    #    一天内完成，因此这不构成障碍 —— 但它是这条性质的真实边界，写在这里
    #    以免将来有人以为「关闭旧区间后立刻重跑」也能work。
    next_day = FIXED_NOW + dt.timedelta(days=1)
    old_identity = db_session.query(ProviderFundIdentity).filter_by(
        provider_fund_id="000001", share_class_id=a.id
    ).one()
    old_identity.valid_to = next_day.date()
    db_session.flush()

    later_adapter = AkShareSourceAdapter(
        clock=lambda: next_day, caller=_renamed_caller
    )
    third = IngestService(
        db_session, later_adapter, disclosure_lag_days=1
    ).ingest_fund_list()
    db_session.flush()
    assert third.reassignments == (), "旧区间已关闭，不应再有冲突"
    assert third.created == 0, "复用孤儿，不得新建份额类别"
    assert _orphans() == [], "孤儿已被人工处置后的重跑接管"
    open_mapping = {
        row.provider_fund_id: row.share_class_id
        for row in db_session.query(ProviderFundIdentity)
        .filter(ProviderFundIdentity.valid_to.is_(None)).all()
    }
    assert open_mapping["000001"] == orphan_id


# --- 「已成功部分已提交」必须在事务外被验证 -------------------------------
# fix round 3 item 4：db_session fixture 把整个测试包在一个最终 rollback 的
# 事务里，且 join_transaction_mode="create_savepoint" 让被测代码的 commit()
# 只释放一个 SAVEPOINT。于是在那个 fixture 下断言 session 内的行【即使
# cmd_ingest_funds 根本没调用 commit() 也照样通过】—— 而「一条映射冲突不该
# 毁掉一整批已抓数据」这条性质，恰恰全靠那次 commit 成立。
# 下面这条测试因此用真实事务 + 独立连接复查。


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
            conn.execute(text(
                "TRUNCATE fund.provider_fund_identity, fund.fund_share_class, "
                "fund.fund, raw.canonical_raw, raw.raw_payload, "
                "governance.data_provider_dataset, governance.data_provider "
                "RESTART IDENTITY CASCADE"
            ))


def test_ingest_funds_really_commits_the_successful_part(
    committed_session, db_engine, monkeypatch
):
    """有冲突时，本批【已成功的部分】必须真的落盘 —— 用独立连接在事务外复查。

    这是 cmd_ingest_funds 里那句 `session.commit()` 的唯一守卫：它先于
    SystemExit 执行，若被挪到 raise 之后（或被删掉），一条映射冲突就会重新
    毁掉整批已抓数据 —— 而任何在同一个 session 里做的断言都看不出区别。
    """
    baseline = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_caller)
    IngestService(committed_session, baseline, disclosure_lag_days=1).ingest_fund_list()
    committed_session.commit()
    a_id = committed_session.query(FundShareClass).filter_by(
        share_class_code="A").one().id

    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_renamed_caller)
    monkeypatch.setattr(cli, "_session", lambda: contextlib.nullcontext(committed_session))
    monkeypatch.setattr(
        cli, "_service",
        lambda session: IngestService(session, adapter, disclosure_lag_days=1),
    )

    with pytest.raises(SystemExit) as excinfo:
        cli.cmd_ingest_funds(argparse.Namespace(limit=None))
    assert excinfo.value.code != 0

    # 独立连接：自己的事务，只可能看见【已提交】的行。
    with db_engine.connect() as probe:
        mapping = dict(probe.execute(text(
            "SELECT provider_fund_id, share_class_id FROM fund.provider_fund_identity"
        )).all())
        share_classes = dict(probe.execute(text(
            "SELECT display_name, id FROM fund.fund_share_class"
        )).all())
        payloads = probe.execute(text(
            "SELECT count(*) FROM raw.raw_payload"
        )).scalar_one()

    assert mapping["000003"] == share_classes["测试另一只混合A"], (
        "本批新代码 000003 必须已提交 —— 一条映射冲突不得毁掉整批"
    )
    assert mapping["000001"] == a_id, "旧映射必须原样保留，不被静默改写"
    assert "测试改名混合A" in share_classes, "冲突批次的孤儿维度行同样已提交"
    assert payloads == 2, "两批 fund_list 的 raw payload 都必须已提交"


# --- 生产装配路径的披露时滞 ---------------------------------------------
# fix round 4 item 4：把 cli.DISCLOSURE_LAG_DAYS 从 1 改成 7，全套测试依然
# 全绿 —— 8 处测试各自注入 disclosure_lag_days=1，没有任何测试走过
# cli._service() 这条【生产装配】路径。于是那个常量事实上没有任何测试保护，
# 而它决定了全库每一行净值的 available_at，也就决定了每一个 decision_at 上
# 什么可见、什么不可见。

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
    """钉住【生产装配路径】的披露时滞：净值可见时刻 = 净值日 + 1 天。

    刻意不走 IngestService(..., disclosure_lag_days=1)，而是走
    cli._service(session) —— 常量 cli.DISCLOSURE_LAG_DAYS 就装配在那里。
    断言里的 1 天是【写死的字面量】而不是 cli.DISCLOSURE_LAG_DAYS：若写成
    后者，把常量改成 7 时本测试会跟着一起变，等于什么也没钉住。

    只替换适配器（AkShareSourceAdapter 需要联网），装配链路的其余部分原样
    保留。改动那个常量必须让本测试失败。
    """
    monkeypatch.setattr(akshare_client, "AkShareSourceAdapter", _OfflineAdapter)

    share_class = _resolve(db_session, "000001")
    assert cli._service(db_session).ingest_nav(share_class.id, "000001") == 1

    row = db_session.query(FundNav).filter_by(share_class_id=share_class.id).one()
    assert row.effective_at == dt.date(2020, 1, 2)
    assert row.available_at == dt.datetime(2020, 1, 3, tzinfo=dt.UTC)
    # C-12：AKShare 给不出这两个时刻，必须如实留空，质量恒为 INFERRED。
    assert row.published_at is None
    assert row.provider_available_at is None
    assert row.availability_quality == "INFERRED"

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

from fip.platform import cli
from fip.platform.cli import _resolve
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import FundShareClass, ProviderFundIdentity

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

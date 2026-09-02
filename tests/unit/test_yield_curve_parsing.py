import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare import parse as parse_module
from fip.services.data_service.adapters.akshare.datasets import (
    DATASETS,
    YIELD_TENOR_COLUMNS,
)
from fip.services.data_service.adapters.akshare.parse import parse_yield_curve_frame

# 实测（AKShare 1.18.94，bond_china_yield 20240101~20240110）返回的三条曲线。
TREASURY = "中债国债收益率曲线"
MTN_AAA = "中债中短期票据收益率曲线(AAA)"
BANK_AAA = "中债商业银行普通债收益率曲线(AAA)"


def _payload(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


def _treasury(**columns) -> bytes:
    """单曲线载荷。曲线名称是【必填】列，因此每个夹具都要显式给出。"""
    rows = len(next(iter(columns.values())))
    return _payload(pd.DataFrame({"曲线名称": [TREASURY] * rows, **columns}))


def test_wide_frame_is_melted_into_tenor_rows():
    """中债曲线是宽表（每个期限一列），需展开为 (曲线, 日期, 期限, 利率) 行。"""
    payload = _treasury(
        日期=["2024-01-02", "2024-01-03"],
        **{"3月": [2.10, 2.12], "1年": [2.30, 2.31], "10年": [2.60, 2.62]},
    )
    rows = parse_yield_curve_frame(payload)
    assert len(rows) == 6
    one_year = [r for r in rows if r.tenor == "1Y"]
    assert [r.effective_at for r in one_year] == [dt.date(2024, 1, 2), dt.date(2024, 1, 3)]


def test_percentage_is_converted_to_decimal_fraction():
    """全平台百分比一律用小数（10-api §12.1）。2.30% → 0.023。"""
    row = parse_yield_curve_frame(_treasury(日期=["2024-01-02"], **{"1年": [2.30]}))[0]
    assert row.rate == Decimal("0.02300000")
    assert isinstance(row.rate, Decimal)


@pytest.mark.parametrize(
    ("column", "tenor"),
    [("3月", "3M"), ("6月", "6M"), ("1年", "1Y"), ("3年", "3Y"), ("10年", "10Y")],
)
def test_chinese_tenor_labels_are_normalized(column, tenor):
    payload = _treasury(日期=["2024-01-02"], **{column: [2.0]})
    assert parse_yield_curve_frame(payload)[0].tenor == tenor


def test_missing_rate_is_dropped_not_filled():
    assert parse_yield_curve_frame(_treasury(日期=["2024-01-02"], **{"1年": [None]})) == []


# --------------------------------------------------------------------------
# 曲线身份：同一个日期下有三条【不同】的曲线
# --------------------------------------------------------------------------


def test_three_curves_on_one_date_are_distinguishable():
    """上游同一个「日期」下有三行，靠「曲线名称」区分 —— 解析结果必须能分开。

    这是本轮的阻断项：解析器此前逐行遍历、只读「日期」与期限列，把
    (2024-01-02, "10Y") 输出三次、值分别是 0.030482 / 0.025601 / 0.028867，
    彼此不可区分。而 RiskFreeRate 的主键第一列正是 curve_code —— 解析器
    在结构上无法为它提供取值，下游要么主键冲突/最后一条胜出（R_f 静默变成
    信用债收益率，10Y 高约 30bp），要么在 service 层再发明一次曲线过滤
    （spec §4.1 禁止的「外部格式穿透领域层」）。
    """
    payload = _payload(pd.DataFrame({
        "曲线名称": [MTN_AAA, TREASURY, BANK_AAA],
        "日期": ["2024-01-02"] * 3,
        "10年": [3.0482, 2.5601, 2.8867],
    }))
    rows = parse_yield_curve_frame(payload)
    assert {(r.curve_code, r.rate) for r in rows} == {
        ("CN_MTN_AAA", Decimal("0.03048200")),
        ("CN_TREASURY", Decimal("0.02560100")),
        ("CN_BANK_AAA", Decimal("0.02886700")),
    }
    # 三条曲线在 (curve_code, effective_at, tenor) 上互不相同 —— 这正是
    # RiskFreeRate 主键所需的粒度，不会互相覆盖。
    assert len({(r.curve_code, r.effective_at, r.tenor) for r in rows}) == 3


def test_curve_name_column_maps_to_a_platform_curve_code():
    """「曲线名称」是【曲线身份】，不是一个无法识别的期限列。

    ⚠️ 本条替换的是旧测试 test_unrecognized_tenor_columns_are_skipped：
    它往夹具里放了一列「曲线名称」，然后断言它被「跳过」—— 把阻断项的
    bug 当成预期行为焊死了。「跳过曲线名称」不是正确行为，正确行为是
    【读它】并映射成平台的 curve_code。
    """
    payload = _payload(pd.DataFrame({
        "日期": ["2024-01-02"], "1年": [2.30], "曲线名称": [TREASURY],
    }))
    rows = parse_yield_curve_frame(payload)
    assert [(r.curve_code, r.tenor) for r in rows] == [("CN_TREASURY", "1Y")]


def test_frame_without_the_curve_name_column_is_rejected():
    """缺「曲线名称」列时必须报错，不得产出无法归属的点。

    静默产出会让下游为 curve_code 现编一个取值 —— 那正是无风险利率被
    换成信用债收益率的入口。
    """
    payload = _payload(pd.DataFrame({"日期": ["2024-01-02"], "1年": [2.30]}))
    with pytest.raises(ValueError, match="曲线名称"):
        parse_yield_curve_frame(payload)


def test_unrecognized_curve_names_are_skipped_but_known_ones_survive():
    """未登记的曲线不猜其含义，直接跳过；已登记的照常解析。"""
    payload = _payload(pd.DataFrame({
        "曲线名称": [TREASURY, "中债城投债收益率曲线(AA)"],
        "日期": ["2024-01-02", "2024-01-02"],
        "1年": [2.30, 3.10],
    }))
    rows = parse_yield_curve_frame(payload)
    assert [(r.curve_code, r.rate) for r in rows] == [
        ("CN_TREASURY", Decimal("0.02300000"))
    ]


def test_frame_where_no_curve_is_recognized_fails_loudly():
    """一条都认不出来 = 映射已过时，必须报错而不是静默返回零行。

    静默返回零行的后果是「灌数成功、R_f 表为空」，下游到很久以后才发现。
    """
    payload = _payload(pd.DataFrame({
        "曲线名称": ["中债国债收益率曲线(新)"], "日期": ["2024-01-02"], "1年": [2.30],
    }))
    with pytest.raises(ValueError, match="曲线名称"):
        parse_yield_curve_frame(payload)


# --------------------------------------------------------------------------
# 期限：排序按经济期限长度，未映射的标签跳过
# --------------------------------------------------------------------------


def test_tenors_are_sorted_by_economic_length_not_lexicographically():
    """期限必须按【真实期限长度】排序（Task 16 deferred）。

    字典序会给出 "10Y" < "1Y" < "3M"，即 10 年排在 3 个月之前 —— 任何按
    顺序取「最短端」或做曲线插值的下游都会拿错点。
    """
    payload = _treasury(
        日期=["2024-01-02"],
        **{"3月": [1.80], "1年": [2.10], "10年": [2.56], "30年": [2.84]},
    )
    assert [r.tenor for r in parse_yield_curve_frame(payload)] == ["3M", "1Y", "10Y", "30Y"]


def test_plausible_but_unmapped_tenor_label_is_skipped():
    """「4年」形状可信但未登记 —— 跳过，不猜（Task 16 deferred）。

    不猜的理由：若自动把「N年」推成 "NY"，上游任何一个我们没核对过的列
    都会被当成期限收下（例如「加权平均期限」这类非期限列），错的点会
    直接进 R_f 曲线而不报错。
    """
    payload = _treasury(日期=["2024-01-02"], **{"1年": [2.30], "4年": [2.45]})
    assert [r.tenor for r in parse_yield_curve_frame(payload)] == ["1Y"]


# --------------------------------------------------------------------------
# 契约：datasets.py 声明的列必须覆盖解析器真正依赖的列
# --------------------------------------------------------------------------


def test_declared_contract_covers_every_column_the_parser_depends_on():
    """契约必须包含解析器实际读取的期限列。

    此前 required_columns 只有 {曲线名称, 日期}：上游把「1年」改成「1Y」，
    parse_yield_curve_frame 会静默返回零行，而契约测试照样绿。
    """
    declared = DATASETS["risk_free_rate"].required_columns
    assert {"曲线名称", "日期"} <= declared
    assert YIELD_TENOR_COLUMNS <= declared
    # 声明为必需的期限列必须都是解析器认识的标签，否则契约在守卫一列
    # 解析器根本不读的东西。
    assert YIELD_TENOR_COLUMNS <= set(parse_module.TENOR_LABELS)


def test_declared_tenor_columns_match_the_probed_upstream_shape():
    """探查结果（task-10-report）：上游返回 8 个期限列，没有「2年」。"""
    assert YIELD_TENOR_COLUMNS == frozenset(
        {"3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"}
    )

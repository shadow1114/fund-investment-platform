import datetime as dt
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd


@dataclass(frozen=True, slots=True)
class ParsedNav:
    effective_at: dt.date
    unit_nav: Decimal


def _to_decimal(raw: object) -> Decimal | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text or text in {"nan", "None", "--", "-"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_nav_frame(payload: bytes) -> list[ParsedNav]:
    """把 AKShare 的单位净值走势 parquet 解析为规范记录。

    缺失值直接【丢弃】而非填充（C-6）—— 前向填充会在净值停更期间
    伪造出「零波动」，直接污染波动率与最大回撤。
    """
    frame = pd.read_parquet(io.BytesIO(payload))
    rows: list[ParsedNav] = []
    seen: set[dt.date] = set()
    for _, record in frame.iterrows():
        value = _to_decimal(record["单位净值"])
        if value is None:
            continue
        if value <= 0:
            raise ValueError(f"净值必须为正，得到 {value}")
        day = pd.to_datetime(record["净值日期"]).date()
        if day in seen:
            raise ValueError(f"净值日期重复：{day}")
        seen.add(day)
        rows.append(ParsedNav(effective_at=day, unit_nav=value))
    rows.sort(key=lambda r: r.effective_at)
    return rows


@dataclass(frozen=True, slots=True)
class ParsedDistribution:
    effective_at: dt.date
    dividend_per_unit: Decimal
    split_ratio: Decimal


def _to_date(raw: object) -> dt.date | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text or text in {"nan", "None", "--", "-"}:
        return None
    parsed: dt.date = pd.to_datetime(text).date()
    return parsed


#   份与金额之间的分隔符排除 “-”：若把负号并入分隔符，负号会被吞掉，
#   金额组只能匹配到裸的正数，负分红（脏数据）就会被当成正分红悄悄
#   接受 —— brief 原正则 `[^0-9]*` 正是这个疏漏，`amount` 组补上可选的
#   `-?` 前缀、分隔符改成 `[^0-9-]*`，负号才会被保留进 amount 而不是被
#   分隔符吃掉，下游 `amount < 0` 校验才有机会触发。
_DIVIDEND_RE = re.compile(r"每\s*(?P<base>\d+)\s*份[^0-9-]*(?P<amount>-?\d+(?:\.\d+)?)")


def _parse_dividend_per_unit(raw: object) -> Decimal | None:
    """把「每10份分红」列解析为【每一份】的分红金额。

    ⚠️ 实测（AKShare 1.18.94）：该列不是数字，而是字符串，形如
    `每10份派现金0.4500元`。必须同时提取【基数 10】与【金额 0.4500】并相除。

    若直接把 0.4500 当作每份分红，每一笔分红会放大 10 倍，复权净值系统性高估，
    而且【不会有任何报错】—— 这正是最危险的一类缺陷。
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text:
        return None
    match = _DIVIDEND_RE.search(text)
    if match is None:
        return None
    base = Decimal(match.group("base"))
    if base <= 0:
        return None
    return Decimal(match.group("amount")) / base


def parse_distribution_frame(payload: bytes) -> list[ParsedDistribution]:
    """分红送配详情 → 除息事件。

    用【除息日】而非权益登记日：净值在除息日下跌，复权必须对齐那一天。
    """
    frame = pd.read_parquet(io.BytesIO(payload))
    rows: list[ParsedDistribution] = []
    for _, record in frame.iterrows():
        day = _to_date(record.get("除息日"))
        amount = _parse_dividend_per_unit(record.get("每10份分红"))
        if day is None or amount is None:
            continue
        if amount < 0:
            raise ValueError(f"每份分红不得为负，得到 {amount}")
        if amount == 0:
            continue
        rows.append(ParsedDistribution(day, amount, Decimal(1)))
    rows.sort(key=lambda r: r.effective_at)
    return rows


def _parse_ratio(raw: object) -> Decimal | None:
    """拆分比例可能是 '2.0000' 或 '1:2' 两种形式。"""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text or text in {"nan", "None", "--", "-"}:
        return None
    if ":" in text or "：" in text:
        left, _, right = text.replace("：", ":").partition(":")
        base = _to_decimal(left)
        target = _to_decimal(right)
        if base is None or target is None or base == 0:
            return None
        return target / base
    return _to_decimal(text)


def parse_split_frame(payload: bytes) -> list[ParsedDistribution]:
    """拆分详情 → 拆分事件。split_ratio 表示 1 份拆为几份。"""
    frame = pd.read_parquet(io.BytesIO(payload))
    rows: list[ParsedDistribution] = []
    for _, record in frame.iterrows():
        day = _to_date(record.get("拆分折算日"))
        ratio = _parse_ratio(record.get("拆分折算比例"))
        if day is None or ratio is None:
            continue
        if ratio <= 0:
            raise ValueError(f"拆分折算比例必须为正，得到 {ratio}")
        rows.append(ParsedDistribution(day, Decimal(0), ratio))
    rows.sort(key=lambda r: r.effective_at)
    return rows

import datetime as dt
import io
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

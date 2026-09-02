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


#   两处修正（均是 fix round 1 code review 发现的真实缺陷，不是风格问题）：
#
#   1. 金额锚定到「现金」/「派」，不能让分隔符匹配任意非数字字符。
#      若分隔符是不受限的 `[^0-9]*`，遇到「每10份转增2股派现金0.30元」这种
#      转增 + 现金分红同时出现的形状，`amount` 组会先撞上「转增2股」里的
#      「2」，把 0.30 元的现金分红误解析成 2（放大约 6.7 倍），且不报错。
#      要求分隔符里必须出现「现金」或「派」才能到达金额数字，锚定的是
#      「现金分红金额」这个语义，而不是「份后面第一个数」这个位置。
#   2. 份与金额之间的分隔符排除 “-”：若把负号并入分隔符，负号会被吞掉，
#      金额组只能匹配到裸的正数，负分红（脏数据）就会被当成正分红悄悄
#      接受 —— brief 原正则 `[^0-9]*` 正是这个疏漏，`amount` 组补上可选的
#      `-?` 前缀、分隔符改成 `[^0-9-]*`，负号才会被保留进 amount 而不是被
#      分隔符吃掉，下游 `amount < 0` 校验才有机会触发。
_DIVIDEND_RE = re.compile(
    r"每\s*(?P<base>\d+)\s*份.*?(?:现金|派)[^0-9-]*(?P<amount>-?\d+(?:\.\d+)?)"
)


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
        if base is None or target is None:
            # 左右两侧本身就不是数字：判定为无法解析，丢弃而非猜测。
            return None
        if base == 0:
            # 分母为 0 不是「缺失记录」，是脏数据 —— 与下方 ratio <= 0 的
            # 拒绝逻辑保持一致，都应该报错而不是被静默丢弃（fix round 1）。
            raise ValueError(f"拆分折算比例的分母不得为 0，得到 {text!r}")
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


# 期限标签 → (平台期限码, 期限月数)。月数【不是】装饰：排序必须按经济期限
# 长度，而不是 tenor 的字典序 —— 字典序会给出 "10Y" < "1Y" < "3M"，把 10 年
# 排到 3 个月前面，任何按顺序取曲线短端或做插值的下游都会拿错点。
#
# 「2年」认得但上游目前不提供（探查结果见 datasets.YIELD_TENOR_COLUMNS）；
# 认得一个上游没给的列不会产生任何行，而一旦上游补上它就能直接解析。
# 反过来，形状可信但未登记的标签（如「4年」）一律【跳过】而不推断：若把
# 「N年」自动推成 "NY"，任何我们没核对过的列（例如「加权平均期限」这类
# 根本不是期限的列）都会被当成期限收下，错的点会不报错地进 R_f 曲线。
TENOR_LABELS: dict[str, tuple[str, int]] = {
    "3月": ("3M", 3), "6月": ("6M", 6), "1年": ("1Y", 12), "2年": ("2Y", 24),
    "3年": ("3Y", 36), "5年": ("5Y", 60), "7年": ("7Y", 84), "10年": ("10Y", 120),
    "30年": ("30Y", 360),
}

_TENOR_MONTHS: dict[str, int] = {
    tenor: months for tenor, months in TENOR_LABELS.values()
}

_CURVE_NAME_COLUMN = "曲线名称"

# 上游曲线名称 → 平台 curve_code。实测（AKShare 1.18.94，
# bond_china_yield 20240101~20240110）：同一个「日期」下【有三行】，
# 靠「曲线名称」区分：
#
#   中债中短期票据收益率曲线(AAA)      2024-01-02  10年=3.0482
#   中债国债收益率曲线                 2024-01-02  10年=2.5601   ← 唯一的无风险曲线
#   中债商业银行普通债收益率曲线(AAA)   2024-01-02  10年=2.8867
#
# 为什么在这里就把中文名映射成平台码，而不是把中文名原样传下去：curve_code
# 是 RiskFreeRate 的主键第一列，下游会用它来选「哪条曲线」。把上游的中文
# 名字直接当主键，等于让 provider 的外部格式穿透到领域层（spec §4.1 禁止），
# 下游查询会写成 WHERE curve_code = '中债国债收益率曲线'。适配器的职责正是
# 在这里做这一次翻译。
_CURVE_CODES: dict[str, str] = {
    "中债国债收益率曲线": "CN_TREASURY",
    "中债中短期票据收益率曲线(AAA)": "CN_MTN_AAA",
    "中债商业银行普通债收益率曲线(AAA)": "CN_BANK_AAA",
}


@dataclass(frozen=True, slots=True)
class ParsedYieldPoint:
    """曲线上的一个点。curve_code 是身份的一部分，不是可选标注。

    (curve_code, effective_at, tenor) 与 RiskFreeRate 的主键
    (curve_code, currency, tenor, effective_at, version) 一一对应；缺了
    curve_code，三条曲线的同一个 (日期, 期限) 会退化成三个彼此不可区分的
    点，写库时主键冲突或最后一条胜出，R_f 会静默变成信用债收益率
    （实测 10Y 高约 30bp、3M 高约 54bp）。
    """

    curve_code: str
    effective_at: dt.date
    tenor: str
    rate: Decimal


def parse_yield_curve_frame(payload: bytes) -> list[ParsedYieldPoint]:
    """中债收益率曲线（多曲线宽表）→ (曲线, 日期, 期限, 利率) 行。

    利率一律转为小数（2.30% → 0.023），与全平台「百分比用小数」一致
    （10-api/01 §12.1）。混用会在下游产生难以察觉的 100 倍误差。

    三条「不猜」的规则：
      · 缺「曲线名称」列 → 直接报错。产出无法归属到某条曲线的点，等于把
        「这是哪条曲线」这个决定甩给下游去现编。
      · 未登记的曲线名称 → 跳过该行，不猜它是什么曲线。
      · 未登记的期限列   → 跳过该列，不猜它的含义。

    但「一条曲线都认不出来」不是跳过，而是【报错】：那说明上游改了曲线
    名称，映射已过时。静默返回零行会表现为「灌数成功、R_f 表为空」，
    要到下游算 Sharpe 时才暴露。
    """
    frame = pd.read_parquet(io.BytesIO(payload))
    if _CURVE_NAME_COLUMN not in frame.columns:
        raise ValueError(
            f"收益率曲线数据缺少「{_CURVE_NAME_COLUMN}」列，无法判定每一行属于"
            f"哪条曲线；实际列为 {sorted(frame.columns)}。"
            "中债数据同一个日期下有多条曲线（国债 / 中短期票据AAA / "
            "商业银行普通债AAA），缺了曲线身份的点不得产出。"
        )

    rows: list[ParsedYieldPoint] = []
    hundred = Decimal(100)
    tenor_columns = [
        (column, tenor)
        for column, (tenor, _months) in TENOR_LABELS.items()
        if column in frame.columns
    ]
    recognized_rows = 0
    unknown_curves: set[str] = set()
    for _, record in frame.iterrows():
        day = _to_date(record.get("日期"))
        if day is None:
            continue
        curve_name = str(record[_CURVE_NAME_COLUMN]).strip()
        curve_code = _CURVE_CODES.get(curve_name)
        if curve_code is None:
            unknown_curves.add(curve_name)
            continue
        recognized_rows += 1
        for column, tenor in tenor_columns:
            percent = _to_decimal(record[column])
            if percent is None:
                continue
            rate = (percent / hundred).quantize(Decimal("0.00000001"))
            rows.append(ParsedYieldPoint(curve_code, day, tenor, rate))

    if recognized_rows == 0 and unknown_curves:
        raise ValueError(
            f"没有任何一行的「{_CURVE_NAME_COLUMN}」可识别：{sorted(unknown_curves)}；"
            f"已登记的曲线为 {sorted(_CURVE_CODES)}。上游很可能改了曲线名称 —— "
            "请重新探查并同步 _CURVE_CODES，不要让本次解析静默返回零行。"
        )

    rows.sort(key=lambda r: (r.effective_at, r.curve_code, _TENOR_MONTHS[r.tenor]))
    return rows

import datetime as dt
from enum import StrEnum


class AvailabilityQuality(StrEnum):
    EXACT = "EXACT"        # 取自供应商推送时刻
    DERIVED = "DERIVED"    # 取自公告时刻（推送时刻不可得）
    INFERRED = "INFERRED"  # 取自平台落库时刻或声明的推导规则


def resolve_availability(
    published_at: dt.datetime | None,
    provider_available_at: dt.datetime | None,
    ingested_at: dt.datetime,
) -> tuple[dt.datetime, AvailabilityQuality]:
    """按三级优先级解析 available_at（03-data/01 §11.3）。

    这是 Constraint C-12 的唯一实现点：Adapter 必须如实传入 None，
    本函数据此产出正确的 quality。任何 Adapter 都不得自行拼装这两个字段。

    「公告发布 ≠ 投资系统已知」—— 10:00 公告、10:03 推送时，系统在
    10:00 并不知道。因此只有推送时刻才配称 EXACT。
    """
    if provider_available_at is not None:
        return provider_available_at, AvailabilityQuality.EXACT
    if published_at is not None:
        return published_at, AvailabilityQuality.DERIVED
    return ingested_at, AvailabilityQuality.INFERRED


def declared_lag_availability(
    effective_at: dt.date, lag: dt.timedelta
) -> tuple[dt.datetime, AvailabilityQuality]:
    """用【声明的披露时滞】推导 available_at，质量恒为 INFERRED。

    用于 AKShare 净值历史回补：上游没有披露时刻，但净值的披露节奏是
    已知且稳定的。这是一条【声明的推导规则】而非猜测 —— 时滞取值写入
    governance.data_source_priority 并版本化，回测报告必须复述它。

    质量恒为 INFERRED，绝不因为规则可信就升级为 DERIVED。
    """
    if lag < dt.timedelta(0):
        raise ValueError(f"披露时滞 lag={lag} 不得为负")
    base = dt.datetime.combine(effective_at, dt.time.min, tzinfo=dt.UTC)
    return base + lag, AvailabilityQuality.INFERRED

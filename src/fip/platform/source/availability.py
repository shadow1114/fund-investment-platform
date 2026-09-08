import datetime as dt
from collections.abc import Iterable
from enum import StrEnum


class AvailabilityQuality(StrEnum):
    EXACT = "EXACT"        # 取自供应商推送时刻
    DERIVED = "DERIVED"    # 取自公告时刻（推送时刻不可得）
    INFERRED = "INFERRED"  # 取自平台落库时刻或声明的推导规则


_QUALITY_STRENGTH: dict[AvailabilityQuality, int] = {
    AvailabilityQuality.EXACT: 3,
    AvailabilityQuality.DERIVED: 2,
    AvailabilityQuality.INFERRED: 1,
}


def weakest_quality(
    qualities: Iterable[str | AvailabilityQuality],
) -> AvailabilityQuality:
    """返回整条计算链中最弱的可用性质量。

    空链路没有质量结论，因此不用任何默认等级代替。
    """
    strengths = []
    for quality in qualities:
        parsed = AvailabilityQuality(quality)
        strengths.append((_QUALITY_STRENGTH[parsed], parsed))
    if not strengths:
        raise ValueError("空链路没有 availability_quality 结论")
    return min(strengths, key=lambda pair: pair[0])[1]


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
    已知且稳定的。这是一条【声明的推导规则】而非猜测。

    ⚠️ 如实登记（fix round 4 item 4）：本函数此前的注释声称时滞「写入
    governance.data_source_priority 并版本化」——那是假的。该表由迁移 0006
    建出，但全库没有任何一处往它写行，也没有任何读取方。时滞的唯一取值点是
    调用方传进来的 lag（生产装配路径上来自 fip.platform.cli.DISCLOSURE_LAG_DAYS
    这个常量）。引入第二个 provider 之前必须把它登记进那张表并版本化，否则
    回测报告无法复述「当时用的是哪一套时滞」。

    质量恒为 INFERRED，绝不因为规则可信就升级为 DERIVED。
    """
    if lag < dt.timedelta(0):
        raise ValueError(f"披露时滞 lag={lag} 不得为负")
    base = dt.datetime.combine(effective_at, dt.time.min, tzinfo=dt.UTC)
    return base + lag, AvailabilityQuality.INFERRED

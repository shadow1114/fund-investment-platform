import datetime as dt
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """一次外部取数的原始产物。

    payload 是序列化后的原始返回（parquet），全量留存 —— 上游格式会漂移，
    保留原始 payload 才能在 Adapter 修 bug 后重解析而不重新抓取
    （raw_payload : canonical_raw = 1:N，03-erd §7.1）。

    published_at 与 provider_available_at 拿不到时【必须】为 None，
    不得用 ingested_at 回填（Constraint C-12）。
    """

    dataset: str
    payload: bytes
    row_count: int
    ingested_at: dt.datetime
    request_params: dict[str, str] = field(default_factory=dict)
    published_at: dt.datetime | None = None
    provider_available_at: dt.datetime | None = None


@runtime_checkable
class SourceAdapter(Protocol):
    """外部数据源端口。

    Adapter 只负责协议与格式转换、字段映射到规范模型、如实填写三个时间来源。
    它【不负责】业务规则判断与数据质量分级 —— 后者属 data-service 本体
    （04-integration-architecture §2）。

    保留本端口使 M2+ 换商业数据源时下游零改动。
    """

    provider_code: str
    adapter_version: str

    def fetch(self, dataset: str, **params: str) -> SourceRecord: ...

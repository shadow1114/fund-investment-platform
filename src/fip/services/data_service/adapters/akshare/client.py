import datetime as dt
import io
from collections.abc import Callable
from typing import Any

import pandas as pd

from fip.platform.source.port import SourceRecord
from fip.services.data_service.adapters.akshare.datasets import DATASETS, DatasetSpec


class AkShareContractError(RuntimeError):
    """上游返回的列结构与声明的契约不符。

    显式失败而非静默继续 —— 错映射的因子值不会报错，只会悄悄算错。
    """


def _default_caller(name: str, **params: Any) -> pd.DataFrame:
    import akshare

    fn = getattr(akshare, name, None)
    if fn is None:
        raise AkShareContractError(f"AKShare 无函数 {name}，可能是版本变更")
    return fn(**params)


def _library_version() -> str:
    import akshare

    return str(getattr(akshare, "__version__", "unknown"))


class AkShareSourceAdapter:
    """AKShare 数据源适配器。

    只做协议与格式转换、列契约校验、如实填写三个时间来源。
    不做任何业务规则判断与质量分级（后者属 data-service 本体）。

    AKShare 底层是天天基金 / 新浪 / 中债等公开源，【没有披露时刻】。
    因此 published_at 与 provider_available_at 恒为 None —— 这是事实，
    不是缺陷掩盖。下游据此得到 INFERRED 质量并在 bias-check 中暴露。
    """

    provider_code = "AKSHARE"
    adapter_version = "1"

    def __init__(
        self,
        clock: Callable[[], dt.datetime] | None = None,
        caller: Callable[..., pd.DataFrame] | None = None,
    ) -> None:
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))
        self._caller = caller or _default_caller

    @property
    def library_version(self) -> str:
        return _library_version()

    def fetch(self, dataset: str, **params: str) -> SourceRecord:
        try:
            spec: DatasetSpec = DATASETS[dataset]
        except KeyError:
            raise KeyError(f"未声明的数据集：{dataset}") from None

        call_params: dict[str, Any] = {**spec.fixed_params, **params}
        frame = self._caller(spec.callable_name, **call_params)
        self._assert_columns(spec, frame)

        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        return SourceRecord(
            dataset=dataset,
            payload=buffer.getvalue(),
            row_count=len(frame),
            ingested_at=self._clock(),
            request_params={k: str(v) for k, v in call_params.items()},
            published_at=None,  # AKShare 给不出，如实留空（C-12）
            provider_available_at=None,  # 同上
        )

    @staticmethod
    def _assert_columns(spec: DatasetSpec, frame: pd.DataFrame) -> None:
        missing = spec.required_columns - set(frame.columns)
        if missing:
            raise AkShareContractError(
                f"数据集 {spec.code}（{spec.callable_name}）缺少列 "
                f"{sorted(missing)}；实际列为 {sorted(frame.columns)}。"
                "AKShare 版本变更会改列名，请核对并同步 datasets.py"
            )

import base64
import datetime as dt
import io
import json
import math
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from fip.platform.source.port import SourceRecord
from fip.services.data_service.adapters.akshare.datasets import DATASETS, DatasetSpec


class AkShareContractError(RuntimeError):
    record: SourceRecord
    raw_payload: bytes = b""

    """上游返回的列结构与声明的契约不符。

    显式失败而非静默继续 —— 错映射的因子值不会报错，只会悄悄算错。
    """


def _default_caller(name: str, **params: Any) -> pd.DataFrame:
    import akshare

    fn = getattr(akshare, name, None)
    if fn is None:
        raise AkShareContractError(f"AKShare 无函数 {name}，可能是版本变更")
    return fn(**params)


_overview_lock = threading.Lock()
_overview_last_start = 0.0


def _throttle_overview() -> None:
    global _overview_last_start
    with _overview_lock:
        now = time.monotonic()
        wait = max(0.0, _overview_last_start + 0.5 - now)
        if wait:
            time.sleep(wait)
        _overview_last_start = now + wait


def _isolated_overview(**params: Any) -> pd.DataFrame:
    return _isolated_call(
        [
            sys.executable,
            "-m",
            "fip.services.data_service.adapters.akshare.overview_worker",
            str(params["symbol"]),
        ],
    )


def _run_isolated(command: list[str], *, timeout: float = 25) -> subprocess.CompletedProcess[bytes]:
    # subprocess.run kills and waits for its child on TimeoutExpired, unlike a future timeout.
    return subprocess.run(command, capture_output=True, timeout=timeout, check=True)


def _isolated_call(command: list[str]) -> pd.DataFrame:
    for attempt in range(3):
        _throttle_overview()
        try:
            result = _run_isolated(command)
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise
            time.sleep(0.5 * (2**attempt))
            continue
        envelope = json.loads(result.stdout)
        raw = base64.b64decode(envelope.get("raw", ""))
        if envelope["kind"] == "ok":
            frame = pd.read_parquet(io.BytesIO(base64.b64decode(envelope["parquet"])))
            return frame
        if not envelope["retryable"] or attempt == 2:
            error = AkShareContractError(envelope.get("error", "overview request failed"))
            error.raw_payload = raw
            raise error
        time.sleep(0.5 * (2**attempt))
    raise RuntimeError("unreachable")


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
        self._injected_caller = caller is not None

    @property
    def library_version(self) -> str:
        return _library_version()

    def fetch(self, dataset: str, **params: str) -> SourceRecord:
        try:
            spec: DatasetSpec = DATASETS[dataset]
        except KeyError:
            raise KeyError(f"未声明的数据集：{dataset}") from None

        call_params: dict[str, Any] = {**spec.fixed_params, **params}
        classification_source = dataset in {
            "fund_index_passive",
            "fund_index_enhanced",
            "fund_detail_xq",
        }
        if dataset in {"fund_index_passive", "fund_index_enhanced"}:
            if call_params != spec.fixed_params:
                raise ValueError(
                    "Index membership requires the registered indicator and 全部 scope"
                )
        if dataset == "fund_detail_xq":
            call_params.setdefault("timeout", 20)
            symbol = call_params.get("symbol")
            if not isinstance(symbol, str) or not re.fullmatch(r"[0-9]{6}", symbol):
                raise ValueError("Snowball requires an exact six-digit fund code")
            timeout = float(call_params["timeout"])
            if not math.isfinite(timeout) or not 0 < timeout <= 20:
                raise ValueError("Snowball timeout must be positive and at most 20 seconds")
            call_params["timeout"] = timeout
        if classification_source:
            try:
                if self._injected_caller:
                    frame = self._caller(spec.callable_name, **call_params)
                else:
                    frame = _isolated_call(
                        [
                            sys.executable,
                            "-m",
                            "fip.services.data_service.adapters.akshare.source_worker",
                            spec.callable_name,
                            json.dumps(call_params, ensure_ascii=False),
                        ]
                    )
            except Exception as exc:
                error = (
                    exc
                    if isinstance(exc, AkShareContractError)
                    else AkShareContractError(f"{type(exc).__name__}: {exc}")
                )
                error.record = SourceRecord(
                    dataset=dataset,
                    payload=error.raw_payload,
                    row_count=0,
                    ingested_at=self._clock(),
                    request_params={
                        **{k: str(v) for k, v in call_params.items()},
                        "payload_format": "http_body",
                    },
                )
                if error is exc:
                    raise
                raise error from exc
        elif dataset == "fund_overview" and not self._injected_caller:
            try:
                frame = _isolated_overview(**call_params)
            except AkShareContractError as error:
                error.record = SourceRecord(
                    dataset=dataset,
                    payload=error.raw_payload,
                    row_count=0,
                    ingested_at=self._clock(),
                    request_params={
                        **{k: str(v) for k, v in call_params.items()},
                        "payload_format": "html",
                    },
                    published_at=None,
                    provider_available_at=None,
                )
                raise
        else:
            frame = self._caller(spec.callable_name, **call_params)

        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        record = SourceRecord(
            dataset=dataset,
            payload=buffer.getvalue(),
            row_count=len(frame),
            ingested_at=self._clock(),
            request_params={k: str(v) for k, v in call_params.items()},
            published_at=None,  # AKShare 给不出，如实留空（C-12）
            provider_available_at=None,  # 同上
        )

        try:
            self._assert_columns(spec, frame)
        except AkShareContractError as error:
            error.record = record
            raise
        return record

    @staticmethod
    def _assert_columns(spec: DatasetSpec, frame: pd.DataFrame) -> None:
        """校验列契约。

        AKShare 对“该基金没有这类记录”（如从未拆分过）与“上游改了列结构”
        这两种情况的表达方式恰好都可能是缺列，必须区分：
        - 完全无 schema（0 行 0 列，即 df.columns 为空）：这是上游对“无此类
          记录”的合法表达，不校验列、原样放行，row_count=0。
        - 0 行但列集不为空、或列集不为空但内容不符：无论有没有数据行，
          只要上游声明了列结构且与契约不符，都说明 schema 变了，必须显式
          失败 —— 不要把这条弱化成“空的就放行”，判据是“上游有没有给出
          schema”，不是“有没有数据”。
        """
        if len(frame.columns) == 0:
            return
        missing = spec.required_columns - set(frame.columns)
        if missing:
            raise AkShareContractError(
                f"数据集 {spec.code}（{spec.callable_name}）缺少列 "
                f"{sorted(missing)}；实际列为 {sorted(frame.columns)}。"
                "AKShare 版本变更会改列名，请核对并同步 datasets.py"
            )

"""中债估值中心指数接口适配器，按北京时间把毫秒时间戳还原为行情日期。"""

import datetime as dt
import io
import json
import re
from collections.abc import Callable
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from fip.platform.source.port import SourceRecord

QUERY_URL = "https://valuation.chinabond.com.cn/cbweb-mn/indices/singleIndexQueryResult"
# 除指数 ID、期限类型、指数类型外，其余参数固定使用样例 URL 的取值。
FIXED_PARAMS = {"ltcslx": "", "zslxt1": "", "lx": "1", "locale": "zh_CN"}
COLUMNS = ["date", "value"]
_BEIJING = ZoneInfo("Asia/Shanghai")
_CODE = re.compile(r"[0-9A-Za-z]{1,64}")
_TOKEN = re.compile(r"[0-9A-Za-z]{1,16}")


class ChinaBondContractError(RuntimeError):
    """中债响应结构、序列键或时间戳不符合契约。"""


def _trade_date(raw: Any) -> dt.date:
    """中债时间戳为北京时间零点的毫秒数；非零点说明口径变化，显式报错。"""
    if not isinstance(raw, str) or not raw.isdigit():
        raise ChinaBondContractError(f"时间戳必须是毫秒数字字符串：{raw!r}")
    moment = dt.datetime.fromtimestamp(int(raw) / 1000, tz=_BEIJING)
    if moment.time() != dt.time.min:
        raise ChinaBondContractError(f"时间戳不是北京时间零点：{raw}")
    return moment.date()


def _value(raw: Any, stamp: str) -> float | None:
    # 上游用 null 表示当日无值，保留为空，不补零也不前填。
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ChinaBondContractError(f"指数值必须是数字或 null：{stamp}={raw!r}")
    return float(raw)


class ChinaBondSourceAdapter:
    """独立中债通道；接口不提供发布时间，可得时间保持为空。"""

    provider_code = "CHINABOND"
    adapter_version = "1"

    def __init__(
        self,
        clock: Callable[[], dt.datetime] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))
        # 注入的客户端由调用方管理生命周期。
        self._client = client

    def fetch(self, dataset: str, **params: str) -> SourceRecord:
        if dataset != "index_daily":
            raise KeyError(f"未声明的数据集：{dataset}")
        unknown = set(params) - {"code", "index_type", "period_type"}
        if unknown:
            raise ValueError(f"不支持的请求参数：{sorted(unknown)}")
        code = params.get("code", "")
        index_type = params.get("index_type", "")
        period_type = params.get("period_type", "")
        if not isinstance(code, str) or not _CODE.fullmatch(code):
            raise ValueError("code 必须是中债指数 ID（字母数字）")
        for name, value in (("index_type", index_type), ("period_type", period_type)):
            if not isinstance(value, str) or not _TOKEN.fullmatch(value):
                raise ValueError(f"{name} 必须是非空字母数字")
        if self._client is not None:
            return self._fetch(self._client, dataset, code, index_type, period_type)
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://valuation.chinabond.com.cn/",
            },
            follow_redirects=True,
        ) as client:
            return self._fetch(client, dataset, code, index_type, period_type)

    def _fetch(
        self,
        client: httpx.Client,
        dataset: str,
        code: str,
        index_type: str,
        period_type: str,
    ) -> SourceRecord:
        query = {"indexid": code, "qxlxt": period_type, "zslxt": index_type, **FIXED_PARAMS}
        # 该接口拒绝 GET（405），参数仍按样例 URL 放在查询串中通过 POST 提交。
        response = client.post(QUERY_URL, params=query)
        response.raise_for_status()
        try:
            # 中债接口的 Content-Type 不一定是 JSON，按正文解析。
            body = json.loads(response.text)
        except ValueError as exc:
            raise ChinaBondContractError("中债接口未返回有效 JSON") from exc
        if not isinstance(body, dict):
            raise ChinaBondContractError("中债接口响应必须是对象")
        key = f"{index_type}_{period_type}"
        series = body.get(key)
        if series is None:
            raise ChinaBondContractError(f"响应缺少序列 {key}")
        if not isinstance(series, dict):
            raise ChinaBondContractError(f"序列 {key} 必须是时间戳到数值的对象")
        rows: dict[dt.date, float | None] = {}
        for stamp, raw in series.items():
            day = _trade_date(stamp)
            if day in rows:
                raise ChinaBondContractError(f"序列 {key} 存在重复日期：{day}")
            rows[day] = _value(raw, stamp)
        frame = pd.DataFrame(
            [{"date": day, "value": rows[day]} for day in sorted(rows)], columns=COLUMNS
        )
        frame["value"] = frame["value"].astype("float64")
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        return SourceRecord(
            dataset=dataset,
            payload=buffer.getvalue(),
            row_count=len(frame),
            ingested_at=self._clock(),
            request_params={"code": code, "index_type": index_type, "period_type": period_type},
            published_at=None,
            provider_available_at=None,
        )

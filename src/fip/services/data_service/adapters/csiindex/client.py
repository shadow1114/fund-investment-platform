"""中证指数官方接口适配器，保留原始行情字段及时间来源。"""

import datetime as dt
import io
import re
from collections.abc import Callable
from typing import Any

import httpx
import pandas as pd

from fip.platform.source.port import SourceRecord

BASE_URL = "https://www.csindex.com.cn/csindex-home"
REQUIRED_COLUMNS = frozenset({"tradeDate", "indexCode", "open", "high", "low", "close"})


class CsiIndexContractError(RuntimeError):
    """中证响应状态、身份或字段结构不符合契约。"""


def _date(value: str, name: str, *, basic: bool = False) -> dt.date:
    pattern = r"[0-9]{4}-[0-9]{2}-[0-9]{2}" if basic else r"[0-9]{8}"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError(f"{name} 必须使用 {'YYYY-MM-DD' if basic else 'YYYYMMDD'} 格式")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d" if basic else "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{name} 不是有效日期：{value}") from exc


class CsiIndexSourceAdapter:
    """独立中证通道；不将指数发布日期冒充每日行情可得时间。"""

    provider_code = "CSIINDEX"
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
        unknown = set(params) - {"indexCode", "startDate", "endDate"}
        if unknown:
            raise ValueError(f"不支持的请求参数：{sorted(unknown)}")
        code = params.get("indexCode", "")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9]{6}", code):
            raise ValueError("indexCode 必须是六位字母数字指数代码")
        end = _date(params.get("endDate", ""), "endDate")
        start_value = params.get("startDate", "")
        start = _date(start_value, "startDate") if start_value else None
        if start is not None and start > end:
            raise ValueError("startDate 不能晚于 endDate")
        if self._client is not None:
            return self._fetch(self._client, dataset, code, start, end)
        with httpx.Client(
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.csindex.com.cn/"},
            follow_redirects=True,
        ) as client:
            return self._fetch(client, dataset, code, start, end)

    @staticmethod
    def _get(client: httpx.Client, path: str, **params: str) -> Any:
        response = client.get(f"{BASE_URL}/{path}", params=params)
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError as exc:
            raise CsiIndexContractError("中证接口未返回有效 JSON") from exc
        if not isinstance(body, dict):
            raise CsiIndexContractError("中证接口响应必须是对象")
        if str(body.get("code")) != "200" or body.get("success") is not True:
            raise CsiIndexContractError(
                f"中证接口返回失败：code={body.get('code')}，msg={body.get('msg')}"
            )
        return body.get("data")

    def _fetch(
        self,
        client: httpx.Client,
        dataset: str,
        code: str,
        start: dt.date | None,
        end: dt.date,
    ) -> SourceRecord:
        basic = self._get(client, f"indexInfo/index-basic-info/{code}")
        if not isinstance(basic, dict) or basic.get("indexCode") != code:
            raise CsiIndexContractError("基本信息缺失或指数代码与请求不一致")
        try:
            basic_date = _date(basic.get("basicDate") or "", "basicDate", basic=True)
        except ValueError as exc:
            raise CsiIndexContractError(str(exc)) from exc
        actual_start = max(start, basic_date) if start is not None else basic_date
        if actual_start > end:
            raise ValueError("endDate 早于指数 basicDate，没有有效请求区间")
        request_params = {
            "indexCode": code,
            "startDate": actual_start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }
        rows = self._get(client, "perf/index-perf", **request_params)
        if not isinstance(rows, list):
            raise CsiIndexContractError("行情 data 必须是列表")
        for row in rows:
            if not isinstance(row, dict) or not REQUIRED_COLUMNS <= row.keys():
                raise CsiIndexContractError("行情记录缺少必需字段或不是对象")
            if row["indexCode"] != code:
                raise CsiIndexContractError("行情指数代码与请求不一致")
            try:
                trade_date = _date(row["tradeDate"], "tradeDate")
            except ValueError as exc:
                raise CsiIndexContractError(str(exc)) from exc
            if not actual_start <= trade_date <= end:
                raise CsiIndexContractError("行情日期超出请求区间")
        # 空结果仍保留必需字段；非空结果保留全部上游字段，不修改价格或单位。
        frame = pd.DataFrame(rows) if rows else pd.DataFrame(columns=sorted(REQUIRED_COLUMNS))
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        return SourceRecord(
            dataset=dataset,
            payload=buffer.getvalue(),
            row_count=len(frame),
            ingested_at=self._clock(),
            request_params=request_params,
            published_at=None,
            provider_available_at=None,
        )

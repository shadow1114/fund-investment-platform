"""基准指数日频行情的抓取请求解析、解析与 PIT 版本化写库。

三类数据源（中证 / 中债 / AKShare）都给不出发布时刻与推送时刻，可得时间统一
交给 resolve_availability，由落库时刻推导，质量为 INFERRED，不伪造。
"""

import contextlib
import datetime as dt
import io
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.source.availability import resolve_availability
from fip.platform.source.port import SourceAdapter, SourceRecord
from fip.services.data_service.adapters.akshare.datasets import DATASETS
from fip.services.data_service.models.benchmark import BenchmarkIndex, BenchmarkIndexValue

SOURCE_CSINDEX = "csindex"
SOURCE_CHINABOND = "chinabond"
SOURCE_AKSHARE = "akshare"
SUPPORTED_BENCHMARK_SOURCES: tuple[str, ...] = (SOURCE_CSINDEX, SOURCE_CHINABOND, SOURCE_AKSHARE)

# NavNumeric 为 Numeric(18, 8)，比较前按存储精度量化，避免浮点尾差制造伪版本。
_VALUE_PRECISION = Decimal("0.00000001")


@dataclass(frozen=True, slots=True)
class FrameColumns:
    """数据集 parquet 中的日期列与数值列。"""

    date_column: str
    value_column: str


# 显式映射：(source, dataset) → 日期列 / 数值列。未登记的组合一律拒绝，不猜测列名。
BENCHMARK_FRAME_COLUMNS: dict[tuple[str, str], FrameColumns] = {
    (SOURCE_CSINDEX, "index_daily"): FrameColumns("tradeDate", "close"),
    (SOURCE_CHINABOND, "index_daily"): FrameColumns("date", "value"),
    (SOURCE_AKSHARE, "hk_index_daily"): FrameColumns("date", "latest"),
}


class BenchmarkConfigError(ValueError):
    """基准指数的 source / api / param 配置不足以发起请求（不可重试）。"""


class BenchmarkDataError(ValueError):
    """上游返回的行情不符合契约（日期重复、非正值等）。"""


@dataclass(frozen=True, slots=True)
class BenchmarkFetchRequest:
    source: str
    dataset: str
    params: dict[str, str]


@dataclass(frozen=True, slots=True)
class ParsedIndexValue:
    effective_at: dt.date
    value: Decimal


@dataclass(frozen=True, slots=True)
class ParsedFrame:
    values: list[ParsedIndexValue]
    fetched_row_count: int
    null_count: int


def resolve_akshare_dataset(api: str | None) -> str:
    """按 api（即 AKShare 函数名 DatasetSpec.callable_name）反查已登记的基准数据集。"""
    if not isinstance(api, str) or not api.strip():
        raise BenchmarkConfigError("AKShare 基准指数缺少 api 配置，无法确定调用的数据集")
    candidates = sorted(
        code
        for code, spec in DATASETS.items()
        if spec.callable_name == api.strip() and (SOURCE_AKSHARE, code) in BENCHMARK_FRAME_COLUMNS
    )
    if not candidates:
        raise BenchmarkConfigError(f"AKShare 接口 api={api} 未登记为基准行情数据集，暂不支持")
    if len(candidates) > 1:
        raise BenchmarkConfigError(f"AKShare 接口 api={api} 对应多个数据集：{candidates}")
    return candidates[0]


def build_fetch_request(
    *,
    source: str | None,
    provider_code: str,
    api: str | None,
    param: Mapping[str, object] | None,
    start_date: dt.date | None,
    end_date: dt.date,
) -> BenchmarkFetchRequest:
    """把 benchmark_index 一行配置翻译为对应适配器的 fetch 参数。"""
    if source == SOURCE_CSINDEX:
        # 中证直接用 provider_code，不读取 api / param。
        params = {"indexCode": provider_code, "endDate": end_date.strftime("%Y%m%d")}
        if start_date is not None:
            params["startDate"] = start_date.strftime("%Y%m%d")
        return BenchmarkFetchRequest(source, "index_daily", params)
    if source == SOURCE_CHINABOND:
        if not isinstance(param, Mapping):
            raise BenchmarkConfigError(
                "中债基准指数缺少 param 配置（需要 index_type、period_type）"
            )
        values: dict[str, str] = {}
        for name in ("index_type", "period_type"):
            raw = param.get(name)
            if not isinstance(raw, str) or not raw.strip():
                raise BenchmarkConfigError(f"中债基准指数 param 缺少 {name}")
            values[name] = raw.strip()
        return BenchmarkFetchRequest(
            source,
            "index_daily",
            {"code": provider_code, "index_type": values["index_type"],
             "period_type": values["period_type"]},
        )
    if source == SOURCE_AKSHARE:
        dataset = resolve_akshare_dataset(api)
        return BenchmarkFetchRequest(source, dataset, {"symbol": provider_code})
    raise BenchmarkConfigError(f"不支持的基准数据源 source={source}")


def _parse_date(raw: object) -> dt.date:
    if isinstance(raw, pd.Timestamp):
        day: dt.date = raw.date()
        return day
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        try:
            if len(text) == 8 and text.isdigit():
                return dt.datetime.strptime(text, "%Y%m%d").date()
            return dt.date.fromisoformat(text[:10])
        except ValueError as exc:
            raise BenchmarkDataError(f"行情日期无法解析：{raw!r}") from exc
    raise BenchmarkDataError(f"行情日期类型不支持：{raw!r}")


def _parse_value(raw: object) -> Decimal | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise BenchmarkDataError(f"指数值不是数字：{raw!r}")
    if isinstance(raw, float) and math.isnan(raw):
        return None
    if raw is pd.NA or raw is pd.NaT:
        return None
    text = str(raw).strip()
    if not text or text in {"nan", "NaN", "None", "--", "-"}:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise BenchmarkDataError(f"指数值不是数字：{raw!r}") from exc
    if not value.is_finite():
        raise BenchmarkDataError(f"指数值不是有限数：{raw!r}")
    return value.quantize(_VALUE_PRECISION)


def parse_index_frame(
    payload: bytes,
    columns: FrameColumns,
    start_date: dt.date | None,
    end_date: dt.date,
) -> ParsedFrame:
    """解析 parquet，按 [start_date, end_date] 过滤；null 跳过，非正值显式失败。"""
    frame = pd.read_parquet(io.BytesIO(payload))
    if len(frame.columns) == 0:
        return ParsedFrame([], 0, 0)
    missing = {columns.date_column, columns.value_column} - set(frame.columns)
    if missing:
        raise BenchmarkDataError(f"行情缺少必需列：{sorted(missing)}")
    values: dict[dt.date, Decimal] = {}
    seen: set[dt.date] = set()
    null_count = 0
    for raw_date, raw_value in zip(
        frame[columns.date_column].tolist(), frame[columns.value_column].tolist(), strict=True
    ):
        day = _parse_date(raw_date)
        if day in seen:
            raise BenchmarkDataError(f"行情日期重复：{day}")
        seen.add(day)
        if (start_date is not None and day < start_date) or day > end_date:
            continue
        value = _parse_value(raw_value)
        if value is None:
            null_count += 1
            continue
        if value <= 0:
            raise BenchmarkDataError(f"指数值必须为正：{day}={value}")
        values[day] = value
    return ParsedFrame(
        [ParsedIndexValue(day, values[day]) for day in sorted(values)], len(frame), null_count
    )


@dataclass(frozen=True, slots=True)
class WriteResult:
    inserted_count: int
    unchanged_count: int


def write_index_values(
    session: Session,
    index_id: int,
    values: list[ParsedIndexValue],
    record: SourceRecord,
) -> WriteResult:
    """沿用净值的 PIT 版本规则：同日期值未变不新增版本，变化则 version + 1。"""
    available_at, quality = resolve_availability(
        record.published_at, record.provider_available_at, record.ingested_at
    )
    if not values:
        return WriteResult(0, 0)
    first, last = values[0].effective_at, values[-1].effective_at
    latest: dict[dt.date, BenchmarkIndexValue] = {}
    for row in session.scalars(
        select(BenchmarkIndexValue)
        .where(
            BenchmarkIndexValue.index_id == index_id,
            BenchmarkIndexValue.effective_at >= first,
            BenchmarkIndexValue.effective_at <= last,
        )
        .order_by(BenchmarkIndexValue.effective_at, BenchmarkIndexValue.version)
    ):
        latest[row.effective_at] = row  # 按 version 升序遍历，最后一条即最大版本
    inserted = unchanged = 0
    for parsed in values:
        current = latest.get(parsed.effective_at)
        if current is not None and Decimal(current.value) == parsed.value:
            unchanged += 1
            continue
        # available_at 不得早于生效日 UTC 零点（版本化表时序约束 clause 4）。
        row_available_at = max(
            available_at, dt.datetime.combine(parsed.effective_at, dt.time.min, tzinfo=dt.UTC)
        )
        session.add(
            BenchmarkIndexValue(
                index_id=index_id,
                effective_at=parsed.effective_at,
                version=1 if current is None else current.version + 1,
                value=parsed.value,
                available_at=row_available_at,
                availability_quality=quality.value,
                published_at=record.published_at,
                provider_available_at=record.provider_available_at,
                ingested_at=record.ingested_at,
            )
        )
        inserted += 1
    session.flush()
    return WriteResult(inserted, unchanged)


AdapterFactory = Callable[[str], SourceAdapter]


def _annotate(error: Exception, request: BenchmarkFetchRequest) -> None:
    """把失败所在的数据源 / 数据集附到异常上，供任务项结果展示。"""
    with contextlib.suppress(AttributeError, TypeError):
        error.benchmark_source = request.source  # type: ignore[attr-defined]
        error.benchmark_dataset = request.dataset  # type: ignore[attr-defined]


def default_adapter_factory(source: str) -> SourceAdapter:
    """按 source 构造真实适配器；测试可注入假工厂。"""
    if source == SOURCE_CSINDEX:
        from fip.services.data_service.adapters.csiindex import CsiIndexSourceAdapter

        return CsiIndexSourceAdapter()
    if source == SOURCE_CHINABOND:
        from fip.services.data_service.adapters.chinabond import ChinaBondSourceAdapter

        return ChinaBondSourceAdapter()
    if source == SOURCE_AKSHARE:
        from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter

        return AkShareSourceAdapter()
    raise BenchmarkConfigError(f"不支持的基准数据源 source={source}")


def ingest_benchmark_index(
    session: Session,
    index_id: int,
    *,
    start_date: dt.date | None,
    end_date: dt.date,
    adapter_factory: AdapterFactory = default_adapter_factory,
) -> dict[str, Any]:
    """抓取单个基准指数并写库，返回项级结果；异常向上抛出由调用方记为失败。

    原始返回先于解析留存（raw_payload），解析失败时原始返回仍保留以便排查。
    """
    from fip.services.data_service.ingest import IngestService

    index = session.scalar(
        select(BenchmarkIndex).where(BenchmarkIndex.id == index_id).with_for_update()
    )
    if index is None:
        raise BenchmarkConfigError(f"基准指数 {index_id} 不存在")
    request = build_fetch_request(
        source=index.source,
        provider_code=index.provider_code,
        api=index.api,
        param=index.param,
        start_date=start_date,
        end_date=end_date,
    )
    columns = BENCHMARK_FRAME_COLUMNS[(request.source, request.dataset)]
    adapter = adapter_factory(request.source)
    raw_service = IngestService(session, adapter, None)
    try:
        record = adapter.fetch(request.dataset, **request.params)
    except Exception as error:
        # 适配器在契约失败时可能附带原始返回，照常留存。
        failed_record = getattr(error, "record", None)
        if isinstance(failed_record, SourceRecord):
            with session.begin_nested():
                raw_service._store_raw(failed_record)
        _annotate(error, request)
        raise
    try:
        with session.begin_nested():
            payload = raw_service._store_raw(record)
            parsed = parse_index_frame(record.payload, columns, start_date, end_date)
            written = write_index_values(session, index.id, parsed.values, record)
    except Exception as error:
        # 写值失败回滚后单独留存原始返回，便于修正解析后重放。
        with session.begin_nested():
            raw_service._store_raw(record)
        _annotate(error, request)
        raise
    return {
        "source": request.source,
        "dataset": request.dataset,
        "row_count": len(parsed.values),
        "inserted_count": written.inserted_count,
        "unchanged_count": written.unchanged_count,
        "first_date": parsed.values[0].effective_at.isoformat() if parsed.values else None,
        "last_date": parsed.values[-1].effective_at.isoformat() if parsed.values else None,
        "fetched_row_count": parsed.fetched_row_count,
        "null_count": parsed.null_count,
        "raw_payload_id": payload.id,
    }

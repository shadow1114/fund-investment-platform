"""基金合同基准的保守解析及结构化关联，不猜测缺失权重或指数身份。"""

import datetime as dt
import re
import unicodedata
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fip.platform.source.availability import resolve_availability
from fip.platform.source.port import SourceRecord
from fip.services.data_service.models.benchmark import (
    BenchmarkComponent,
    BenchmarkDefinition,
    BenchmarkIndex,
    BenchmarkMapping,
)
from fip.services.data_service.models.fund import FundShareClass

COMPONENT_MAPPING_PATH = Path("config/benchmark/component_provider_codes.yaml")
_WEIGHT = r"([0-9]+(?:\.[0-9]+)?)%"
_PRECISION = Decimal("0.00000001")


def normalize_component(value: str) -> str:
    """仅统一排版字符，不合并币种、期限或回报口径。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).replace("×", "*")


def load_component_mapping(path: Path = COMPONENT_MAPPING_PATH) -> dict[str, str]:
    body = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = None
    if isinstance(body, dict):
        values = body.get("component_to_lookup_name") or body.get("component_to_provider_code")
    if not isinstance(values, dict) or not values:
        raise ValueError("基准配置缺少 component_to_provider_code 映射")
    result: dict[str, str] = {}
    for name, provider_code in values.items():
        if (
            not isinstance(name, str) or not isinstance(provider_code, str)
            or not name.strip() or not provider_code.strip()
        ):
            raise ValueError("基准组成项和 provider_code 必须是非空字符串")
        key = normalize_component(name)
        if key in result and result[key] != provider_code:
            raise ValueError(f"基准映射名称冲突：{name}")
        result[key] = provider_code
    return result


def parse_benchmark(expression: str) -> tuple[tuple[str, Decimal], ...]:
    """解析简单加权和；单项无法解析权重时按 100%，多项缺权重显式拒绝。"""
    text = normalize_component(expression)
    if not text:
        raise ValueError("基准为空")
    parts: list[str] = []
    depth = 0
    begin = 0
    for pos, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
            if depth < 0:
                raise ValueError(f"基准括号不完整：{expression}")
        elif char == "+" and depth == 0:
            parts.append(text[begin:pos])
            begin = pos + 1
    if depth:
        raise ValueError(f"基准括号不完整：{expression}")
    parts.append(text[begin:])
    result: dict[str, Decimal] = {}
    for part in parts:
        suffix = re.fullmatch(rf"(.+?)\*{_WEIGHT}", part)
        prefix = re.fullmatch(rf"{_WEIGHT}\*(.+)", part)
        if suffix:
            name, percent = suffix.groups()
            weight = Decimal(percent) / 100
        elif prefix:
            percent, name = prefix.groups()
            weight = Decimal(percent) / 100
        elif len(parts) == 1:
            # 无法识别权重时保留完整名称，由配置决定能否映射到具体指数。
            return ((part, Decimal(1)),)
        else:
            raise ValueError(f"基准组成项不能解析权重：{part}")
        if any(c in name for c in "*%+") or not Decimal(0) < weight <= Decimal(1):
            raise ValueError(f"基准组成项或权重不支持：{part}")
        if weight != weight.quantize(_PRECISION):
            raise ValueError(f"基准权重超出存储精度：{part}")
        result[name] = result.get(name, Decimal(0)) + weight
    if sum(result.values(), Decimal(0)) != Decimal(1):
        raise ValueError(f"基准权重之和不等于 100%：{expression}")
    return tuple(result.items())


def save_fund_benchmark(
    session: Session,
    *,
    share_class_id: int,
    fund_code: str,
    expression: str,
    record: SourceRecord,
    component_mapping: Mapping[str, str],
    warnings: list[str],
) -> None:
    """按展示名称完整匹配；已有份额关联及其专属定义原地更新。"""
    def warn(message: str) -> None:
        message = f"{fund_code}: {message}"
        warnings.append(message)
        print(f"基准待复核：{message}")

    try:
        components = parse_benchmark(expression)
    except ValueError as exc:
        warn(str(exc))
        return
    resolved: dict[int, Decimal] = {}
    missing = False
    for name, weight in components:
        provider_code = component_mapping.get(name)
        if provider_code is None:
            warn(f"基准未找到配置 mapping：{name}")
            missing = True
            continue
        index_filter = (
            BenchmarkIndex.display_name == provider_code
            if any("\u4e00" <= char <= "\u9fff" for char in provider_code)
            else BenchmarkIndex.provider_code == provider_code
        )
        matches = session.scalars(select(BenchmarkIndex).where(index_filter)).all()
        if len(matches) != 1:
            warn(
                f"基准未找到唯一 benchmark_index：{name}"
                f"（provider_code={provider_code}，匹配 {len(matches)} 条）"
            )
            missing = True
            continue
        index_id = matches[0].id
        resolved[index_id] = resolved.get(index_id, Decimal(0)) + weight
    if missing:
        return

    # 锁定份额，串行分配该份额的映射变更；不改动共享基准的既有组成项。
    session.execute(
        select(FundShareClass.id).where(FundShareClass.id == share_class_id).with_for_update()
    ).scalar_one()
    current = session.scalars(
        select(BenchmarkMapping)
        .where(
            BenchmarkMapping.share_class_id == share_class_id,
            BenchmarkMapping.valid_to.is_(None),
        )
        .order_by(
            BenchmarkMapping.valid_from.desc(),
            BenchmarkMapping.available_at.desc(),
            BenchmarkMapping.id.desc(),
        )
    ).first()
    observed_day = record.ingested_at.date()
    if current is not None and (
        current.valid_from > observed_day or current.ingested_at > record.ingested_at
    ):
        warn(f"基准观察早于已有映射，不覆盖：{expression}")
        return
    if current is not None:
        definition = session.scalar(
            select(BenchmarkDefinition)
            .where(BenchmarkDefinition.id == current.benchmark_id)
            .with_for_update()
        )
        if definition is None:
            warn(f"已有基准定义不存在：{expression}")
            return
        existing = session.scalars(
            select(BenchmarkComponent).where(BenchmarkComponent.benchmark_id == definition.id)
        ).all()
        previous_weights = {item.index_id: item.weight for item in existing}
        if previous_weights == resolved and definition.display_name == expression[:128]:
            return
        # 旧版本可能复用共享定义，禁止原地更新时连带修改其他基金或分类。
        other_mapping = session.scalar(
            select(BenchmarkMapping.id).where(
                BenchmarkMapping.benchmark_id == definition.id,
                BenchmarkMapping.id != current.id,
            ).limit(1)
        )
        if other_mapping is not None:
            warn(f"已有基准定义被其他映射引用，跳过原地更新：{expression}")
            return
        session.execute(
            delete(BenchmarkComponent).where(BenchmarkComponent.benchmark_id == definition.id)
        )
    else:
        # 每个份额维护专属定义，避免以后更新时影响其他基金。
        benchmark_code = f"BM-FUND-{share_class_id}"
        definition = session.scalar(
            select(BenchmarkDefinition).where(BenchmarkDefinition.benchmark_code == benchmark_code)
        )
        if definition is not None:
            warn(f"份额专属基准定义已存在但没有当前映射：{expression}")
            return
        definition = BenchmarkDefinition(
            benchmark_code=benchmark_code,
            display_name=expression[:128],
        )
        session.add(definition)
        session.flush()
    definition.display_name = expression[:128]
    session.add_all([
        BenchmarkComponent(benchmark_id=definition.id, index_id=index_id, weight=weight)
        for index_id, weight in sorted(resolved.items())
    ])
    available_at, quality = resolve_availability(
        record.published_at, record.provider_available_at, record.ingested_at
    )
    available_at = max(
        available_at, dt.datetime.combine(observed_day, dt.time.min, tzinfo=dt.UTC)
    )
    if current is None:
        current = BenchmarkMapping(
            benchmark_id=definition.id,
            share_class_id=share_class_id,
            classification_code=None,
            valid_from=observed_day,
            valid_to=None,
        )
        session.add(current)
    # 原地更新意味着不再保留旧组成及映射的 PIT 历史。
    current.mapping_source = "FUND_OVERVIEW"
    current.mapping_version = record.ingested_at.strftime("%Y%m%dT%H%M%S%f")
    current.available_at = available_at
    current.availability_quality = quality.value
    current.published_at = record.published_at
    current.provider_available_at = record.provider_available_at
    current.ingested_at = record.ingested_at
    session.flush()

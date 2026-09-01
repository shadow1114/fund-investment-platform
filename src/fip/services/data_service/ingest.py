import datetime as dt
import hashlib
import io
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fip.platform.source.availability import declared_lag_availability, resolve_availability
from fip.platform.source.port import SourceAdapter, SourceRecord
from fip.services.data_service.adapters.akshare.parse import (
    ParsedDistribution,
    parse_distribution_frame,
    parse_nav_frame,
    parse_split_frame,
)
from fip.services.data_service.grouping import split_share_class_name
from fip.services.data_service.models.fund import (
    Fund,
    FundShareClass,
    ProviderFundIdentity,
)
from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
from fip.services.data_service.models.market import FundDistribution, FundNav
from fip.services.data_service.models.raw import CanonicalRaw, RawPayload
from fip.services.data_service.normalization.backfill import backfill_adjusted_nav


@dataclass
class _MergedEvent:
    """同一天的分红与拆分合并态：分红相加、拆分比例相乘（见模块末尾说明）。"""

    dividend: Decimal
    split_ratio: Decimal
    ingested_at: dt.datetime
    payload_id: int


class IngestService:
    """灌数编排。

    每次取数都先留存 raw_payload 再解析 —— 上游格式会漂移，保留原始
    返回才能在 Adapter 修 bug 后重解析而不重新抓取（03-erd §7.1）。

    净值的 available_at 由【声明的披露时滞】推导，质量恒为 INFERRED
    （AKShare 给不出披露时刻）。时滞是配置而非猜测，回测报告须复述它。
    """

    def __init__(
        self, session: Session, adapter: SourceAdapter, disclosure_lag_days: int
    ) -> None:
        self._session = session
        self._adapter = adapter
        self._lag = dt.timedelta(days=disclosure_lag_days)

    # ---------- 基础设施 ----------

    def _provider(self) -> DataProvider:
        provider = self._session.execute(
            select(DataProvider).where(
                DataProvider.provider_code == self._adapter.provider_code
            )
        ).scalar_one_or_none()
        if provider is None:
            provider = DataProvider(
                provider_code=self._adapter.provider_code,
                display_name=self._adapter.provider_code,
            )
            self._session.add(provider)
            self._session.flush()
        return provider

    def ensure_dataset(self, dataset_code: str) -> DataProviderDataset:
        provider = self._provider()
        dataset = self._session.execute(
            select(DataProviderDataset).where(
                DataProviderDataset.provider_id == provider.id,
                DataProviderDataset.dataset_code == dataset_code,
            )
        ).scalar_one_or_none()
        if dataset is None:
            dataset = DataProviderDataset(
                provider_id=provider.id,
                dataset_code=dataset_code,
                adapter_version=self._adapter.adapter_version,
                library_version=getattr(self._adapter, "library_version", "unknown"),
            )
            self._session.add(dataset)
            self._session.flush()
        return dataset

    def _store_raw(self, record: SourceRecord) -> RawPayload:
        dataset = self.ensure_dataset(record.dataset)
        payload = RawPayload(
            dataset_id=dataset.id,
            request_params=record.request_params,
            payload=record.payload,
            row_count=record.row_count,
            library_version=dataset.library_version,
            published_at=record.published_at,
            provider_available_at=record.provider_available_at,
            ingested_at=record.ingested_at,
        )
        self._session.add(payload)
        self._session.flush()
        self._session.add(CanonicalRaw(
            raw_payload_id=payload.id,
            adapter_version=self._adapter.adapter_version,
            parsed_row_count=record.row_count,
        ))
        self._session.flush()
        return payload

    def _times(self, effective_at: dt.date, ingested_at: dt.datetime) -> dict[str, object]:
        available_at, quality = declared_lag_availability(effective_at, self._lag)
        return {
            "available_at": available_at,
            "availability_quality": quality.value,
            "published_at": None,           # AKShare 给不出，如实留空（C-12）
            "provider_available_at": None,  # 同上
            "ingested_at": ingested_at,
        }

    def _ensure_provider_identity(
        self,
        provider: DataProvider,
        provider_fund_id: str,
        share_class_id: int,
        ingested_at: dt.datetime,
    ) -> None:
        """登记 (provider, provider_fund_id) → share_class 的映射，幂等。

        这张映射是 provider 代码与平台份额类别之间【唯一】的桥。没有它，
        任何「按 provider 代码找份额类别」的调用方都只能靠猜，而猜错的
        后果是把一只基金的净值静默写进另一只基金的 PIT 历史 —— 不报错、
        不告警（这正是 cli._resolve 此前的行为）。

        provider_fund_id 【不得】做成 share class 的列（03-erd §5.3）：那会
        锁死单 provider，且映射变化会污染主数据。因此它登记在这张区间型表上。

        三时点按 C-12 如实填写：AKShare 既给不出 provider 推送时刻也给不出
        公告时刻，两列留 NULL，available_at 只能取落库时刻，质量恒为
        INFERRED。valid_from 取落库当日 —— 我们【就是】在这一刻才知道这条
        映射，不去伪造一个更早的生效日（那会让区间表宣称平台在看到映射前
        它就已生效）。
        """
        existing = self._session.execute(
            select(ProviderFundIdentity)
            .where(
                ProviderFundIdentity.provider_id == provider.id,
                ProviderFundIdentity.provider_fund_id == provider_fund_id,
                ProviderFundIdentity.valid_to.is_(None),
            )
            .order_by(ProviderFundIdentity.valid_from.desc())
            .limit(1)
        ).scalars().first()
        if existing is not None:
            if existing.share_class_id != share_class_id:
                # Provider 把同一个代码重新指派给了另一个份额类别（§6.2.1）。
                # 这需要「关闭旧区间、另开新区间」，且必须由人确认哪一段历史
                # 归属谁 —— 自动改写会让既有 PIT 历史的归属静默改变。
                # Plan-1 不处理它，但【绝不】静默沿用旧映射：那等价于继续把
                # 新基金的数据写进旧基金。
                raise ValueError(
                    f"provider {provider.provider_code} 的代码 {provider_fund_id} "
                    f"已登记到份额类别 {existing.share_class_id}，本次却解析到 "
                    f"{share_class_id}。这是一次 provider 映射重指派，需要人工"
                    "关闭旧区间后再重跑（Plan-1 不自动处理）。"
                )
            return

        available_at, quality = resolve_availability(None, None, ingested_at)
        self._session.add(ProviderFundIdentity(
            provider_id=provider.id,
            provider_fund_id=provider_fund_id,
            share_class_id=share_class_id,
            valid_from=ingested_at.astimezone(dt.UTC).date(),
            valid_to=None,
            available_at=available_at,
            availability_quality=quality.value,
            published_at=None,           # AKShare 给不出，如实留空（C-12）
            provider_available_at=None,  # 同上
            ingested_at=ingested_at,
        ))
        self._session.flush()

    # ---------- 基金主数据 ----------

    def ingest_fund_list(self, limit: int | None = None) -> int:
        record = self._adapter.fetch("fund_list")
        self._store_raw(record)
        frame = pd.read_parquet(io.BytesIO(record.payload))
        if limit is not None:
            frame = frame.head(limit)

        provider = self._provider()
        created = 0
        for _, row in frame.iterrows():
            code = str(row["基金代码"]).strip()
            display_name = str(row["基金简称"]).strip()
            grouping = split_share_class_name(display_name)

            fund = self._session.execute(
                select(Fund).where(Fund.product_name == grouping.product_name)
            ).scalar_one_or_none()
            if fund is None:
                fund = Fund(
                    # fund_code 是 String(32)，中文基金全称会超长。
                    # 用 product_name 的稳定短哈希派生；可读性由 product_name 承担。
                    fund_code="P-" + hashlib.sha1(
                        grouping.product_name.encode("utf-8")
                    ).hexdigest()[:16],
                    product_name=grouping.product_name,
                    grouping_status=grouping.status.value,
                )
                self._session.add(fund)
                self._session.flush()

            share_class = self._session.execute(
                select(FundShareClass).where(
                    FundShareClass.fund_id == fund.id,
                    FundShareClass.share_class_code == grouping.share_class_code,
                )
            ).scalar_one_or_none()
            if share_class is None:
                share_class = FundShareClass(
                    fund_id=fund.id,
                    share_class_code=grouping.share_class_code,
                    display_name=display_name,
                )
                self._session.add(share_class)
                self._session.flush()
                created += 1

            # 已存在的份额类别也要走这一步：映射本身可能是上一轮遗漏的，
            # 「份额类别已存在」不蕴含「映射已存在」。_ensure_provider_identity
            # 是幂等的。
            self._ensure_provider_identity(
                provider, code, share_class.id, record.ingested_at
            )
        return created

    # ---------- 净值与事件 ----------

    def _next_version(
        self, model: type[FundNav] | type[FundDistribution], **keys: object
    ) -> int:
        current = self._session.execute(
            select(func.max(model.version)).filter_by(**keys)
        ).scalar_one_or_none()
        return 1 if current is None else int(current) + 1

    def ingest_nav(self, share_class_id: int, provider_fund_id: str) -> int:
        record = self._adapter.fetch("fund_nav", symbol=provider_fund_id)
        payload = self._store_raw(record)
        inserted = 0
        for parsed in parse_nav_frame(record.payload):
            latest = self._session.execute(
                select(FundNav)
                .where(
                    FundNav.share_class_id == share_class_id,
                    FundNav.effective_at == parsed.effective_at,
                )
                .order_by(FundNav.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest is not None and latest.unit_nav == parsed.unit_nav:
                continue  # 值未变，不产生新版本
            self._session.add(FundNav(
                share_class_id=share_class_id,
                effective_at=parsed.effective_at,
                version=self._next_version(
                    FundNav,
                    share_class_id=share_class_id,
                    effective_at=parsed.effective_at,
                ),
                unit_nav=parsed.unit_nav,
                adjusted_nav=None,  # 由 rebuild_adjusted_nav 回填
                raw_payload_id=payload.id,
                **self._times(parsed.effective_at, record.ingested_at),
            ))
            inserted += 1
        self._session.flush()
        return inserted

    def ingest_distributions(self, share_class_id: int, provider_fund_id: str) -> int:
        events: list[tuple[ParsedDistribution, dt.datetime, int]] = []
        for dataset, parser in (
            ("fund_distribution", parse_distribution_frame),
            ("fund_split", parse_split_frame),
        ):
            record = self._adapter.fetch(dataset, symbol=provider_fund_id)
            payload = self._store_raw(record)
            for parsed in parser(record.payload):
                events.append((parsed, record.ingested_at, payload.id))

        merged: dict[dt.date, _MergedEvent] = {}
        for parsed, ingested_at, payload_id in events:
            slot = merged.setdefault(
                parsed.effective_at,
                _MergedEvent(Decimal(0), Decimal(1), ingested_at, payload_id),
            )
            slot.dividend += parsed.dividend_per_unit
            slot.split_ratio *= parsed.split_ratio

        inserted = 0
        for day, merged_event in sorted(merged.items()):
            # 与 ingest_nav 同一条规则：值没变就不产生新版本。重跑是预期的
            # 日常增量用法，若无条件 _next_version + insert，每次重跑都会把
            # 整部分红/拆分史重新插一遍，version（语义是「真实修订」）被无界
            # 污染。两个值【都】相等才算未变，只比其中一个会漏掉另一个的修订。
            latest = self._session.execute(
                select(FundDistribution)
                .where(
                    FundDistribution.share_class_id == share_class_id,
                    FundDistribution.effective_at == day,
                )
                .order_by(FundDistribution.version.desc())
                .limit(1)
            ).scalars().first()
            if (
                latest is not None
                and latest.dividend_per_unit == merged_event.dividend
                and latest.split_ratio == merged_event.split_ratio
            ):
                continue  # 值未变，不产生新版本
            self._session.add(FundDistribution(
                share_class_id=share_class_id,
                effective_at=day,
                version=self._next_version(
                    FundDistribution, share_class_id=share_class_id, effective_at=day
                ),
                dividend_per_unit=merged_event.dividend,
                split_ratio=merged_event.split_ratio,
                raw_payload_id=merged_event.payload_id,
                **self._times(day, merged_event.ingested_at),
            ))
            inserted += 1
        self._session.flush()
        return inserted

    def rebuild_adjusted_nav(self, share_class_id: int, decision_at: dt.date) -> int:
        return backfill_adjusted_nav(self._session, share_class_id, decision_at)


# 同日事件的合并规则：同一天可能同时出现在分红表与拆分表中。分红相加、
# 拆分比例相乘，合并为一行 —— 与 compute_adjusted_nav 的「同日先除息后
# 拆分」口径一致。

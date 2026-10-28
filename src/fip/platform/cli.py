from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.settings import settings

# 只在类型检查期导入 services 层符号——运行期一律用函数体内的延迟 import。
# platform 层不得在模块级依赖 services 层（依赖方向单向，tests/fitness/
# test_architecture.py::test_platform_layer_does_not_import_services_at_module_level
# 会对此断言）；TYPE_CHECKING 分支在运行时永远为 False，不构成模块级依赖，
# mypy 仍能据此做类型检查。
if TYPE_CHECKING:
    from fip.services.data_service.classification.models import ClassificationSnapshot, Evidence
    from fip.services.data_service.classification.service import (
        ClassificationService,
        StoredInterval,
    )
    from fip.services.data_service.ingest import IngestService
    from fip.services.data_service.models.fund import (
        FundClassificationReviewCase,
        FundClassificationRevision,
        FundShareClass,
    )
    from fip.services.data_service.models.raw import RawPayload

DATA_SOURCE_RULE_VERSION = "v1"


def _session() -> Session:
    return Session(create_engine(settings.database_url, future=True), future=True)


def _service(session: Session) -> IngestService:
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.ingest import IngestService

    return IngestService(session, AkShareSourceAdapter(), None)


def _nav_service(session: Session) -> IngestService:
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.ingest import IngestService

    return IngestService.from_policy(
        session, AkShareSourceAdapter(), rule_version=DATA_SOURCE_RULE_VERSION
    )


def _resolve(session: Session, symbol: str) -> FundShareClass:
    """把 provider 的基金代码解析为份额类别，经 fund.provider_fund_identity。

    symbol 是 AKShare 的数字代码（如 "000001"）。它与平台份额类别之间【唯一】
    的桥是 provider_fund_identity —— 它由 ingest-funds 登记。

    这里【没有】也不得有任何兜底分支：解析不到就报错退出。此前的实现先用
    `display_name LIKE %symbol%` 匹配（display_name 是中文简称，永远不含数字
    代码，是死代码），再兜底 `ORDER BY id LIMIT 1` 返回全表最小 id 的份额类别
    并报告成功 —— CLI 会从 AKShare 抓到【这只】基金的真实净值，写进【别人】的
    PIT 历史，无错误、无告警、退出码 0。静默取错基金比报错退出坏得多。

    ── 已知限制：本函数不做 PIT 标识解析 ──

    它只读 valid_to IS NULL 的开放区间，不接受 decision_at、也不按
    available_at 过滤。这【不是】「暂不支持」或「留待后续实现」：

    Plan-1 的标识映射数据【本身没有历史】。AKShare 的基金列表接口只返回
    「今天」的代码与简称，拿不到任何一条「这个代码在 2023-05-01 指向谁」的
    记录；provider_fund_identity 里每一行的 valid_from 都是我们【落库当日】
    （见 IngestService._ensure_provider_identity —— 按 C-12 不得伪造一个更早
    的生效日）。因此即使这里写上 `available_at <= decision_at` 的过滤，灌数日
    之前的任何 decision_at 都只会解析出【零条】映射，而不是一条更正确的映射。

    真实限制因此是：**Plan-1 的标识数据无历史，灌数日之前的回测无法做 PIT
    标识解析**。放宽区间表的 clause 4（fix round 2 item 1）不改变这一点 ——
    它让数据库能【存下】提前公告的区间，但我们手上根本没有这样的历史数据可存。
    要解除这条限制，需要的是一个能提供标识变更历史的数据源，不是这里多写
    一个 WHERE。
    """
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.models.fund import (
        FundShareClass,
        ProviderFundIdentity,
    )
    from fip.services.data_service.models.governance import DataProvider

    share_class = (
        session.execute(
            select(FundShareClass)
            .join(
                ProviderFundIdentity,
                ProviderFundIdentity.share_class_id == FundShareClass.id,
            )
            .join(DataProvider, DataProvider.id == ProviderFundIdentity.provider_id)
            .where(
                DataProvider.provider_code == AkShareSourceAdapter.provider_code,
                ProviderFundIdentity.provider_fund_id == symbol,
                # 只认仍然开放的映射区间；已被关闭的历史映射不参与当下的解析。
                ProviderFundIdentity.valid_to.is_(None),
            )
            # 同一段开放区间正常只有一条；显式定序保证结果确定，不靠数据库返回顺序。
            .order_by(ProviderFundIdentity.valid_from.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if share_class is None:
        raise SystemExit(
            f"symbol {symbol} 尚未登记到 {AkShareSourceAdapter.provider_code} 的"
            "基金标识映射（fund.provider_fund_identity）。请先执行 "
            "`fip ingest-funds` 灌入基金列表；若灌入后仍解析不到，说明该代码不在"
            "上游基金列表中，请核对代码，不要绕过本检查。"
        )
    return share_class


def cmd_ingest_funds(args: argparse.Namespace) -> None:
    with _session() as session:
        result = _service(session).ingest_fund_list(limit=args.limit)
        # 冲突不影响本批其余部分：已成功处理的照常提交，包括本次抓到的
        # raw payload。此前 _ensure_provider_identity 直接抛 ValueError 穿出
        # 这里，整批 ingest-funds 全废 —— 一条映射冲突不该毁掉一整批已抓数据。
        session.commit()
    print(f"新建份额类别 {result.created} 个")
    for warning in result.classification_warnings:
        print(f"待复核：{warning}")
    if result.reassignments:
        # 响亮失败：逐条列出冲突并以非零退出码结束。绝不静默沿用旧映射
        # （那等价于继续把新基金的数据写进旧基金），也绝不自动改写
        # （那会让既有 PIT 历史的归属静默改变）。
        detail = "\n".join(f"  · {c.describe()}" for c in result.reassignments)
        raise SystemExit(
            f"检测到 {len(result.reassignments)} 处 provider 映射重指派，"
            f"这些映射【未被改动】，其余基金已正常登记并提交：\n{detail}\n"
            "请人工确认每一条历史的归属、关闭旧区间后再重跑"
            "（Plan-1 不自动处理重指派）。"
        )


def cmd_ingest_nav(args: argparse.Namespace) -> None:
    from fip.services.data_service.batch import BatchItemStatus, FundIngestSubject

    with _session() as session:
        share_class = _resolve(session, args.symbol)
        # commit() 默认会 expire ORM 属性，离开 with 后 Session 又已关闭；
        # 展示字段必须在提交前复制为普通值，不能在 detached instance 上再读。
        display_name = share_class.display_name
        result = _nav_service(session).ingest_nav_batch(
            [FundIngestSubject(share_class.id, args.symbol)]
        )
        session.commit()
    item = result.items[0]
    print(f"{display_name}：{item.status}" + (f" —— {item.error}" if item.error else ""))
    if item.status in {BatchItemStatus.INVALID, BatchItemStatus.FAILED}:
        raise SystemExit(f"净值灌入失败（{item.status}）：{item.error or '未知错误'}")


def cmd_pit_nav(args: argparse.Namespace) -> None:
    decision_at = dt.date.fromisoformat(args.decision_at)
    context = DecisionExecutionContext(
        decision_id=f"CLI-{decision_at}",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="cli",
        policy_version="cli",
        code_version="cli",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable

    with _session() as session:
        share_class = _resolve(session, args.symbol)
        try:
            points = (
                PitDataContext(context=context, session=session)
                .navs()
                .adjusted_nav_series(
                    share_class.id,
                    dt.date.fromisoformat(args.date_from),
                    dt.date.fromisoformat(args.date_to),
                )
            )
        except AdjustedNavUnavailable as exc:
            # 复权净值现在按 decision_at 现算，算不出来就是【真的】算不出来。
            # 这里【不得】吞掉异常、回退去读 market.fund_nav.adjusted_nav 列、
            # 填 0 或沿用上期（C-6）—— 那会让一段不可信的序列冒充可信序列
            # 流进因子计算。唯一正确的出口是报错退出，并说清是哪只份额类别、
            # 哪个决策日算不出来。
            raise SystemExit(
                f"份额类别 {share_class.display_name}"
                f"（id={share_class.id}, symbol={args.symbol}）在 "
                f"decision_at={decision_at} 无法计算复权净值：{exc}。"
                "该区间的复权净值必须标记为 UNAVAILABLE，不得填 0、"
                "不得沿用上期，也不得改读 fund_nav.adjusted_nav 列"
                "（那只是运维物化值，不是 PIT 真值来源）。"
            ) from exc
    print(f"{share_class.display_name} @ decision_at={decision_at}  共 {len(points)} 条")
    for point in points[:10]:
        print(
            f"  {point.effective_at}  unit={point.unit_nav}  "
            f"adj={point.adjusted_nav}  v{point.version}  "
            f"row={point.availability_quality}  "
            f"chain={point.chain_availability_quality}"
        )


def _latest_classification_interval(
    service: ClassificationService, fund_id: int, target: dt.date
) -> tuple[FundClassificationRevision | None, StoredInterval | None]:
    revision = service.latest(fund_id)
    if revision is None:
        return None, None
    intervals = service.intervals(revision.id)
    interval = next(
        (item for item in intervals if item[0] <= target and (item[1] is None or target < item[1])),
        None,
    )
    return revision, interval


def _active_review_cases(
    cases: Iterable[FundClassificationReviewCase], limit: int
) -> list[FundClassificationReviewCase]:
    """Do not put paused legacy issues in the operator's default queue."""
    selected = []
    for case in cases:
        details = case.details if isinstance(case.details, dict) else {}
        if details.get("evaluation_state") == "PAUSED" or details.get("active_scope") == []:
            continue
        selected.append(case)
        if len(selected) >= limit:
            break
    return selected


def _saved_v3_source_evidence(session: Session, symbol: str) -> tuple[Evidence, ...]:
    """Replay saved source payloads only; this helper never constructs an adapter."""

    from fip.services.data_service.adapters.akshare.classification_sources import (
        parse_fund_overview_observations,
        parse_index_batch,
        parse_snowball_detail,
        source_record_from_payload,
    )
    from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
    from fip.services.data_service.models.raw import RawPayload

    codes = {"fund_overview", "fund_detail_xq", "fund_index_passive", "fund_index_enhanced"}
    rows = session.scalars(
        select(RawPayload)
        .join(DataProviderDataset, DataProviderDataset.id == RawPayload.dataset_id)
        .join(DataProvider, DataProvider.id == DataProviderDataset.provider_id)
        .where(DataProvider.provider_code == "AKSHARE", DataProviderDataset.dataset_code.in_(codes))
        .order_by(RawPayload.ingested_at.desc(), RawPayload.id.desc())
    )
    latest: dict[str, RawPayload] = {}
    for payload in rows:
        dataset = session.get(DataProviderDataset, payload.dataset_id)
        if dataset is None:
            continue
        code = dataset.dataset_code
        if (
            code in {"fund_overview", "fund_detail_xq"}
            and payload.request_params.get("symbol") != symbol
        ):
            continue
        latest.setdefault(code, payload)
    evidence: list[Evidence] = []
    for code in ("fund_index_passive", "fund_index_enhanced"):
        selected = latest.get(code)
        if selected is None:
            continue
        record = source_record_from_payload(selected, dataset=code)
        batch = parse_index_batch(
            record,
            batch_id=f"saved:{selected.id}",
            payload_ref=f"raw_payload:{selected.id}",
        )
        evidence.extend(item for item in batch.evidence if item.raw_value == symbol)
    overview = latest.get("fund_overview")
    if overview is not None:
        evidence.extend(
            parse_fund_overview_observations(
                source_record_from_payload(overview, dataset="fund_overview"),
                payload_ref=f"raw_payload:{overview.id}",
                symbol=symbol,
            )
        )
    detail = latest.get("fund_detail_xq")
    if detail is not None:
        parsed = parse_snowball_detail(
            source_record_from_payload(detail, dataset="fund_detail_xq"),
            payload_ref=f"raw_payload:{detail.id}",
        )
        evidence.extend(parsed.evidence)
    return tuple(evidence)


def _classify_saved_v3(
    session: Session,
    fund_id: int,
    symbol: str,
    payload: RawPayload,
    *,
    actor: str,
    dry_run: bool,
) -> tuple[ClassificationSnapshot, str]:
    from fip.services.data_service.adapters.akshare.classification_sources import (
        parse_fund_list_observations,
        source_record_from_payload,
    )
    from fip.services.data_service.classification.service import ClassificationService
    from fip.services.data_service.classification.workflow import (
        classify_v3_preview,
        merge_snapshot_observations,
        preview_classification,
    )

    listed = parse_fund_list_observations(
        source_record_from_payload(payload, dataset="fund_list"),
        payload_ref=f"raw_payload:{payload.id}",
    )
    evidence = (*listed.get(symbol, ()), *_saved_v3_source_evidence(session, symbol))
    service = ClassificationService(session)
    target = payload.ingested_at.date()
    previous, interval = _latest_classification_interval(service, fund_id, target)
    baseline = interval[2] if interval else None
    revision_id = previous.id if previous else None
    merged = merge_snapshot_observations(baseline, evidence)
    available_at = max((item.classified_at for item in merged), default=payload.ingested_at)
    proposed = classify_v3_preview(
        merged,
        available_at=available_at,
        baseline=baseline,
        baseline_revision_id=revision_id,
    )
    preview = preview_classification(
        proposed, baseline=baseline, baseline_reviewed=bool(previous and previous.reviewed)
    )
    action = preview.action
    if not dry_run and action != "NO_CHANGE":
        service.refresh_v3(
            fund_id,
            evidence,
            available_at=available_at,
            actor=actor,
            reason="replay saved classification payloads",
            valid_from=target,
            ingested_at=payload.ingested_at,
        )
    return preview.snapshot, action


def cmd_classification(args: argparse.Namespace) -> None:
    import pandas as pd

    from fip.services.data_service.classification.service import (
        ClassificationService,
        ReviewDecision,
    )
    from fip.services.data_service.models.fund import FundClassificationReviewCase
    from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
    from fip.services.data_service.models.raw import RawPayload

    with _session() as session:
        service = ClassificationService(session)
        if args.command == "list-classification-reviews":
            cases = session.scalars(
                select(FundClassificationReviewCase)
                .where(FundClassificationReviewCase.status == "PENDING")
                .order_by(FundClassificationReviewCase.id)
                .limit(args.limit * 10)
            )
            for case in _active_review_cases(cases, args.limit):
                print(
                    json.dumps(
                        {"id": case.id, "fund_id": case.fund_id, "revision_id": case.revision_id}
                    )
                )
            return
        if not args.actor.strip():
            raise SystemExit("--actor must be nonempty")
        if args.command == "review-classification":
            # CLI operates under the project's trusted operator environment,
            # never an invented HTTP identity. Production must provision allowlist.
            allowed = {
                v.strip()
                for v in os.environ.get("FIP_CLASSIFICATION_REVIEWERS", "").split(",")
                if v.strip()
            }
            decisions = json.loads(args.decisions)
            revision = service.review(
                args.case_id,
                expected_revision=args.expected_revision,
                decisions={
                    key: ReviewDecision.model_validate(value) for key, value in decisions.items()
                },
                actor=args.actor,
                reason=args.reason,
                can_review=args.actor in allowed,
            )
            session.commit()
            print(f"revision={revision.id}")
            return
        if args.command == "refresh-classification":
            share = _resolve(session, args.symbol)
            if args.dry_run:
                from fip.services.data_service.classification.workflow import fund_refresh_requests

                print(
                    json.dumps(
                        {
                            "fund_id": share.fund_id,
                            "symbol": args.symbol,
                            "rule_version": "3.0.0",
                            "requests": fund_refresh_requests(args.symbol),
                            "network_calls": 0,
                            "write": False,
                        },
                        ensure_ascii=False,
                    )
                )
                return
            from fip.platform.jobs.submitter import JobSubmitter

            day = dt.date.today().isoformat()
            job = JobSubmitter(session).submit(
                "fund_classification_refresh",
                f"classification-refresh|{share.fund_id}|{args.symbol}|{day}",
                resource_id=str(share.fund_id),
                job_payload={
                    "action": "refresh_fund",
                    "fund_id": share.fund_id,
                    "symbol": args.symbol,
                    "actor": args.actor,
                },
            )
            session.commit()
            print(json.dumps({"execution_id": job.execution_id, "status": job.status}))
            return
        if args.command == "refresh-index-sets":
            from fip.services.data_service.classification.workflow import index_refresh_requests

            if args.dry_run:
                print(
                    json.dumps(
                        {"requests": index_refresh_requests(), "network_calls": 0, "write": False},
                        ensure_ascii=False,
                    )
                )
                return
            from fip.platform.jobs.submitter import JobSubmitter

            day = dt.date.today().isoformat()
            job = JobSubmitter(session).submit(
                "fund_classification_index_sets",
                f"classification-index-sets|{day}",
                job_payload={"action": "refresh_index_sets", "actor": args.actor},
            )
            session.commit()
            print(json.dumps({"execution_id": job.execution_id, "status": job.status}))
            return
        # Classification replay consumes saved payloads only. It must not
        # instantiate or invoke a source adapter until an explicitly requested
        # non-v3 legacy replay reaches the parsing branch below.
        payloads = session.scalars(
            select(RawPayload)
            .join(DataProviderDataset, DataProviderDataset.id == RawPayload.dataset_id)
            .join(DataProvider, DataProvider.id == DataProviderDataset.provider_id)
            .where(
                DataProvider.provider_code == "AKSHARE",
                DataProviderDataset.dataset_code == "fund_list",
            )
            .order_by(RawPayload.ingested_at.desc(), RawPayload.id.desc())
        )
        seen: set[str] = set()
        processed = 0
        from fip.services.data_service.classification import DIMENSIONS
        from fip.services.data_service.models.fund import Fund

        report_dimensions = (
            ("asset_class", "strategy") if args.rule_version == "3.0.0" else DIMENSIONS
        )
        unknown = dict.fromkeys(report_dimensions, 0)
        conflicts = dict.fromkeys(report_dimensions, 0)
        tag_states: dict[str, int] = {}
        actions: dict[str, int] = {}
        unknown_types: set[str] = set()
        grouping: set[int] = set()
        for payload in payloads:
            frame = pd.read_parquet(io.BytesIO(payload.payload))
            for _, row in frame.iterrows():
                symbol = str(row["基金代码"]).strip()
                if symbol in seen or (args.symbol and args.symbol != symbol):
                    continue
                seen.add(symbol)
                share = _resolve(session, symbol)
                if args.fund_id and args.fund_id != share.fund_id:
                    continue
                if args.rule_version == "3.0.0":
                    snapshot, action = _classify_saved_v3(
                        session,
                        share.fund_id,
                        symbol,
                        payload,
                        actor=args.actor,
                        dry_run=args.dry_run,
                    )
                else:
                    ingest = _service(session)
                    previous, interval = _latest_classification_interval(
                        service, share.fund_id, payload.ingested_at.date()
                    )
                    baseline = interval[2] if interval else None
                    snapshot = ingest.classify_fields(
                        share.fund_id,
                        {"基金类型": str(row["基金类型"]), "基金简称": str(row["基金简称"])},
                        payload,
                        actor=args.actor,
                        dry_run=args.dry_run,
                    )
                    from fip.services.data_service.classification.workflow import (
                        preview_classification,
                    )

                    action = preview_classification(
                        snapshot,
                        baseline=baseline,
                        baseline_reviewed=bool(previous and previous.reviewed),
                    ).action
                print(
                    json.dumps(
                        {
                            "symbol": symbol,
                            "fund_id": share.fund_id,
                            "action": action,
                            "classification": snapshot.to_dict(),
                        },
                        ensure_ascii=False,
                    )
                )
                processed += 1
                actions[action] = actions.get(action, 0) + 1
                for name in report_dimensions:
                    state = getattr(snapshot, name).status
                    unknown[name] += state == "UNKNOWN"
                    conflicts[name] += state == "CONFLICT"
                for tag, result in (snapshot.strategy_tag_results or {}).items():
                    state = f"{tag}:{result.evaluation_state}:{result.status}"
                    tag_states[state] = tag_states.get(state, 0) + 1
                if snapshot.asset_class.status == "UNKNOWN":
                    unknown_types.add(str(row["基金类型"]))
                product = session.get(Fund, share.fund_id)
                if product is not None and product.grouping_status != "CONFIRMED":
                    grouping.add(product.id)
                if processed % args.batch_size == 0 and not args.dry_run:
                    session.commit()
                if processed >= args.limit:
                    break
            if processed >= args.limit:
                break
        if not args.dry_run:
            session.commit()
        print(
            json.dumps(
                {
                    "summary": {
                        "processed": processed,
                        "dry_run": args.dry_run,
                        "unknown_rates": {
                            k: v / processed if processed else 0 for k, v in unknown.items()
                        },
                        "conflict_rates": {
                            k: v / processed if processed else 0 for k, v in conflicts.items()
                        },
                        "unrecognized_types": sorted(unknown_types),
                        "unconfirmed_grouping_fund_ids": sorted(grouping),
                        "actions": actions,
                        "strategy_tag_states": tag_states,
                    }
                },
                ensure_ascii=False,
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fip")
    sub = parser.add_subparsers(dest="command", required=True)

    p_funds = sub.add_parser("ingest-funds", help="灌入基金列表")
    p_funds.add_argument("--limit", type=int, default=None)
    p_funds.set_defaults(func=cmd_ingest_funds)

    p_nav = sub.add_parser("ingest-nav", help="灌入某只基金的净值与事件并回填复权净值")
    p_nav.add_argument("--symbol", required=True)
    p_nav.set_defaults(func=cmd_ingest_nav)

    p_pit = sub.add_parser("pit-nav", help="按历史 decision_at 查询复权净值序列")
    p_pit.add_argument("--symbol", required=True)
    p_pit.add_argument("--decision-at", required=True, dest="decision_at")
    p_pit.add_argument("--from", required=True, dest="date_from")
    p_pit.add_argument("--to", required=True, dest="date_to")
    p_pit.set_defaults(func=cmd_pit_nav)

    for command in (
        "classify-funds",
        "refresh-classification",
        "refresh-index-sets",
        "list-classification-reviews",
        "review-classification",
    ):
        command_parser = sub.add_parser(command)
        command_parser.set_defaults(func=cmd_classification)
        if command == "list-classification-reviews":
            command_parser.add_argument("--limit", type=int, default=100)
            continue
        command_parser.add_argument("--actor", required=True)
        if command == "review-classification":
            command_parser.add_argument("--case-id", type=int, required=True)
            command_parser.add_argument("--expected-revision", type=int, required=True)
            command_parser.add_argument("--reason", required=True)
            command_parser.add_argument(
                "--decisions", required=True, help="JSON dimension -> ReviewDecision"
            )
        else:
            command_parser.add_argument("--dry-run", action="store_true")
            command_parser.add_argument("--symbol", required=command == "refresh-classification")
            if command == "classify-funds":
                command_parser.add_argument("--fund-id", type=int)
                command_parser.add_argument("--limit", type=int, default=100)
                command_parser.add_argument("--batch-size", type=int, default=50)
                command_parser.add_argument(
                    "--rule-version", choices=("1.0.0", "3.0.0"), default="1.0.0"
                )

    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) is not None and getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "batch_size", 1) <= 0:
        parser.error("--batch-size must be positive")
    if args.command == "classify-funds" and args.limit > 1000:
        parser.error("--limit cannot exceed 1000; classification replay must stay bounded")
    if args.command == "classify-funds" and args.batch_size > 100:
        parser.error("--batch-size cannot exceed 100")
    if args.command == "list-classification-reviews" and args.limit > 1000:
        parser.error("--limit cannot exceed 1000")
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

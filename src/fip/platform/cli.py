import argparse
import datetime as dt
import sys
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
    from fip.services.data_service.ingest import IngestService
    from fip.services.data_service.models.fund import FundShareClass

DATA_SOURCE_RULE_VERSION = "v1"


def _session() -> Session:
    return Session(create_engine(settings.database_url, future=True), future=True)


def _service(session: Session) -> "IngestService":
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.ingest import IngestService

    return IngestService(session, AkShareSourceAdapter(), None)


def _nav_service(session: Session) -> "IngestService":
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.ingest import IngestService

    return IngestService.from_policy(
        session, AkShareSourceAdapter(), rule_version=DATA_SOURCE_RULE_VERSION
    )


def _resolve(session: Session, symbol: str) -> "FundShareClass":
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

    share_class = session.execute(
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
    ).scalars().first()
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
    print(f"{display_name}：{item.status}"
          + (f" —— {item.error}" if item.error else ""))
    if item.status in {BatchItemStatus.INVALID, BatchItemStatus.FAILED}:
        raise SystemExit(
            f"净值灌入失败（{item.status}）：{item.error or '未知错误'}"
        )


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
            points = PitDataContext(
                context=context, session=session
            ).navs().adjusted_nav_series(
                share_class.id,
                dt.date.fromisoformat(args.date_from),
                dt.date.fromisoformat(args.date_to),
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
        print(f"  {point.effective_at}  unit={point.unit_nav}  "
              f"adj={point.adjusted_nav}  v{point.version}  "
              f"row={point.availability_quality}  "
              f"chain={point.chain_availability_quality}")


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

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

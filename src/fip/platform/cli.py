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

DISCLOSURE_LAG_DAYS = 1  # 与 governance.data_source_priority 中登记的时滞一致


def _session() -> Session:
    return Session(create_engine(settings.database_url, future=True), future=True)


def _service(session: Session) -> "IngestService":
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.ingest import IngestService

    return IngestService(session, AkShareSourceAdapter(), DISCLOSURE_LAG_DAYS)


def _resolve(session: Session, symbol: str) -> "FundShareClass":
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.models.fund import FundShareClass

    share_class = session.execute(
        select(FundShareClass).where(FundShareClass.display_name.like(f"%{symbol}%"))
    ).scalars().first()
    if share_class is None:
        share_class = session.execute(
            select(FundShareClass).order_by(FundShareClass.id).limit(1)
        ).scalar_one_or_none()
    if share_class is None:
        raise SystemExit("未找到任何份额类别，请先执行 ingest-funds")
    return share_class


def cmd_ingest_funds(args: argparse.Namespace) -> None:
    with _session() as session:
        created = _service(session).ingest_fund_list(limit=args.limit)
        session.commit()
    print(f"新建份额类别 {created} 个")


def cmd_ingest_nav(args: argparse.Namespace) -> None:
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable

    with _session() as session:
        share_class = _resolve(session, args.symbol)
        service = _service(session)
        navs = service.ingest_nav(share_class.id, args.symbol)
        events = service.ingest_distributions(share_class.id, args.symbol)
        try:
            rebuilt = service.rebuild_adjusted_nav(share_class.id, dt.date.today())
        except AdjustedNavUnavailable as exc:
            # 净值与事件已成功灌入，不能因复权回填失败而把它们一并丢弃——
            # 否则在一个批处理循环里逐只基金调用本命令时，一只基金复权
            # 不可算就会连带丢失它本已成功抓到的净值行，且异常若继续向外
            # 传播会让整个循环中断（本任务的三处 carry-forward 之一：
            # 逐份额类别捕获 AdjustedNavUnavailable，如实记录并继续）。
            session.commit()
            print(f"净值 {navs} 行、事件 {events} 行；复权回填跳过：{exc}")
            return
        session.commit()
    print(f"净值 {navs} 行、事件 {events} 行、复权回填 {rebuilt} 行")


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
    with _session() as session:
        share_class = _resolve(session, args.symbol)
        points = PitDataContext(context=context, session=session).navs().adjusted_nav_series(
            share_class.id,
            dt.date.fromisoformat(args.date_from),
            dt.date.fromisoformat(args.date_to),
        )
    print(f"{share_class.display_name} @ decision_at={decision_at}  共 {len(points)} 条")
    for point in points[:10]:
        print(f"  {point.effective_at}  unit={point.unit_nav}  "
              f"adj={point.adjusted_nav}  v{point.version}  {point.availability_quality}")


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

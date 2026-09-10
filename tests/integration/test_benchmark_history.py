import datetime as dt
from decimal import Decimal

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.models.benchmark import (
    BenchmarkComponent,
    BenchmarkDefinition,
    BenchmarkIndex,
    BenchmarkIndexValue,
    BenchmarkMapping,
)
from fip.services.data_service.models.fund import Fund, FundShareClass

pytestmark = pytest.mark.integration


def _utc(year: int, month: int, day: int) -> dt.datetime:
    return dt.datetime(year, month, day, tzinfo=dt.UTC)


def _times(available_at: dt.datetime) -> dict[str, object]:
    return {
        "available_at": available_at,
        "availability_quality": "INFERRED",
        "published_at": None,
        "provider_available_at": None,
        "ingested_at": _utc(2025, 8, 1),
    }


def _context(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-BENCHMARK-HISTORY",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


@pytest.fixture()
def benchmark_history(db_session):
    fund = Fund(
        fund_code="P-BENCHMARK-HISTORY",
        product_name="benchmark history",
        grouping_status="CONFIRMED",
    )
    db_session.add(fund)
    db_session.flush()
    share_class = FundShareClass(
        fund_id=fund.id,
        share_class_code="A",
        display_name="benchmark history A",
    )
    db_session.add(share_class)

    fallback = BenchmarkDefinition(
        id=1101,
        benchmark_code="HYBRID-FALLBACK",
        display_name="Hybrid fallback",
    )
    direct = BenchmarkDefinition(
        id=1102,
        benchmark_code="HYBRID-DIRECT",
        display_name="Hybrid direct",
    )
    indexes = (
        BenchmarkIndex(
            id=101,
            provider_code="TEST",
            provider_symbol="TR-101",
            display_name="TR 101",
            currency="CNY",
            index_type="TOTAL_RETURN",
        ),
        BenchmarkIndex(
            id=202,
            provider_code="TEST",
            provider_symbol="FP-202",
            display_name="FP 202",
            currency="CNY",
            index_type="FULL_PRICE",
        ),
        BenchmarkIndex(
            id=303,
            provider_code="TEST",
            provider_symbol="TR-303",
            display_name="TR 303",
            currency="CNY",
            index_type="TOTAL_RETURN",
        ),
        BenchmarkIndex(
            id=404,
            provider_code="TEST",
            provider_symbol="FP-404",
            display_name="FP 404",
            currency="CNY",
            index_type="FULL_PRICE",
        ),
    )
    db_session.add_all((fallback, direct, *indexes))
    db_session.flush()
    db_session.add_all(
        (
            BenchmarkComponent(benchmark_id=fallback.id, index_id=101, weight=Decimal("0.6")),
            BenchmarkComponent(benchmark_id=fallback.id, index_id=202, weight=Decimal("0.4")),
            BenchmarkComponent(benchmark_id=direct.id, index_id=303, weight=Decimal("0.7")),
            BenchmarkComponent(benchmark_id=direct.id, index_id=404, weight=Decimal("0.3")),
            BenchmarkMapping(
                benchmark_id=fallback.id,
                share_class_id=None,
                classification_code="HYBRID",
                mapping_source="CLASSIFICATION",
                mapping_version="fallback-v1",
                valid_from=dt.date(2025, 1, 1),
                valid_to=None,
                **_times(_utc(2024, 12, 20)),
            ),
            BenchmarkMapping(
                benchmark_id=direct.id,
                share_class_id=share_class.id,
                classification_code=None,
                mapping_source="SHARE_CLASS",
                mapping_version="direct-v1",
                valid_from=dt.date(2025, 4, 1),
                valid_to=None,
                **_times(_utc(2025, 3, 20)),
            ),
            # Overlaps the request but is not yet visible to the bound decision context.
            BenchmarkMapping(
                benchmark_id=direct.id,
                share_class_id=share_class.id,
                classification_code=None,
                mapping_source="SHARE_CLASS",
                mapping_version="future-correction",
                valid_from=dt.date(2025, 2, 1),
                valid_to=dt.date(2025, 3, 1),
                **_times(_utc(2025, 7, 2)),
            ),
            # Visible but outside the requested effective interval.
            BenchmarkMapping(
                benchmark_id=direct.id,
                share_class_id=share_class.id,
                classification_code=None,
                mapping_source="SHARE_CLASS",
                mapping_version="outside-range",
                valid_from=dt.date(2024, 1, 1),
                valid_to=dt.date(2025, 1, 1),
                **_times(_utc(2024, 1, 1)),
            ),
        )
    )
    db_session.add_all(
        (
            BenchmarkIndexValue(
                index_id=101,
                effective_at=dt.date(2025, 1, 2),
                version=1,
                value=Decimal("100"),
                **_times(_utc(2025, 1, 3)),
            ),
            BenchmarkIndexValue(
                index_id=101,
                effective_at=dt.date(2025, 1, 2),
                version=2,
                value=Decimal("101"),
                **_times(_utc(2025, 7, 2)),
            ),
            BenchmarkIndexValue(
                index_id=202,
                effective_at=dt.date(2025, 1, 2),
                version=1,
                value=Decimal("200"),
                **_times(_utc(2025, 1, 3)),
            ),
            BenchmarkIndexValue(
                index_id=303,
                effective_at=dt.date(2025, 4, 2),
                version=3,
                value=Decimal("300"),
                **_times(_utc(2025, 4, 3)),
            ),
            BenchmarkIndexValue(
                index_id=404,
                effective_at=dt.date(2025, 4, 2),
                version=4,
                value=Decimal("400"),
                **_times(_utc(2025, 4, 3)),
            ),
        )
    )
    db_session.flush()
    return _context(dt.date(2025, 6, 30)), share_class.id


def test_resolve_history_obeys_effective_and_available_time(db_session, benchmark_history):
    context, share_class_id = benchmark_history

    segments = PitDataContext(context, db_session).benchmarks().resolve_history(
        share_class_id,
        "HYBRID",
        dt.date(2025, 1, 1),
        dt.date(2025, 6, 30),
    )

    assert [(item.effective_from, item.effective_to) for item in segments] == [
        (dt.date(2025, 1, 1), dt.date(2025, 4, 1)),
        (dt.date(2025, 4, 1), dt.date(2025, 7, 1)),
    ]
    assert [(item.index_id, item.weight) for item in segments[0].components] == [
        (101, Decimal("0.6")),
        (202, Decimal("0.4")),
    ]
    assert segments[0].mapping_version == "fallback-v1"
    assert segments[1].mapping_version == "direct-v1"
    assert [
        (item.index_id, item.effective_at, item.version)
        for item in segments[0].index_versions
    ] == [
        (101, dt.date(2025, 1, 2), 1),
        (202, dt.date(2025, 1, 2), 1),
    ]
    assert [
        (item.index_id, item.effective_at, item.version)
        for item in segments[1].index_versions
    ] == [
        (303, dt.date(2025, 4, 2), 3),
        (404, dt.date(2025, 4, 2), 4),
    ]


def test_share_class_precedence_is_applied_per_segment(db_session, benchmark_history):
    context, share_class_id = benchmark_history
    repository = PitDataContext(context, db_session).benchmarks()

    segments = repository.resolve_history(
        share_class_id,
        "HYBRID",
        dt.date(2025, 3, 15),
        dt.date(2025, 4, 15),
    )

    actual = [
        (item.effective_from, item.effective_to, item.mapping_version) for item in segments
    ]
    assert actual == [
        (dt.date(2025, 3, 15), dt.date(2025, 4, 1), "fallback-v1"),
        (dt.date(2025, 4, 1), dt.date(2025, 4, 16), "direct-v1"),
    ]

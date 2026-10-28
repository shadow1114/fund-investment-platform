"""Offline v3 replay and preview contracts."""

import datetime as dt
import io

import pandas as pd

from fip.platform.source.port import SourceRecord
from fip.services.data_service.adapters.akshare.classification_sources import (
    parse_fund_list_observations,
    parse_fund_overview_observations,
)
from fip.services.data_service.classification.models import Evidence
from fip.services.data_service.classification.workflow import (
    classify_v3_preview,
    fund_refresh_requests,
    index_refresh_requests,
    merge_snapshot_observations,
    preview_classification,
    should_fetch_snowball,
)

NOW = dt.datetime(2026, 10, 28, tzinfo=dt.UTC)


def record(frame: pd.DataFrame, dataset: str, params: dict[str, str]) -> SourceRecord:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return SourceRecord(dataset, buffer.getvalue(), len(frame), NOW, params)


def test_saved_fund_list_rows_become_stable_v3_observations_without_provider_calls():
    source = record(
        pd.DataFrame([{"基金代码": "000001", "基金简称": "测试混合A", "基金类型": "混合型-偏股"}]),
        "fund_list",
        {},
    )
    parsed = parse_fund_list_observations(source, payload_ref="raw_payload:11")
    assert set(parsed) == {"000001"}
    assert {item.normalized_field for item in parsed["000001"]} == {"formal_type", "name"}
    for item in parsed["000001"]:
        assert item.payload_ref == "raw_payload:11"
        assert '"provider_fund_code":"000001"' in item.locator
        assert item.raw_field in {"基金简称", "基金类型"}


def test_overview_never_turns_benchmark_or_investment_scope_into_strategy():
    source = record(
        pd.DataFrame(
            [
                {
                    "基金全称": "测试基金",
                    "基金类型": "混合型-偏股",
                    "投资范围": "可投资股票债券",
                    "业绩比较基准": "沪深300指数",
                }
            ]
        ),
        "fund_overview",
        {"symbol": "000001"},
    )
    parsed = parse_fund_overview_observations(source, payload_ref="raw_payload:12", symbol="000001")
    assert {item.normalized_field for item in parsed} == {"formal_type"}


def test_v3_preview_uses_saved_observations_and_describes_review_without_persistence():
    items = (
        Evidence(
            source="AGGREGATOR",
            rule_id="SOURCE",
            confidence="PUBLIC_AGGREGATOR",
            classified_at=NOW,
            raw_field="基金类型",
            normalized_field="formal_type",
            raw_value="混合型-偏股",
            locator=(
                'identity:{"provider":"EASTMONEY","dataset":"fund_list",'
                '"provider_fund_code":"000001","raw_field":"基金类型","params":{}}'
            ),
        ),
    )
    result = classify_v3_preview(items, available_at=NOW)
    preview = preview_classification(result, baseline=None)
    assert result.rule_version == "3.0.0"
    assert preview.action in {"WRITE_REVISION", "CREATE_REVIEW"}
    assert result.observations == items
    assert result.strategy.evaluation_state == "EVALUATED"


def test_snapshot_observation_merge_replaces_same_source_identity_only():
    first = Evidence(
        source="AGGREGATOR",
        rule_id="SOURCE",
        confidence="PUBLIC_AGGREGATOR",
        classified_at=NOW,
        raw_field="基金类型",
        normalized_field="formal_type",
        raw_value="混合型-偏股",
        locator=(
            'identity:{"provider":"EASTMONEY","dataset":"fund_list",'
            '"provider_fund_code":"000001","raw_field":"基金类型","params":{}}'
        ),
    )
    revised = first.model_copy(
        update={"raw_value": "债券型-长债", "classified_at": NOW + dt.timedelta(days=1)}
    )
    other_share = first.model_copy(
        update={"raw_value": "债券型-长债", "locator": first.locator.replace("000001", "000002")}
    )
    merged = merge_snapshot_observations(None, [first, revised, other_share])
    assert len(merged) == 2
    assert {item.raw_value for item in merged} == {"债券型-长债"}


def test_refresh_dry_run_plans_central_sets_once_and_detail_conditionally():
    assert index_refresh_requests() == (
        {"dataset": "fund_index_passive", "params": {"symbol": "全部", "indicator": "被动指数型"}},
        {"dataset": "fund_index_enhanced", "params": {"symbol": "全部", "indicator": "增强指数型"}},
    )
    detail = fund_refresh_requests("000001")[-1]
    assert detail["dataset"] == "fund_detail_xq"
    assert detail["params"] == {"symbol": "000001", "timeout": 20}
    assert "not evaluated" in detail["condition"]


def test_resolved_index_strategy_still_fetches_details_when_tag_not_evaluated():
    from tests.unit.test_classification_strategy_v3 import member, v3

    snapshot = v3([member("fund_index_passive")])
    assert snapshot.strategy.status == "CONFIRMED"
    assert snapshot.strategy_tag_results["QUANTITATIVE"].evaluation_state == "NOT_EVALUATED"
    assert should_fetch_snowball(snapshot, available_at=NOW)


def test_preview_ignores_retrieval_timestamp_churn_but_flags_reviewed_semantic_change():
    first = Evidence(
        source="AGGREGATOR",
        rule_id="SOURCE",
        confidence="PUBLIC_AGGREGATOR",
        classified_at=NOW,
        raw_field="基金类型",
        normalized_field="formal_type",
        raw_value="混合型-偏股",
        locator=(
            'identity:{"provider":"EASTMONEY","dataset":"fund_list",'
            '"provider_fund_code":"000001","raw_field":"基金类型","params":{}};row:0'
        ),
    )
    baseline = classify_v3_preview([first], available_at=NOW)
    reingested = first.model_copy(
        update={"classified_at": NOW + dt.timedelta(days=1), "payload_ref": "raw_payload:new"}
    )
    same = classify_v3_preview([reingested], available_at=NOW + dt.timedelta(days=1))
    assert preview_classification(same, baseline=baseline).action == "NO_CHANGE"

    changed = reingested.model_copy(update={"raw_value": "债券型-长债"})
    changed_snapshot = classify_v3_preview(
        [changed], available_at=NOW + dt.timedelta(days=1), baseline=baseline
    )
    assert (
        preview_classification(changed_snapshot, baseline=baseline, baseline_reviewed=True).action
        == "CREATE_REVIEW"
    )

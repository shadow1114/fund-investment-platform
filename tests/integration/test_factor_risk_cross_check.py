import datetime as dt
from decimal import Decimal

import pytest

from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.estimation_adapter import SqlFactorRiskCrossCheckProvider
from fip.services.factor_service.models import (
    FactorDefinition,
    FactorRun,
    FactorValue,
    FactorVersion,
)
from fip.services.fund_service.models import PeerGroupSnapshot

pytestmark = pytest.mark.integration


@pytest.fixture()
def factor_risk_candidates(db_session) -> int:
    policy = PolicyVersion(
        policy_kind="evaluation", version_label="risk-cross-check-v1", content={}
    )
    fund = Fund(
        fund_code="risk-cross-check",
        product_name="Risk Cross Check",
        grouping_status="CONFIRMED",
    )
    db_session.add_all((policy, fund))
    db_session.flush()
    share = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="Risk Cross Check A")
    other_share = FundShareClass(
        fund_id=fund.id,
        share_class_code="B",
        display_name="Risk Cross Check B",
    )
    db_session.add_all((share, other_share))
    peer_group = PeerGroupSnapshot(
        decision_id="decision-1",
        decision_at=dt.date(2026, 9, 10),
        policy_version_id=policy.id,
        classification_code="BOND",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=2,
    )
    db_session.add(peer_group)
    db_session.flush()
    runs = (
        FactorRun(
            decision_id="decision-1",
            peer_group_snapshot_id=peer_group.id,
            metric_version_id=policy.id,
            evaluation_policy_version_id=policy.id,
            input_quality_summary={},
        ),
        FactorRun(
            decision_id="decision-2",
            peer_group_snapshot_id=peer_group.id,
            metric_version_id=policy.id,
            evaluation_policy_version_id=policy.id,
            input_quality_summary={},
        ),
    )
    definitions = (
        FactorDefinition(factor_id="F-RISK-001", display_name="Volatility", usage="DISPLAY"),
        FactorDefinition(factor_id="F-RET-001", display_name="Return", usage="DISPLAY"),
    )
    db_session.add_all((*runs, *definitions))
    db_session.flush()
    risk_version = FactorVersion(
        factor_definition_id=definitions[0].id,
        version_label="v1",
        parameters={},
    )
    return_version = FactorVersion(
        factor_definition_id=definitions[1].id,
        version_label="v1",
        parameters={},
    )
    db_session.add_all((risk_version, return_version))
    db_session.flush()

    comparable_lineage = {
        "observation_dates": ["2026-01-02", "2026-01-03", "2026-01-04"],
        "observation_fingerprint": (
            "c94d617140270757763837396cf104e4001fecaa47f319610c8258ed94297abb"
        ),
        "return_type": "SIMPLE",
        "ddof": 1,
        "annualization": 252,
    }
    db_session.add_all(
        (
            FactorValue(
                id=205,
                factor_run_id=runs[0].id,
                share_class_id=share.id,
                factor_version_id=risk_version.id,
                window="3Y",
                effective_at=dt.date(2026, 9, 10),
                version=2,
                status="AVAILABLE",
                reason_code=None,
                raw_value=Decimal("0.22"),
                normalized_value=None,
                input_lineage={
                    "observation_dates": ["2026-01-02", "2026-01-03", "2026-01-04"],
                    "return_type": "SIMPLE",
                    "ddof": 1,
                    "annualization": 252,
                },
                adjustment_policy_version="adjusted-nav-v1",
                evaluation_policy_version_id=policy.id,
            ),
            FactorValue(
                id=101,
                factor_run_id=runs[0].id,
                share_class_id=share.id,
                factor_version_id=risk_version.id,
                window="3Y",
                effective_at=dt.date(2026, 9, 10),
                version=3,
                status="AVAILABLE",
                reason_code=None,
                raw_value=Decimal("0.12"),
                normalized_value=None,
                input_lineage=comparable_lineage,
                adjustment_policy_version="adjusted-nav-v1",
                evaluation_policy_version_id=policy.id,
            ),
            FactorValue(
                id=150,
                factor_run_id=runs[0].id,
                share_class_id=share.id,
                factor_version_id=return_version.id,
                window="3Y",
                effective_at=dt.date(2026, 9, 10),
                version=1,
                status="AVAILABLE",
                reason_code=None,
                raw_value=Decimal("0.05"),
                normalized_value=None,
                input_lineage=comparable_lineage,
                adjustment_policy_version="adjusted-nav-v1",
                evaluation_policy_version_id=policy.id,
            ),
            FactorValue(
                id=202,
                factor_run_id=runs[1].id,
                share_class_id=share.id,
                factor_version_id=risk_version.id,
                window="3Y",
                effective_at=dt.date(2026, 9, 10),
                version=1,
                status="AVAILABLE",
                reason_code=None,
                raw_value=Decimal("0.10"),
                normalized_value=None,
                input_lineage=comparable_lineage,
                adjustment_policy_version="adjusted-nav-v1",
                evaluation_policy_version_id=policy.id,
            ),
            FactorValue(
                id=203,
                factor_run_id=runs[0].id,
                share_class_id=other_share.id,
                factor_version_id=risk_version.id,
                window="3Y",
                effective_at=dt.date(2026, 9, 10),
                version=1,
                status="AVAILABLE",
                reason_code=None,
                raw_value=Decimal("0.10"),
                normalized_value=None,
                input_lineage=comparable_lineage,
                adjustment_policy_version="adjusted-nav-v1",
                evaluation_policy_version_id=policy.id,
            ),
        )
    )
    db_session.flush()
    return share.id


def test_adapter_returns_all_candidates_in_stable_order(db_session, factor_risk_candidates):
    candidates = SqlFactorRiskCrossCheckProvider(db_session).load_candidates(
        factor_risk_candidates, "decision-1"
    )

    assert tuple(candidate.factor_value_id for candidate in candidates) == (101, 205)
    assert candidates[0].factor_run_id > 0
    assert candidates[0].factor_version_id > 0
    assert candidates[0].volatility == 0.12
    assert candidates[0].window == "3Y"
    assert candidates[0].observation_fingerprint == (
        "c94d617140270757763837396cf104e4001fecaa47f319610c8258ed94297abb"
    )
    assert (candidates[0].return_type, candidates[0].ddof, candidates[0].annualization) == (
        "SIMPLE",
        1,
        252,
    )


def test_adapter_marks_incomplete_lineage_not_comparable(db_session, factor_risk_candidates):
    candidates = SqlFactorRiskCrossCheckProvider(db_session).load_candidates(
        factor_risk_candidates, "decision-1"
    )

    incomplete = candidates[1]
    assert incomplete.factor_value_id == 205
    assert incomplete.observation_fingerprint is None
    assert (incomplete.return_type, incomplete.ddof, incomplete.annualization) == (
        "SIMPLE",
        1,
        252,
    )

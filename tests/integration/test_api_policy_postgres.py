import pytest

from fip.api.context import Principal
from fip.api.policy import ResourcePolicy
from fip.services.portfolio_service.models import PortfolioRecord


@pytest.mark.integration
def test_postgres_portfolio_visibility_uses_owner_and_viewers(db_session):
    db_session.add(
        PortfolioRecord(
            id="P-POLICY-1",
            name="Policy portfolio",
            portfolio_type="MODEL",
            status="ACTIVE",
            base_currency="CNY",
            portfolio_version="v1",
            risk_profile="BALANCED",
            benchmark={},
            portfolio_rule_version="rule-v1",
            owner_user_id="USR-OWNER",
            viewer_user_ids=["USR-VIEWER"],
        )
    )
    db_session.flush()
    resource = db_session.get(PortfolioRecord, "P-POLICY-1")

    assert resource is not None
    policy = ResourcePolicy()
    assert policy.can_read(Principal("USR-VIEWER", ("Researcher",), False), "portfolio", resource)
    assert not policy.can_read(Principal("USR-OTHER", ("Researcher",), False), "portfolio", resource)

from types import SimpleNamespace

from fip.api.context import Principal
from fip.api.policy import ResourcePolicy


def test_portfolio_policy_hides_unowned_resource():
    principal = Principal("USR-2", ("Researcher",), False)
    row = SimpleNamespace(owner_user_id="USR-1", viewer_user_ids=[])

    assert ResourcePolicy().can_read(principal, "portfolio", row) is False


def test_admin_policy_can_read_unowned_resource():
    principal = Principal("USR-2", ("Administrator",), False)
    row = SimpleNamespace(owner_user_id="USR-1", viewer_user_ids=[])

    assert ResourcePolicy().can_read(principal, "portfolio", row) is True

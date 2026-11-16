from datetime import date

from fip.api.repositories import _factor_analysis_as_of_date
from fip.platform.decision_data.pit import resolve_visible_until


class _LatestNavSession:
    def __init__(self, latest_nav_date: date) -> None:
        self.latest_nav_date = latest_nav_date
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return self.latest_nav_date


def test_live_factor_default_uses_latest_visible_nav_date_but_current_data_visibility():
    latest_nav = date(2026, 11, 5)
    session = _LatestNavSession(latest_nav)

    view_date, visible_until = _factor_analysis_as_of_date(
        session, share_class_id=5748, as_of_date=None
    )

    assert view_date == latest_nav
    assert visible_until == resolve_visible_until(date.today())
    assert len(session.statements) == 1


def test_live_factor_explicit_as_of_date_preserves_point_in_time_visibility():
    session = _LatestNavSession(date(2026, 11, 5))
    requested_date = date(2025, 11, 5)

    view_date, visible_until = _factor_analysis_as_of_date(
        session, share_class_id=5748, as_of_date=requested_date.isoformat()
    )

    assert view_date == requested_date
    assert visible_until == resolve_visible_until(requested_date)
    assert session.statements == []

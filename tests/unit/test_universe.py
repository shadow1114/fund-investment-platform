import pytest

from fip.services.fund_service.universe import UniverseRepository
from fip.strategy_library.universe import SelectionCondition, evaluate_candidate


class _ScalarResult:
    def __init__(self, values: tuple[int, ...]) -> None:
        self._values = values

    def scalars(self) -> tuple[int, ...]:
        return self._values


class _OrderedMemberSession:
    def execute(self, statement):
        sql = str(statement)
        assert "fund_universe_member.status = :status_1" in sql
        assert "ORDER BY evaluation.fund_universe_member.share_class_id" in sql
        return _ScalarResult((3, 8, 21))


@pytest.fixture()
def repository() -> UniverseRepository:
    return UniverseRepository(_OrderedMemberSession())  # type: ignore[arg-type]


def test_universe_retains_all_condition_results_for_rejected_candidate():
    result = evaluate_candidate(
        (
            SelectionCondition("eligible", "AVAILABLE", True),
            SelectionCondition("score", "UNAVAILABLE", None),
        )
    )
    assert result.status == "REJECTED"
    assert len(result.conditions) == 2


def test_selected_members_are_sorted(repository):
    assert repository.load_selected_members_ordered(42) == (3, 8, 21)

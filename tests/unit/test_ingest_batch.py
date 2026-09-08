import datetime as dt
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from fip.services.data_service.batch import (
    BatchIngestResult,
    BatchItemStatus,
    FundIngestSubject,
)
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable


class _Session:
    def begin_nested(self):
        return nullcontext()


class _BatchService(IngestService):
    def __init__(self) -> None:
        self._session = _Session()  # type: ignore[assignment]
        self.visited: list[tuple[str, int]] = []

    def ingest_nav(self, share_class_id: int, provider_fund_id: str) -> int:
        self.visited.append(("nav", share_class_id))
        if share_class_id == 4:
            raise ValueError("invalid payload")
        if share_class_id == 5:
            raise RuntimeError("system failure")
        return 1

    def ingest_distributions(self, share_class_id: int, provider_fund_id: str) -> int:
        self.visited.append(("events", share_class_id))
        return 0

    def rebuild_adjusted_nav(self, share_class_id: int, decision_at=None) -> int:
        self.visited.append(("rebuild", share_class_id))
        if share_class_id == 2:
            raise AdjustedNavUnavailable("broken chain")
        return 1


def _subject(subject_id: int) -> FundIngestSubject:
    return FundIngestSubject(subject_id, f"P-{subject_id}")


def test_unavailable_item_does_not_stop_later_subjects():
    service = _BatchService()

    result = service.ingest_nav_batch([_subject(1), _subject(2), _subject(3)])

    assert isinstance(result, BatchIngestResult)
    assert [item.status for item in result.items] == [
        BatchItemStatus.SUCCESS,
        BatchItemStatus.UNAVAILABLE,
        BatchItemStatus.SUCCESS,
    ]
    assert ("rebuild", 3) in service.visited
    assert result.items[1].subject_id == 2
    assert result.items[1].error == "broken chain"


def test_value_error_is_invalid_and_does_not_stop_batch():
    result = _BatchService().ingest_nav_batch([_subject(4), _subject(3)])

    assert [item.status for item in result.items] == [
        BatchItemStatus.INVALID,
        BatchItemStatus.SUCCESS,
    ]


def test_unknown_system_error_is_not_swallowed():
    with pytest.raises(RuntimeError, match="system failure"):
        _BatchService().ingest_nav_batch([_subject(5), _subject(3)])


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _PolicySession:
    def __init__(self, *values) -> None:
        self._values = iter(values)

    def execute(self, _statement):
        return _ScalarResult(next(self._values))


_ADAPTER = SimpleNamespace(provider_code="AKSHARE", adapter_version="v1")


def test_policy_factory_loads_versioned_disclosure_lag_per_dataset():
    nav_dataset = SimpleNamespace(id=12)
    distribution_dataset = SimpleNamespace(id=13)
    split_dataset = SimpleNamespace(id=14)

    service = IngestService.from_policy(  # type: ignore[arg-type]
        _PolicySession(
            nav_dataset,
            SimpleNamespace(disclosure_lag_days=1),
            distribution_dataset,
            SimpleNamespace(disclosure_lag_days=2),
            split_dataset,
            SimpleNamespace(disclosure_lag_days=3),
        ),
        _ADAPTER,
        rule_version="v1",
    )

    assert {code: lag.days for code, lag in service._lags.items()} == {
        "fund_nav": 1,
        "fund_distribution": 2,
        "fund_split": 3,
    }


def test_policy_factory_fails_loudly_when_rule_is_missing():
    dataset = SimpleNamespace(id=12)

    with pytest.raises(ValueError, match="disclosure lag"):
        IngestService.from_policy(  # type: ignore[arg-type]
            _PolicySession(dataset, None), _ADAPTER, rule_version="v1"
        )


def test_rebuild_uses_strict_backfill_so_batch_can_report_unavailable(monkeypatch):
    service = IngestService(_Session(), _ADAPTER, disclosure_lag_days=1)  # type: ignore[arg-type]

    def strict_backfill(_session, _share_class_id, _decision_at, *, strict=False):
        assert strict is True
        raise AdjustedNavUnavailable("broken production chain")

    monkeypatch.setattr(
        "fip.services.data_service.ingest.backfill_adjusted_nav", strict_backfill
    )

    with pytest.raises(AdjustedNavUnavailable, match="broken production chain"):
        service.rebuild_adjusted_nav(1, decision_at=None)  # type: ignore[arg-type]


def test_availability_uses_the_rule_for_the_actual_dataset():
    service = IngestService(
        _Session(),  # type: ignore[arg-type]
        _ADAPTER,  # type: ignore[arg-type]
        disclosure_lag_days={
            "fund_nav": 1,
            "fund_distribution": 2,
            "fund_split": 3,
        },
    )

    nav = service._times(
        "fund_nav", dt.date(2026, 9, 1), dt.datetime(2026, 9, 8, tzinfo=dt.UTC)
    )
    split = service._times(
        "fund_split", dt.date(2026, 9, 1), dt.datetime(2026, 9, 8, tzinfo=dt.UTC)
    )

    assert nav["available_at"] == dt.datetime(2026, 9, 2, tzinfo=dt.UTC)
    assert split["available_at"] == dt.datetime(2026, 9, 4, tzinfo=dt.UTC)

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from fip.api.repositories import FundRepository
from fip.api.schemas import BenchmarkComponentModel, NavSeriesPayloadModel
from fip.platform.decision_data.pit import resolve_visible_until
from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable
from fip.services.data_service.repositories.benchmark import SqlBenchmarkPitRepository

VIEW_DATE = dt.date(2025, 1, 31)
VISIBLE_UNTIL = resolve_visible_until(VIEW_DATE)
START = dt.date(2025, 1, 1)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def scalars(self):
        return iter(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class _BenchmarkSession:
    """无数据库测试替身，同时检查 SQL 的 PIT 过滤与映射优先级。"""

    def __init__(self):
        self.session = Mock(spec=Session)
        self.session.execute.side_effect = self.execute
        self.mapping_rows = [
            self.mapping(11, None, "ACTIVE_EQUITY", START, START),
            self.mapping(22, 7, None, START, START),
            self.mapping(33, 7, None, START, dt.date(2025, 2, 1)),
            self.mapping(44, 7, None, dt.date(2025, 2, 1), START),
        ]
        self.components = [
            {
                "index_id": 101,
                "display_name": "股票指数",
                "weight": Decimal("0.6"),
                "index_type": None,
            },
            {
                "index_id": 202,
                "display_name": "债券指数",
                "weight": Decimal("0.4"),
                "index_type": None,
            },
        ]
        self.values = [
            self.value(101, 2, 1, "100", dt.date(2025, 1, 2)),
            self.value(101, 2, 2, "102", VIEW_DATE),
            self.value(101, 2, 3, "999", dt.date(2025, 2, 1)),
            self.value(101, 3, 1, "103", dt.date(2025, 1, 3)),
            self.value(202, 2, 1, "2000", dt.date(2025, 1, 2)),
            self.value(202, 4, 1, "2100", dt.date(2025, 1, 4)),
        ]
        self.nav = [
            SimpleNamespace(effective_at=dt.date(2025, 1, 2), version=2, unit_nav=Decimal("1.2")),
            SimpleNamespace(effective_at=dt.date(2025, 1, 2), version=1, unit_nav=Decimal("1.1")),
            SimpleNamespace(effective_at=dt.date(2025, 1, 3), version=1, unit_nav=Decimal("1.3")),
        ]

    @staticmethod
    def mapping(benchmark_id, share_class_id, classification_code, valid_from, available_date):
        return {
            "id": benchmark_id,
            "benchmark_id": benchmark_id,
            "share_class_id": share_class_id,
            "classification_code": classification_code,
            "valid_from": valid_from,
            "valid_to": None,
            "available_at": resolve_visible_until(available_date),
            "mapping_source": "SHARE_CLASS" if share_class_id else "CLASSIFICATION",
            "mapping_version": f"mapping-{benchmark_id}",
        }

    @staticmethod
    def value(index_id, day, version, value, available_date):
        return {
            "index_id": index_id,
            "effective_at": dt.date(2025, 1, day),
            "version": version,
            "value": Decimal(value),
            "available_at": resolve_visible_until(available_date),
            "availability_quality": "INFERRED",
        }

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM market.benchmark_mapping" in sql:
            assert "available_at <= :visible_until" in sql
            assert "valid_from <= :effective_at" in sql
            assert "valid_to > :effective_at" in sql
            assert "CASE WHEN share_class_id IS NOT NULL THEN 0 ELSE 1 END" in sql
            assert "valid_from DESC, available_at DESC, id DESC" in sql
            rows = [
                row
                for row in self.mapping_rows
                if row["available_at"] <= params["visible_until"]
                and row["valid_from"] <= params["effective_at"]
                and (row["valid_to"] is None or row["valid_to"] > params["effective_at"])
                and (
                    row["share_class_id"] == params["share_class_id"]
                    or row["classification_code"] == params["classification_code"]
                )
            ]
            rows.sort(
                key=lambda row: (
                    row["share_class_id"] is not None,
                    row["valid_from"],
                    row["available_at"],
                    row["id"],
                ),
                reverse=True,
            )
            return _Result(rows[:1])
        if "FROM market.benchmark_definition" in sql:
            assert params["benchmark_id"] in {11, 22}
            return _Result([{"display_name": "真实复合基准"}])
        if "FROM market.benchmark_component" in sql:
            assert "JOIN market.benchmark_index" in sql
            return _Result(self.components)
        if "FROM market.benchmark_index_value" in sql:
            assert "available_at <= :visible_until" in sql
            assert "effective_at BETWEEN :date_from AND :date_to" in sql
            assert "DISTINCT ON (effective_at)" in sql
            assert "ORDER BY effective_at, version DESC" in sql
            rows = [
                row
                for row in self.values
                if row["index_id"] == params["index_id"]
                and row["available_at"] <= params["visible_until"]
                and params["date_from"] <= row["effective_at"] <= params["date_to"]
            ]
            latest = {}
            for row in sorted(rows, key=lambda row: row["version"], reverse=True):
                latest.setdefault(row["effective_at"], row)
            return _Result([latest[day] for day in sorted(latest)])
        if "FROM market.fund_nav" in sql:
            return _Result(self.nav)
        raise AssertionError(f"未预期的查询：{sql}")


@pytest.fixture
def display_repository(monkeypatch):
    fake = _BenchmarkSession()
    repository = FundRepository(fake.session)
    pair = (SimpleNamespace(id=5), SimpleNamespace(id=7, inception_date=START))
    monkeypatch.setattr(repository, "_required_share_class", lambda identifier: pair)
    monkeypatch.setattr(repository, "_summary", lambda *args: {"fund_id": "7"})
    monkeypatch.setattr(repository, "_manager_ids", lambda *args: [])
    classification = Mock()
    classification.current.return_value = SimpleNamespace(
        classification_code="ACTIVE_EQUITY", valid_from=START
    )
    factory = Mock(return_value=classification)
    monkeypatch.setattr("fip.api.repositories.SqlClassificationPitRepository", factory)
    fee = Mock()
    fee.current.return_value = ()
    monkeypatch.setattr("fip.api.repositories.SqlFeePitRepository", Mock(return_value=fee))
    return repository, fake, factory


def _read_nav(repository, **overrides):
    params = {
        "date_from": START.isoformat(),
        "date_to": VIEW_DATE.isoformat(),
        "frequency": "DAILY",
        "nav_type": "UNIT",
        "as_of_date": VIEW_DATE.isoformat(),
    }
    return repository.read_nav_series("7", **(params | overrides))


def test_configured_mapping_uses_pit_precedence_without_relaxing_evaluation_validation():
    fake = _BenchmarkSession()
    repository = SqlBenchmarkPitRepository(fake.session, VISIBLE_UNTIL)
    configured = repository.configured_mapping(7, "ACTIVE_EQUITY")
    assert configured.benchmark_id == 22
    assert configured.benchmark_name == "真实复合基准"
    assert configured.benchmark_type == "COMPOSITE"
    assert [item.benchmark_name for item in configured.components] == ["股票指数", "债券指数"]
    assert repository.resolve(7, "ACTIVE_EQUITY").status == "BENCHMARK_UNAVAILABLE"
    fake.components = [fake.components[0] | {"index_type": "TOTAL_RETURN", "weight": Decimal(1)}]
    assert repository.configured_mapping(7, "ACTIVE_EQUITY").benchmark_type == "INDEX"
    assert repository.resolve(7, "ACTIVE_EQUITY").status == "AVAILABLE"


def test_configured_mapping_falls_back_to_classification_and_honors_interval_end():
    fake = _BenchmarkSession()
    fake.mapping_rows[1]["valid_to"] = VIEW_DATE
    configured = SqlBenchmarkPitRepository(fake.session, VISIBLE_UNTIL).configured_mapping(
        7, "ACTIVE_EQUITY"
    )
    assert configured.benchmark_id == 11
    assert configured.mapping_version == "mapping-11"


def test_detail_displays_real_definition_and_index_names_with_seed_types(display_repository):
    repository, fake, factory = display_repository
    benchmark = repository.read_detail("7", as_of_date=VIEW_DATE.isoformat())["benchmark"]
    assert benchmark == {
        "benchmark_id": "22",
        "benchmark_name": "真实复合基准",
        "benchmark_type": "COMPOSITE",
        "mapping_version": "mapping-22",
        "status": "AVAILABLE",
        "components": [
            {"benchmark_id": "101", "benchmark_name": "股票指数", "weight": Decimal("0.6")},
            {"benchmark_id": "202", "benchmark_name": "债券指数", "weight": Decimal("0.4")},
        ],
    }
    factory.assert_called_once_with(fake.session, VISIBLE_UNTIL)


@pytest.mark.parametrize("frequency", ["DAILY", "WEEKLY", "MONTHLY"])
def test_nav_returns_all_raw_pit_indexes_without_weighting_or_filling(
    display_repository, frequency
):
    repository, fake, factory = display_repository
    payload = _read_nav(repository, frequency=frequency)
    assert payload["data"]["benchmark_series"] == [
        {
            "benchmark_id": "101",
            "benchmark_name": "股票指数",
            "weight": 0.6,
            "points": [
                {"date": "2025-01-02", "value": 102.0},
                {"date": "2025-01-03", "value": 103.0},
            ],
        },
        {
            "benchmark_id": "202",
            "benchmark_name": "债券指数",
            "weight": 0.4,
            "points": [
                {"date": "2025-01-02", "value": 2000.0},
                {"date": "2025-01-04", "value": 2100.0},
            ],
        },
    ]
    nav_values = [point["nav"] for point in payload["data"]["points"]]
    assert nav_values == ([1.2, 1.3] if frequency == "DAILY" else [1.3])
    assert payload["meta"]["unavailable_count"] == 0
    factory.assert_called_once_with(fake.session, VISIBLE_UNTIL)
    NavSeriesPayloadModel.model_validate(payload["data"])


def test_nav_applies_date_range_and_preserves_components_without_values(display_repository):
    repository, fake, _factory = display_repository
    fake.values = [row for row in fake.values if row["index_id"] != 202]
    series = _read_nav(repository, date_from="2025-01-03")["data"]["benchmark_series"]
    assert series[0]["points"] == [{"date": "2025-01-03", "value": 103.0}]
    assert series[1]["benchmark_id"] == "202"
    assert series[1]["weight"] == 0.4
    assert series[1]["points"] == []


def test_no_visible_mapping_returns_empty_series_and_unknown_detail(display_repository):
    repository, fake, _factory = display_repository
    fake.mapping_rows = []
    assert _read_nav(repository)["data"]["benchmark_series"] == []
    detail = repository.read_detail("7", as_of_date=VIEW_DATE.isoformat())["benchmark"]
    assert detail["benchmark_name"] == "UNKNOWN"
    assert detail["components"] == []
    assert detail["status"] == "BENCHMARK_UNAVAILABLE"


@pytest.mark.parametrize("unavailable", [False, True])
def test_adjusted_nav_behavior_is_preserved_with_benchmark_series(
    display_repository, monkeypatch, unavailable
):
    repository, fake, _factory = display_repository
    nav = Mock()
    if unavailable:
        nav.adjusted_nav_series.side_effect = AdjustedNavUnavailable("不可用")
        fake.nav = [dt.date(2025, 1, 2)]
    else:
        nav.adjusted_nav_series.return_value = [
            SimpleNamespace(effective_at=dt.date(2025, 1, 2), adjusted_nav=Decimal("1.5"))
        ]
    factory = Mock(return_value=nav)
    monkeypatch.setattr("fip.api.repositories.SqlNavPitRepository", factory)
    payload = _read_nav(repository, nav_type="ADJUSTED")
    assert payload["data"]["points"] == [{
        "date": "2025-01-02",
        "nav": None if unavailable else 1.5,
        "nav_status": "UNAVAILABLE" if unavailable else "VALID",
        "nav_reason": "ADJUSTED_NAV_UNAVAILABLE" if unavailable else None,
    }]
    assert payload["meta"]["unavailable_count"] == int(unavailable)
    assert len(payload["data"]["benchmark_series"]) == 2
    factory.assert_called_once_with(fake.session, VISIBLE_UNTIL)
    nav.adjusted_nav_series.assert_called_once_with(7, START, VIEW_DATE)


def test_new_response_fields_are_backward_compatible_and_accept_nullable_values():
    assert BenchmarkComponentModel(benchmark_id="101", weight=1).benchmark_name is None
    first = NavSeriesPayloadModel(fund_id="7", points=[])
    second = NavSeriesPayloadModel(fund_id="8", points=[])
    first.benchmark_series.append({})
    assert second.benchmark_series == []
    payload = NavSeriesPayloadModel.model_validate(
        {
            "fund_id": "7",
            "points": [],
            "benchmark_series": [
                {
                    "benchmark_id": "101",
                    "benchmark_name": "股票指数",
                    "weight": 1,
                    "points": [{"date": "2025-01-02", "value": None}],
                },
            ],
        }
    )
    assert payload.benchmark_series[0].points[0].value is None

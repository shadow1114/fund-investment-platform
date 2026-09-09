import datetime as dt
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import (
    BenchmarkComponentPoint,
    BenchmarkResolution,
)

_MAPPING_SQL = text("""
    SELECT id, benchmark_id, mapping_source, mapping_version
    FROM market.benchmark_mapping
    WHERE available_at <= :visible_until
      AND valid_from <= :effective_at
      AND (valid_to IS NULL OR valid_to > :effective_at)
      AND ((:share_class_id IS NOT NULL AND share_class_id = :share_class_id)
        OR (:classification_code IS NOT NULL AND classification_code = :classification_code))
    ORDER BY CASE WHEN share_class_id IS NOT NULL THEN 0 ELSE 1 END,
             valid_from DESC, available_at DESC, id DESC
    LIMIT 1
""")
_COMPONENT_SQL = text("""
    SELECT component.index_id, component.weight, index.index_type
    FROM market.benchmark_component AS component
    JOIN market.benchmark_index AS index ON index.id = component.index_id
    WHERE component.benchmark_id = :benchmark_id ORDER BY component.index_id
""")
_SERIES_SQL = text("""
    SELECT DISTINCT ON (effective_at) effective_at, value, version, availability_quality
    FROM market.benchmark_index_value
    WHERE index_id = :index_id AND available_at <= :visible_until
      AND effective_at BETWEEN :date_from AND :date_to
    ORDER BY effective_at, version DESC
""")


class SqlBenchmarkPitRepository:
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        self._session = session
        self._visible_until = visible_until

    def resolve(self, share_class_id: int, classification_code: str) -> BenchmarkResolution:
        row = (
            self._session.execute(
                _MAPPING_SQL,
                {
                    "share_class_id": share_class_id,
                    "classification_code": classification_code,
                    "effective_at": self._visible_until.date(),
                    "visible_until": self._visible_until,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            return BenchmarkResolution.unavailable()
        component_rows = (
            self._session.execute(_COMPONENT_SQL, {"benchmark_id": row["benchmark_id"]})
            .mappings()
            .all()
        )
        components = tuple(
            BenchmarkComponentPoint(r["index_id"], r["weight"]) for r in component_rows
        )
        if not components or sum((c.weight for c in components), Decimal(0)) != Decimal(1):
            return BenchmarkResolution.unavailable()
        required_types = {
            "ACTIVE_EQUITY": {"TOTAL_RETURN"},
            "PASSIVE_EQUITY": {"TOTAL_RETURN"},
            "BOND": {"FULL_PRICE"},
            "HYBRID": {"TOTAL_RETURN", "FULL_PRICE"},
        }.get(classification_code)
        if (
            required_types is not None
            and {r["index_type"] for r in component_rows} != required_types
        ):
            return BenchmarkResolution.unavailable()
        return BenchmarkResolution(
            row["benchmark_id"],
            components,
            row["mapping_source"],
            row["mapping_version"],
            "AVAILABLE",
        )

    def index_series(
        self, index_id: int, date_from: dt.date, date_to: dt.date
    ) -> tuple[tuple[dt.date, Decimal, int, str], ...]:
        rows = (
            self._session.execute(
                _SERIES_SQL,
                {
                    "index_id": index_id,
                    "date_from": date_from,
                    "date_to": date_to,
                    "visible_until": self._visible_until,
                },
            )
            .mappings()
            .all()
        )
        return tuple(
            (r["effective_at"], r["value"], r["version"], r["availability_quality"]) for r in rows
        )

    def composite_series(
        self, resolution: BenchmarkResolution, date_from: dt.date, date_to: dt.date
    ) -> tuple[tuple[dt.date, Decimal | None, str], ...]:
        """Materialize a composite without filling or renormalizing missing components."""
        component_series = {
            component.index_id: {
                effective_at: value
                for effective_at, value, _version, _quality in self.index_series(
                    component.index_id, date_from, date_to
                )
            }
            for component in resolution.components
        }
        dates = sorted({day for series in component_series.values() for day in series})
        result: list[tuple[dt.date, Decimal | None, str]] = []
        for day in dates:
            if any(day not in series for series in component_series.values()):
                result.append((day, None, "UNAVAILABLE"))
                continue
            value = sum(
                (
                    component_series[component.index_id][day] * component.weight
                    for component in resolution.components
                ),
                Decimal(0),
            )
            result.append((day, value, "AVAILABLE"))
        return tuple(result)

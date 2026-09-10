import datetime as dt
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import (
    BenchmarkComponentPoint,
    BenchmarkIndexObservationVersion,
    BenchmarkResolution,
    BenchmarkResolutionSegment,
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
_HISTORY_MAPPING_SQL = text("""
    SELECT id, benchmark_id, share_class_id, classification_code,
           mapping_source, mapping_version, valid_from, valid_to, available_at
    FROM market.benchmark_mapping
    WHERE available_at <= :visible_until
      AND valid_from < :range_end
      AND (valid_to IS NULL OR valid_to > :range_start)
      AND (share_class_id = :share_class_id OR classification_code = :classification_code)
    ORDER BY valid_from, available_at, id
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
        components, index_types = self._components(row["benchmark_id"])
        if not self._components_are_valid(components, index_types, classification_code):
            return BenchmarkResolution.unavailable()
        return BenchmarkResolution(
            row["benchmark_id"],
            components,
            row["mapping_source"],
            row["mapping_version"],
            "AVAILABLE",
        )

    def resolve_history(
        self,
        share_class_id: int,
        classification_code: str,
        date_from: dt.date,
        date_to: dt.date,
    ) -> tuple[BenchmarkResolutionSegment, ...]:
        if date_to < date_from:
            return ()
        range_end = date_to + dt.timedelta(days=1)
        mappings = (
            self._session.execute(
                _HISTORY_MAPPING_SQL,
                {
                    "share_class_id": share_class_id,
                    "classification_code": classification_code,
                    "range_start": date_from,
                    "range_end": range_end,
                    "visible_until": self._visible_until,
                },
            )
            .mappings()
            .all()
        )
        boundaries = {date_from, range_end}
        for row in mappings:
            boundaries.add(max(date_from, row["valid_from"]))
            boundaries.add(min(range_end, row["valid_to"] or range_end))

        atomic_segments: list[tuple[dt.date, dt.date, RowMapping]] = []
        ordered_boundaries = sorted(boundaries)
        for effective_from, effective_to in zip(
            ordered_boundaries, ordered_boundaries[1:], strict=False
        ):
            candidates = [
                row
                for row in mappings
                if row["valid_from"] <= effective_from
                and (row["valid_to"] is None or row["valid_to"] > effective_from)
            ]
            if not candidates:
                continue
            selected = max(
                candidates,
                key=lambda row: (
                    row["share_class_id"] is not None,
                    row["valid_from"],
                    row["available_at"],
                    row["id"],
                ),
            )
            if atomic_segments and atomic_segments[-1][2]["id"] == selected["id"]:
                previous_from, _previous_to, previous_row = atomic_segments[-1]
                atomic_segments[-1] = (previous_from, effective_to, previous_row)
            else:
                atomic_segments.append((effective_from, effective_to, selected))

        result: list[BenchmarkResolutionSegment] = []
        for effective_from, effective_to, row in atomic_segments:
            components, index_types = self._components(row["benchmark_id"])
            status = (
                "AVAILABLE"
                if self._components_are_valid(components, index_types, classification_code)
                else "BENCHMARK_UNAVAILABLE"
            )
            index_versions = tuple(
                BenchmarkIndexObservationVersion(component.index_id, day, version)
                for component in components
                for day, _value, version, _quality in self.index_series(
                    component.index_id,
                    effective_from,
                    effective_to - dt.timedelta(days=1),
                )
            )
            result.append(
                BenchmarkResolutionSegment(
                    effective_from=effective_from,
                    effective_to=effective_to,
                    benchmark_id=row["benchmark_id"],
                    components=components,
                    mapping_source=row["mapping_source"],
                    mapping_version=row["mapping_version"],
                    index_versions=index_versions,
                    status=status,
                )
            )
        return tuple(result)

    def _components(
        self, benchmark_id: int
    ) -> tuple[tuple[BenchmarkComponentPoint, ...], frozenset[str]]:
        rows = (
            self._session.execute(_COMPONENT_SQL, {"benchmark_id": benchmark_id})
            .mappings()
            .all()
        )
        return (
            tuple(BenchmarkComponentPoint(row["index_id"], row["weight"]) for row in rows),
            frozenset(row["index_type"] for row in rows),
        )

    @staticmethod
    def _components_are_valid(
        components: tuple[BenchmarkComponentPoint, ...],
        index_types: frozenset[str],
        classification_code: str,
    ) -> bool:
        if not components or sum((item.weight for item in components), Decimal(0)) != Decimal(1):
            return False
        required_types = {
            "ACTIVE_EQUITY": {"TOTAL_RETURN"},
            "PASSIVE_EQUITY": {"TOTAL_RETURN"},
            "BOND": {"FULL_PRICE"},
            "HYBRID": {"TOTAL_RETURN", "FULL_PRICE"},
        }.get(classification_code)
        return required_types is None or index_types == required_types

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

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
    SELECT index_id, weight FROM market.benchmark_component
    WHERE benchmark_id = :benchmark_id ORDER BY index_id
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
        components = tuple(
            BenchmarkComponentPoint(r["index_id"], r["weight"])
            for r in self._session.execute(_COMPONENT_SQL, {"benchmark_id": row["benchmark_id"]})
            .mappings()
            .all()
        )
        if not components or sum((c.weight for c in components), Decimal(0)) != Decimal(1):
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

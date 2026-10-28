import datetime as dt
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import ClassificationPoint
from fip.services.data_service.classification import ClassificationSnapshot, project_legacy
from fip.services.data_service.classification.service import verified_tag_rejections
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationHistory,
    FundClassificationRevision,
)

CLASSIFICATION_SCHEME = "FIP_INTERNAL_L2"


def _timestamp(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).isoformat()


_CURRENT_SQL = text("""
    SELECT classification_code, valid_from, availability_quality
    FROM fund.fund_classification_history
    WHERE fund_id = :fund_id
      AND classification_scheme = :classification_scheme
      AND available_at <= :visible_until
      AND valid_from <= :effective_at
      AND (valid_to IS NULL OR valid_to > :effective_at)
    ORDER BY valid_from DESC, available_at DESC, id DESC
    LIMIT 1
""")


class SqlClassificationPitRepository:
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        self._session = session
        self._visible_until = visible_until

    def visible_revision(self, fund_id: int) -> FundClassificationRevision | None:
        return self._session.scalar(
            select(FundClassificationRevision)
            .where(
                FundClassificationRevision.fund_id == fund_id,
                FundClassificationRevision.scheme == "FIP_CLASSIFICATION_V1",
                FundClassificationRevision.available_at <= self._visible_until,
            )
            .order_by(FundClassificationRevision.version.desc())
            .limit(1)
        )

    def snapshot(
        self, fund_id: int, *, effective_at: dt.date | None = None
    ) -> dict[str, Any] | None:
        revision = self.visible_revision(fund_id)
        if revision is None:
            return None
        day = effective_at or self._visible_until.date()
        row = self._session.scalar(
            select(FundClassificationHistory).where(
                FundClassificationHistory.revision_id == revision.id,
                FundClassificationHistory.valid_from <= day,
                (FundClassificationHistory.valid_to.is_(None))
                | (FundClassificationHistory.valid_to > day),
            )
        )
        if row is None:
            return None
        return {
            **(row.classification_result or {}),
            "revision_id": revision.id,
            "version": revision.version,
            "valid_from": row.valid_from.isoformat(),
            "valid_to": row.valid_to.isoformat() if row.valid_to else None,
            "available_at": _timestamp(revision.available_at),
            "classified_at": _timestamp(revision.classified_at),
            "availability_quality": revision.availability_quality,
            "published_at": _timestamp(revision.published_at) if revision.published_at else None,
            "provider_available_at": _timestamp(revision.provider_available_at)
            if revision.provider_available_at
            else None,
            "ingested_at": _timestamp(revision.ingested_at),
            "source_summary": sorted(
                {
                    e["source"]
                    for d in (row.classification_result or {}).values()
                    if isinstance(d, dict)
                    for e in d.get("evidence", [])
                }
            ),
            "trading_eligibility": row.trading_eligibility or {"status": "UNKNOWN"},
        }

    def history(self, fund_id: int) -> list[dict[str, Any]]:
        revisions = self._session.scalars(
            select(FundClassificationRevision)
            .where(
                FundClassificationRevision.fund_id == fund_id,
                FundClassificationRevision.scheme == "FIP_CLASSIFICATION_V1",
                FundClassificationRevision.available_at <= self._visible_until,
            )
            .order_by(FundClassificationRevision.version.desc())
        ).all()
        return [
            {
                "revision_id": r.id,
                "version": r.version,
                "rule_version": r.rule_version,
                "enum_version": r.enum_version,
                "available_at": _timestamp(r.available_at),
                "classified_at": _timestamp(r.classified_at),
                "published_at": _timestamp(r.published_at) if r.published_at else None,
                "provider_available_at": _timestamp(r.provider_available_at)
                if r.provider_available_at
                else None,
                "ingested_at": _timestamp(r.ingested_at),
                "availability_quality": r.availability_quality,
                "actor": r.actor,
                "reason": r.reason,
                "reviewed": r.reviewed,
                "intervals": [
                    {
                        "valid_from": i.valid_from.isoformat(),
                        "valid_to": i.valid_to.isoformat() if i.valid_to else None,
                        "classification": i.classification_result,
                        "trading_eligibility": i.trading_eligibility,
                    }
                    for i in self._session.scalars(
                        select(FundClassificationHistory)
                        .where(FundClassificationHistory.revision_id == r.id)
                        .order_by(FundClassificationHistory.valid_from)
                    )
                ],
            }
            for r in revisions
        ]

    def current(self, fund_id: int) -> ClassificationPoint | None:
        revision = self.visible_revision(fund_id)
        if revision is not None:
            result = self.snapshot(fund_id)
            if result is None:
                return None
            snapshot = ClassificationSnapshot.model_validate(
                {k: v for k, v in result.items() if k in ClassificationSnapshot.model_fields}
            )
            product = self._session.get(Fund, fund_id)
            projection = project_legacy(
                snapshot,
                grouping_confirmed=(product is not None and product.grouping_status == "CONFIRMED"),
                verified_tag_rejections=verified_tag_rejections(
                    self._session,
                    fund_id,
                    snapshot,
                    visible_until=self._visible_until,
                    revision_id=revision.id,
                    valid_from=dt.date.fromisoformat(result["valid_from"]),
                    valid_to=dt.date.fromisoformat(result["valid_to"])
                    if result["valid_to"]
                    else None,
                ),
            )
            return ClassificationPoint(
                projection.value or "UNKNOWN",
                dt.date.fromisoformat(result["valid_from"]),
                revision.availability_quality,
                revision.id,
                revision.version,
                projection.mapping_version,
                projection.reason,
            )
        row = (
            self._session.execute(
                _CURRENT_SQL,
                {
                    "fund_id": fund_id,
                    "classification_scheme": CLASSIFICATION_SCHEME,
                    "visible_until": self._visible_until,
                    "effective_at": self._visible_until.date(),
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return ClassificationPoint(
            row["classification_code"],
            row["valid_from"],
            row["availability_quality"],
        )

"""Transactional classification revisions and review, shared by HTTP and CLI."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.data_service.classification.legacy import project_legacy
from fip.services.data_service.classification.models import (
    DIMENSIONS,
    ClassificationSnapshot,
    DimensionResult,
    Evidence,
)
from fip.services.data_service.classification.rules import CATALOG
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationHistory,
    FundClassificationReviewCase,
    FundClassificationRevision,
)
from fip.services.data_service.models.governance import AuditLog

SCHEME = "FIP_CLASSIFICATION_V1"
Interval = tuple[dt.date, dt.date | None, ClassificationSnapshot]
StoredInterval = tuple[dt.date, dt.date | None, ClassificationSnapshot, dict[str, object]]


class ClassificationConflict(ValueError):
    """The submitted baseline is stale or the review is already consumed."""


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Literal["CONFIRM", "OVERRIDE", "REJECT"]
    value: str | tuple[str, ...] = "UNKNOWN"
    evidence: tuple[Evidence, ...] = ()


def _canonical(value: object) -> object:
    """Retrieval/classification timestamps and storage IDs are not semantic changes."""
    if isinstance(value, dict):
        return {
            k: _canonical(v) for k, v in value.items() if k not in {"classified_at", "payload_ref"}
        }
    if isinstance(value, list):
        return sorted((_canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def _hash(intervals: Sequence[StoredInterval]) -> str:
    content = [
        (a.isoformat(), b.isoformat() if b else None, _canonical(s.to_dict()), _canonical(trading))
        for a, b, s, trading in intervals
    ]
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def _validate_snapshot(snapshot: ClassificationSnapshot) -> None:
    for name in DIMENSIONS:
        dim: DimensionResult = getattr(snapshot, name)
        values = (dim.value,) if isinstance(dim.value, str) else dim.value
        if not values or not set(values) <= set(CATALOG[name]):
            raise ValueError(f"invalid {name} values")
        if len(set(values)) != len(values) or ("UNKNOWN" in values and len(values) != 1):
            raise ValueError(f"invalid {name} labels")
        if name not in {"geography", "market_attributes"} and len(values) != 1:
            raise ValueError(f"{name} is single valued")
        if dim.status != "CONFIRMED" and values != ("UNKNOWN",):
            raise ValueError(f"unconfirmed {name} cannot contain final values")
        if dim.status == "CONFIRMED" and (values == ("UNKNOWN",) or not dim.evidence):
            raise ValueError(f"confirmed {name} requires evidence and a known value")
        if dim.status == "CONFIRMED" and not any(e.source != "NAME" for e in dim.evidence):
            raise ValueError(f"confirmed {name} requires non-name evidence")
        if not set(dim.candidates) <= set(CATALOG[name]):
            raise ValueError(f"invalid {name} candidates")


class ClassificationService:
    """Never commits: caller owns the transaction including raw ingestion and audit."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_product(self, fund_id: int) -> None:
        product = self.session.scalar(select(Fund).where(Fund.id == fund_id).with_for_update())
        if product is None:
            raise LookupError(f"fund {fund_id} not found")

    def latest(self, fund_id: int) -> FundClassificationRevision | None:
        return self.session.scalar(
            select(FundClassificationRevision)
            .where(
                FundClassificationRevision.fund_id == fund_id,
                FundClassificationRevision.scheme == SCHEME,
            )
            .order_by(FundClassificationRevision.version.desc())
            .limit(1)
        )

    def intervals(self, revision_id: int) -> list[StoredInterval]:
        rows = self.session.scalars(
            select(FundClassificationHistory)
            .where(
                FundClassificationHistory.revision_id == revision_id,
            )
            .order_by(FundClassificationHistory.valid_from)
        ).all()
        return [
            (
                r.valid_from,
                r.valid_to,
                ClassificationSnapshot.model_validate(r.classification_result),
                r.trading_eligibility or {"status": "UNKNOWN"},
            )
            for r in rows
        ]

    def write(
        self,
        fund_id: int,
        snapshot: ClassificationSnapshot,
        *,
        valid_from: dt.date,
        available_at: dt.datetime,
        actor: str,
        reason: str,
        valid_to: dt.date | None = None,
        reviewed: bool = False,
    ) -> FundClassificationRevision:
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason are required")
        if available_at.utcoffset() is None:
            raise ValueError("available_at must include timezone")
        if valid_to is not None and valid_to <= valid_from:
            raise ValueError("invalid interval")
        _validate_snapshot(snapshot)
        self.lock_product(fund_id)
        latest = self.latest(fund_id)
        old = self.intervals(latest.id) if latest else []
        # Cut at both classification and eligibility boundaries, preserving independent facts.
        boundaries = {valid_from}
        if valid_to is not None:
            boundaries.add(valid_to)
        for start, end, _, _ in old:
            boundaries.add(start)
            if end is not None:
                boundaries.add(end)
        points = sorted(boundaries)
        result: list[StoredInterval] = []
        for i, start in enumerate(points):
            end = points[i + 1] if i + 1 < len(points) else None
            prior = next((v for v in old if v[0] <= start and (v[1] is None or start < v[1])), None)
            overridden = valid_from <= start and (valid_to is None or start < valid_to)
            if overridden:
                result.append((start, end, snapshot, prior[3] if prior else {"status": "UNKNOWN"}))
            elif prior:
                result.append((start, end, prior[2], prior[3]))
        return self.replace_intervals(
            fund_id,
            result,
            available_at=available_at,
            actor=actor,
            reason=reason,
            reviewed=reviewed,
        )

    def replace_intervals(
        self,
        fund_id: int,
        intervals: Sequence[Interval | StoredInterval],
        *,
        available_at: dt.datetime,
        actor: str,
        reason: str,
        reviewed: bool = False,
    ) -> FundClassificationRevision:
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason are required")
        if available_at.tzinfo is None:
            raise ValueError("available_at must include timezone")
        self.lock_product(fund_id)
        ordered: list[StoredInterval] = sorted(
            [(v[0], v[1], v[2], v[3] if len(v) == 4 else {"status": "UNKNOWN"}) for v in intervals],
            key=lambda v: v[0],
        )
        if not ordered:
            raise ValueError("revision must contain intervals")
        for i, (start, end, snapshot, _) in enumerate(ordered):
            _validate_snapshot(snapshot)
            if end is not None and end <= start:
                raise ValueError("invalid interval")
            previous_end = ordered[i - 1][1] if i else start
            if i and (previous_end is None or previous_end > start):
                raise ValueError("overlapping intervals")
        merged: list[StoredInterval] = []
        for start, end, value, trading in ordered:
            if (
                merged
                and merged[-1][1] == start
                and _canonical(merged[-1][2].to_dict()) == _canonical(value.to_dict())
                and merged[-1][3] == trading
            ):
                prev = merged[-1]
                merged[-1] = (prev[0], end, prev[2], trading)
            else:
                merged.append((start, end, value, trading))
        ordered = merged
        digest = _hash(ordered)
        previous = self.latest(fund_id)
        if previous is not None and previous.content_hash == digest and not reviewed:
            return previous
        if previous is not None and previous.reviewed and not reviewed:
            prior = self.intervals(previous.id)
            for start, end, value, trading in ordered:
                old = next(
                    (v for v in prior if v[0] <= start and (v[1] is None or start < v[1])), None
                )
                if (
                    old
                    and _canonical(old[2].to_dict()) == _canonical(value.to_dict())
                    and old[3] == trading
                ):
                    continue
                differing = [
                    name
                    for name in DIMENSIONS
                    if old is None
                    or _canonical(getattr(old[2], name).model_dump(mode="json"))
                    != _canonical(getattr(value, name).model_dump(mode="json"))
                ]
                for name in differing or ["asset_class"]:
                    self._case(
                        previous,
                        f"REFRESH:{digest}:{start}:{name}",
                        "NEW_EVIDENCE_AFTER_REVIEW",
                        {
                            "valid_from": start.isoformat(),
                            "valid_to": end.isoformat() if end else None,
                            "dimension": name,
                            "intervals": [
                                [
                                    start.isoformat(),
                                    end.isoformat() if end else None,
                                    value.to_dict(),
                                ]
                            ],
                        },
                        available_at,
                    )
            return previous
        snapshot = ordered[-1][2]
        revision = FundClassificationRevision(
            fund_id=fund_id,
            scheme=SCHEME,
            version=previous.version + 1 if previous else 1,
            rule_version=snapshot.rule_version,
            enum_version=snapshot.enum_version,
            content_hash=digest,
            classified_at=available_at,
            available_at=available_at,
            ingested_at=available_at,
            published_at=None,
            provider_available_at=None,
            availability_quality="INFERRED",
            reason=reason,
            actor=actor,
            reviewed=reviewed,
        )
        self.session.add(revision)
        self.session.flush()
        carry: list[FundClassificationReviewCase] = []
        if previous:
            for case in self.session.scalars(
                select(FundClassificationReviewCase).where(
                    FundClassificationReviewCase.fund_id == fund_id,
                    FundClassificationReviewCase.status == "PENDING",
                )
            ):
                if case.issue_type in {"NEW_EVIDENCE_AFTER_REVIEW", "GROUPING_UNCONFIRMED"}:
                    carry.append(case)
                case.status = "SUPERSEDED"
                case.resolved_at = available_at
        for start, end, value, trading in ordered:
            projection = project_legacy(value, grouping_confirmed=True)
            self.session.add(
                FundClassificationHistory(
                    fund_id=fund_id,
                    classification_scheme=SCHEME,
                    classification_code=projection.value or "UNKNOWN",
                    revision_id=revision.id,
                    classification_result=value.to_dict(),
                    trading_eligibility=trading,
                    valid_from=start,
                    valid_to=end,
                    available_at=available_at,
                    ingested_at=available_at,
                    published_at=None,
                    provider_available_at=None,
                    availability_quality="INFERRED",
                )
            )
            for name in DIMENSIONS:
                dimension = getattr(value, name)
                if dimension.status != "CONFIRMED":
                    self._case(
                        revision,
                        f"{start}:{name}",
                        dimension.status,
                        {
                            "dimension": name,
                            "valid_from": start.isoformat(),
                            "result": dimension.model_dump(mode="json"),
                        },
                        available_at,
                    )
        for prior_case in carry:
            self._case(
                revision,
                prior_case.issue_key,
                prior_case.issue_type,
                dict(prior_case.details),
                available_at,
            )
        self.session.add(
            AuditLog(
                resource_type="fund_classification",
                resource_id=str(fund_id),
                action="REVISE",
                operator=actor,
                detail={"reason": reason, "revision_id": revision.id, "version": revision.version},
            )
        )
        self.session.flush()
        return revision

    def _case(
        self,
        revision: FundClassificationRevision,
        key: str,
        issue: str,
        details: dict[str, object],
        at: dt.datetime,
    ) -> FundClassificationReviewCase:
        existing = self.session.scalar(
            select(FundClassificationReviewCase).where(
                FundClassificationReviewCase.fund_id == revision.fund_id,
                FundClassificationReviewCase.revision_id == revision.id,
                FundClassificationReviewCase.issue_key == key,
            )
        )
        if existing is not None:
            return existing
        case = FundClassificationReviewCase(
            fund_id=revision.fund_id,
            revision_id=revision.id,
            issue_key=key,
            issue_type=issue,
            status="PENDING",
            details=details,
            created_at=at,
        )
        self.session.add(case)
        self.session.flush()
        return case

    def review(
        self,
        case_id: int,
        *,
        expected_revision: int,
        decisions: Mapping[str, ReviewDecision],
        actor: str,
        reason: str,
        can_review: bool,
        reviewed_at: dt.datetime | None = None,
    ) -> FundClassificationRevision:
        if not can_review:
            raise PermissionError("classification review capability required")
        case = self.session.get(FundClassificationReviewCase, case_id)
        if case is None:
            raise LookupError(f"review {case_id} not found")
        self.lock_product(case.fund_id)
        self.session.refresh(case)
        latest = self.latest(case.fund_id)
        if (
            latest is None
            or latest.id != expected_revision
            or case.revision_id != expected_revision
            or case.status != "PENDING"
        ):
            raise ClassificationConflict("Classification revision changed; reload before reviewing")
        if not decisions or not set(decisions) <= set(DIMENSIONS):
            raise ValueError("dimension decisions are required")
        at = reviewed_at or dt.datetime.now(dt.UTC)
        intervals = self.intervals(latest.id)
        target_start = case.details.get("valid_from")
        if not isinstance(target_start, str):
            raise ValueError("This case needs an authorized product identity workflow")
        target = dt.date.fromisoformat(target_start)
        base = next(
            (v for v in intervals if v[0] <= target and (v[1] is None or target < v[1])), None
        )
        snapshot = (
            base[2]
            if base
            else ClassificationSnapshot.model_validate(
                {
                    name: DimensionResult(
                        status="UNKNOWN",
                        value=("UNKNOWN",)
                        if name in {"geography", "market_attributes"}
                        else "UNKNOWN",
                    )
                    for name in DIMENSIONS
                }
            )
        )
        target_end = case.details.get("valid_to")
        end = (
            dt.date.fromisoformat(target_end)
            if isinstance(target_end, str)
            else (None if "valid_to" in case.details else base[1] if base else None)
        )
        incoming_intervals = case.details.get("intervals", [])
        incoming = (
            ClassificationSnapshot.model_validate(incoming_intervals[0][2])
            if incoming_intervals
            else None
        )
        updates: dict[str, object] = {}
        for name, decision in decisions.items():
            original: DimensionResult = getattr(snapshot, name)
            if not decision.evidence:
                raise ValueError("review decisions require evidence")
            retained = original.evidence + (getattr(incoming, name).evidence if incoming else ())
            if decision.action == "REJECT":
                dim = DimensionResult(
                    status="UNKNOWN",
                    value=("UNKNOWN",) if name in {"geography", "market_attributes"} else "UNKNOWN",
                    evidence=retained + decision.evidence,
                )
            else:
                values = (decision.value,) if isinstance(decision.value, str) else decision.value
                if decision.action == "CONFIRM" and not set(values) <= set(original.candidates):
                    raise ValueError("confirmation must select a baseline candidate")
                dim = DimensionResult(
                    status="CONFIRMED",
                    value=tuple(sorted(set(values)))
                    if name in {"geography", "market_attributes"}
                    else decision.value,
                    evidence=retained + decision.evidence,
                )
            updates[name] = dim
        result = ClassificationSnapshot.model_validate({**snapshot.model_dump(), **updates})
        result = result.model_copy(
            update={
                "review_items": tuple(
                    f"{name}:{getattr(result, name).status}"
                    for name in DIMENSIONS
                    if getattr(result, name).status != "CONFIRMED"
                )
            }
        )
        revision = self.write(
            case.fund_id,
            result,
            valid_from=target,
            valid_to=end,
            available_at=at,
            actor=actor,
            reason=reason,
            reviewed=True,
        )
        # Persistent incoming proposals are rebased, except dimensions explicitly decided here.
        for rebased in self.session.scalars(
            select(FundClassificationReviewCase).where(
                FundClassificationReviewCase.revision_id == revision.id,
                FundClassificationReviewCase.status == "PENDING",
                FundClassificationReviewCase.issue_type == "NEW_EVIDENCE_AFTER_REVIEW",
            )
        ):
            if (
                rebased.details.get("valid_from") == target_start
                and rebased.details.get("dimension") in decisions
            ):
                rebased.status = "RESOLVED"
                rebased.resolved_at = at
                rebased.result_revision_id = revision.id
        case.status = "RESOLVED"
        case.resolved_at = at
        case.result_revision_id = revision.id
        self.session.add(
            AuditLog(
                resource_type="fund_classification",
                resource_id=str(case.fund_id),
                action="REVIEW",
                operator=actor,
                detail={
                    "reason": reason,
                    "case_id": case.id,
                    "expected_revision": expected_revision,
                    "decisions": {
                        name: value.model_dump(mode="json") for name, value in decisions.items()
                    },
                    "revision_id": revision.id,
                },
            )
        )
        self.session.flush()
        return revision

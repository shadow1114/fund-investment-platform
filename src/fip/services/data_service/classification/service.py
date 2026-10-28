"""Transactional classification revisions and review, shared by HTTP and CLI."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.services.data_service.classification.legacy import project_legacy
from fip.services.data_service.classification.models import (
    DIMENSIONS,
    CURRENT_ACTIVE_DIMENSIONS,
    CURRENT_CATALOG,
    CURRENT_PAUSED_DIMENSIONS,
    CURRENT_STRATEGY_TAGS,
    ClassificationSnapshot,
    DimensionResult,
    Evidence,
    StrategyTagResult,
)
from fip.services.data_service.classification.rules import CATALOG, HISTORICAL_CATALOG
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationHistory,
    FundClassificationReviewCase,
    FundClassificationRevision,
)
from fip.services.data_service.models.governance import AuditLog

SCHEME = "FIP_CLASSIFICATION"
Interval = tuple[dt.date, dt.date | None, ClassificationSnapshot]
StoredInterval = tuple[dt.date, dt.date | None, ClassificationSnapshot, dict[str, object]]


class ClassificationConflict(ValueError):
    """The submitted baseline is stale or the review is already consumed."""


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Literal["CONFIRM", "OVERRIDE", "REJECT"]
    value: str | tuple[str, ...] = "UNKNOWN"
    evidence: tuple[Evidence, ...] = ()


class StrategyTagDecision(BaseModel):
    """A tag is independently confirmed or rejected, never a strategy enum value."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Literal["CONFIRM", "REJECT"]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class _TagReviewAuthorization:
    fund_id: int
    expected_revision: int
    valid_from: dt.date
    valid_to: dt.date | None
    tags: Mapping[str, StrategyTagResult]
    result_revision: int | None = None


def _range_within(
    start: dt.date, end: dt.date | None, scope_start: dt.date, scope_end: dt.date | None
) -> bool:
    return start >= scope_start and (scope_end is None or end is not None and end <= scope_end)


def _source_identity(item: Evidence) -> dict[str, object] | None:
    locator = item.locator or ""
    if locator.startswith("identity:"):
        try:
            identity, _ = json.JSONDecoder().raw_decode(locator[len("identity:") :])
        except ValueError:
            return None
        if (
            isinstance(identity, dict)
            and all(
                isinstance(identity.get(key), str) and identity[key].strip()
                for key in ("provider", "dataset", "provider_fund_code", "raw_field")
            )
            and identity["raw_field"] == item.raw_field
            and isinstance(identity.get("params"), dict)
        ):
            return identity
    return None


def _observation_key(item: Evidence) -> str:
    identity = _source_identity(item)
    if identity is not None:
        # Row positions change when an upstream list is reordered. Necessary stable
        # row identities belong inside identity, alongside provider/share/params.
        locator = "identity:" + json.dumps(identity, sort_keys=True, ensure_ascii=False)
        return json.dumps([item.source, item.raw_field, locator])
    # An incomplete legacy locator cannot prove source/share equivalence. Preserve
    # distinct immutable records; a new partial refresh may not overwrite them.
    return "legacy:" + item.model_dump_json()


def _observations(snapshot: ClassificationSnapshot) -> tuple[Evidence, ...]:
    if snapshot.observations is not None:
        return snapshot.observations
    results = [getattr(snapshot, name) for name in DIMENSIONS]
    results.extend((snapshot.strategy_tag_results or {}).values())
    raw: dict[str, Evidence] = {}

    def retain(item: Evidence) -> None:
        if item.required_observations:
            for required in item.required_observations:
                retain(required)
        else:
            raw[_observation_key(item)] = item

    for result in results:
        for item in result.evidence:
            retain(item)
    return tuple(raw.values())


def _active_dimensions(snapshot: ClassificationSnapshot) -> tuple[str, ...]:
    return tuple(
        name
        for name in DIMENSIONS
        if getattr(snapshot, name).evaluation_state not in ("PAUSED", "NOT_EVALUATED")
    )


def _changed_tags(old: ClassificationSnapshot, new: ClassificationSnapshot) -> set[str]:
    changed = set()
    for tag in CURRENT_STRATEGY_TAGS:
        prior = (old.strategy_tag_results or {}).get(tag)
        incoming = (new.strategy_tag_results or {}).get(tag)
        if _canonical(prior.model_dump(mode="json") if prior else None) != _canonical(
            incoming.model_dump(mode="json") if incoming else None
        ):
            changed.add(tag)
    return changed


def _carry_paused(
    incoming: ClassificationSnapshot, baseline: ClassificationSnapshot, revision_id: int
) -> ClassificationSnapshot:
    updates = {}
    for name in CURRENT_PAUSED_DIMENSIONS:
        old = getattr(baseline, name)
        if (
            baseline.scheme == SCHEME
            and old.evaluation_state == "NOT_EVALUATED"
            and old.carried_from_revision_id is None
        ):
            updates[name] = old
            continue
        if old.carried_from_revision_id is not None:
            updates[name] = old
            continue
        values = (old.value,) if isinstance(old.value, str) else old.value
        compatible = set((*values, *old.candidates)) <= set(CURRENT_CATALOG[name])
        provenance = {"carried_from_revision_id": revision_id}
        updates[name] = (
            old.model_copy(update={"evaluation_state": "PAUSED", **provenance})
            if compatible
            else DimensionResult(
                status="UNKNOWN",
                evaluation_state="NOT_EVALUATED",
                carried_from_revision_id=revision_id,
            )
        )
    return ClassificationSnapshot.model_validate({**incoming.model_dump(), **updates})


def review_case_is_active(case: FundClassificationReviewCase) -> bool:
    """Paused cases stay PENDING for history; default queues omit them."""
    return case.status == "PENDING" and case.details.get("evaluation_state") != "PAUSED"


def _time_metadata(
    available_at: dt.datetime,
    published_at: dt.datetime | None,
    provider_available_at: dt.datetime | None,
    ingested_at: dt.datetime | None,
    availability_quality: str | None,
) -> dict[str, object]:
    ingested_at = ingested_at or available_at
    for timestamp in (available_at, published_at, provider_available_at, ingested_at):
        if timestamp is not None and timestamp.utcoffset() is None:
            raise ValueError("source timestamps must include timezone")
    quality = "EXACT" if provider_available_at else "DERIVED" if published_at else "INFERRED"
    if availability_quality is not None and availability_quality != quality:
        raise ValueError("availability_quality must match source timestamps")
    if (
        (published_at and provider_available_at and provider_available_at < published_at)
        or (ingested_at < (provider_available_at or published_at or ingested_at))
        or available_at < (provider_available_at or published_at or available_at)
    ):
        raise ValueError("available_at/source timestamps are inconsistent")
    return dict(
        published_at=published_at,
        provider_available_at=provider_available_at,
        ingested_at=ingested_at,
        availability_quality=quality,
    )


def _canonical(value: object) -> object:
    """Retrieval/classification timestamps and storage IDs are not semantic changes."""
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if k in {
                "classified_at",
                "payload_ref",
                "published_at",
                "provider_available_at",
                "ingested_at",
            }:
                continue
            if k == "locator" and isinstance(v, str) and v.startswith("identity:"):
                try:
                    v, _ = json.JSONDecoder().raw_decode(v[len("identity:") :])
                except ValueError:
                    pass
            result[k] = _canonical(v)
        return result
    if isinstance(value, list):
        return sorted((_canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def _hash(intervals: Sequence[StoredInterval]) -> str:
    content = [
        (a.isoformat(), b.isoformat() if b else None, _canonical(s.to_dict()), _canonical(trading))
        for a, b, s, trading in sorted(intervals, key=lambda interval: interval[0])
    ]
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def _validate_snapshot(snapshot: ClassificationSnapshot) -> None:
    catalog = (
        CURRENT_CATALOG
        if snapshot.scheme == "FIP_CLASSIFICATION"
        else HISTORICAL_CATALOG
    )
    for name in DIMENSIONS:
        dim: DimensionResult = getattr(snapshot, name)
        values = (dim.value,) if isinstance(dim.value, str) else dim.value
        if not values or not set(values) <= set(catalog[name]):
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
        if not set(dim.candidates) <= set(catalog[name]):
            raise ValueError(f"invalid {name} candidates")


def _assert_observations_visible(snapshot: ClassificationSnapshot, at: dt.datetime) -> None:
    def check(item: Evidence) -> None:
        if item.classified_at.utcoffset() is None or item.classified_at > at:
            raise ValueError("available_at cannot predate classification evidence")
        for required in item.required_observations or ():
            check(required)

    for item in snapshot.observations or ():
        check(item)
    for result in [
        *(getattr(snapshot, name) for name in DIMENSIONS),
        *(snapshot.strategy_tag_results or {}).values(),
    ]:
        for item in result.evidence:
            check(item)


def verified_tag_rejections(
    session: Session,
    fund_id: int,
    snapshot: ClassificationSnapshot,
    *,
    visible_until: dt.datetime,
    revision_id: int,
    valid_from: dt.date,
    valid_to: dt.date | None,
) -> frozenset[str]:
    """Manual admission requires an actual matching review, never a JSON flag alone."""
    requested = {
        tag: result
        for tag, result in (snapshot.strategy_tag_results or {}).items()
        if result.manual_action == "REJECT"
    }
    if not requested:
        return frozenset()
    verified = set()
    audits = session.scalars(
        select(AuditLog).where(
            AuditLog.resource_type == "fund_classification",
            AuditLog.resource_id == str(fund_id),
            AuditLog.action == "REVIEW",
            AuditLog.created_at <= visible_until,
        )
    )
    for audit in audits:
        detail = audit.detail or {}
        audit_revision_id = detail.get("revision_id")
        revision = (
            session.get(FundClassificationRevision, audit_revision_id)
            if isinstance(audit_revision_id, int)
            else None
        )
        case_id = detail.get("case_id")
        case = (
            session.get(FundClassificationReviewCase, case_id) if isinstance(case_id, int) else None
        )
        if (
            revision is None
            or revision.id != revision_id
            or not revision.reviewed
            or revision.fund_id != fund_id
            or revision.available_at > visible_until
            or revision.scheme != snapshot.scheme
            or case is None
            or case.fund_id != fund_id
            or case.revision_id != detail.get("expected_revision")
            or not audit.operator.strip()
            or not str(detail.get("reason", "")).strip()
        ):
            continue
        # Copying a tag is not reviewed interval/revision lineage. Only the exact
        # result revision and intervals contained in its explicit review range
        # inherit admission, including trading/eligibility splits inside it.
        try:
            scope_start = dt.date.fromisoformat(detail["valid_from"])
            scope_end = (
                dt.date.fromisoformat(detail["valid_to"])
                if detail["valid_to"] is not None
                else None
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (scope_end is not None and scope_end <= scope_start) or not _range_within(
            valid_from, valid_to, scope_start, scope_end
        ):
            continue
        result_tags = detail.get("result_tag_results") or {}
        decisions = detail.get("tag_decisions") or {}
        for tag, result in requested.items():
            if (
                decisions.get(tag, {}).get("action") == "REJECT"
                and decisions.get(tag, {}).get("evidence")
                and result_tags.get(tag) == result.model_dump(mode="json")
            ):
                verified.add(tag)
    return frozenset(verified)


class ClassificationService:
    """Never commits: caller owns the transaction including raw ingestion and audit."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._authorized_tag_rejections: _TagReviewAuthorization | None = None

    def lock_product(self, fund_id: int) -> None:
        product = self.session.scalar(select(Fund).where(Fund.id == fund_id).with_for_update())
        if product is None:
            raise LookupError(f"fund {fund_id} not found")

    def latest(
        self, fund_id: int, *, available_at: dt.datetime | None = None
    ) -> FundClassificationRevision | None:
        filters = [
            FundClassificationRevision.fund_id == fund_id,
            FundClassificationRevision.scheme == SCHEME,
        ]
        order = [FundClassificationRevision.version.desc()]
        if available_at is not None:
            if available_at.utcoffset() is None:
                raise ValueError("available_at must include timezone")
            filters.append(FundClassificationRevision.available_at <= available_at)
        return self.session.scalar(
            select(FundClassificationRevision).where(*filters).order_by(*order).limit(1)
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

    def active_review_cases(self, fund_id: int | None = None) -> list[FundClassificationReviewCase]:
        query = (
            select(FundClassificationReviewCase)
            .where(FundClassificationReviewCase.status == "PENDING")
            .order_by(FundClassificationReviewCase.id)
        )
        if fund_id is not None:
            query = query.where(FundClassificationReviewCase.fund_id == fund_id)
        return [case for case in self.session.scalars(query) if review_case_is_active(case)]

    def _mark_paused_cases(self, fund_id: int) -> None:
        for case in self.active_review_cases(fund_id):
            scope = case.details.get("source_dimensions") or [case.details.get("dimension")]
            if any(name in CURRENT_PAUSED_DIMENSIONS for name in scope):
                active = [
                    name
                    for name in scope
                    if name in CURRENT_ACTIVE_DIMENSIONS or str(name).startswith("strategy_tags.")
                ]
                case.details = {
                    **case.details,
                    "source_dimensions": scope,
                    "active_scope": active,
                    "evaluation_state": "EVALUATED" if active else "PAUSED",
                }

    def refresh(
        self,
        fund_id: int,
        evidence: Sequence[Evidence],
        *,
        available_at: dt.datetime,
        actor: str,
        reason: str,
        valid_from: dt.date | None = None,
        diagnostics: Sequence[str] = (),
        published_at: dt.datetime | None = None,
        provider_available_at: dt.datetime | None = None,
        ingested_at: dt.datetime | None = None,
        availability_quality: str | None = None,
    ) -> FundClassificationRevision:
        """Replay only saved raw observations. Callers resolve product/share membership.

        An omitted observation is retained; explicit empty replaces only its stable
        identity. Failed sources supply diagnostics and no replacement evidence.
        """
        from .policy import load_policy
        from .rules import classify

        if (
            available_at.utcoffset() is None
            or any(
                item.classified_at.utcoffset() is None or item.classified_at > available_at
                for item in evidence
            )
            or (ingested_at is not None and available_at < ingested_at)
        ):
            raise ValueError("available_at cannot predate newly collected evidence")
        if any(_source_identity(item) is None for item in evidence):
            raise ValueError("refresh requires stable provider/share observation identity")
        self.lock_product(fund_id)
        previous = self.latest(fund_id)
        target = valid_from or available_at.date()
        baseline = (
            next(
                (
                    v[2]
                    for v in self.intervals(previous.id)
                    if v[0] <= target and (v[1] is None or target < v[1])
                ),
                None,
            )
            if previous
            else None
        )
        retained = (
            {_observation_key(item): item for item in _observations(baseline)} if baseline else {}
        )
        # Pending proposals carry raw observations that have not replaced the manual
        # baseline. Use them for the next partial refresh rather than losing them.
        if previous:
            for case in self.active_review_cases(fund_id):
                start = case.details.get("valid_from")
                end = case.details.get("valid_to")
                if (
                    case.revision_id != previous.id
                    or not isinstance(start, str)
                    or dt.date.fromisoformat(start) > target
                    or isinstance(end, str)
                    and target >= dt.date.fromisoformat(end)
                ):
                    continue
                proposal = case.details.get("intervals", [])
                if proposal:
                    for item in _observations(
                        ClassificationSnapshot.model_validate(proposal[0][2])
                    ):
                        retained[_observation_key(item)] = item
        for item in evidence:
            if item.required_observations:
                raise ValueError("refresh requires raw observations, not derived assertions")
            retained[_observation_key(item)] = item
        raw = tuple(retained.values())
        result = classify(raw, classified_at=available_at, policy=load_policy())
        result = result.model_copy(
            update={"observations": raw, "source_diagnostics": tuple(sorted(set(diagnostics)))}
        )
        if baseline is not None and previous is not None:
            result = _carry_paused(result, baseline, previous.id)
        return self.write(
            fund_id,
            result,
            valid_from=target,
            available_at=available_at,
            actor=actor,
            reason=reason,
            published_at=published_at,
            provider_available_at=provider_available_at,
            ingested_at=ingested_at,
            availability_quality=availability_quality,
        )

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
        published_at: dt.datetime | None = None,
        provider_available_at: dt.datetime | None = None,
        ingested_at: dt.datetime | None = None,
        availability_quality: str | None = None,
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
            published_at=published_at,
            provider_available_at=provider_available_at,
            ingested_at=ingested_at,
            availability_quality=availability_quality,
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
        published_at: dt.datetime | None = None,
        provider_available_at: dt.datetime | None = None,
        ingested_at: dt.datetime | None = None,
        availability_quality: str | None = None,
    ) -> FundClassificationRevision:
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason are required")
        if available_at.tzinfo is None:
            raise ValueError("available_at must include timezone")
        time_metadata = _time_metadata(
            available_at, published_at, provider_available_at, ingested_at, availability_quality
        )
        self.lock_product(fund_id)
        previous = self.latest(fund_id)
        prior = self.intervals(previous.id) if previous else []
        ordered: list[StoredInterval] = sorted(
            [(v[0], v[1], v[2], v[3] if len(v) == 4 else {"status": "UNKNOWN"}) for v in intervals],
            key=lambda v: v[0],
        )
        if not ordered:
            raise ValueError("revision must contain intervals")
        carried: list[StoredInterval] = []
        for start, end, value, trading in ordered:
            if value.scheme != SCHEME or previous is None:
                carried.append((start, end, value, trading))
                continue
            boundaries = {start}
            for old_start, old_end, _, _ in prior:
                for point in (old_start, old_end):
                    if point is not None and start < point and (end is None or point < end):
                        boundaries.add(point)
            points = sorted(boundaries)
            for index, point in enumerate(points):
                stop = points[index + 1] if index + 1 < len(points) else end
                baseline = next(
                    (v[2] for v in prior if v[0] <= point and (v[1] is None or point < v[1])), None
                )
                carried.append(
                    (
                        point,
                        stop,
                        _carry_paused(value, baseline, previous.id) if baseline else value,
                        trading,
                    )
                )
        ordered = carried
        for i, (start, end, snapshot, _) in enumerate(ordered):
            _validate_snapshot(snapshot)
            if snapshot.scheme == SCHEME:
                _assert_observations_visible(snapshot, available_at)
            if end is not None and end <= start:
                raise ValueError("invalid interval")
            previous_end = ordered[i - 1][1] if i else start
            if i and (previous_end is None or previous_end > start):
                raise ValueError("overlapping intervals")
        merged: list[StoredInterval] = []
        authorization = self._authorized_tag_rejections
        review_boundaries = (
            {authorization.valid_from, authorization.valid_to}
            if authorization is not None
            and authorization.fund_id == fund_id
            and previous is not None
            and authorization.expected_revision == previous.id
            else set()
        )
        for start, end, value, trading in ordered:
            if (
                merged
                and merged[-1][1] == start
                and start not in review_boundaries
                and _canonical(merged[-1][2].to_dict()) == _canonical(value.to_dict())
                and merged[-1][3] == trading
            ):
                prev = merged[-1]
                merged[-1] = (prev[0], end, prev[2], trading)
            else:
                merged.append((start, end, value, trading))
        ordered = merged
        digest = _hash(ordered)
        if any(value.scheme == SCHEME for _, _, value, _ in ordered):
            self._mark_paused_cases(fund_id)
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
                    for name in _active_dimensions(value)
                    if old is None
                    or _canonical(getattr(old[2], name).model_dump(mode="json"))
                    != _canonical(getattr(value, name).model_dump(mode="json"))
                ]
                if old is not None:
                    differing.extend(
                        f"strategy_tags.{tag}" for tag in sorted(_changed_tags(old[2], value))
                    )
                for name in differing or ["asset_class"]:
                    self._case(
                        previous,
                        f"REFRESH:{digest}:{start}:{name}",
                        "NEW_EVIDENCE_AFTER_REVIEW",
                        {
                            "valid_from": start.isoformat(),
                            "valid_to": end.isoformat() if end else None,
                            "dimension": name,
                            "changed_scope": differing,
                            "source_dimensions": differing,
                            "baseline": old[2].to_dict() if old else None,
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
            content_hash=digest,
            classified_at=available_at,
            available_at=available_at,
            **time_metadata,
            reason=reason,
            actor=actor,
            reviewed=reviewed,
        )
        self.session.add(revision)
        self.session.flush()
        authorization = self._authorized_tag_rejections
        if (
            authorization is not None
            and authorization.result_revision is None
            and authorization.fund_id == fund_id
            and previous is not None
            and authorization.expected_revision == previous.id
        ):
            self._authorized_tag_rejections = replace(authorization, result_revision=revision.id)
        carry: list[FundClassificationReviewCase] = []
        if previous:
            for case in self.session.scalars(
                select(FundClassificationReviewCase).where(
                    FundClassificationReviewCase.fund_id == fund_id,
                    FundClassificationReviewCase.status == "PENDING",
                )
            ):
                scope = case.details.get("source_dimensions") or [case.details.get("dimension")]
                if snapshot.scheme == SCHEME and any(
                    name in CURRENT_PAUSED_DIMENSIONS for name in scope
                ):
                    active = [
                        name
                        for name in scope
                        if name in CURRENT_ACTIVE_DIMENSIONS or str(name).startswith("strategy_tags.")
                    ]
                    case.details = {
                        **case.details,
                        "source_dimensions": scope,
                        "active_scope": [],
                        "evaluation_state": "PAUSED",
                    }
                    if active and case.issue_type in {
                        "NEW_EVIDENCE_AFTER_REVIEW",
                        "GROUPING_UNCONFIRMED",
                    }:
                        self._case(
                            revision,
                            case.issue_key,
                            case.issue_type,
                            {
                                **case.details,
                                "source_dimensions": active,
                                "historical_source_dimensions": scope,
                                "historical_case_id": case.id,
                                "evaluation_state": "EVALUATED",
                                "active_scope": active,
                            },
                            available_at,
                        )
                    # Preserve the original mixed/paused issue on its revision.
                    continue
                if case.issue_type in {"NEW_EVIDENCE_AFTER_REVIEW", "GROUPING_UNCONFIRMED"}:
                    carry.append(case)
                case.status = "SUPERSEDED"
                case.resolved_at = available_at
        for start, end, value, trading in ordered:
            authorization = self._authorized_tag_rejections
            projection = project_legacy(
                value,
                grouping_confirmed=True,
                verified_tag_rejections=frozenset(
                    tag
                    for tag, result in (authorization.tags.items() if authorization else ())
                    if (value.strategy_tag_results or {}).get(tag) == result
                    and authorization is not None
                    and authorization.fund_id == fund_id
                    and authorization.result_revision == revision.id
                    and _range_within(start, end, authorization.valid_from, authorization.valid_to)
                )
                | verified_tag_rejections(
                    self.session,
                    fund_id,
                    value,
                    visible_until=available_at,
                    revision_id=revision.id,
                    valid_from=start,
                    valid_to=end,
                ),
            )
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
                    **time_metadata,
                )
            )
            for name in _active_dimensions(snapshot):
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
            for tag, result in (value.strategy_tag_results or {}).items():
                if result.status in {"CANDIDATE", "CONFLICT"}:
                    self._case(
                        revision,
                        f"{start}:strategy_tags.{tag}",
                        result.status,
                        {
                            "dimension": f"strategy_tags.{tag}",
                            "valid_from": start.isoformat(),
                            "result": result.model_dump(mode="json"),
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
        tag_decisions: Mapping[str, StrategyTagDecision] | None = None,
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
        if not review_case_is_active(case):
            raise ValueError("paused historical classification cases cannot be reviewed")
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason are required")
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
        return self._review(
            case,
            latest,
            snapshot,
            incoming,
            target=target,
            end=end,
            at=at,
            decisions=decisions,
            tag_decisions=tag_decisions or {},
            actor=actor,
            reason=reason,
        )
        if not decisions or not set(decisions) <= set(DIMENSIONS):
            raise ValueError("dimension decisions are required")
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

    def _review(
        self,
        case: FundClassificationReviewCase,
        latest: FundClassificationRevision,
        baseline: ClassificationSnapshot,
        incoming: ClassificationSnapshot | None,
        *,
        target: dt.date,
        end: dt.date | None,
        at: dt.datetime,
        decisions: Mapping[str, ReviewDecision],
        tag_decisions: Mapping[str, StrategyTagDecision],
        actor: str,
        reason: str,
    ) -> FundClassificationRevision:
        if at.utcoffset() is None:
            raise ValueError("reviewed_at must include timezone")
        if at < max(latest.available_at, case.created_at):
            raise ValueError("reviewed_at cannot predate the baseline or proposal")
        proposed = incoming or baseline
        if proposed.scheme != SCHEME:
            raise ValueError("Review requires a proposal from the current classification rules")
        if set(decisions) != set(CURRENT_ACTIVE_DIMENSIONS) or not set(tag_decisions) <= set(
            CURRENT_STRATEGY_TAGS
        ):
            raise ValueError("Review scope must cover the current active dimensions")
        required_tags = _changed_tags(baseline, proposed)
        dimension = str(case.details.get("dimension", ""))
        if dimension.startswith("strategy_tags."):
            required_tags.add(dimension.split(".", 1)[1])
        if not required_tags <= set(tag_decisions):
            raise ValueError("Review decisions must cover changed strategy tags")
        proposed = _carry_paused(proposed, baseline, latest.id)
        updates: dict[str, object] = {}
        for name, decision in decisions.items():
            original = getattr(baseline, name)
            new = getattr(proposed, name)
            if not decision.evidence:
                raise ValueError("review decisions require evidence")
            values = (decision.value,) if isinstance(decision.value, str) else decision.value
            allowed = set((*original.candidates, *new.candidates))
            for dim in (original, new):
                if dim.status == "CONFIRMED":
                    allowed.update((dim.value,) if isinstance(dim.value, str) else dim.value)
            if decision.action == "CONFIRM" and not set(values) <= allowed:
                raise ValueError("confirmation must select a baseline or incoming candidate")
            updates[name] = DimensionResult(
                status="UNKNOWN" if decision.action == "REJECT" else "CONFIRMED",
                value="UNKNOWN" if decision.action == "REJECT" else decision.value,
                evidence=original.evidence + new.evidence + decision.evidence,
                evaluation_state="EVALUATED",
            )
        tags = dict(proposed.strategy_tag_results or {})
        for tag, tag_decision in tag_decisions.items():
            if not tag_decision.evidence:
                raise ValueError("tag decisions require evidence")
            evidence = tuple(
                e
                for source in (baseline, proposed)
                for e in (
                    (source.strategy_tag_results or {})[tag].evidence
                    if tag in (source.strategy_tag_results or {})
                    else ()
                )
            )
            tags[tag] = StrategyTagResult(
                status="CONFIRMED" if tag_decision.action == "CONFIRM" else "UNKNOWN",
                value=tag if tag_decision.action == "CONFIRM" else "UNKNOWN",
                evidence=evidence + tag_decision.evidence,
                evaluation_state="EVALUATED",
                manual_action=tag_decision.action,
            )
        reviewed = ClassificationSnapshot.model_validate(
            {
                **proposed.model_dump(),
                **updates,
                "strategy_tag_results": tags,
                "strategy_tags": None,
                "observations": _observations(proposed),
                "review_items": tuple(
                    sorted(
                        [
                            f"{name}:{dim.status}"
                            for name, dim in updates.items()
                            if isinstance(dim, DimensionResult) and dim.status != "CONFIRMED"
                        ]
                        + [
                            f"strategy_tags:{tag}:{value.status}"
                            for tag, value in tags.items()
                            if value.status in {"CANDIDATE", "CONFLICT"}
                        ]
                    )
                ),
            }
        )
        _validate_snapshot(reviewed)
        # Only this authorized/CAS-checked review path may admit newly rejected
        # tags while its revision and matching audit are built atomically.
        prior_scope = self._authorized_tag_rejections
        self._authorized_tag_rejections = _TagReviewAuthorization(
            fund_id=case.fund_id,
            expected_revision=latest.id,
            valid_from=target,
            valid_to=end,
            tags={
                tag: tags[tag]
                for tag, value in tag_decisions.items()
                if value.action == "REJECT"
            },
        )
        try:
            result = self.write(
                case.fund_id,
                reviewed,
                valid_from=target,
                valid_to=end,
                available_at=at,
                actor=actor,
                reason=reason,
                reviewed=True,
            )
        finally:
            self._authorized_tag_rejections = prior_scope
        decided_scope = set(decisions) | {f"strategy_tags.{tag}" for tag in tag_decisions}
        for rebased in self.active_review_cases(case.fund_id):
            if (
                rebased.revision_id == result.id
                and rebased.issue_type == "NEW_EVIDENCE_AFTER_REVIEW"
                and rebased.details.get("valid_from") == target.isoformat()
                and rebased.details.get("dimension") in decided_scope
            ):
                rebased.status = "RESOLVED"
                rebased.resolved_at = at
                rebased.result_revision_id = result.id
        historical_scope = [
            name
            for name in case.details.get("source_dimensions", [])
            if name in CURRENT_PAUSED_DIMENSIONS
        ]
        if historical_scope:
            case.details = {
                **case.details,
                "evaluation_state": "PAUSED",
                "active_scope": [],
                "reviewed_scope": sorted(decided_scope),
            }
            case.status = "PENDING"
        else:
            case.status = "RESOLVED"
            case.resolved_at = at
            case.result_revision_id = result.id
        self.session.add(
            AuditLog(
                resource_type="fund_classification",
                resource_id=str(case.fund_id),
                action="REVIEW",
                operator=actor,
                detail={
                    "reason": reason,
                    "case_id": case.id,
                    "expected_revision": latest.id,
                    "revision_id": result.id,
                    "baseline": baseline.to_dict(),
                    "incoming": incoming.to_dict() if incoming else None,
                    "valid_from": target.isoformat(),
                    "valid_to": end.isoformat() if end else None,
                    "result_tag_results": {
                        tag: value.model_dump(mode="json")
                        for tag, value in (reviewed.strategy_tag_results or {}).items()
                    },
                    "decisions": {
                        name: value.model_dump(mode="json") for name, value in decisions.items()
                    },
                    "tag_decisions": {
                        name: value.model_dump(mode="json") for name, value in tag_decisions.items()
                    },
                },
                created_at=at,
            )
        )
        self.session.flush()
        return result

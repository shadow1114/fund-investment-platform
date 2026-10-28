"""Contract-facing fund read adapters.

These adapters deliberately only select, order, and project repository results.
PIT resolution, NAV adjustment, factor calculation, and eligibility evaluation
remain owned by the repositories and domain services behind the injected fund
adapter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from fip.api.classification_policy import get_classification_policy
from fip.api.errors import InvalidQueryError, NotFoundError
from fip.api.repositories import FundRepository


@dataclass(frozen=True, slots=True)
class QueryResult:
    data: Any
    meta: dict[str, object]


def _as_iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _as_tuple(value: Sequence[str] | None) -> tuple[str, ...] | None:
    return None if value is None else tuple(value)


def _as_mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value)


def _response(value: object) -> QueryResult:
    """Allow a repository to return either a bare data payload or data/meta."""
    if isinstance(value, Mapping) and "data" in value:
        meta = value.get("meta", {})
        return QueryResult(value["data"], dict(_as_mapping(meta)))
    return QueryResult(value, {})


def _row_date(value: object) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    return value if isinstance(value, str) else None


def _matches(row: Mapping[str, object], filters: Mapping[str, object]) -> bool:
    classification = row.get("classification")
    catalog = None
    classification_filters = (
        "asset_class",
        "strategy",
        "geography",
        "product_structure",
        "market_attributes",
        "strategy_tags",
        "classification_status",
    )
    if any(filters.get(name) for name in classification_filters):
        if not isinstance(classification, Mapping):
            # Existing UNKNOWN-status reads also include funds without a snapshot.
            if any(
                filters.get(name)
                for name in classification_filters
                if name != "classification_status"
            ):
                return False
        else:
            try:
                catalog = get_classification_policy()
            except InvalidQueryError:
                return False
    for dimension in (
        "asset_class",
        "strategy",
        "geography",
        "product_structure",
        "market_attributes",
    ):
        choices = filters.get(dimension)
        if choices:
            if not isinstance(classification, Mapping):
                return False
            if catalog is None or not set(cast(Sequence[str], choices)).intersection(
                catalog.catalog[dimension]
            ):
                return False
            result = classification.get(dimension)
            if not isinstance(result, Mapping) or result.get("status") != "CONFIRMED":
                return False
            value = result.get("value")
            values = [value] if isinstance(value, str) else value
            if not isinstance(values, list | tuple) or not set(values).intersection(
                cast(Sequence[str], choices), catalog.catalog[dimension]
            ):
                return False
    tags = filters.get("strategy_tags")
    if tags:
        results = (
            classification.get("strategy_tag_results")
            if isinstance(classification, Mapping)
            else None
        )
        if (
            catalog is None
            or not isinstance(results, Mapping)
            or not any(
                tag in catalog.strategy_tag_catalog
                and isinstance(result := results.get(tag), Mapping)
                and result.get("status") == "CONFIRMED"
                and result.get("value") == tag
                and result.get("evaluation_state") == "EVALUATED"
                and bool(result.get("evidence"))
                for tag in cast(Sequence[str], tags)
            )
        ):
            return False
    statuses = filters.get("classification_status")
    if statuses:
        active_dimensions = (
            set(catalog.active_dimensions)
            if catalog is not None
            else {
                "asset_class",
                "strategy",
                "geography",
                "product_structure",
                "market_attributes",
            }
        )
        present = (
            {
                v.get("status")
                for k, v in classification.items()
                if k in active_dimensions
                and isinstance(v, Mapping)
                and v.get("evaluation_state") not in {"PAUSED", "NOT_EVALUATED"}
            }
            if isinstance(classification, Mapping)
            else {"UNKNOWN"}
        )
        if not present.intersection(cast(Sequence[str], statuses)):
            return False
    name = filters.get("fund_name")
    if isinstance(name, str) and name.casefold() not in str(row.get("fund_name", "")).casefold():
        return False

    requested_types = cast(tuple[str, ...] | None, filters.get("fund_type"))
    row_type = row.get("fund_type", row.get("fund_classification"))
    if requested_types is not None and row_type not in requested_types:
        return False

    for field in ("management_company_id",):
        expected = filters.get(field)
        if expected is not None and row.get(field) != expected:
            return False

    manager_id = filters.get("manager_id")
    if manager_id is not None:
        managers = row.get("manager_ids", ())
        if (
            not isinstance(managers, Sequence)
            or isinstance(managers, str)
            or manager_id not in managers
        ):
            return False

    for field in ("lifecycle_status", "investment_eligibility"):
        choices = cast(tuple[str, ...] | None, filters.get(field))
        if choices is not None and row.get(field) not in choices:
            return False

    inception_date = _row_date(row.get("inception_date"))
    date_from = cast(str | None, filters.get("inception_date_from"))
    date_to = cast(str | None, filters.get("inception_date_to"))
    if date_from is not None and (inception_date is None or inception_date < date_from):
        return False
    if date_to is not None and (inception_date is None or inception_date > date_to):
        return False

    aum = row.get("aum")
    aum_min = cast(float | None, filters.get("aum_min"))
    aum_max = cast(float | None, filters.get("aum_max"))
    if aum_min is not None and (not isinstance(aum, int | float) or aum < aum_min):
        return False
    return not (aum_max is not None and (not isinstance(aum, int | float) or aum > aum_max))


def _sort_rows(
    rows: list[dict[str, object]], sort: str | None, order: str
) -> list[dict[str, object]]:
    field = sort if sort in {"fund_name", "inception_date", "aum"} else "fund_name"

    def stable_id(row: Mapping[str, object]) -> str:
        return str(row.get("fund_id", row.get("id", "")))

    def primary(row: Mapping[str, object]) -> tuple[bool, object]:
        value = row.get(field)
        if field == "aum" and isinstance(value, int | float):
            return (False, value)
        return (value is None, str(value or ""))

    rows.sort(key=stable_id)
    rows.sort(key=primary, reverse=order == "desc")
    return rows


class FundQueries:
    """Thin application reads over the request-scoped ``FundRepository`` seam."""

    def __init__(self, repository: FundRepository) -> None:
        self._repository = repository

    def list(
        self,
        *,
        fund_name: str | None,
        asset_class: Sequence[str] | None = None,
        strategy: Sequence[str] | None = None,
        strategy_tags: Sequence[str] | None = None,
        geography: Sequence[str] | None = None,
        product_structure: Sequence[str] | None = None,
        market_attributes: Sequence[str] | None = None,
        classification_status: Sequence[str] | None = None,
        fund_type: Sequence[str] | None,
        management_company_id: str | None,
        manager_id: str | None,
        lifecycle_status: Sequence[str] | None,
        investment_eligibility: Sequence[str] | None,
        inception_date_from: date | None,
        inception_date_to: date | None,
        aum_min: float | None,
        aum_max: float | None,
        as_of_date: date | None,
        page: int,
        page_size: int,
        sort: str | None,
        order: str,
    ) -> QueryResult:
        filters: dict[str, object] = {
            "asset_class": _as_tuple(asset_class),
            "strategy": _as_tuple(strategy),
            "strategy_tags": _as_tuple(strategy_tags),
            "geography": _as_tuple(geography),
            "product_structure": _as_tuple(product_structure),
            "market_attributes": _as_tuple(market_attributes),
            "classification_status": _as_tuple(classification_status),
            "fund_name": fund_name,
            "fund_type": _as_tuple(fund_type),
            "management_company_id": management_company_id,
            "manager_id": manager_id,
            "lifecycle_status": _as_tuple(lifecycle_status),
            "investment_eligibility": _as_tuple(investment_eligibility),
            "inception_date_from": _as_iso(inception_date_from),
            "inception_date_to": _as_iso(inception_date_to),
            "aum_min": aum_min,
            "aum_max": aum_max,
            "as_of_date": _as_iso(as_of_date),
        }
        for key in (
            "asset_class",
            "strategy",
            "strategy_tags",
            "geography",
            "product_structure",
            "market_attributes",
            "classification_status",
        ):
            if filters[key] is None:
                del filters[key]
        rows = [dict(row) for row in self._repository.list(**filters)]
        if (
            management_company_id is not None
            and rows
            and all(row.get("management_company_id") in (None, "UNKNOWN") for row in rows)
        ):
            raise InvalidQueryError("management_company_id is unavailable for the current data set")
        if (
            (aum_min is not None or aum_max is not None)
            and rows
            and all(not isinstance(row.get("aum"), int | float) for row in rows)
        ):
            raise InvalidQueryError("aum filters are unavailable for the current data set")
        matched = _sort_rows([row for row in rows if _matches(row, filters)], sort, order)
        offset = (page - 1) * page_size
        return QueryResult(
            matched[offset : offset + page_size],
            {
                "as_of_date": _as_iso(as_of_date),
                "is_point_in_time": as_of_date is not None,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": len(matched),
                    "total_pages": (len(matched) + page_size - 1) // page_size if matched else 0,
                },
            },
        )

    def detail(self, fund_id: str, *, as_of_date: date | None) -> QueryResult:
        value = self._optional_read("read_detail", fund_id, as_of_date=_as_iso(as_of_date))
        result = _response(self._repository.get(fund_id) if value is None else value)
        return QueryResult(result.data, {**result.meta, **self._pit_meta(as_of_date)})

    def nav_series(
        self,
        fund_id: str,
        *,
        date_from: date | None,
        date_to: date | None,
        frequency: str,
        nav_type: str,
        as_of_date: date | None,
    ) -> QueryResult:
        self._repository.get(fund_id)
        value = self._optional_read(
            "read_nav_series",
            fund_id,
            date_from=_as_iso(date_from),
            date_to=_as_iso(date_to),
            frequency=frequency,
            nav_type=nav_type,
            as_of_date=_as_iso(as_of_date),
        )
        if value is None:
            raise NotFoundError("fund NAV series", fund_id)
        result = _response(value)
        return QueryResult(
            result.data,
            {
                **result.meta,
                **self._pit_meta(as_of_date),
                "nav_type": nav_type,
                "adjustment_convention": "BACKWARD",
                "adjustment_rule_version": result.meta.get("adjustment_rule_version", "unknown"),
                "unavailable_count": result.meta.get("unavailable_count", 0),
            },
        )

    def evaluations(
        self, fund_id: str, *, evaluation_period: str | None, as_of_date: date | None
    ) -> QueryResult:
        self._repository.get(fund_id)
        value = self._optional_read(
            "read_evaluation",
            fund_id,
            evaluation_period=evaluation_period,
            as_of_date=_as_iso(as_of_date),
        )
        if value is None:
            raise NotFoundError("fund evaluation", fund_id)
        result = _response(value)
        return QueryResult(result.data, {**result.meta, **self._pit_meta(as_of_date)})

    def scores(
        self, fund_id: str, *, evaluation_period: str | None, as_of_date: date | None
    ) -> QueryResult:
        self._repository.get(fund_id)
        value = self._optional_read(
            "read_scores",
            fund_id,
            evaluation_period=evaluation_period,
            as_of_date=_as_iso(as_of_date),
        )
        if value is None:
            raise NotFoundError("fund score", fund_id)
        result = _response(value)
        return QueryResult(result.data, {**result.meta, **self._pit_meta(as_of_date)})

    def _optional_read(self, name: str, fund_id: str, **filters: object) -> object | None:
        read = getattr(self._repository, name, None)
        if not callable(read):
            return None
        return cast(Callable[..., object], read)(fund_id, **filters)

    @staticmethod
    def _pit_meta(as_of_date: date | None) -> dict[str, object]:
        return {"as_of_date": _as_iso(as_of_date), "is_point_in_time": as_of_date is not None}

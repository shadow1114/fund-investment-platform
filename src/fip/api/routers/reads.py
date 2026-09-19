from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from fip.api.context import principal_from_request
from fip.api.contracts import success
from fip.api.dependencies import get_api_repositories
from fip.api.errors import InvalidQueryError
from fip.api.fund_queries import FundQueries
from fip.api.portfolio_queries import DecisionQueries, OptimizationQueries, PortfolioQueries
from fip.api.repositories import ApiRepositories
from fip.api.universe_queries import UniverseQueries

# FastAPI's dependency/query declarations intentionally live in signatures.
# ruff: noqa: B008

router = APIRouter()


def get_repository(
    repositories: ApiRepositories = Depends(get_api_repositories),
) -> ApiRepositories:
    """Keep existing route signatures on the canonical request-scoped adapter set."""
    return repositories


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _page_meta(page: int, page_size: int, total: int) -> dict[str, Any]:
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": total_pages,
        }
    }


def _multi_values(
    values: list[str] | None, *, name: str, allowed: set[str] | None = None
) -> tuple[str, ...] | None:
    if values is None:
        return None
    parsed = tuple(item for value in values for item in value.split(",") if item)
    if not parsed or (allowed is not None and not set(parsed) <= allowed):
        raise InvalidQueryError(f"Invalid {name}")
    return parsed


@router.get("/session", operation_id="getSession")
def get_session(request: Request) -> dict[str, Any]:
    principal = principal_from_request(request)
    return success(
        {
            "user_id": principal.user_id,
            "roles": list(principal.roles),
            "capabilities": {"can_review_decisions": principal.can_review_decisions},
        },
        request_id=_request_id(request),
    )


@router.get("/funds", operation_id="listFunds")
def list_funds(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort: Literal["fund_name", "inception_date", "aum"] | None = None,
    order: Literal["asc", "desc"] = "asc",
    as_of_date: date | None = None,
    fund_name: str | None = None,
    fund_type: list[str] | None = Query(None),
    management_company_id: str | None = None,
    manager_id: str | None = None,
    lifecycle_status: list[str] | None = Query(None),
    investment_eligibility: list[str] | None = Query(None),
    inception_date_from: date | None = None,
    inception_date_to: date | None = None,
    aum_min: float | None = None,
    aum_max: float | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    if (
        inception_date_from is not None
        and inception_date_to is not None
        and inception_date_from > inception_date_to
    ):
        raise InvalidQueryError("inception_date_from must not be after inception_date_to")
    if aum_min is not None and aum_max is not None and aum_min > aum_max:
        raise InvalidQueryError("aum_min must not be greater than aum_max")
    result = FundQueries(repository.funds).list(
        fund_name=fund_name,
        fund_type=_multi_values(fund_type, name="fund_type"),
        management_company_id=management_company_id,
        manager_id=manager_id,
        lifecycle_status=_multi_values(
            lifecycle_status,
            name="lifecycle_status",
            allowed={
                "NORMAL",
                "SUSPENDED_SUBSCRIPTION",
                "LIQUIDATED",
                "MERGED",
                "TRANSFORMED",
                "UNKNOWN",
            },
        ),
        investment_eligibility=_multi_values(
            investment_eligibility,
            name="investment_eligibility",
            allowed={
                "FULLY_ELIGIBLE",
                "HOLD_ONLY",
                "LIMITED",
                "EXIT_ONLY",
                "NOT_TRADABLE",
                "UNKNOWN",
            },
        ),
        inception_date_from=inception_date_from,
        inception_date_to=inception_date_to,
        aum_min=aum_min,
        aum_max=aum_max,
        as_of_date=as_of_date,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/fund-universes", operation_id="listUniverses")
def list_universes(
    request: Request,
    strategy_id: str | None = None,
    decision_at: date | None = None,
    eligibility_rules_version: str | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = UniverseQueries(repository.universes).list(
        strategy_id=strategy_id,
        decision_at=decision_at,
        eligibility_rules_version=eligibility_rules_version,
    )
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/portfolios", operation_id="listPortfolios")
def list_portfolios(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort: Literal["portfolio_name"] | None = None,
    order: Literal["asc", "desc"] = "asc",
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    principal = principal_from_request(request)
    rows, meta = PortfolioQueries(repository.portfolios).list(
        principal=principal, page=page, page_size=page_size, sort=sort, order=order
    )
    return success(rows, request_id=_request_id(request), **meta)


@router.get("/funds/{fund_id}", operation_id="getFund")
def get_fund(
    fund_id: str,
    request: Request,
    as_of_date: date | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = FundQueries(repository.funds).detail(fund_id, as_of_date=as_of_date)
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/funds/{fund_id}/nav-series", operation_id="getFundNavSeries")
def get_nav_series(
    fund_id: str,
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"] = "DAILY",
    nav_type: Literal["ADJUSTED", "RAW"] = "ADJUSTED",
    as_of_date: date | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = FundQueries(repository.funds).nav_series(
        fund_id,
        date_from=date_from,
        date_to=date_to,
        frequency=frequency,
        nav_type=nav_type,
        as_of_date=as_of_date,
    )
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/funds/{fund_id}/evaluations", operation_id="getFundEvaluations")
def get_evaluations(
    fund_id: str,
    request: Request,
    evaluation_period: Literal["1M", "3M", "6M", "1Y", "3Y", "5Y"] | None = None,
    as_of_date: date | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = FundQueries(repository.funds).evaluations(
        fund_id, evaluation_period=evaluation_period, as_of_date=as_of_date
    )
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/funds/{fund_id}/scores", operation_id="getFundScores")
def get_scores(
    fund_id: str,
    request: Request,
    evaluation_period: Literal["1M", "3M", "6M", "1Y", "3Y", "5Y"] | None = None,
    as_of_date: date | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = FundQueries(repository.funds).scores(
        fund_id, evaluation_period=evaluation_period, as_of_date=as_of_date
    )
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/fund-universes/{universe_id}", operation_id="getUniverse")
def get_universe(
    universe_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = UniverseQueries(repository.universes).detail(universe_id)
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/portfolios/{id}", operation_id="getPortfolio")
def get_portfolio(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    return success(
        PortfolioQueries(repository.portfolios).detail(
            id, principal=principal_from_request(request)
        ),
        request_id=_request_id(request),
    )


@router.get("/portfolios/{id}/optimizations/{optimization_id}", operation_id="getOptimization")
def get_optimization(
    id: str,
    optimization_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    data = OptimizationQueries(repository.optimizations).detail(optimization_id, portfolio_id=id)
    provenance = data.pop("_meta", {})
    provenance_map = provenance if isinstance(provenance, Mapping) else {}
    return success(
        data,
        request_id=_request_id(request),
        portfolio_rule_version=str(provenance_map.get("portfolio_rule_version", "UNKNOWN")),
        return_estimate_version=str(provenance_map.get("return_estimate_version", "UNKNOWN")),
        risk_model_version=str(provenance_map.get("risk_model_version", "UNKNOWN")),
        code_version=str(provenance_map.get("code_version", "UNKNOWN")),
    )


@router.get("/decisions/{decision_id}", operation_id="getDecision")
def get_decision(
    decision_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    data = DecisionQueries(repository.decisions).detail(decision_id)
    provenance = data.pop("_meta", {})
    provenance_map = provenance if isinstance(provenance, Mapping) else {}
    return success(
        data,
        request_id=_request_id(request),
        versions=provenance_map.get("versions", {}),
        is_point_in_time=bool(provenance_map.get("is_point_in_time", False)),
    )


@router.get("/backtests/{id}/status", operation_id="getBacktestStatus")
def get_backtest_status(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    repository.backtests.get(id)
    return success({}, request_id=_request_id(request))


@router.get("/backtests/{id}/result", operation_id="getBacktestResult")
def get_backtest_result(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    repository.backtests.get(id)
    return success({}, request_id=_request_id(request))


@router.get("/backtests/{id}/performance", operation_id="getBacktestPerformance")
def get_backtest_performance(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    repository.backtests.get(id)
    return success({}, request_id=_request_id(request))


@router.get("/backtests/{id}/bias-check", operation_id="getBacktestBiasCheck")
def get_backtest_bias_check(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    repository.backtests.get(id)
    return success({}, request_id=_request_id(request))

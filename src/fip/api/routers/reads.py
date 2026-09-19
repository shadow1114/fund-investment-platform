from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from fip.api.context import principal_from_request
from fip.api.contracts import success
from fip.api.dependencies import get_api_repositories
from fip.api.fund_queries import FundQueries
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
    sort: str | None = None,
    order: Literal["asc", "desc"] = "asc",
    as_of_date: date | None = None,
    fund_name: str | None = None,
    fund_type: list[str] | None = Query(None),
    management_company_id: str | None = None,
    manager_id: str | None = None,
    lifecycle_status: list[
        Literal[
            "NORMAL",
            "SUSPENDED_SUBSCRIPTION",
            "LIQUIDATED",
            "MERGED",
            "TRANSFORMED",
            "UNKNOWN",
        ]
    ] | None = Query(None),
    investment_eligibility: list[
        Literal["FULLY_ELIGIBLE", "HOLD_ONLY", "LIMITED", "EXIT_ONLY", "NOT_TRADABLE", "UNKNOWN"]
    ] | None = Query(None),
    inception_date_from: date | None = None,
    inception_date_to: date | None = None,
    aum_min: float | None = None,
    aum_max: float | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = FundQueries(repository.funds).list(
        fund_name=fund_name,
        fund_type=fund_type,
        management_company_id=management_company_id,
        manager_id=manager_id,
        lifecycle_status=lifecycle_status,
        investment_eligibility=investment_eligibility,
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
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    rows = repository.list_portfolios()
    return success(rows, request_id=_request_id(request), **_page_meta(page, page_size, len(rows)))


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
    return success(dict(repository.portfolios.get(id)), request_id=_request_id(request))


@router.get("/portfolios/{id}/optimizations/{optimization_id}", operation_id="getOptimization")
def get_optimization(
    id: str,
    optimization_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    return success(
        dict(repository.optimizations.get(optimization_id)),
        request_id=_request_id(request),
    )


@router.get("/decisions/{decision_id}", operation_id="getDecision")
def get_decision(
    decision_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    return success(dict(repository.decisions.get(decision_id)), request_id=_request_id(request))


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

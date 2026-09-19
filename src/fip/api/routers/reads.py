from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from fip.api.context import principal_from_request
from fip.api.contracts import success
from fip.api.dependencies import get_api_repositories
from fip.api.errors import NotFoundError
from fip.api.repositories import ApiRepositories

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
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    rows = repository.list_funds()
    return success(rows, request_id=_request_id(request), **_page_meta(page, page_size, len(rows)))


@router.get("/fund-universes", operation_id="listUniverses")
def list_universes(
    request: Request, repository: ApiRepositories = Depends(get_repository)
) -> dict[str, Any]:
    rows = repository.list_universes()
    return success(
        rows,
        request_id=_request_id(request),
        eligibility_rules_version="unknown",
        scoring_policy_version=None,
    )


@router.get("/portfolios", operation_id="listPortfolios")
def list_portfolios(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    rows = repository.list_portfolios()
    return success(rows, request_id=_request_id(request), **_page_meta(page, page_size, len(rows)))


def _not_found(resource: str, identifier: str) -> None:
    raise NotFoundError(resource, identifier)


@router.get("/funds/{fund_id}", operation_id="getFund")
def get_fund(fund_id: str, request: Request, as_of_date: date | None = None) -> dict[str, Any]:
    _not_found("fund", fund_id)
    return success({}, request_id=_request_id(request))


@router.get("/funds/{fund_id}/nav-series", operation_id="getFundNavSeries")
def get_nav_series(fund_id: str, request: Request) -> dict[str, Any]:
    _not_found("fund", fund_id)
    return success([], request_id=_request_id(request))


@router.get("/funds/{fund_id}/evaluations", operation_id="getFundEvaluations")
def get_evaluations(fund_id: str, request: Request) -> dict[str, Any]:
    _not_found("fund", fund_id)
    return success({}, request_id=_request_id(request))


@router.get("/funds/{fund_id}/scores", operation_id="getFundScores")
def get_scores(fund_id: str, request: Request) -> dict[str, Any]:
    _not_found("fund", fund_id)
    return success({}, request_id=_request_id(request))


@router.get("/fund-universes/{universe_id}", operation_id="getUniverse")
def get_universe(universe_id: str, request: Request) -> dict[str, Any]:
    _not_found("fund universe", universe_id)
    return success({}, request_id=_request_id(request))


@router.get("/portfolios/{id}", operation_id="getPortfolio")
def get_portfolio(id: str, request: Request) -> dict[str, Any]:
    _not_found("portfolio", id)
    return success({}, request_id=_request_id(request))


@router.get("/portfolios/{id}/optimizations/{optimization_id}", operation_id="getOptimization")
def get_optimization(id: str, optimization_id: str, request: Request) -> dict[str, Any]:
    _not_found("optimization", optimization_id)
    return success({}, request_id=_request_id(request))


@router.get("/decisions/{decision_id}", operation_id="getDecision")
def get_decision(decision_id: str, request: Request) -> dict[str, Any]:
    _not_found("decision", decision_id)
    return success({}, request_id=_request_id(request))


@router.get("/backtests/{id}/status", operation_id="getBacktestStatus")
def get_backtest_status(id: str, request: Request) -> dict[str, Any]:
    _not_found("backtest", id)
    return success({}, request_id=_request_id(request))


@router.get("/backtests/{id}/result", operation_id="getBacktestResult")
def get_backtest_result(id: str, request: Request) -> dict[str, Any]:
    _not_found("backtest", id)
    return success({}, request_id=_request_id(request))


@router.get("/backtests/{id}/performance", operation_id="getBacktestPerformance")
def get_backtest_performance(id: str, request: Request) -> dict[str, Any]:
    _not_found("backtest", id)
    return success({}, request_id=_request_id(request))


@router.get("/backtests/{id}/bias-check", operation_id="getBacktestBiasCheck")
def get_backtest_bias_check(id: str, request: Request) -> dict[str, Any]:
    _not_found("backtest", id)
    return success({}, request_id=_request_id(request))

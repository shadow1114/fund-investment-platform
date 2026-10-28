from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from fip.api.auth import get_principal
from fip.api.classification_policy import get_classification_policy
from fip.api.context import Principal
from fip.api.contracts import success
from fip.api.dependencies import get_api_repositories
from fip.api.errors import ConflictError, ForbiddenError, InvalidQueryError, NotFoundError
from fip.api.fund_queries import FundQueries
from fip.api.policy import require_read_access
from fip.api.portfolio_queries import DecisionQueries, OptimizationQueries, PortfolioQueries
from fip.api.repositories import ApiRepositories
from fip.api.schemas import ReadEnvelopeModel
from fip.api.universe_queries import UniverseQueries
from fip.services.data_service.classification.policy import POLICY_REGISTRY

# FastAPI's dependency/query declarations intentionally live in signatures.
# ruff: noqa: B008

router = APIRouter()


def _ensure_portfolio_visible(
    repository: ApiRepositories, portfolio_id: str, principal: Principal
) -> None:
    try:
        row = repository.portfolios.get(portfolio_id)
    except NotFoundError:
        if not isinstance(getattr(repository.portfolios, "session", None), Session):
            return
        raise
    require_read_access(principal, "portfolio", row)


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


@router.get("/session", operation_id="getSession", response_model=ReadEnvelopeModel)
def get_session(request: Request) -> dict[str, Any]:
    principal = get_principal(request)
    return success(
        {
            "user_id": principal.user_id,
            "roles": list(principal.roles),
            "capabilities": {
                "can_review_decisions": principal.can_review_decisions,
                "can_review_classifications": principal.can_review_classifications,
                "can_manage_data_ingestion": principal.can_manage_data_ingestion,
            },
        },
        request_id=_request_id(request),
    )


@router.get("/funds", operation_id="listFunds", response_model=ReadEnvelopeModel)
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
    asset_class: list[str] | None = Query(None),
    strategy: list[str] | None = Query(None),
    strategy_tags: list[str] | None = Query(None),
    enum_version: str | None = None,
    geography: list[str] | None = Query(None),
    product_structure: list[str] | None = Query(None),
    market_attributes: list[str] | None = Query(None),
    classification_status: list[str] | None = Query(None),
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
    policies = (
        [get_classification_policy(enum_version=enum_version)]
        if enum_version is not None
        else [get_classification_policy(rule, enum) for _, rule, enum in POLICY_REGISTRY]
    )
    allowed = {
        name: {value for policy in policies for value in policy.catalog[name]}
        for name in policies[0].catalog
    }
    result = FundQueries(repository.funds).list(
        strategy_tags=_multi_values(
            strategy_tags,
            name="strategy_tags",
            allowed={tag for policy in policies for tag in policy.strategy_tag_catalog},
        ),
        enum_version=enum_version,
        asset_class=_multi_values(asset_class, name="asset_class", allowed=allowed["asset_class"]),
        strategy=_multi_values(strategy, name="strategy", allowed=allowed["strategy"]),
        geography=_multi_values(geography, name="geography", allowed=allowed["geography"]),
        product_structure=_multi_values(
            product_structure, name="product_structure", allowed=allowed["product_structure"]
        ),
        market_attributes=_multi_values(
            market_attributes, name="market_attributes", allowed=allowed["market_attributes"]
        ),
        classification_status=_multi_values(
            classification_status,
            name="classification_status",
            allowed={"CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"},
        ),
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


@router.get("/fund-universes", operation_id="listUniverses", response_model=ReadEnvelopeModel)
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


@router.get("/portfolios", operation_id="listPortfolios", response_model=ReadEnvelopeModel)
def list_portfolios(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort: Literal["portfolio_name"] | None = None,
    order: Literal["asc", "desc"] = "asc",
    repository: ApiRepositories = Depends(get_repository),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    rows, meta = PortfolioQueries(repository.portfolios).list(
        principal=principal, page=page, page_size=page_size, sort=sort, order=order
    )
    return success(rows, request_id=_request_id(request), **meta)


@router.get("/funds/{fund_id}", operation_id="getFund", response_model=ReadEnvelopeModel)
def get_fund(
    fund_id: str,
    request: Request,
    as_of_date: date | None = None,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = FundQueries(repository.funds).detail(fund_id, as_of_date=as_of_date)
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get(
    "/funds/{fund_id}/nav-series", operation_id="getFundNavSeries", response_model=ReadEnvelopeModel
)
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


@router.get(
    "/funds/{fund_id}/evaluations",
    operation_id="getFundEvaluations",
    response_model=ReadEnvelopeModel,
)
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


@router.get(
    "/funds/{fund_id}/scores", operation_id="getFundScores", response_model=ReadEnvelopeModel
)
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


@router.get(
    "/fund-universes/{universe_id}", operation_id="getUniverse", response_model=ReadEnvelopeModel
)
def get_universe(
    universe_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    result = UniverseQueries(repository.universes).detail(universe_id)
    return success(result.data, request_id=_request_id(request), **result.meta)


@router.get("/portfolios/{id}", operation_id="getPortfolio", response_model=ReadEnvelopeModel)
def get_portfolio(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    return success(
        PortfolioQueries(repository.portfolios).detail(id, principal=principal),
        request_id=_request_id(request),
    )


@router.get(
    "/portfolios/{id}/optimizations/{optimization_id}",
    operation_id="getOptimization",
    response_model=ReadEnvelopeModel,
)
def get_optimization(
    id: str,
    optimization_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    _ensure_portfolio_visible(repository, id, principal)
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


@router.get(
    "/decisions/{decision_id}", operation_id="getDecision", response_model=ReadEnvelopeModel
)
def get_decision(
    decision_id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    data = DecisionQueries(repository.decisions).detail(decision_id)
    portfolio_id = data.get("portfolio_id") if isinstance(data, Mapping) else None
    if isinstance(portfolio_id, str):
        _ensure_portfolio_visible(repository, portfolio_id, principal)
    elif isinstance(getattr(repository.decisions, "session", None), Session):
        raise ForbiddenError()
    provenance = data.pop("_meta", {})
    provenance_map = provenance if isinstance(provenance, Mapping) else {}
    return success(
        data,
        request_id=_request_id(request),
        versions=provenance_map.get("versions", {}),
        is_point_in_time=bool(provenance_map.get("is_point_in_time", False)),
    )


@router.get(
    "/backtests/{id}/status", operation_id="getBacktestStatus", response_model=ReadEnvelopeModel
)
def get_backtest_status(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    row = dict(repository.backtests.get(id))
    return success(
        {
            "backtest_id": id,
            "status": row.get("status", "UNKNOWN"),
            "validation_status": row.get("validation_status"),
            "progress": row.get(
                "progress",
                {
                    "current_decision_date": None,
                    "completed_periods": 0,
                    "total_periods": None,
                    "total_periods_is_estimate": False,
                },
            ),
            "started_at": row.get("started_at"),
        },
        request_id=_request_id(request),
    )


@router.get(
    "/backtests/{id}/result", operation_id="getBacktestResult", response_model=ReadEnvelopeModel
)
def get_backtest_result(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    row = dict(repository.backtests.get(id))
    result = row.get("result")
    if not isinstance(result, Mapping):
        if not isinstance(getattr(repository.backtests, "session", None), Session):
            return success(row, request_id=_request_id(request))
        raise ConflictError("Backtest result is not available")
    required = {
        "backtest_id",
        "status",
        "validation_status",
        "backtest_mode",
        "period",
        "initial_capital",
        "final_value",
        "summary",
        "excess_return",
        "significance_verdict",
        "validation_summary",
    }
    if not required <= set(result):
        raise ConflictError("Backtest result is incomplete")
    meta = row.get("result_meta")
    required_meta = {
        "configuration_version",
        "data_version",
        "strategy_versions",
        "code_version",
        "transaction_cost_model_version",
        "methodology_policy_version",
        "report_policy_version",
    }
    if not isinstance(meta, Mapping) or not required_meta <= set(meta):
        raise ConflictError("Backtest result metadata is incomplete")
    strategy_versions = meta["strategy_versions"]
    if not isinstance(strategy_versions, Mapping) or not {
        "metric_version",
        "scoring_version",
        "portfolio_rule_version",
        "rebalance_rule_version",
        "return_estimate_version",
        "risk_model_version",
        "eligibility_universe_version",
        "benchmark_version",
        "peer_group_classification_version",
    } <= set(strategy_versions):
        raise ConflictError("Backtest strategy metadata is incomplete")
    return success(
        result,
        request_id=_request_id(request),
        configuration_version=meta["configuration_version"],
        data_version=meta["data_version"],
        strategy_versions=strategy_versions,
        code_version=meta["code_version"],
        transaction_cost_model_version=meta["transaction_cost_model_version"],
        methodology_policy_version=meta["methodology_policy_version"],
        report_policy_version=meta["report_policy_version"],
    )


@router.get(
    "/backtests/{id}/performance",
    operation_id="getBacktestPerformance",
    response_model=ReadEnvelopeModel,
)
def get_backtest_performance(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    repository.backtests.get(id)
    return success({}, request_id=_request_id(request))


@router.get(
    "/backtests/{id}/bias-check",
    operation_id="getBacktestBiasCheck",
    response_model=ReadEnvelopeModel,
)
def get_backtest_bias_check(
    id: str,
    request: Request,
    repository: ApiRepositories = Depends(get_repository),
) -> dict[str, Any]:
    repository.backtests.get(id)
    return success({}, request_id=_request_id(request))

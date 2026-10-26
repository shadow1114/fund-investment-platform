import { queryOptions } from "@tanstack/react-query";

import {
  getBacktestBiasCheck,
  getBacktestPerformance,
  getBacktestResult,
  getBacktestStatus,
  getDecision,
  getFund,
  getFundBasicInfoHistory,
  getFundEvaluations,
  getFundNavSeries,
  getFundScores,
  getOperation,
  getOptimization,
  getPortfolio,
  getSession,
  getUniverse,
  listFunds,
  listFundIngestions,
  listPortfolios,
  listUniverses,
} from "./generated/m17";
import type {
  GetBacktestPerformanceParams,
  GetFundEvaluationsParams,
  GetFundNavSeriesParams,
  GetFundParams,
  GetFundScoresParams,
  ListFundsParams,
  ListPortfoliosParams,
  ListUniversesParams,
} from "./generated/m17.schemas";
import { normalizeOptimization, unwrapResponse } from "./http";

export const queryKeys = {
  all: ["api"] as const,
  session: ["api", "session"] as const,
  funds: (params?: ListFundsParams) => ["api", "funds", params] as const,
  fund: (fundId: string, params?: GetFundParams) =>
    ["api", "funds", fundId, params] as const,
  fundNavSeries: (fundId: string, params?: GetFundNavSeriesParams) =>
    ["api", "funds", fundId, "nav-series", params] as const,
  fundEvaluations: (fundId: string, params?: GetFundEvaluationsParams) =>
    ["api", "funds", fundId, "evaluations", params] as const,
  fundScores: (fundId: string, params?: GetFundScoresParams) =>
    ["api", "funds", fundId, "scores", params] as const,
  fundIngestions: (fundId: string) =>
    ["api", "funds", fundId, "ingestions"] as const,
  fundBasicInfoHistory: (fundId: string, asOfDate?: string) =>
    ["api", "funds", fundId, "basic-info-history", asOfDate] as const,
  universes: (params?: ListUniversesParams) =>
    ["api", "fund-universes", params] as const,
  universe: (universeId: string) =>
    ["api", "fund-universes", universeId] as const,
  portfolios: (params?: ListPortfoliosParams) =>
    ["api", "portfolios", params] as const,
  portfolio: (portfolioId: string) =>
    ["api", "portfolios", portfolioId] as const,
  optimization: (portfolioId: string, optimizationId: string) =>
    [
      "api",
      "portfolios",
      portfolioId,
      "optimizations",
      optimizationId,
    ] as const,
  decision: (decisionId: string) => ["api", "decisions", decisionId] as const,
  backtestStatus: (backtestId: string) =>
    ["api", "backtests", backtestId, "status"] as const,
  backtestResult: (backtestId: string) =>
    ["api", "backtests", backtestId, "result"] as const,
  backtestPerformance: (
    backtestId: string,
    params?: GetBacktestPerformanceParams,
  ) => ["api", "backtests", backtestId, "performance", params] as const,
  backtestBiasCheck: (backtestId: string) =>
    ["api", "backtests", backtestId, "bias-check"] as const,
  operation: (operationId: string) =>
    ["api", "operations", operationId] as const,
};

export const getFundBasicInfoHistoryQueryOptions = (
  fundId: string,
  asOfDate?: string,
) =>
  queryOptions({
    queryKey: queryKeys.fundBasicInfoHistory(fundId, asOfDate),
    queryFn: async () =>
      unwrapResponse(
        await getFundBasicInfoHistory(fundId, {
          as_of_date: asOfDate,
          limit: 20,
        }),
      ),
    enabled: Boolean(fundId),
  });

export const getFundIngestionsQueryOptions = (fundId: string) =>
  queryOptions({
    queryKey: queryKeys.fundIngestions(fundId),
    queryFn: async () =>
      unwrapResponse(await listFundIngestions(fundId, { limit: 20 })),
    enabled: Boolean(fundId),
  });

export const getSessionQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.session,
    queryFn: async () => unwrapResponse(await getSession()),
  });

export const listFundsQueryOptions = (params?: ListFundsParams) =>
  queryOptions({
    queryKey: queryKeys.funds(params),
    queryFn: async () =>
      unwrapResponse(await listFunds(params), {
        requiredMeta: [
          "as_of_date",
          "data_version",
          "versions",
          "is_point_in_time",
          "pagination",
          "availability_quality_distribution",
        ],
      }),
  });

export const getFundQueryOptions = (fundId: string, params?: GetFundParams) =>
  queryOptions({
    queryKey: queryKeys.fund(fundId, params),
    queryFn: async () => unwrapResponse(await getFund(fundId, params)),
  });

export const getFundNavSeriesQueryOptions = (
  fundId: string,
  params?: GetFundNavSeriesParams,
) =>
  queryOptions({
    queryKey: queryKeys.fundNavSeries(fundId, params),
    queryFn: async () => unwrapResponse(await getFundNavSeries(fundId, params)),
  });

export const getFundEvaluationsQueryOptions = (
  fundId: string,
  params?: GetFundEvaluationsParams,
) =>
  queryOptions({
    queryKey: queryKeys.fundEvaluations(fundId, params),
    queryFn: async () =>
      unwrapResponse(await getFundEvaluations(fundId, params)),
  });

export const getFundScoresQueryOptions = (
  fundId: string,
  params?: GetFundScoresParams,
) =>
  queryOptions({
    queryKey: queryKeys.fundScores(fundId, params),
    queryFn: async () => unwrapResponse(await getFundScores(fundId, params)),
  });

export const listUniversesQueryOptions = (params?: ListUniversesParams) =>
  queryOptions({
    queryKey: queryKeys.universes(params),
    queryFn: async () => unwrapResponse(await listUniverses(params)),
  });

export const getUniverseQueryOptions = (universeId: string) =>
  queryOptions({
    queryKey: queryKeys.universe(universeId),
    queryFn: async () => unwrapResponse(await getUniverse(universeId)),
  });

export const listPortfoliosQueryOptions = (params?: ListPortfoliosParams) =>
  queryOptions({
    queryKey: queryKeys.portfolios(params),
    queryFn: async () =>
      unwrapResponse(await listPortfolios(params), {
        requiredMeta: ["versions", "is_point_in_time", "pagination"],
      }),
  });

export const getPortfolioQueryOptions = (portfolioId: string) =>
  queryOptions({
    queryKey: queryKeys.portfolio(portfolioId),
    queryFn: async () => unwrapResponse(await getPortfolio(portfolioId)),
  });

export const getOptimizationQueryOptions = (
  portfolioId: string,
  optimizationId: string,
) =>
  queryOptions({
    queryKey: queryKeys.optimization(portfolioId, optimizationId),
    queryFn: async () =>
      normalizeOptimization(
        unwrapResponse(await getOptimization(portfolioId, optimizationId)),
      ),
  });

export const getDecisionQueryOptions = (decisionId: string) =>
  queryOptions({
    queryKey: queryKeys.decision(decisionId),
    queryFn: async () => unwrapResponse(await getDecision(decisionId)),
  });

export const getBacktestStatusQueryOptions = (backtestId: string) =>
  queryOptions({
    queryKey: queryKeys.backtestStatus(backtestId),
    queryFn: async () => unwrapResponse(await getBacktestStatus(backtestId)),
  });

export const getBacktestResultQueryOptions = (backtestId: string) =>
  queryOptions({
    queryKey: queryKeys.backtestResult(backtestId),
    queryFn: async () => unwrapResponse(await getBacktestResult(backtestId)),
  });

export const getBacktestPerformanceQueryOptions = (
  backtestId: string,
  params?: GetBacktestPerformanceParams,
) =>
  queryOptions({
    queryKey: queryKeys.backtestPerformance(backtestId, params),
    queryFn: async () =>
      unwrapResponse(await getBacktestPerformance(backtestId, params)),
  });

export const getBacktestBiasCheckQueryOptions = (backtestId: string) =>
  queryOptions({
    queryKey: queryKeys.backtestBiasCheck(backtestId),
    queryFn: async () => unwrapResponse(await getBacktestBiasCheck(backtestId)),
  });

export const getOperationQueryOptions = (operationId: string) =>
  queryOptions({
    queryKey: queryKeys.operation(operationId),
    queryFn: async () => unwrapResponse(await getOperation(operationId)),
  });

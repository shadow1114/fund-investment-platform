import { queryOptions, type QueryClient } from "@tanstack/react-query";

import {
  getFundIngestion,
  listFundIngestionHistory,
  listFundIngestionItems,
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
  listFundManagementCompanies,
  listPortfolios,
  listUniverses,
} from "./generated/m17";
import type {
  FundListMeta,
  ListFundIngestionHistoryParams,
  ListFundIngestionItemsParams,
  GetBacktestPerformanceParams,
  GetFundEvaluationsParams,
  GetFundNavSeriesParams,
  GetFundParams,
  GetFundScoresParams,
  ListFundsParams,
  ListFundManagementCompaniesParams,
  ListPortfoliosParams,
  ListUniversesParams,
} from "./generated/m17.schemas";
import { normalizeOptimization, unwrapResponse } from "./http";

export const queryKeys = {
  all: ["api"] as const,
  session: ["api", "session"] as const,
  funds: (params?: ListFundsParams) => ["api", "funds", params] as const,
  fundPages: (params: ListFundsParams, revision = 0) =>
    ["api", "funds", "grid", params, revision] as const,
  fundManagementCompanies: (params?: ListFundManagementCompaniesParams) =>
    ["api", "fund-management-companies", params] as const,
  fundDataRevision: ["api", "fund-data-revision"] as const,
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
          "subscription_status_source",
        ],
      }),
  });

export const fundPageQueryOptions = (params: ListFundsParams, revision = 0) =>
  queryOptions({
    queryKey: queryKeys.fundPages(params, revision),
    staleTime: 30_000,
    queryFn: async () => {
      const response = await listFunds(params);
      const rows = unwrapResponse(response, {
        requiredMeta: [
          "as_of_date",
          "data_version",
          "versions",
          "is_point_in_time",
          "pagination",
          "availability_quality_distribution",
          "subscription_status_source",
        ],
      });
      return {
        rows,
        meta: response.data.meta as FundListMeta,
      };
    },
  });

export const listFundManagementCompaniesQueryOptions = (asOfDate?: string) => {
  const params = asOfDate ? { as_of_date: asOfDate } : undefined;
  return queryOptions({
    queryKey: queryKeys.fundManagementCompanies(params),
    queryFn: async () =>
      unwrapResponse(await listFundManagementCompanies(params)),
  });
};

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

export const ingestionKeys = {
  history: ["api", "ingestion-history"] as const,
  task: (id: string) => ["api", "ingestion-tasks", id] as const,
  items: (id: string) => ["api", "ingestion-items", id] as const,
};

export const getIngestionHistoryQueryOptions = (
  params: ListFundIngestionHistoryParams,
) =>
  queryOptions({
    queryKey: [...ingestionKeys.history, params],
    queryFn: async () => unwrapResponse(await listFundIngestionHistory(params)),
  });

export const getIngestionTaskQueryOptions = (id: string) =>
  queryOptions({
    queryKey: ingestionKeys.task(id),
    queryFn: async () => unwrapResponse(await getFundIngestion(id)),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      query.state.data?.status === "RUNNING" ? 2500 : false,
  });

export const getIngestionItemsQueryOptions = (
  id: string,
  params: ListFundIngestionItemsParams,
  running = false,
) =>
  queryOptions({
    queryKey: [...ingestionKeys.items(id), params],
    queryFn: async () =>
      unwrapResponse(await listFundIngestionItems(id, params)),
    enabled: Boolean(id),
    refetchInterval: running ? 2500 : false,
  });

export const getLatestIngestionQueryOptions = (completedOnly = false) =>
  queryOptions({
    queryKey: ["api", "ingestion-latest", completedOnly],
    queryFn: async () =>
      unwrapResponse(
        await listFundIngestionHistory({
          page: 1,
          page_size: 1,
          sort: "finished_at",
          status: completedOnly ? "COMPLETED" : undefined,
        }),
      ),
  });

export const invalidateIngestionFundData = (client: QueryClient) => {
  client.setQueryData<number>(
    queryKeys.fundDataRevision,
    (revision) => (revision ?? 0) + 1,
  );
  return Promise.all([
    client.invalidateQueries({ queryKey: ["api", "funds"] }),
    client.invalidateQueries({
      queryKey: ["api", "fund-management-companies"],
    }),
    ...[
      "fund-research",
      "fund-detail",
      "fund-nav",
      "fund-evaluation",
      "fund-score",
    ].map((prefix) => client.invalidateQueries({ queryKey: [prefix] })),
  ]);
};

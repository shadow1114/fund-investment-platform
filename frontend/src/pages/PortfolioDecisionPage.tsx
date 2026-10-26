import {
  Alert,
  Button,
  Group,
  Stack,
  Tabs,
  Text,
  TextInput,
} from "@mantine/core";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams, useParams } from "react-router-dom";

import {
  getDecision,
  getOptimization,
  getOperation,
  getPortfolio,
  getSession,
  listPortfolios,
  reviewDecision,
  submitOptimization,
} from "../api/generated/m17";
import type {
  Decision,
  DecisionMeta,
  DecisionReviewRequest,
  DecisionReviewOutcomeEnvelope,
  OptimizationMeta,
  OptimizationRequest,
  Portfolio,
  PortfolioListMeta,
  ResponseMeta,
  Session,
} from "../api/generated/m17.schemas";
import {
  normalizeOptimization,
  unwrapResponse,
  withIdempotencyKey,
} from "../api/http";
import { queryKeys } from "../api/queries";
import { ErrorState } from "../components/ErrorState";
import { OperationProgress } from "../components/OperationProgress";
import { PageHeader } from "../components/PageHeader";
import { ProvenanceBar } from "../components/ProvenanceBar";
import { WorkbenchPanels } from "../components/WorkbenchPanels";
import { DecisionReviewPanel } from "../features/portfolio/DecisionReviewPanel";
import { LivePortfolioPanel } from "../features/portfolio/LivePortfolioPanel";
import { OptimizationForm } from "../features/portfolio/OptimizationForm";
import { OptimizationResult } from "../features/portfolio/OptimizationResult";
import { PortfolioList } from "../features/portfolio/PortfolioList";
import { PortfolioOverview } from "../features/portfolio/PortfolioOverview";
import { RebalancingPanel } from "../features/portfolio/RebalancingPanel";

type Props = { pollIntervalMs?: number };

const provenanceMeta = (meta: ResponseMeta) => ({
  versions: meta.versions,
  is_point_in_time: meta.is_point_in_time,
  availability_quality_distribution: meta.availability_quality_distribution,
});

const PortfolioIndex = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, Number(searchParams.get("page") || "1"));
  const pageSize = Math.max(1, Number(searchParams.get("page_size") || "20"));
  const sort = searchParams.get("sort") || "portfolio_name";
  const order = searchParams.get("order") === "desc" ? "desc" : "asc";
  const query = useQuery({
    queryKey: queryKeys.portfolios({ page, page_size: pageSize, sort, order }),
    queryFn: async () => {
      const response = await listPortfolios({
        page,
        page_size: pageSize,
        sort,
        order,
      });
      return {
        data: unwrapResponse(response, {
          requiredMeta: ["versions", "is_point_in_time", "pagination"],
        }),
        meta: response.data.meta as PortfolioListMeta,
      };
    },
    placeholderData: keepPreviousData,
  });
  const changePage = (nextPage: number) => {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(nextPage));
    next.set("page_size", String(pageSize));
    next.set("sort", sort);
    next.set("order", order);
    setSearchParams(next);
  };

  return (
    <Stack gap="lg">
      <PageHeader
        title="组合决策"
        breadcrumbs={[{ label: "组合决策" }]}
        context={
          <Text size="sm" c="dimmed">
            当前身份有权访问的组合。
          </Text>
        }
      />
      {query.isPending && <p role="status">正在加载组合…</p>}
      {query.isFetching && query.data && (
        <Text role="status" size="sm" c="dimmed">
          正在更新组合列表；保留上一次结果。
        </Text>
      )}
      {query.isError && (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      )}
      {query.data && (
        <Stack gap="md">
          <ProvenanceBar meta={provenanceMeta(query.data.meta)} />
          {query.data.data.length > 0 ? (
            <>
              <PortfolioList portfolios={query.data.data} />
              <nav aria-label="组合列表分页">
                <Group justify="space-between" wrap="wrap">
                  <Button
                    variant="default"
                    disabled={query.data.meta.pagination.page <= 1}
                    onClick={() =>
                      changePage(query.data.meta.pagination.page - 1)
                    }
                  >
                    上一页
                  </Button>
                  <Text size="sm">
                    第 {query.data.meta.pagination.page} /{" "}
                    {query.data.meta.pagination.total_pages} 页，共{" "}
                    {query.data.meta.pagination.total_items} 个组合
                  </Text>
                  <Button
                    variant="default"
                    disabled={
                      query.data.meta.pagination.page >=
                      query.data.meta.pagination.total_pages
                    }
                    onClick={() =>
                      changePage(query.data.meta.pagination.page + 1)
                    }
                  >
                    下一页
                  </Button>
                </Group>
              </nav>
            </>
          ) : (
            <p>当前用户没有可见组合。</p>
          )}
        </Stack>
      )}
    </Stack>
  );
};

const optimizationRef = (resultRef: string | null, portfolioId: string) => {
  if (!resultRef) return undefined;
  const match = resultRef.match(
    /^\/api\/v1\/portfolios\/([^/]+)\/optimizations\/([^/?#]+)$/,
  );
  if (!match || decodeURIComponent(match[1]) !== portfolioId) return undefined;
  return decodeURIComponent(match[2]);
};

const newIdempotencyKey = () => globalThis.crypto.randomUUID();

const PortfolioDetail = ({
  portfolioId,
  pollIntervalMs,
}: {
  portfolioId: string;
  pollIntervalMs: number;
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const operationId = searchParams.get("operation_id") ?? undefined;
  const submittedOptimizationId =
    searchParams.get("optimization_id") ?? undefined;
  const [decisionInput, setDecisionInput] = useState(
    searchParams.get("decision_id") ?? "",
  );
  const decisionId = searchParams.get("decision_id") ?? undefined;
  const tabValue = searchParams.get("tab");
  const activeTab: "optimization" | "decision" | "live" | "rebalance" =
    tabValue === "decision" || tabValue === "live" || tabValue === "rebalance"
      ? tabValue
      : "optimization";
  const selectTab = (value: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (value && value !== "optimization") next.set("tab", value);
    else next.delete("tab");
    setSearchParams(next);
  };
  const optimizationKey = useRef<string>();

  useEffect(() => {
    setDecisionInput(searchParams.get("decision_id") ?? "");
  }, [searchParams]);

  const portfolioQuery = useQuery({
    queryKey: queryKeys.portfolio(portfolioId),
    queryFn: async () => {
      const response = await getPortfolio(portfolioId);
      return {
        data: unwrapResponse(response) as Portfolio,
        meta: response.data.meta as ResponseMeta,
      };
    },
  });

  const sessionQuery = useQuery({
    queryKey: queryKeys.session,
    queryFn: async () => unwrapResponse(await getSession()) as Session,
  });

  const submitMutation = useMutation({
    mutationFn: async (request: OptimizationRequest) => {
      optimizationKey.current ??= newIdempotencyKey();
      return unwrapResponse(
        await submitOptimization(
          portfolioId,
          request,
          withIdempotencyKey(optimizationKey.current),
        ),
      );
    },
    onSuccess: (submission) => {
      optimizationKey.current = undefined;
      const next = new URLSearchParams(searchParams);
      next.set("operation_id", submission.operation_id);
      next.set("optimization_id", submission.optimization_id);
      next.delete("tab");
      setSearchParams(next);
    },
  });

  const operationQuery = useQuery({
    queryKey: queryKeys.operation(operationId ?? ""),
    enabled: Boolean(operationId),
    queryFn: async () => unwrapResponse(await getOperation(operationId ?? "")),
    refetchInterval: (query) =>
      query.state.data?.status === "RUNNING" ? pollIntervalMs : false,
  });

  const resultOptimizationId = useMemo(() => {
    if (operationQuery.data?.status !== "COMPLETED") return undefined;
    return (
      optimizationRef(operationQuery.data.result_ref, portfolioId) ??
      (operationQuery.data.result_ref === null
        ? submittedOptimizationId
        : undefined)
    );
  }, [operationQuery.data, portfolioId, submittedOptimizationId]);

  const optimizationQuery = useQuery({
    queryKey: queryKeys.optimization(portfolioId, resultOptimizationId ?? ""),
    enabled: Boolean(resultOptimizationId),
    queryFn: async () => {
      const response = await getOptimization(
        portfolioId,
        resultOptimizationId ?? "",
      );
      return {
        data: normalizeOptimization(unwrapResponse(response)),
        meta: response.data.meta as OptimizationMeta,
      };
    },
  });

  const decisionQuery = useQuery({
    queryKey: queryKeys.decision(decisionId ?? ""),
    enabled: Boolean(decisionId),
    queryFn: async () => {
      const response = await getDecision(decisionId ?? "");
      return {
        data: unwrapResponse(response) as Decision,
        meta: response.data.meta as DecisionMeta,
      };
    },
  });

  const reviewMutation = useMutation({
    mutationFn: async ({
      reviewedDecisionId,
      request,
    }: {
      reviewedDecisionId: string;
      request: DecisionReviewRequest;
    }): Promise<DecisionReviewOutcomeEnvelope> => {
      const response = await reviewDecision(reviewedDecisionId, request);
      return {
        data: unwrapResponse(response, { requiredMeta: ["audit_id"] }),
        meta: response.data.meta as DecisionReviewOutcomeEnvelope["meta"],
        error: null,
      };
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.decision(decisionId ?? ""),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.portfolio(portfolioId),
        }),
      ]);
    },
  });

  if (portfolioQuery.isPending) return <p role="status">正在加载组合…</p>;
  if (portfolioQuery.isError)
    return <ErrorState error={portfolioQuery.error} />;

  const decision = decisionQuery.data?.data;
  const reviewIsCurrent =
    reviewMutation.variables?.reviewedDecisionId === decisionId;
  const reviewResult =
    reviewIsCurrent && reviewMutation.data?.data.decision_id === decisionId
      ? reviewMutation.data
      : undefined;
  const canReview =
    sessionQuery.data?.capabilities.can_review_decisions === true;

  return (
    <Stack gap="lg">
      <PageHeader
        title={portfolioQuery.data.data.portfolio_name}
        breadcrumbs={[
          { label: "组合决策", href: "/portfolios" },
          { label: portfolioQuery.data.data.portfolio_name },
        ]}
        actions={
          <Button component={Link} to="/portfolios" variant="default">
            返回组合列表
          </Button>
        }
      />
      <PortfolioOverview portfolio={portfolioQuery.data.data} />
      <ProvenanceBar meta={provenanceMeta(portfolioQuery.data.meta)} />

      <Tabs value={activeTab} onChange={selectTab} keepMounted={false}>
        <Tabs.List aria-label="组合功能">
          <Tabs.Tab value="optimization">组合优化</Tabs.Tab>
          <Tabs.Tab value="decision">决策复核</Tabs.Tab>
          <Tabs.Tab value="live">实盘持仓</Tabs.Tab>
          <Tabs.Tab value="rebalance">再平衡</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="optimization" pt="md">
          <WorkbenchPanels
            layoutKey="portfolio"
            primaryLabel="优化配置"
            secondaryLabel="优化结果"
            primary={
              <Stack gap="md">
                <OptimizationForm
                  portfolioRuleVersion={
                    portfolioQuery.data.data.portfolio_rule_version
                  }
                  pending={submitMutation.isPending}
                  onSubmit={(request) => submitMutation.mutate(request)}
                />
                {submitMutation.error && (
                  <ErrorState error={submitMutation.error} />
                )}
                {operationId && (
                  <OperationProgress
                    operationId={operationId}
                    resultRef={operationQuery.data?.result_ref}
                    pollIntervalMs={pollIntervalMs}
                  />
                )}
                {operationQuery.error && (
                  <ErrorState
                    error={operationQuery.error}
                    onRetry={() => void operationQuery.refetch()}
                  />
                )}
              </Stack>
            }
            secondary={
              <Stack gap="md">
                {operationQuery.data?.status === "COMPLETED" &&
                  operationQuery.data.result_ref &&
                  !resultOptimizationId && (
                    <Alert color="red" title="结果关联错误">
                      优化结果引用与当前组合不匹配。
                    </Alert>
                  )}
                {optimizationQuery.isPending && resultOptimizationId && (
                  <Text role="status">正在读取优化结果…</Text>
                )}
                {optimizationQuery.error && (
                  <ErrorState
                    error={optimizationQuery.error}
                    onRetry={() => void optimizationQuery.refetch()}
                  />
                )}
                {optimizationQuery.data && (
                  <OptimizationResult
                    optimization={optimizationQuery.data.data}
                    meta={optimizationQuery.data.meta}
                  />
                )}
                {!resultOptimizationId && (
                  <Text c="dimmed">提交并完成优化后，结果会显示在此处。</Text>
                )}
              </Stack>
            }
          />
        </Tabs.Panel>

        <Tabs.Panel value="decision" pt="md">
          <Stack gap="md">
            <Alert color="blue" variant="light" title="打开已有决策">
              当前优化结果契约没有返回关联的 decision_id；请使用已有决策 ID
              打开真实决策。服务端仍负责资源授权。
            </Alert>
            <Group align="flex-end" wrap="wrap" aria-label="决策查询">
              <TextInput
                label="决策 ID"
                value={decisionInput}
                onChange={(event) =>
                  setDecisionInput(event.currentTarget.value)
                }
              />
              <Button
                disabled={!decisionInput.trim()}
                onClick={() => {
                  const nextDecisionId = decisionInput.trim();
                  if (nextDecisionId !== decisionId) reviewMutation.reset();
                  const next = new URLSearchParams(searchParams);
                  next.set("decision_id", nextDecisionId);
                  setSearchParams(next);
                }}
              >
                加载决策
              </Button>
            </Group>
            {sessionQuery.isPending && (
              <Text role="status">正在校验复核权限…</Text>
            )}
            {sessionQuery.error && (
              <ErrorState
                error={sessionQuery.error}
                onRetry={() => void sessionQuery.refetch()}
              />
            )}
            {sessionQuery.data && !canReview && (
              <Alert color="yellow">当前会话没有决策复核权限。</Alert>
            )}
            {decisionQuery.isPending && decisionId && (
              <Text role="status">正在读取决策…</Text>
            )}
            {decisionQuery.error && (
              <ErrorState
                error={decisionQuery.error}
                onRetry={() => void decisionQuery.refetch()}
              />
            )}
            {decision && (
              <>
                {decisionQuery.data?.meta && (
                  <ProvenanceBar
                    meta={provenanceMeta(decisionQuery.data.meta)}
                  />
                )}
                <DecisionReviewPanel
                  key={decision.decision_id}
                  decision={decision}
                  reviewResult={reviewResult}
                  reviewAction={
                    reviewIsCurrent
                      ? reviewMutation.variables?.request.action
                      : undefined
                  }
                  canReview={canReview}
                  pending={reviewIsCurrent && reviewMutation.isPending}
                  error={reviewIsCurrent ? reviewMutation.error : null}
                  onReview={(request) =>
                    reviewMutation.mutate({
                      reviewedDecisionId: decision.decision_id,
                      request,
                    })
                  }
                />
              </>
            )}
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="live" pt="md">
          <LivePortfolioPanel portfolioId={portfolioId} />
        </Tabs.Panel>
        <Tabs.Panel value="rebalance" pt="md">
          <RebalancingPanel portfolioId={portfolioId} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
};

export const PortfolioDecisionPage = ({ pollIntervalMs = 1000 }: Props) => {
  const { portfolioId } = useParams();
  return portfolioId ? (
    <PortfolioDetail
      portfolioId={portfolioId}
      pollIntervalMs={pollIntervalMs}
    />
  ) : (
    <PortfolioIndex />
  );
};

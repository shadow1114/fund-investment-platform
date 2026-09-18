import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

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
import { ProvenanceBar } from "../components/ProvenanceBar";
import { DecisionReviewPanel } from "../features/portfolio/DecisionReviewPanel";
import { OptimizationForm } from "../features/portfolio/OptimizationForm";
import { OptimizationResult } from "../features/portfolio/OptimizationResult";
import { PortfolioList } from "../features/portfolio/PortfolioList";
import { PortfolioOverview } from "../features/portfolio/PortfolioOverview";

type Props = { pollIntervalMs?: number };

const provenanceMeta = (meta: ResponseMeta) => ({
  versions: meta.versions,
  is_point_in_time: meta.is_point_in_time,
  availability_quality_distribution: meta.availability_quality_distribution,
});

const PortfolioIndex = () => {
  const query = useQuery({
    queryKey: queryKeys.portfolios(),
    queryFn: async () => {
      const response = await listPortfolios();
      return {
        data: unwrapResponse(response, {
          requiredMeta: ["versions", "is_point_in_time", "pagination"],
        }),
        meta: response.data.meta as PortfolioListMeta,
      };
    },
  });

  return (
    <section>
      <h1>组合决策</h1>
      {query.isPending && <p role="status">正在加载组合…</p>}
      {query.isError && <ErrorState error={query.error} />}
      {query.data && (
        <>
          <ProvenanceBar meta={provenanceMeta(query.data.meta)} />
          {query.data.data.length > 0 ? (
            <PortfolioList portfolios={query.data.data} />
          ) : (
            <p>当前用户没有可见组合。</p>
          )}
        </>
      )}
    </section>
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
  const queryClient = useQueryClient();
  const [operationId, setOperationId] = useState<string>();
  const [submittedOptimizationId, setSubmittedOptimizationId] =
    useState<string>();
  const [decisionInput, setDecisionInput] = useState("");
  const [decisionId, setDecisionId] = useState<string>();

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
    mutationFn: async (request: OptimizationRequest) =>
      unwrapResponse(
        await submitOptimization(
          portfolioId,
          request,
          withIdempotencyKey(newIdempotencyKey()),
        ),
      ),
    onSuccess: (submission) => {
      setOperationId(submission.operation_id);
      setSubmittedOptimizationId(submission.optimization_id);
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
    mutationFn: async (request: DecisionReviewRequest) =>
      unwrapResponse(
        await reviewDecision(decisionId ?? "", request),
      ) as Decision,
    onSuccess: (decision) => {
      queryClient.setQueryData(queryKeys.decision(decision.decision_id), {
        data: decision,
        meta: decisionQuery.data?.meta,
      });
    },
  });

  if (portfolioQuery.isPending) return <p role="status">正在加载组合…</p>;
  if (portfolioQuery.isError)
    return <ErrorState error={portfolioQuery.error} />;

  const decision = reviewMutation.data ?? decisionQuery.data?.data;
  const canReview =
    sessionQuery.data?.capabilities.can_review_decisions === true;

  return (
    <section>
      <Link to="/portfolios">返回组合列表</Link>
      <PortfolioOverview portfolio={portfolioQuery.data.data} />
      <ProvenanceBar meta={provenanceMeta(portfolioQuery.data.meta)} />
      <OptimizationForm
        portfolioRuleVersion={portfolioQuery.data.data.portfolio_rule_version}
        pending={submitMutation.isPending}
        onSubmit={(request) => submitMutation.mutate(request)}
      />
      {submitMutation.error && <ErrorState error={submitMutation.error} />}
      {operationId && (
        <OperationProgress
          operationId={operationId}
          resultRef={operationQuery.data?.result_ref}
          pollIntervalMs={pollIntervalMs}
        />
      )}
      {operationQuery.error && <ErrorState error={operationQuery.error} />}
      {operationQuery.data?.status === "COMPLETED" &&
        operationQuery.data.result_ref &&
        !resultOptimizationId && (
          <p role="alert">优化结果引用与当前组合不匹配。</p>
        )}
      {optimizationQuery.isPending && resultOptimizationId && (
        <p role="status">正在读取优化结果…</p>
      )}
      {optimizationQuery.error && (
        <ErrorState error={optimizationQuery.error} />
      )}
      {optimizationQuery.data && (
        <OptimizationResult
          optimization={optimizationQuery.data.data}
          meta={optimizationQuery.data.meta}
        />
      )}

      <section aria-label="决策查询">
        <h2>读取决策快照</h2>
        <label>
          决策 ID
          <input
            value={decisionInput}
            onChange={(event) => setDecisionInput(event.target.value)}
          />
        </label>
        <button
          disabled={!decisionInput.trim()}
          onClick={() => setDecisionId(decisionInput.trim())}
        >
          加载决策
        </button>
      </section>
      {sessionQuery.isPending && <p role="status">正在校验复核权限…</p>}
      {sessionQuery.error && <ErrorState error={sessionQuery.error} />}
      {sessionQuery.data && !canReview && <p>当前会话无决策复核权限。</p>}
      {decisionQuery.isPending && decisionId && (
        <p role="status">正在读取决策…</p>
      )}
      {decisionQuery.error && <ErrorState error={decisionQuery.error} />}
      {decision && (
        <>
          {decisionQuery.data?.meta && (
            <ProvenanceBar meta={provenanceMeta(decisionQuery.data.meta)} />
          )}
          <DecisionReviewPanel
            decision={decision}
            canReview={canReview}
            pending={reviewMutation.isPending}
            error={reviewMutation.error}
            onReview={(request) => reviewMutation.mutate(request)}
          />
        </>
      )}
    </section>
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

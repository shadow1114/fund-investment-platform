import { useMutation, useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useRef, useState } from "react";
import {
  Alert,
  Button,
  Group,
  SegmentedControl,
  Stack,
  Text,
} from "@mantine/core";
import { useSearchParams } from "react-router-dom";

import {
  createBacktest,
  getBacktestBiasCheck,
  getBacktestPerformance,
  getBacktestResult,
  getBacktestStatus,
  getOperation,
  runBacktest,
  validateBacktest,
} from "../api/generated/m17";
import type {
  BacktestBiasCheck,
  BacktestCreateRequest,
  BacktestPerformance,
  BacktestResult,
  BacktestResultMeta,
  BacktestStatus,
  BacktestValidation as BacktestValidationData,
} from "../api/generated/m17.schemas";
import { unwrapResponse, withIdempotencyKey } from "../api/http";
import { queryKeys } from "../api/queries";
import { ErrorState } from "../components/ErrorState";
import { OperationProgress } from "../components/OperationProgress";
import { PageHeader } from "../components/PageHeader";
import { ProvenanceBar } from "../components/ProvenanceBar";
import { WorkbenchPanels } from "../components/WorkbenchPanels";
import { BacktestForm } from "../features/backtest/BacktestForm";
import { BacktestProgress } from "../features/backtest/BacktestProgress";
import { BacktestSummary } from "../features/backtest/BacktestSummary";
import { BacktestValidation } from "../features/backtest/BacktestValidation";
import { BiasCheckPanel } from "../features/backtest/BiasCheckPanel";

const BacktestPerformanceChart = lazy(() =>
  import("../features/backtest/BacktestPerformanceChart").then((module) => ({
    default: module.BacktestPerformanceChart,
  })),
);

type Props = { pollIntervalMs?: number };
const activeBacktestStatuses = new Set([
  "VALIDATING_CONFIGURATION",
  "RUNNING",
  "VALIDATING_RESULTS",
]);
const inspectableBacktestStatuses = new Set([
  "COMPLETED",
  "INVALID",
  "ABORTED",
]);
const newIdempotencyKey = () => globalThis.crypto.randomUUID();

const isPerformance = (value: unknown): value is BacktestPerformance => {
  if (!value || typeof value !== "object" || !("series" in value)) return false;
  const series = value.series;
  return Boolean(
    series &&
    typeof series === "object" &&
    "cumulative_return" in series &&
    "portfolio_value" in series &&
    Array.isArray(series.portfolio_value),
  );
};

const isBiasCheck = (value: unknown): value is BacktestBiasCheck =>
  Boolean(
    value &&
    typeof value === "object" &&
    "checks" in value &&
    "snapshot_summary" in value &&
    "data_limitations" in value,
  );

export const BacktestPage = ({ pollIntervalMs = 1000 }: Props) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const backtestId = searchParams.get("backtest_id") ?? undefined;
  const operationId = searchParams.get("operation_id") ?? undefined;
  const rawSegment = searchParams.get("segment");
  const performanceSegment =
    rawSegment === "IN_SAMPLE" || rawSegment === "OUT_OF_SAMPLE"
      ? rawSegment
      : "FULL";
  const [validation, setValidation] = useState<BacktestValidationData>();
  const [formGeneration, setFormGeneration] = useState(0);
  const runKeys = useRef(new Map<string, string>());

  const createMutation = useMutation({
    mutationFn: async (request: BacktestCreateRequest) =>
      unwrapResponse(await createBacktest(request)),
    onSuccess: (created) => {
      setValidation(undefined);
      const next = new URLSearchParams(searchParams);
      next.set("backtest_id", created.backtest_id);
      next.delete("operation_id");
      setSearchParams(next);
    },
  });

  const validationMutation = useMutation({
    mutationFn: async (id: string) =>
      unwrapResponse(await validateBacktest(id)) as BacktestValidationData,
    onSuccess: setValidation,
  });

  const runMutation = useMutation({
    mutationFn: async (id: string) => {
      const key = runKeys.current.get(id) ?? newIdempotencyKey();
      runKeys.current.set(id, key);
      return unwrapResponse(await runBacktest(id, withIdempotencyKey(key)));
    },
    onSuccess: (run) => {
      runKeys.current.delete(run.backtest_id);
      const next = new URLSearchParams(searchParams);
      next.set("backtest_id", run.backtest_id);
      next.set("operation_id", run.operation_id);
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

  const statusQuery = useQuery({
    queryKey: queryKeys.backtestStatus(backtestId ?? ""),
    enabled: Boolean(backtestId),
    queryFn: async () =>
      unwrapResponse(
        await getBacktestStatus(backtestId ?? ""),
      ) as BacktestStatus,
    refetchInterval: (query) =>
      query.state.data && activeBacktestStatuses.has(query.state.data.status)
        ? pollIntervalMs
        : false,
  });

  const canInspect = Boolean(
    backtestId &&
    statusQuery.data &&
    inspectableBacktestStatuses.has(statusQuery.data.status),
  );
  const resultQuery = useQuery({
    queryKey: queryKeys.backtestResult(backtestId ?? ""),
    enabled: canInspect,
    queryFn: async () => {
      const response = await getBacktestResult(backtestId ?? "");
      return {
        data: unwrapResponse(response) as BacktestResult,
        meta: response.data.meta as BacktestResultMeta,
      };
    },
  });
  const performanceQuery = useQuery({
    queryKey: queryKeys.backtestPerformance(backtestId ?? "", {
      segment: performanceSegment,
    }),
    enabled: canInspect,
    queryFn: async () => {
      const value: unknown = unwrapResponse(
        await getBacktestPerformance(backtestId ?? "", {
          segment: performanceSegment,
        }),
      );
      return isPerformance(value) ? value : null;
    },
  });
  const biasQuery = useQuery({
    queryKey: queryKeys.backtestBiasCheck(backtestId ?? ""),
    enabled: canInspect,
    queryFn: async () => {
      const value: unknown = unwrapResponse(
        await getBacktestBiasCheck(backtestId ?? ""),
      );
      return isBiasCheck(value) ? value : null;
    },
  });

  const resetBacktest = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("backtest_id");
    next.delete("operation_id");
    setSearchParams(next);
    setValidation(undefined);
    validationMutation.reset();
    createMutation.reset();
    runMutation.reset();
    setFormGeneration((value) => value + 1);
  };

  return (
    <Stack gap="lg">
      <PageHeader
        title="回测分析"
        breadcrumbs={[{ label: "回测分析" }]}
        context={
          <Text size="sm" c="dimmed">
            回测 ID 与操作 ID 保存在 URL；刷新后重新读取服务端状态。
          </Text>
        }
      />
      {!backtestId ? (
        <Stack gap="md">
          {operationId && (
            <Alert color="yellow">
              URL 缺少 backtest_id，无法验证操作与回测资源的关联。
            </Alert>
          )}
          <BacktestForm
            key={formGeneration}
            pending={createMutation.isPending}
            onSubmit={(request) => createMutation.mutate(request)}
          />
          {createMutation.error && <ErrorState error={createMutation.error} />}
        </Stack>
      ) : (
        <WorkbenchPanels
          layoutKey="backtest"
          primaryLabel="回测配置与任务"
          secondaryLabel="回测结果"
          primary={
            <Stack gap="md">
              <Group justify="space-between" wrap="wrap">
                <Text fw={600}>回测 {backtestId}</Text>
                <Button
                  variant="default"
                  disabled={runMutation.isPending}
                  onClick={resetBacktest}
                >
                  新建回测
                </Button>
              </Group>
              <Alert color="blue" variant="light">
                配置以服务端回测资源为准。当前 API
                未提供配置读取端点；此页面不会用空表单重建或覆盖已有配置。
              </Alert>
              <Group>
                <Button
                  variant="default"
                  disabled={
                    validationMutation.isPending || Boolean(operationId)
                  }
                  loading={validationMutation.isPending}
                  onClick={() => validationMutation.mutate(backtestId)}
                >
                  校验配置
                </Button>
                <Button
                  disabled={
                    !validation ||
                    validation.blocking_issues.length > 0 ||
                    runMutation.isPending ||
                    Boolean(operationId)
                  }
                  loading={runMutation.isPending}
                  onClick={() => runMutation.mutate(backtestId)}
                >
                  启动回测
                </Button>
              </Group>
              {validation && <BacktestValidation validation={validation} />}
              {validationMutation.error && (
                <ErrorState error={validationMutation.error} />
              )}
              {runMutation.error && <ErrorState error={runMutation.error} />}
              {operationId && (
                <OperationProgress
                  operationId={operationId}
                  resultRef={operationQuery.data?.result_ref}
                  pollIntervalMs={pollIntervalMs}
                />
              )}
              {statusQuery.data && (
                <BacktestProgress status={statusQuery.data} />
              )}
              {operationQuery.error && (
                <ErrorState
                  error={operationQuery.error}
                  onRetry={() => void operationQuery.refetch()}
                />
              )}
              {statusQuery.error && (
                <ErrorState
                  error={statusQuery.error}
                  onRetry={() => void statusQuery.refetch()}
                />
              )}
              {resultQuery.error && (
                <ErrorState
                  error={resultQuery.error}
                  onRetry={() => void resultQuery.refetch()}
                />
              )}
              {performanceQuery.error && (
                <ErrorState
                  error={performanceQuery.error}
                  onRetry={() => void performanceQuery.refetch()}
                />
              )}
              {biasQuery.error && (
                <ErrorState
                  error={biasQuery.error}
                  onRetry={() => void biasQuery.refetch()}
                />
              )}
            </Stack>
          }
          secondary={
            <Stack gap="md">
              {resultQuery.data && (
                <>
                  <ProvenanceBar meta={resultQuery.data.meta} />
                  <Text size="sm">
                    成本模型：
                    {resultQuery.data.meta.transaction_cost_model_version} ·
                    配置：{resultQuery.data.meta.configuration_version} · 代码：
                    {resultQuery.data.meta.code_version}
                  </Text>
                  <BacktestSummary result={resultQuery.data.data} />
                </>
              )}
              {canInspect && performanceQuery.data && (
                <Stack gap="sm">
                  <Text size="sm">绩效区间</Text>
                  <SegmentedControl
                    value={performanceSegment}
                    data={[
                      { value: "FULL", label: "完整区间" },
                      { value: "IN_SAMPLE", label: "样本内" },
                      { value: "OUT_OF_SAMPLE", label: "样本外" },
                    ]}
                    onChange={(segment) => {
                      const next = new URLSearchParams(searchParams);
                      if (segment === "FULL") next.delete("segment");
                      else next.set("segment", segment);
                      setSearchParams(next);
                    }}
                  />
                  <Suspense
                    fallback={<Text role="status">正在加载绩效图表…</Text>}
                  >
                    <BacktestPerformanceChart
                      performance={performanceQuery.data}
                    />
                  </Suspense>
                </Stack>
              )}
              {canInspect && performanceQuery.data === null && (
                <Alert color="yellow" title="绩效序列不可用">
                  当前后端性能接口返回空结果，不能展示净值、收益或回撤图表。
                </Alert>
              )}
              {canInspect && biasQuery.data && (
                <BiasCheckPanel bias={biasQuery.data} />
              )}
              {canInspect && biasQuery.data === null && (
                <Alert color="yellow" title="偏差检查不可用">
                  当前后端偏差检查接口返回空结果，不能据此判断回测通过。
                </Alert>
              )}
              {!canInspect && (
                <Text c="dimmed">
                  完成回测并由服务端确认终态后，结果会显示在此处。
                </Text>
              )}
            </Stack>
          }
        />
      )}
    </Stack>
  );
};

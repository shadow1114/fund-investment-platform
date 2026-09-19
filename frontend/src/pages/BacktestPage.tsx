import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

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
import { ProvenanceBar } from "../components/ProvenanceBar";
import { BacktestForm } from "../features/backtest/BacktestForm";
import { BacktestPerformanceChart } from "../features/backtest/BacktestPerformanceChart";
import { BacktestProgress } from "../features/backtest/BacktestProgress";
import { BacktestSummary } from "../features/backtest/BacktestSummary";
import { BacktestValidation } from "../features/backtest/BacktestValidation";
import { BiasCheckPanel } from "../features/backtest/BiasCheckPanel";

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

export const BacktestPage = ({ pollIntervalMs = 1000 }: Props) => {
  const [backtestId, setBacktestId] = useState<string>();
  const [validation, setValidation] = useState<BacktestValidationData>();
  const [operationId, setOperationId] = useState<string>();

  const createMutation = useMutation({
    mutationFn: async (request: BacktestCreateRequest) =>
      unwrapResponse(await createBacktest(request)),
    onSuccess: (created) => {
      setBacktestId(created.backtest_id);
      setValidation(undefined);
      setOperationId(undefined);
    },
  });

  const validationMutation = useMutation({
    mutationFn: async (id: string) =>
      unwrapResponse(await validateBacktest(id)) as BacktestValidationData,
    onSuccess: setValidation,
  });

  const runMutation = useMutation({
    mutationFn: async (id: string) =>
      unwrapResponse(
        await runBacktest(id, withIdempotencyKey(newIdempotencyKey())),
      ),
    onSuccess: (run) => setOperationId(run.operation_id),
  });

  const operationQuery = useQuery({
    queryKey: queryKeys.operation(operationId ?? ""),
    enabled: Boolean(operationId),
    queryFn: async () => unwrapResponse(await getOperation(operationId ?? "")),
    refetchInterval: (query) =>
      query.state.data?.status === "RUNNING" ? pollIntervalMs : false,
  });

  const operationFinished = operationQuery.data?.status === "COMPLETED";
  const statusQuery = useQuery({
    queryKey: queryKeys.backtestStatus(backtestId ?? ""),
    enabled: Boolean(backtestId && operationFinished),
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
      segment: "FULL",
    }),
    enabled: canInspect,
    queryFn: async () =>
      unwrapResponse(
        await getBacktestPerformance(backtestId ?? "", { segment: "FULL" }),
      ) as BacktestPerformance,
  });
  const biasQuery = useQuery({
    queryKey: queryKeys.backtestBiasCheck(backtestId ?? ""),
    enabled: canInspect,
    queryFn: async () =>
      unwrapResponse(
        await getBacktestBiasCheck(backtestId ?? ""),
      ) as BacktestBiasCheck,
  });

  const errors = useMemo(
    () =>
      [
        createMutation.error,
        validationMutation.error,
        runMutation.error,
        operationQuery.error,
        statusQuery.error,
        resultQuery.error,
        performanceQuery.error,
        biasQuery.error,
      ].filter((error): error is Error => error instanceof Error),
    [
      biasQuery.error,
      createMutation.error,
      operationQuery.error,
      performanceQuery.error,
      resultQuery.error,
      runMutation.error,
      statusQuery.error,
      validationMutation.error,
    ],
  );

  return (
    <section>
      <h1>回测</h1>
      <BacktestForm
        disabled={Boolean(backtestId)}
        pending={createMutation.isPending}
        onSubmit={(request) => createMutation.mutate(request)}
      />
      {backtestId && <p>已创建回测 {backtestId}，尚未执行。</p>}
      <div>
        <button
          disabled={
            !backtestId || validationMutation.isPending || Boolean(operationId)
          }
          onClick={() => backtestId && validationMutation.mutate(backtestId)}
        >
          {validationMutation.isPending ? "校验中…" : "校验配置"}
        </button>
        <button
          disabled={
            !backtestId ||
            !validation ||
            validation.blocking_issues.length > 0 ||
            runMutation.isPending ||
            Boolean(operationId)
          }
          onClick={() => backtestId && runMutation.mutate(backtestId)}
        >
          {runMutation.isPending ? "启动中…" : "启动回测"}
        </button>
      </div>

      {validation && <BacktestValidation validation={validation} />}
      {operationId && (
        <OperationProgress
          operationId={operationId}
          resultRef={operationQuery.data?.result_ref}
          pollIntervalMs={pollIntervalMs}
        />
      )}
      {statusQuery.data && <BacktestProgress status={statusQuery.data} />}
      {errors.map((error, index) => (
        <ErrorState key={`${error.message}-${index}`} error={error} />
      ))}

      {resultQuery.data && (
        <>
          <ProvenanceBar meta={resultQuery.data.meta} />
          <p>
            transaction_cost_model_version:{" "}
            {resultQuery.data.meta.transaction_cost_model_version}
          </p>
          <p>
            配置版本：{resultQuery.data.meta.configuration_version}；代码版本：
            {resultQuery.data.meta.code_version}
          </p>
          <BacktestSummary result={resultQuery.data.data} />
        </>
      )}
      {performanceQuery.data && (
        <BacktestPerformanceChart performance={performanceQuery.data} />
      )}
      {biasQuery.data && <BiasCheckPanel bias={biasQuery.data} />}
    </section>
  );
};

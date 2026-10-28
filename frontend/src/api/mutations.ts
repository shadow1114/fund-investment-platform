import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import {
  submitScopedFundIngestion,
  cancelFundIngestion,
  retryFundIngestionFailures,
  createBacktest,
  submitFundIngestion,
  submitFundIngestionBatch,
  reviewDecision,
  runBacktest,
  submitOptimization,
  validateBacktest,
} from "./generated/m17";
import type {
  BacktestCreateRequest,
  DecisionReviewRequest,
  FundIngestionRequest,
  FundIngestionBatchRequest,
  OptimizationRequest,
} from "./generated/m17.schemas";
import { unwrapResponse, withIdempotencyKey } from "./http";
import { ingestionKeys, queryKeys } from "./queries";

export type SubmitOptimizationVariables = {
  portfolioId: string;
  request: OptimizationRequest;
  idempotencyKey: string;
};

export function useSubmitOptimization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      portfolioId,
      request,
      idempotencyKey,
    }: SubmitOptimizationVariables) =>
      unwrapResponse(
        await submitOptimization(
          portfolioId,
          request,
          withIdempotencyKey(idempotencyKey),
        ),
      ),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.portfolio(variables.portfolioId),
      });
    },
  });
}

export function useSubmitFundIngestion() {
  const queryClient = useQueryClient();
  const idempotencyKeys = useRef(new Map<string, string>());
  return useMutation({
    mutationFn: async ({
      fundId,
      request,
    }: {
      fundId: string;
      request: FundIngestionRequest;
    }) => {
      const key = `${fundId}:${request.dataset}`;
      const idempotencyKey =
        idempotencyKeys.current.get(key) ?? globalThis.crypto.randomUUID();
      idempotencyKeys.current.set(key, idempotencyKey);
      return unwrapResponse(
        await submitFundIngestion(
          fundId,
          request,
          withIdempotencyKey(idempotencyKey),
        ),
      );
    },
    onSuccess: async (_data, variables) => {
      idempotencyKeys.current.delete(
        `${variables.fundId}:${variables.request.dataset}`,
      );
      await queryClient.invalidateQueries({
        queryKey: queryKeys.fundIngestions(variables.fundId),
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.fund(variables.fundId),
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.funds() });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.fundBasicInfoHistory(variables.fundId),
      });
    },
  });
}

export function useSubmitFundIngestionBatch() {
  const queryClient = useQueryClient();
  const idempotencyKeys = useRef(new Map<string, string>());
  return useMutation({
    mutationFn: async (request: FundIngestionBatchRequest) => {
      const key = `${request.dataset}:${[...request.fund_ids].sort().join(",")}`;
      const idempotencyKey =
        idempotencyKeys.current.get(key) ?? globalThis.crypto.randomUUID();
      idempotencyKeys.current.set(key, idempotencyKey);
      return unwrapResponse(
        await submitFundIngestionBatch(
          request,
          withIdempotencyKey(idempotencyKey),
        ),
      );
    },
    onSuccess: async (_data, variables) => {
      idempotencyKeys.current.delete(
        `${variables.dataset}:${[...variables.fund_ids].sort().join(",")}`,
      );
      await Promise.all(
        variables.fund_ids.map((fundId) =>
          Promise.all([
            queryClient.invalidateQueries({
              queryKey: queryKeys.fundIngestions(fundId),
            }),
            queryClient.invalidateQueries({
              queryKey: queryKeys.fund(fundId),
            }),
            queryClient.invalidateQueries({
              queryKey: queryKeys.fundBasicInfoHistory(fundId),
            }),
          ]),
        ),
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.funds() });
    },
  });
}

export type ReviewDecisionVariables = {
  decisionId: string;
  request: DecisionReviewRequest;
};

export function useReviewDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ decisionId, request }: ReviewDecisionVariables) =>
      unwrapResponse(await reviewDecision(decisionId, request)),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.decision(variables.decisionId),
      });
    },
  });
}

export function useCreateBacktest() {
  return useMutation({
    mutationFn: async (request: BacktestCreateRequest) =>
      unwrapResponse(await createBacktest(request)),
  });
}

export function useValidateBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (backtestId: string) =>
      unwrapResponse(await validateBacktest(backtestId)),
    onSuccess: async (_data, backtestId) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.backtestStatus(backtestId),
      });
    },
  });
}

export type RunBacktestVariables = {
  backtestId: string;
  idempotencyKey: string;
};

export function useRunBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ backtestId, idempotencyKey }: RunBacktestVariables) =>
      unwrapResponse(
        await runBacktest(backtestId, withIdempotencyKey(idempotencyKey)),
      ),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.backtestStatus(variables.backtestId),
      });
    },
  });
}

// A key remains attached to its preview across transport errors. Retrying the
// same snapshot cannot create another job when the first response was lost.
export function useSubmitScopedIngestion() {
  const client = useQueryClient();
  const keys = useRef(new Map<string, string>());
  return useMutation({
    mutationFn: async (previewId: string) => {
      const key = keys.current.get(previewId) ?? globalThis.crypto.randomUUID();
      keys.current.set(previewId, key);
      return unwrapResponse(
        await submitScopedFundIngestion(
          { preview_id: previewId },
          withIdempotencyKey(key),
        ),
      );
    },
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ingestionKeys.history }),
  });
}

export function useCancelIngestion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrapResponse(await cancelFundIngestion(id)),
    onSuccess: async (task) => {
      client.setQueryData(ingestionKeys.task(task.operation_id), task);
      await Promise.all([
        client.invalidateQueries({
          queryKey: ingestionKeys.task(task.operation_id),
        }),
        client.invalidateQueries({
          queryKey: ingestionKeys.items(task.operation_id),
        }),
        client.invalidateQueries({ queryKey: ingestionKeys.history }),
      ]);
    },
  });
}

export function useRetryIngestionFailures() {
  const client = useQueryClient();
  const keys = useRef(new Map<string, string>());
  return useMutation({
    mutationFn: async (id: string) => {
      const key = keys.current.get(id) ?? globalThis.crypto.randomUUID();
      keys.current.set(id, key);
      return unwrapResponse(
        await retryFundIngestionFailures(id, withIdempotencyKey(key)),
      );
    },
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ingestionKeys.history }),
  });
}

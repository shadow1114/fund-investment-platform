import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import {
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
import { queryKeys } from "./queries";

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

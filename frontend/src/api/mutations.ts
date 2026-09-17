import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createBacktest,
  reviewDecision,
  runBacktest,
  submitOptimization,
  validateBacktest,
} from "./generated/m17";
import type {
  BacktestCreateRequest,
  DecisionReviewRequest,
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

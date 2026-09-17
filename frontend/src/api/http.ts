type ApiFailure = {
  code: string;
  message: string;
  details: Record<string, unknown>;
};

type Envelope = {
  data: unknown;
  meta: Record<string, unknown>;
  error: ApiFailure | null;
};

type GeneratedResponse = {
  status: number;
  data: Envelope;
  headers: Headers;
};

type UnwrapOptions = {
  requiredMeta?: readonly string[];
};

const enumFields = new Set([
  "status",
  "lifecycle_status",
  "investment_eligibility",
  "direction",
  "effectiveness_verdict",
  "weight_source",
  "universe_strategy",
  "result",
  "selection_status",
  "action",
  "backtest_mode",
  "validation_result",
  "overall",
  "thresholds_status",
  "segment",
  "nav_type",
  "included_in_nav",
]);
const knownEnumValues = new Set([
  "UNKNOWN",
  "VALID",
  "UNAVAILABLE",
  "EXCLUDED",
  "RUNNING",
  "COMPLETED",
  "BLOCKED",
  "FAILED",
  "CANCELLED",
  "NORMAL",
  "SUSPENDED_SUBSCRIPTION",
  "LIQUIDATED",
  "MERGED",
  "TRANSFORMED",
  "FULLY_ELIGIBLE",
  "HOLD_ONLY",
  "LIMITED",
  "EXIT_ONLY",
  "NOT_TRADABLE",
  "HIGHER_IS_BETTER",
  "LOWER_IS_BETTER",
  "NOT_ELIGIBLE",
  "PARTIAL",
  "VALIDATION_PENDING",
  "PROFILE_FIXED_V1",
  "OPTIMIZED",
  "A",
  "B",
  "SELECTED",
  "REJECTED",
  "DRAFT",
  "ACTIVE",
  "SUSPENDED",
  "CLOSED",
  "OPTIMAL",
  "INFEASIBLE",
  "UNBOUNDED",
  "NOT_CONVERGED",
  "NUMERICAL_ERROR",
  "PROPOSED",
  "APPROVED",
  "OVERRIDDEN",
  "EXPIRED",
  "SUPERSEDED",
  "CREATED",
  "VALIDATING_CONFIGURATION",
  "VALIDATING_RESULTS",
  "WARNING",
  "INVALID",
  "ABORTED",
  "PASS",
  "FAIL",
  "NOT_VERIFIED",
  "PARTIALLY_MODELED",
  "NOT_MODELED",
  "HISTORICAL_FIDELITY",
  "CURRENT_RULE",
  "PASS_WITH_WARNINGS",
  "SIGNIFICANT",
  "NOT_SIGNIFICANT",
  "CANNOT_DETERMINE",
  "CALIBRATED",
  "PENDING_CALIBRATION",
  "FULL",
  "IN_SAMPLE",
  "OUT_OF_SAMPLE",
  "ADJUSTED",
  "RAW",
  "TRUE",
  "FALSE",
]);

type SuccessfulData<Response> = Response extends {
  data: { error: null; data: infer Data };
}
  ? Data
  : never;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, failure: ApiFailure) {
    super(failure.message);
    this.name = "ApiError";
    this.status = status;
    this.code = failure.code;
    this.details = failure.details;
  }
}

function isEnumField(key: string): boolean {
  return enumFields.has(key) || key.endsWith("_status");
}

function normalizeUnknownStatuses(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(normalizeUnknownStatuses);
  }
  if (value === null || typeof value !== "object") {
    return value;
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [
      key,
      isEnumField(key) &&
      typeof entry === "string" &&
      !knownEnumValues.has(entry)
        ? "UNKNOWN"
        : normalizeUnknownStatuses(entry),
    ]),
  );
}

function contractError(message: string, details: Record<string, unknown> = {}) {
  return new ApiError(500, { code: "CONTRACT_ERROR", message, details });
}

export function unwrapResponse<Response extends GeneratedResponse>(
  response: Response,
  options: UnwrapOptions = {},
): SuccessfulData<Response> {
  if (response.data.error !== null) {
    throw new ApiError(response.status, response.data.error);
  }

  if (response.status < 200 || response.status >= 300) {
    throw new ApiError(response.status, {
      code: "HTTP_ERROR",
      message: `Request failed with status ${response.status}`,
      details: {},
    });
  }

  const missingMeta = (options.requiredMeta ?? []).filter(
    (field) => response.data.meta[field] === undefined,
  );
  if (missingMeta.length > 0) {
    throw contractError(
      `Response metadata is missing: ${missingMeta.join(", ")}`,
      {
        missing_fields: missingMeta,
      },
    );
  }

  return normalizeUnknownStatuses(
    response.data.data,
  ) as SuccessfulData<Response>;
}

export function normalizeOptimization<
  Optimization extends {
    optimization_status: string;
    target_weights: unknown[] | null;
  },
>(optimization: Optimization): Optimization {
  if (
    optimization.optimization_status !== "OPTIMAL" &&
    optimization.target_weights !== null
  ) {
    throw contractError("Non-OPTIMAL optimization returned target weights", {
      optimization_status: optimization.optimization_status,
    });
  }

  return optimization;
}

export function withIdempotencyKey(key: string): RequestInit {
  return { headers: { "Idempotency-Key": key } };
}

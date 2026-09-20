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

const values = (...entries: string[]): ReadonlySet<string> => new Set(entries);

const metricStatuses = values("VALID", "UNAVAILABLE", "EXCLUDED", "UNKNOWN");
const metricStatusFields = new Set([
  "annualized_return_improvement_vs_benchmark_status",
  "annualized_return_improvement_vs_equal_weight_status",
  "bootstrap_ci_lower_vs_benchmark_status",
  "bootstrap_ci_lower_vs_equal_weight_status",
  "delta_sharpe_vs_benchmark_status",
  "delta_sharpe_vs_equal_weight_status",
  "equal_weight_baseline_status",
  "ir_vs_benchmark_status",
  "ir_vs_equal_weight_status",
  "max_drawdown_improvement_vs_benchmark_status",
  "max_drawdown_improvement_vs_equal_weight_status",
  "nav_status",
  "objective_value_status",
  "outperform_ratio_vs_benchmark_status",
  "outperform_ratio_vs_equal_weight_status",
  "passed_status",
  "percentile_status",
  "portfolio_volatility_status",
  "rank_status",
  "relative_performance_score_status",
  "return_score_status",
  "risk_adjusted_score_status",
  "risk_score_status",
  "sharpe_ratio_status",
  "stability_score_status",
  "total_score_status",
  "value_status",
  "vs_benchmark_status",
  "vs_equal_weight_status",
]);

const enumValuesByField: Readonly<Record<string, ReadonlySet<string>>> = {
  lifecycle_status: values(
    "NORMAL",
    "SUSPENDED_SUBSCRIPTION",
    "LIQUIDATED",
    "MERGED",
    "TRANSFORMED",
    "UNKNOWN",
  ),
  investment_eligibility: values(
    "FULLY_ELIGIBLE",
    "HOLD_ONLY",
    "LIMITED",
    "EXIT_ONLY",
    "NOT_TRADABLE",
    "UNKNOWN",
  ),
  direction: values("HIGHER_IS_BETTER", "LOWER_IS_BETTER", "UNKNOWN"),
  evaluation_status: values(
    "NOT_ELIGIBLE",
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    "UNKNOWN",
  ),
  score_status: values(
    "COMPLETED",
    "PARTIAL",
    "VALIDATION_PENDING",
    "FAILED",
    "UNKNOWN",
  ),
  effectiveness_verdict: values("VALID", "INVALID", "UNKNOWN"),
  weight_source: values("PROFILE_FIXED_V1", "OPTIMIZED", "UNKNOWN"),
  universe_strategy: values("A", "B", "UNKNOWN"),
  result: values("PASS", "FAIL", "UNKNOWN"),
  selection_status: values("SELECTED", "REJECTED", "UNKNOWN"),
  optimization_status: values(
    "OPTIMAL",
    "INFEASIBLE",
    "UNBOUNDED",
    "NOT_CONVERGED",
    "NUMERICAL_ERROR",
    "UNKNOWN",
  ),
  decision_status: values(
    "PROPOSED",
    "APPROVED",
    "REJECTED",
    "OVERRIDDEN",
    "EXPIRED",
    "SUPERSEDED",
    "UNKNOWN",
  ),
  action: values("APPROVED", "REJECTED", "OVERRIDDEN", "UNKNOWN"),
  validation_status: values("VALID", "WARNING", "INVALID", "UNKNOWN"),
  validation_result: values("PASS", "PASS_WITH_WARNINGS", "UNKNOWN"),
  backtest_mode: values("HISTORICAL_FIDELITY", "CURRENT_RULE", "UNKNOWN"),
  overall: values(
    "SIGNIFICANT",
    "NOT_SIGNIFICANT",
    "CANNOT_DETERMINE",
    "UNKNOWN",
  ),
  thresholds_status: values("CALIBRATED", "PENDING_CALIBRATION", "UNKNOWN"),
  segment: values("FULL", "IN_SAMPLE", "OUT_OF_SAMPLE", "UNKNOWN"),
  nav_type: values("ADJUSTED", "RAW", "UNKNOWN"),
  included_in_nav: values("TRUE", "FALSE", "UNKNOWN"),
};

type SuccessfulData<Response> = Response extends {
  data: { error: null; data: infer Data };
}
  ? Data
  : never;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(status: number, failure: ApiFailure, headers?: Headers) {
    super(failure.message);
    this.name = "ApiError";
    this.status = status;
    this.code = failure.code;
    this.details = failure.details;
    this.requestId = headers?.get("X-Request-ID") ?? null;
    const retryAfter = headers?.get("Retry-After");
    this.retryAfterSeconds = retryAfter ? Number(retryAfter) : null;
  }
}

function statusValues(
  record: Record<string, unknown>,
  path: readonly string[],
): ReadonlySet<string> | undefined {
  if ("factor_id" in record) {
    return metricStatuses;
  }
  if ("backtest_id" in record && "operation_id" in record) {
    return values("RUNNING", "UNKNOWN");
  }
  if ("backtest_id" in record && "created_at" in record) {
    return values("CREATED", "UNKNOWN");
  }
  if ("operation_id" in record && "optimization_id" in record) {
    return values("RUNNING", "UNKNOWN");
  }
  if ("operation_id" in record) {
    return values(
      "RUNNING",
      "COMPLETED",
      "BLOCKED",
      "FAILED",
      "CANCELLED",
      "UNKNOWN",
    );
  }
  if ("portfolio_id" in record && "portfolio_version" in record) {
    return values("DRAFT", "ACTIVE", "SUSPENDED", "CLOSED", "UNKNOWN");
  }
  if ("backtest_id" in record && "progress" in record) {
    return values(
      "CREATED",
      "VALIDATING_CONFIGURATION",
      "RUNNING",
      "VALIDATING_RESULTS",
      "COMPLETED",
      "FAILED",
      "INVALID",
      "CANCELLED",
      "ABORTED",
      "UNKNOWN",
    );
  }
  if (path.includes("checks")) {
    return values(
      "PASS",
      "WARNING",
      "FAIL",
      "NOT_VERIFIED",
      "PARTIALLY_MODELED",
      "NOT_MODELED",
      "UNKNOWN",
    );
  }
  return undefined;
}

function allowedValues(
  key: string,
  record: Record<string, unknown>,
  path: readonly string[],
): ReadonlySet<string> | undefined {
  if (key === "status") {
    return statusValues(record, path);
  }
  if (metricStatusFields.has(key)) {
    return metricStatuses;
  }
  return enumValuesByField[key];
}

function normalizeUnknownEnums(
  value: unknown,
  path: readonly string[] = [],
): unknown {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeUnknownEnums(entry, path));
  }
  if (value === null || typeof value !== "object") {
    return value;
  }

  const record = value as Record<string, unknown>;
  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => {
      const allowed = allowedValues(key, record, path);
      return [
        key,
        allowed !== undefined &&
        typeof entry === "string" &&
        !allowed.has(entry)
          ? "UNKNOWN"
          : normalizeUnknownEnums(entry, [...path, key]),
      ];
    }),
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
    throw new ApiError(response.status, response.data.error, response.headers);
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

  return normalizeUnknownEnums(response.data.data) as SuccessfulData<Response>;
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

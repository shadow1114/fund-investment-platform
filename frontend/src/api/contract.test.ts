import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import * as generatedClient from "./generated/m17";
import { getGetBacktestPerformanceUrl, getListFundsUrl } from "./generated/m17";
import type {
  BacktestCreatedStatus,
  BacktestRunStatus,
  BacktestStatusStatus,
  FactorResultDirection,
  OperationStatus,
  OptimizationSubmissionStatus,
  OptimizationOptimizationStatus,
} from "./generated/m17.schemas";

type SchemaProjection = {
  required?: string[];
  properties?: Record<string, SchemaProjection>;
  enum?: string[];
  allOf?: SchemaProjection[];
  anyOf?: SchemaProjection[];
  type?: string | string[];
  $ref?: string;
};

type ParameterProjection = {
  name?: string;
  style?: string;
  explode?: boolean;
};

type OpenApiProjection = {
  openapi: string;
  paths: Record<
    string,
    { get?: { parameters?: ParameterProjection[] }; post?: unknown }
  >;
  components: {
    schemas: Record<string, SchemaProjection>;
  };
};

const frozenPaths = [
  "/api/v1/session",
  "/api/v1/operations/{operation_id}",
  "/api/v1/funds",
  "/api/v1/funds/{fund_id}",
  "/api/v1/funds/{fund_id}/nav-series",
  "/api/v1/funds/{fund_id}/evaluations",
  "/api/v1/funds/{fund_id}/scores",
  "/api/v1/fund-universes",
  "/api/v1/fund-universes/{universe_id}",
  "/api/v1/portfolios",
  "/api/v1/portfolios/{id}",
  "/api/v1/portfolios/{id}/optimizations",
  "/api/v1/portfolios/{id}/optimizations/{optimization_id}",
  "/api/v1/decisions/{decision_id}",
  "/api/v1/decisions/{decision_id}/review",
  "/api/v1/backtests",
  "/api/v1/backtests/{id}/validate-configuration",
  "/api/v1/backtests/{id}/runs",
  "/api/v1/backtests/{id}/status",
  "/api/v1/backtests/{id}/result",
  "/api/v1/backtests/{id}/performance",
  "/api/v1/backtests/{id}/bias-check",
] as const;

const frozenOperations = [
  "getSession",
  "listFunds",
  "getFund",
  "getFundNavSeries",
  "getFundEvaluations",
  "getFundScores",
  "listUniverses",
  "getUniverse",
  "listPortfolios",
  "getPortfolio",
  "submitOptimization",
  "getOptimization",
  "getDecision",
  "reviewDecision",
  "createBacktest",
  "validateBacktest",
  "runBacktest",
  "getBacktestStatus",
  "getBacktestResult",
  "getBacktestPerformance",
  "getBacktestBiasCheck",
  "getOperation",
] as const;

const generatedUnknownStatuses: [
  OperationStatus,
  OptimizationSubmissionStatus,
  OptimizationOptimizationStatus,
  BacktestCreatedStatus,
  BacktestRunStatus,
  BacktestStatusStatus,
  FactorResultDirection,
] = [
  "UNKNOWN",
  "UNKNOWN",
  "UNKNOWN",
  "UNKNOWN",
  "UNKNOWN",
  "UNKNOWN",
  "UNKNOWN",
];

function loadOpenApi(path: string): OpenApiProjection {
  return parse(
    readFileSync(resolve(import.meta.dirname, "../../..", path), "utf8"),
  );
}

describe("frozen M1.7 OpenAPI projection", () => {
  it("contains every frozen M1.7 path and no unversioned path", () => {
    const spec = loadOpenApi("frontend/openapi/m17.yaml");

    expect(spec.openapi).toBe("3.1.0");
    expect(Object.keys(spec.paths).sort()).toEqual([...frozenPaths].sort());
    expect(
      Object.keys(spec.paths).every((path) => path.startsWith("/api/v1/")),
    ).toBe(true);
  });

  it("exports a generated function for every frozen operation", () => {
    for (const operation of frozenOperations) {
      expect(generatedClient[operation]).toBeTypeOf("function");
    }
  });

  it("preserves nullable metrics and non-optimal optimization weights", () => {
    const spec = loadOpenApi("frontend/openapi/m17.yaml");
    const metric = spec.components.schemas.NullableMetric;
    const optimization = spec.components.schemas.Optimization;

    expect(metric.required).toEqual(["value", "status", "reason"]);
    expect(optimization.required).toContain("target_weights");
    expect(optimization.properties?.target_weights).toMatchObject({
      type: ["array", "null"],
    });
    expect(optimization.allOf).toHaveLength(1);
  });

  it("types frozen provenance fields and every bias-check status explicitly", () => {
    const spec = loadOpenApi("frontend/openapi/m17.yaml");

    expect(spec.components.schemas.FundEvaluationMeta.required).toEqual(
      expect.arrayContaining([
        "peer_group_id",
        "peer_group_version",
        "evaluation_policy_version",
        "factor_version",
        "data_version",
      ]),
    );
    expect(spec.components.schemas.BiasStatus.enum).toEqual(
      expect.arrayContaining(["PARTIALLY_MODELED", "NOT_MODELED"]),
    );
  });

  it("serializes every multi-value query parameter as one comma-separated value", () => {
    expect(
      getListFundsUrl({
        fund_type: ["EQUITY", "BOND"],
        lifecycle_status: ["NORMAL", "LIQUIDATED"],
        investment_eligibility: ["FULLY_ELIGIBLE", "HOLD_ONLY"],
      }),
    ).toBe(
      "/api/v1/funds?fund_type=EQUITY%2CBOND&lifecycle_status=NORMAL%2CLIQUIDATED&investment_eligibility=FULLY_ELIGIBLE%2CHOLD_ONLY",
    );
    expect(
      getGetBacktestPerformanceUrl("BT-001", {
        include_series: ["portfolio_value", "drawdown"],
      }),
    ).toBe(
      "/api/v1/backtests/BT-001/performance?include_series=portfolio_value%2Cdrawdown",
    );

    const spec = loadOpenApi("frontend/openapi/m17.yaml");
    const parameters = [
      ...(spec.paths["/api/v1/funds"].get?.parameters ?? []),
      ...(spec.paths["/api/v1/backtests/{id}/performance"].get?.parameters ??
        []),
    ];
    for (const name of [
      "fund_type",
      "lifecycle_status",
      "investment_eligibility",
      "include_series",
    ]) {
      expect(
        parameters.find((parameter) => parameter.name === name),
      ).toMatchObject({
        style: "form",
        explode: false,
      });
    }
  });

  it("requires status and reason companions for every nullable metric family", () => {
    const schemas = loadOpenApi("frontend/openapi/m17.yaml").components.schemas;

    expect(schemas.SubScores.required).toEqual(
      expect.arrayContaining([
        "return_score_status",
        "return_score_reason",
        "risk_score_status",
        "risk_score_reason",
        "risk_adjusted_score_status",
        "risk_adjusted_score_reason",
        "stability_score_status",
        "stability_score_reason",
        "relative_performance_score_status",
        "relative_performance_score_reason",
      ]),
    );
    expect(schemas.FundScore.required).toEqual(
      expect.arrayContaining(["total_score_status", "total_score_reason"]),
    );
    expect(schemas.Optimization.required).toEqual(
      expect.arrayContaining([
        "objective_value_status",
        "objective_value_reason",
      ]),
    );
    expect(schemas.PostOptimizationRisk.required).toEqual([
      "portfolio_volatility",
      "portfolio_volatility_status",
      "portfolio_volatility_reason",
    ]);
    expect(schemas.PerformanceMetrics.required).toEqual(
      expect.arrayContaining(["sharpe_ratio_status", "sharpe_ratio_reason"]),
    );
    expect(schemas.SeriesPoint.required).toEqual([
      "date",
      "value",
      "value_status",
      "value_reason",
    ]);
  });

  it("requires endpoint-specific list provenance metadata", () => {
    const schemas = loadOpenApi("frontend/openapi/m17.yaml").components.schemas;

    expect(schemas.FundListMeta.required).toEqual(
      expect.arrayContaining([
        "as_of_date",
        "data_version",
        "versions",
        "is_point_in_time",
        "pagination",
        "availability_quality_distribution",
      ]),
    );
    expect(schemas.PortfolioListMeta.required).toEqual(
      expect.arrayContaining(["versions", "is_point_in_time", "pagination"]),
    );
    expect(schemas.FundListEnvelope.properties?.meta).toEqual({
      $ref: "#/components/schemas/FundListMeta",
    });
    expect(schemas.PortfolioListEnvelope.properties?.meta).toEqual({
      $ref: "#/components/schemas/PortfolioListMeta",
    });
  });

  it("represents a disabled equal-weight baseline with status and reason", () => {
    const schemas = loadOpenApi("frontend/openapi/m17.yaml").components.schemas;

    expect(schemas.BacktestSummary.required).toEqual(
      expect.arrayContaining([
        "equal_weight_baseline",
        "equal_weight_baseline_status",
        "equal_weight_baseline_reason",
      ]),
    );
    expect(
      schemas.BacktestSummary.properties?.equal_weight_baseline?.anyOf,
    ).toEqual(
      expect.arrayContaining([
        { $ref: "#/components/schemas/PerformanceMetrics" },
        { type: "null" },
      ]),
    );
    expect(schemas.CumulativeReturnSeries.required).toEqual(
      expect.arrayContaining([
        "equal_weight_baseline",
        "equal_weight_baseline_status",
        "equal_weight_baseline_reason",
      ]),
    );
  });

  it("requires bias-check evidence fields on their specific checks", () => {
    const schemas = loadOpenApi("frontend/openapi/m17.yaml").components.schemas;

    expect(schemas.PointInTimeBiasCheck.required).toEqual(
      expect.arrayContaining(["status", "availability_quality_distribution"]),
    );
    expect(schemas.TransactionCostBiasCheck.required).toEqual(
      expect.arrayContaining(["status", "unmodeled_costs"]),
    );
  });

  it("exposes a neutral UNKNOWN variant for forward-compatible business enums", () => {
    const schemas = loadOpenApi("frontend/openapi/m17.yaml").components.schemas;

    expect(schemas.MetricStatus.enum).toContain("UNKNOWN");
    expect(schemas.Operation.properties?.status?.enum).toContain("UNKNOWN");
    expect(schemas.OptimizationSubmission.properties?.status?.enum).toContain(
      "UNKNOWN",
    );
    expect(schemas.FactorResult.properties?.direction?.enum).toContain(
      "UNKNOWN",
    );
    expect(
      schemas.Optimization.properties?.optimization_status?.enum,
    ).toContain("UNKNOWN");
    expect(schemas.BacktestStatus.properties?.status?.enum).toContain(
      "UNKNOWN",
    );
    expect(schemas.BacktestCreated.properties?.status?.enum).toContain(
      "UNKNOWN",
    );
    expect(schemas.BacktestRun.properties?.status?.enum).toContain("UNKNOWN");
    expect(schemas.BiasStatus.enum).toContain("UNKNOWN");
    expect(generatedUnknownStatuses).toEqual([
      "UNKNOWN",
      "UNKNOWN",
      "UNKNOWN",
      "UNKNOWN",
      "UNKNOWN",
      "UNKNOWN",
      "UNKNOWN",
    ]);
  });
});

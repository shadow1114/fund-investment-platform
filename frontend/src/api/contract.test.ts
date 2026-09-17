import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import * as generatedClient from "./generated/m17";

type OpenApiProjection = {
  openapi: string;
  paths: Record<string, unknown>;
  components: {
    schemas: Record<
      string,
      {
        required?: string[];
        properties?: Record<string, unknown>;
        enum?: string[];
        allOf?: unknown[];
      }
    >;
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
});

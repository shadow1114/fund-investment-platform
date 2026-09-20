import { describe, expect, it } from "vitest";
import type {
  BacktestResult,
  Fund,
  FundEvaluation,
  FundScore,
  Universe,
} from "./generated/m17.schemas";

describe("generated nested response contracts", () => {
  it("exposes fund benchmark components", () => {
    const fund = {
      benchmark: { components: [{ weight: 1 }] },
    } as Fund;
    expect(fund.benchmark.components?.[0]?.weight).toBe(1);
  });

  it("exposes evaluation and score nested data", () => {
    const evaluation = {
      factor_results: [{ status: "VALID" }],
    } as FundEvaluation;
    const score = {
      sub_scores: { return_score_status: "VALID" },
    } as FundScore;
    expect(evaluation.factor_results[0].status).toBe("VALID");
    expect(score.sub_scores.return_score_status).toBe("VALID");
  });

  it("exposes universe members and every backtest significance layer", () => {
    const universe = { members: [{ fund_id: "000001" }] } as Universe;
    const result = {
      significance_verdict: { layers: { economic: { passed: true } } },
    } as BacktestResult;
    expect(universe.members[0].fund_id).toBe("000001");
    expect(result.significance_verdict.layers.economic.passed).toBe(true);
  });
});

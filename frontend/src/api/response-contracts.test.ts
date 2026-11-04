import { describe, expect, it } from "vitest";
import type {
  BacktestResult,
  Fund,
  FundEvaluation,
  FundScore,
  FundListResponseResponse,
  ListFundManagementCompaniesParams,
  ListFundsParams,
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

  it("types the research filters and nullable fund company list field", () => {
    const filters: ListFundsParams = {
      fund_code: "000001",
      company_name: "示例管理人",
      sub_status: "开放",
    };
    const companyQuery: ListFundManagementCompaniesParams = {
      as_of_date: "2026-01-31",
    };
    const item: FundListResponseResponse["data"][number] = {
      fund_id: "F-001",
      fund_name: "示例基金",
      share_class: "A",
      fund_classification: "UNKNOWN",
      management_company_id: "UNKNOWN",
      inception_date: "2020-01-01",
      lifecycle_status: "UNKNOWN",
      investment_eligibility: "UNKNOWN",
      share_class_id: "101",
      fund_code: "000001",
      company_name: null,
      sub_status: "开放",
      manager_ids: [],
    };
    expect(filters.fund_code).toBe("000001");
    expect(companyQuery.as_of_date).toBe("2026-01-31");
    expect(item.company_name).toBeNull();
    const unknownSubscriptionStatus: FundListResponseResponse["data"][number] =
      {
        ...item,
        sub_status: "UNKNOWN",
      };
    expect(unknownSubscriptionStatus.sub_status).toBe("UNKNOWN");
  });
});

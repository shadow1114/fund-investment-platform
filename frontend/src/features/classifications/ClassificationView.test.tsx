import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { ClassificationView } from "./ClassificationView";

const dimension = (status: string, value: string, evaluation_state?: string) =>
  ({ status, value, candidates: [], evidence: [], evaluation_state }) as never;

it("keeps historical tag absence distinct from a negative quantitative result", () => {
  render(
    <ClassificationView
      classification={{
        scheme: "FIP_CLASSIFICATION_V1",
        asset_class: dimension("CONFIRMED", "EQUITY"),
        strategy: dimension("CONFIRMED", "QUANTITATIVE"),
        geography: dimension("UNKNOWN", "UNKNOWN"),
        product_structure: dimension("UNKNOWN", "UNKNOWN"),
        market_attributes: dimension("UNKNOWN", "UNKNOWN"),
        revision_id: 1,
        version: 1,
        valid_from: "2026-01-01",
        available_at: "2026-01-01T00:00:00Z",
        classified_at: "2026-01-01T00:00:00Z",
        availability_quality: "EXACT",
        source_summary: [],
        trading_eligibility: {},
      }}
    />,
  );

  expect(screen.getByText(/该历史记录未包含量化标签/)).toBeVisible();
  expect(screen.queryByText(/非量化/)).toBeNull();
});

it("renders current and paused dimensions and tag evidence states separately", () => {
  render(
    <ClassificationView
      classification={{
        scheme: "FIP_CLASSIFICATION",
        asset_class: dimension("CONFIRMED", "EQUITY"),
        strategy: {
          status: "CONFLICT",
          value: "UNKNOWN",
          candidates: ["PASSIVE_INDEX", "ENHANCED_INDEX"],
          evidence: [
            {
              source: "AGGREGATOR",
              confidence: "PUBLIC_AGGREGATOR",
              classified_at: "2026-01-01",
              raw_field: "strategy",
              raw_value: "被动指数型",
              rule_id: "STR002",
            },
            {
              source: "AGGREGATOR",
              confidence: "PUBLIC_AGGREGATOR",
              classified_at: "2026-01-01",
              raw_field: "strategy",
              raw_value: "增强指数型",
              rule_id: "STR001",
            },
          ],
        } as never,
        geography: dimension("UNKNOWN", "UNKNOWN", "PAUSED"),
        product_structure: dimension("UNKNOWN", "UNKNOWN", "PAUSED"),
        market_attributes: dimension("UNKNOWN", "UNKNOWN", "PAUSED"),
        revision_id: 2,
        version: 2,
        valid_from: "2026-01-01",
        available_at: "2026-01-01T00:00:00Z",
        classified_at: "2026-01-01T00:00:00Z",
        availability_quality: "EXACT",
        source_summary: [],
        trading_eligibility: {},
        strategy_tags: ["FACTOR"],
        strategy_tag_results: {
          QUANTITATIVE: {
            status: "CANDIDATE",
            value: "UNKNOWN",
            candidates: ["QUANTITATIVE"],
            evaluation_state: "EVALUATED",
            evidence: [
              {
                source: "NAME",
                confidence: "NAME_HINT",
                classified_at: "2026-01-01",
                raw_field: "strategy",
                raw_value: "名称含量化",
                rule_id: "TAG001",
              },
            ],
          },
          PASSIVE: {
            status: "UNKNOWN",
            value: "UNKNOWN",
            evaluation_state: "NOT_EVALUATED",
            evidence: [],
          },
          FACTOR: {
            status: "CONFIRMED",
            value: "FACTOR",
            evaluation_state: "EVALUATED",
            evidence: [],
          },
          SYSTEMATIC: {
            status: "CONFLICT",
            value: "UNKNOWN",
            candidates: ["SYSTEMATIC"],
            evaluation_state: "EVALUATED",
            evidence: [],
          },
        },
      }}
      evidence
    />,
  );

  expect(screen.getAllByText(/执行状态：暂停更新（历史保留）/)).toHaveLength(3);
  expect(screen.getByText(/被动指数型/)).toBeVisible();
  expect(screen.getByText(/增强指数型/)).toBeVisible();
  expect(screen.getByText("QUANTITATIVE").parentElement).toHaveTextContent(
    "候选",
  );
  expect(screen.getByText(/标签未评估/)).toBeVisible();
  expect(screen.getByText(/已确认策略标签：FACTOR/)).toBeVisible();
  expect(screen.getByText("FACTOR").parentElement).toHaveTextContent("已确认");
  expect(screen.getByText("SYSTEMATIC").parentElement).toHaveTextContent(
    "冲突",
  );
});

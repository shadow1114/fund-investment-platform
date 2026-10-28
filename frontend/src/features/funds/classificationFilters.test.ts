import { expect, it } from "vitest";

import { parseParams, serializeFilters } from "../../pages/FundResearchPage";
import { emptyFundFilters } from "./FundFilters";

it("applies v3 asset, strategy, and confirmed-tag filters while ignoring paused dimensions", () => {
  const params = parseParams(
    new URLSearchParams(
      "asset_class=EQUITY&strategy=PASSIVE_INDEX&strategy_tags=QUANTITATIVE&geography=CN&product_structure=ETF&market_attributes=QDII",
    ),
  );

  expect(params).toMatchObject({
    asset_class: "EQUITY",
    strategy: "PASSIVE_INDEX",
    strategy_tags: ["QUANTITATIVE"],
  });
  expect(params).not.toHaveProperty("geography");
  expect(params).not.toHaveProperty("product_structure");
  expect(params).not.toHaveProperty("market_attributes");
});

it("preserves old paused-dimension URL state without applying it to the current API query", () => {
  const values = {
    ...emptyFundFilters(),
    asset_class: ["EQUITY"],
    strategy: ["PASSIVE_INDEX"],
    strategy_tags: ["QUANTITATIVE"],
    geography: ["CN"],
    product_structure: ["ETF"],
    market_attributes: ["QDII"],
  };
  const search = serializeFilters(values);

  expect(search.get("asset_class")).toBe("EQUITY");
  expect(search.get("strategy")).toBe("PASSIVE_INDEX");
  expect(search.get("strategy_tags")).toBe("QUANTITATIVE");
  expect(search.get("geography")).toBe("CN");
  expect(search.get("product_structure")).toBe("ETF");
  expect(search.get("market_attributes")).toBe("QDII");
  const request = parseParams(search);
  expect(request).not.toHaveProperty("geography");
  expect(request).not.toHaveProperty("product_structure");
  expect(request).not.toHaveProperty("market_attributes");
});

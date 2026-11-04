import { expect, it } from "vitest";

import { parseParams, serializeFilters } from "../../pages/FundResearchPage";
import { emptyFundFilters } from "./FundFilters";

it("applies asset, strategy, confirmed-tag, and supported legacy dimension filters", () => {
  const params = parseParams(
    new URLSearchParams(
      "asset_class=EQUITY&strategy=PASSIVE_INDEX&strategy_tags=QUANTITATIVE&geography=CN&product_structure=ETF&market_attributes=QDII",
    ),
  );

  expect(params).toMatchObject({
    asset_class: "EQUITY",
    strategy: "PASSIVE_INDEX",
    strategy_tags: ["QUANTITATIVE"],
    geography: "CN",
    product_structure: "ETF",
    market_attributes: "QDII",
  });
});

it("preserves supported legacy dimension URL state in the current API query", () => {
  const values = {
    ...emptyFundFilters(),
    asset_class: "EQUITY",
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
  expect(request).toMatchObject({
    geography: "CN",
    product_structure: "ETF",
    market_attributes: "QDII",
  });
});

it("round-trips the five research filters using the fund_code and asset_class API fields", () => {
  const values = {
    ...emptyFundFilters(),
    fund_name: "Alpha",
    fund_code: "000001",
    company_name: "永赢基金",
    asset_class: "EQUITY",
    sub_status: "开放",
  };
  const search = serializeFilters(values);

  expect(search.get("fund_name")).toBe("Alpha");
  expect(search.get("fund_code")).toBe("000001");
  expect(search.get("company_name")).toBe("永赢基金");
  expect(search.get("asset_class")).toBe("EQUITY");
  expect(search.get("sub_status")).toBe("开放");
  expect(search.has("fund_type")).toBe(false);
  expect(parseParams(search)).toMatchObject({
    fund_name: "Alpha",
    fund_code: "000001",
    company_name: "永赢基金",
    asset_class: "EQUITY",
    sub_status: "开放",
  });
});

it("keeps supported legacy geography, product, and market filters in API params", () => {
  const params = parseParams(
    new URLSearchParams(
      "geography=CN,US&product_structure=ETF&market_attributes=QDII",
    ),
  );
  expect(params).toMatchObject({
    geography: "CN,US",
    product_structure: "ETF",
    market_attributes: "QDII",
  });
});

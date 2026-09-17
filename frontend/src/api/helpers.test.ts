import { describe, expect, it } from "vitest";

import {
  useCreateBacktest,
  useReviewDecision,
  useRunBacktest,
  useSubmitOptimization,
  useValidateBacktest,
} from "./mutations";
import { getFundQueryOptions, queryKeys } from "./queries";

describe("API query and mutation helpers", () => {
  it("builds stable hierarchical query keys", () => {
    expect(queryKeys.session).toEqual(["api", "session"]);
    expect(queryKeys.fund("F-001", { as_of_date: "2026-08-24" })).toEqual([
      "api",
      "funds",
      "F-001",
      { as_of_date: "2026-08-24" },
    ]);
    expect(queryKeys.operation("OP-001")).toEqual([
      "api",
      "operations",
      "OP-001",
    ]);
  });

  it("uses the same key in generated query options", () => {
    const options = getFundQueryOptions("F-001", {
      as_of_date: "2026-08-24",
    });

    expect(options.queryKey).toEqual(
      queryKeys.fund("F-001", { as_of_date: "2026-08-24" }),
    );
  });

  it("exports hooks for every frozen mutation", () => {
    expect(useSubmitOptimization).toBeTypeOf("function");
    expect(useReviewDecision).toBeTypeOf("function");
    expect(useCreateBacktest).toBeTypeOf("function");
    expect(useValidateBacktest).toBeTypeOf("function");
    expect(useRunBacktest).toBeTypeOf("function");
  });
});

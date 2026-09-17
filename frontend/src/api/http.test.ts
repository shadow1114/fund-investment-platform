import { describe, expect, it } from "vitest";

import { ApiError, normalizeOptimization, unwrapResponse } from "./http";

describe("API response handling", () => {
  it("returns successful envelope data", () => {
    expect(
      unwrapResponse({
        status: 200,
        data: { data: { fund_id: "F-001" }, meta: {}, error: null },
        headers: new Headers(),
      }),
    ).toEqual({ fund_id: "F-001" });
  });

  it("throws a status-aware API error for an error envelope", () => {
    let thrown: unknown;
    try {
      unwrapResponse({
        status: 403,
        data: {
          data: null,
          meta: { request_id: "REQ-001" },
          error: {
            code: "FORBIDDEN",
            message: "Access denied",
            details: { resource: "P-001" },
          },
        },
        headers: new Headers(),
      });
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown).toMatchObject({
      status: 403,
      code: "FORBIDDEN",
      message: "Access denied",
      details: { resource: "P-001" },
    });
  });

  it("rejects a non-optimal optimization carrying target weights", () => {
    expect(() =>
      normalizeOptimization({
        optimization_status: "INFEASIBLE",
        target_weights: [{ fund_id: "F-001", weight: 1 }],
      }),
    ).toThrowError(
      expect.objectContaining({
        code: "CONTRACT_ERROR",
        message: "Non-OPTIMAL optimization returned target weights",
      }),
    );
  });

  it("maps an unknown business status to the neutral UNKNOWN variant", () => {
    const data = unwrapResponse({
      status: 200,
      data: {
        data: { optimization_status: "FUTURE_SOLVER_STATUS" },
        meta: {},
        error: null,
      },
      headers: new Headers(),
    });

    expect(data).toEqual({ optimization_status: "UNKNOWN" });
  });

  it("throws a contract error when required metadata is absent", () => {
    expect(() =>
      unwrapResponse(
        {
          status: 200,
          data: { data: [], meta: {}, error: null },
          headers: new Headers(),
        },
        { requiredMeta: ["pagination", "versions", "is_point_in_time"] },
      ),
    ).toThrowError(
      expect.objectContaining({
        code: "CONTRACT_ERROR",
        message:
          "Response metadata is missing: pagination, versions, is_point_in_time",
      }),
    );
  });
});

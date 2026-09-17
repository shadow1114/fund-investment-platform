import { describe, expect, it } from "vitest";

import { ApiError, unwrapResponse } from "./http";

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
});

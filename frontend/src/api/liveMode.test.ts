import { describe, expect, it } from "vitest";

import { apiBaseUrl } from "./client";
import { ApiError } from "./http";

describe("live API mode", () => {
  it("uses VITE_API_BASE_URL only when configured", () => {
    expect(
      apiBaseUrl(
        { VITE_API_BASE_URL: "http://127.0.0.1:8000" },
        "http://localhost:5173",
      ),
    ).toBe("http://127.0.0.1:8000");
    expect(apiBaseUrl({ VITE_API_BASE_URL: "" }, "http://localhost:5173")).toBe(
      "http://localhost:5173",
    );
  });

  it("keeps request and retry metadata on typed errors", () => {
    const error = new ApiError(
      429,
      { code: "RATE_LIMITED", message: "slow down", details: {} },
      new Headers({ "X-Request-ID": "REQ-1", "Retry-After": "3" }),
    );
    expect(error).toMatchObject({
      status: 429,
      code: "RATE_LIMITED",
      requestId: "REQ-1",
      retryAfterSeconds: 3,
    });
  });
});

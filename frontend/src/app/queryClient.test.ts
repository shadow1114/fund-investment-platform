import { describe, expect, it } from "vitest";

import { queryClient } from "./queryClient";

describe("query retry policy", () => {
  const shouldRetry = queryClient.getDefaultOptions().queries?.retry;
  const errorWithStatus = (status: number) => ({ status }) as unknown as Error;

  it("only retries transient 5xx errors and never beyond the bound", () => {
    expect(shouldRetry).toBeTypeOf("function");
    if (typeof shouldRetry !== "function") return;

    for (const status of [401, 403, 404, 422, 499, 600]) {
      expect(shouldRetry(0, errorWithStatus(status))).toBe(false);
    }
    expect(shouldRetry(0, new Error())).toBe(false);
    expect(shouldRetry(0, errorWithStatus(500))).toBe(true);
    expect(shouldRetry(2, errorWithStatus(503))).toBe(true);
    expect(shouldRetry(3, errorWithStatus(503))).toBe(false);
  });
});

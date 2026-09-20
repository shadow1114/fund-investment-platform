import { getOperation } from "./generated/m17";
import type { Operation } from "./generated/m17.schemas";
import { unwrapResponse } from "./http";

export async function pollOperation(
  operationId: string,
  options: {
    signal?: AbortSignal;
    intervalMs?: number;
    maxAttempts?: number;
  } = {},
): Promise<Operation> {
  const intervalMs = options.intervalMs ?? 500;
  const maxAttempts = options.maxAttempts ?? 60;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (options.signal?.aborted) {
      throw new DOMException("Operation polling aborted", "AbortError");
    }
    const operation = unwrapResponse(await getOperation(operationId));
    if (["COMPLETED", "BLOCKED", "FAILED", "CANCELLED"].includes(operation.status)) {
      return operation;
    }
    if (attempt + 1 < maxAttempts) {
      await new Promise<void>((resolve, reject) => {
        const timer = window.setTimeout(resolve, intervalMs);
        options.signal?.addEventListener(
          "abort",
          () => {
            window.clearTimeout(timer);
            reject(new DOMException("Operation polling aborted", "AbortError"));
          },
          { once: true },
        );
      });
    }
  }
  throw new Error(`Operation ${operationId} polling timed out`);
}

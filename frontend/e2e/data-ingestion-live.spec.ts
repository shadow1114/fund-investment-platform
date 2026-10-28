import { expect, test } from "@playwright/test";

const databaseUrl = process.env.FIP_DATABASE_URL ?? "";
const fundId = process.env.FIP_LIVE_FUND_ID;
const failedOperationId = process.env.FIP_LIVE_FAILED_OPERATION_ID;
const selectedFundIds = (process.env.FIP_LIVE_SELECTED_FUND_IDS ?? "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const isolatedLiveEnabled =
  process.env.FIP_INGESTION_LIVE_TESTS === "true" &&
  /\/fip_test(?:\?|$)/.test(databaseUrl) &&
  Boolean(fundId) &&
  Boolean(failedOperationId) &&
  selectedFundIds.length >= 2 &&
  process.env.FIP_LIVE_CONFIRM_WRITES === "true";

test.skip(
  !isolatedLiveEnabled,
  "Live ingestion tests require explicit write opt-in, fip_test database, isolated fund IDs, and a failed operation owned by the test actor.",
);

test("isolated fund ingestion previews and records BASIC_INFO, NAV, selected and ALL jobs", async ({
  request,
}) => {
  const sessionResponse = await request.get("/api/v1/session");
  expect(sessionResponse.ok()).toBeTruthy();
  const actor = (await sessionResponse.json()).data.user_id as string;
  expect(actor).toBeTruthy();

  const preview = async (dataset: "BASIC_INFO" | "NAV", scope: unknown) => {
    const response = await request.post("/api/v1/fund-ingestion-previews", {
      data: { dataset, scope },
    });
    expect(response.status()).toBe(200);
    const envelope = await response.json();
    expect(envelope.error).toBeNull();
    expect(envelope.data.preview_id).toBeTruthy();
    return envelope.data;
  };

  const submit = async (previewId: string) => {
    const response = await request.post("/api/v1/fund-ingestion-jobs", {
      data: { preview_id: previewId },
      headers: { "Idempotency-Key": `pw-live-${crypto.randomUUID()}` },
    });
    expect(response.status()).toBe(202);
    const envelope = await response.json();
    expect(envelope.error).toBeNull();
    expect(envelope.data.operation_id).toBeTruthy();
    return envelope.data.operation_id as string;
  };

  const singleBasic = await preview("BASIC_INFO", {
    type: "SINGLE",
    fund_id: fundId,
  });
  const basicOperationId = await submit(singleBasic.preview_id);
  const singleNav = await preview("NAV", { type: "SINGLE", fund_id: fundId });
  const navOperationId = await submit(singleNav.preview_id);
  const selected = await preview("BASIC_INFO", {
    type: "SELECTED",
    fund_ids: selectedFundIds,
  });
  const selectedOperationId = await submit(selected.preview_id);
  const all = await preview("BASIC_INFO", { type: "ALL", filters: {} });
  const allOperationId = await submit(all.preview_id);

  for (const [operationId, dataset, scopeType] of [
    [basicOperationId, "BASIC_INFO", "SINGLE"],
    [navOperationId, "NAV", "SINGLE"],
    [selectedOperationId, "BASIC_INFO", "SELECTED"],
    [allOperationId, "BASIC_INFO", "ALL"],
  ] as const) {
    await expect
      .poll(
        async () => {
          const response = await request.get(
            `/api/v1/ingestions/${operationId}`,
          );
          expect(response.ok()).toBeTruthy();
          const envelope = await response.json();
          return envelope.data.status;
        },
        { timeout: 120_000, intervals: [1_000, 2_000, 5_000] },
      )
      .not.toBe("RUNNING");
    const detailResponse = await request.get(
      `/api/v1/ingestions/${operationId}`,
    );
    expect(detailResponse.ok()).toBeTruthy();
    const detail = (await detailResponse.json()).data;
    expect(detail.operation_id).toBe(operationId);
    expect(detail.actor).toBe(actor);
    expect(detail.dataset).toBe(dataset);
    expect(detail.scope_type).toBe(scopeType);
    expect(detail.status).not.toBe("RUNNING");
    const itemsResponse = await request.get(
      `/api/v1/ingestions/${operationId}/items?page=1&page_size=100`,
    );
    expect(itemsResponse.ok()).toBeTruthy();
    const items = (await itemsResponse.json()).data;
    expect(items.total).toBeGreaterThan(0);
    expect(items.items.length).toBeGreaterThan(0);

    if ((detail.failure_count ?? 0) > 0) {
      const retryResponse = await request.post(
        `/api/v1/ingestions/${operationId}/retry-failed`,
        {
          headers: {
            "Idempotency-Key": `pw-live-retry-${crypto.randomUUID()}`,
          },
        },
      );
      expect(retryResponse.status()).toBe(202);
      const retry = (await retryResponse.json()).data;
      expect(retry.operation_id).toBeTruthy();
      const childResponse = await request.get(
        `/api/v1/ingestions/${retry.operation_id}`,
      );
      expect(childResponse.ok()).toBeTruthy();
      const child = (await childResponse.json()).data;
      expect(child.parent_operation_id).toBe(operationId);
      expect(child.actor).toBe(actor);
    }
  }

  const retryResponse = await request.post(
    `/api/v1/ingestions/${failedOperationId}/retry-failed`,
    {
      headers: { "Idempotency-Key": `pw-live-retry-${crypto.randomUUID()}` },
    },
  );
  expect(retryResponse.status()).toBe(202);
  const retry = (await retryResponse.json()).data;
  const childResponse = await request.get(
    `/api/v1/ingestions/${retry.operation_id}`,
  );
  expect(childResponse.ok()).toBeTruthy();
  const child = (await childResponse.json()).data;
  expect(child.parent_operation_id).toBe(failedOperationId);
  expect(child.actor).toBe(actor);
});

import { expect, test } from "@playwright/test";

test("frontend reaches the locally running FastAPI session endpoint", async ({
  page,
}) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/")) apiRequests.push(request.url());
  });
  await page.goto("/funds");
  await expect(page.getByRole("heading", { name: "基金研究" })).toBeVisible();
  await expect.poll(() => apiRequests.length).toBeGreaterThan(0);
  expect(apiRequests.every((url) => url.includes("/api/v1/"))).toBe(true);
});

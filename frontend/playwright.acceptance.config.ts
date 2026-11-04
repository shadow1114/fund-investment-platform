import { defineConfig, devices } from "@playwright/test";

// Frozen browser fixtures only: no API server, scraper, or ingestion worker.
export default defineConfig({
  testDir: "./e2e",
  testMatch: [
    "fund-research-ag-grid.spec.ts",
    "fund-research-layout.spec.ts",
    "fund-detail-modal.spec.ts",
    "business-tables.spec.ts",
    "m17.spec.ts",
    "client-workspace.spec.ts",
  ],
  workers: 1,
  expect: { timeout: 15000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    channel:
      process.env.PLAYWRIGHT_CHANNEL ??
      (process.platform === "darwin" ? "chrome" : undefined),
    baseURL: "http://127.0.0.1:4173",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: true,
  },
});

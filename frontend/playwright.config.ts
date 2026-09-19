import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel:
          process.env.PLAYWRIGHT_CHANNEL ??
          (process.platform === "darwin" ? "chrome" : undefined),
      },
    },
  ],
  webServer: [
    {
      command: "cd .. && LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/uvicorn fip.api.app:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/openapi.json",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: !process.env.CI,
    },
  ],
});

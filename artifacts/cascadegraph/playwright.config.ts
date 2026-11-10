import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const root = path.resolve(import.meta.dirname, "../..");
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:18081", trace: "retain-on-failure" },
  reporter: [["list"]],
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "PORT=18080 LLM_ENABLED=false uv run --frozen python -m cascadegraph_runtime",
      cwd: root,
      url: "http://127.0.0.1:18080/api/v1/health/ready",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "PORT=18081 BASE_PATH=/ CI_API_UPSTREAM=http://127.0.0.1:18080 pnpm --filter @workspace/cascadegraph dev",
      cwd: root,
      url: "http://127.0.0.1:18081",
      reuseExistingServer: !process.env.CI,
    },
  ],
});

import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const root = path.resolve(import.meta.dirname, "../..");
const apiPort = Number(process.env.E2E_API_PORT ?? 18080);
const apiURL = `http://127.0.0.1:${apiPort}`;
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:18081",
    trace: "retain-on-failure",
    // Nix/Replit can use its installed Chromium; CI keeps Playwright's default.
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH },
  },
  reporter: [["list"]],
  projects: [
    { name: "desktop", testIgnore: "**/desktop-layout.spec.ts", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", testIgnore: "**/desktop-layout.spec.ts", use: { ...devices["Pixel 7"] } },
    { name: "desktop-layout", testMatch: "**/desktop-layout.spec.ts", use: { ...devices["Desktop Chrome"], reducedMotion: "reduce" } },
  ],
  webServer: [
    {
      command: `PORT=${apiPort} LLM_ENABLED=false uv run --frozen python -m cascadegraph_runtime`,
      cwd: root,
      url: `${apiURL}/api/v1/health/ready`,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `PORT=18081 BASE_PATH=/ CI_API_UPSTREAM=${apiURL} pnpm --filter @workspace/cascadegraph dev`,
      cwd: root,
      url: "http://127.0.0.1:18081",
      reuseExistingServer: !process.env.CI,
    },
  ],
});

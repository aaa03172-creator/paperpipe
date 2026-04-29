import { defineConfig } from "@playwright/test";
import { resolvePort } from "./playwright.port-utils";

const backendPort = resolvePort("E2E_BACKEND_PORT", "18080");
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*backend\.gated\.spec\.ts/,
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: backendBaseUrl,
    trace: "on-first-retry",
    headless: true,
    httpCredentials: {
      username: "beta",
      password: "beta-pass",
    },
  },
  webServer: [
    {
      command: "./frontend/scripts/run_backend_for_e2e.sh",
      url: `${backendBaseUrl}/health`,
      timeout: 120_000,
      reuseExistingServer,
      cwd: "..",
      env: {
        E2E_BACKEND_PORT: backendPort,
        LATTICE_BETA_PASSWORD: "beta-pass",
      },
    },
  ],
});

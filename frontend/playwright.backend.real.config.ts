import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolvePort } from "./playwright.port-utils";

const backendPort = resolvePort("E2E_BACKEND_PORT", "18080");
const frontendPort = resolvePort("E2E_FRONTEND_PORT", "43174");
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";
const defaultPythonBin = existsSync("../.venv/bin/python") ? "../.venv/bin/python" : "python3";
const pythonBin = process.env.PAPERPIPE_PYTHON_BIN || defaultPythonBin;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*backend\.spec\.ts/,
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: frontendBaseUrl,
    trace: "on-first-retry",
    headless: true,
  },
  webServer: [
    {
      command: `${pythonBin} ./scripts/run_backend_for_real_smoke.py`,
      url: `${backendBaseUrl}/health`,
      timeout: 120_000,
      reuseExistingServer,
      cwd: "..",
      env: {
        E2E_BACKEND_PORT: backendPort,
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      url: frontendBaseUrl,
      timeout: 120_000,
      reuseExistingServer,
      cwd: ".",
      env: {
        LATTICE_UI_BACKEND_URL: backendBaseUrl,
      },
    },
  ],
});

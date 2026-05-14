import { defineConfig } from "@playwright/test";
import { resolvePort } from "./playwright.port-utils";

const backendPort = resolvePort("E2E_BACKEND_PORT", "18080");
const frontendPort = resolvePort("E2E_FRONTEND_PORT", "43174");
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";
const debugFlow = process.env.PAPERPIPE_WORKBENCH_DEBUG_FLOW ?? "cancel-run";
const enableParserWorker = debugFlow === "parser-fallback";
const enableFakeWorker = debugFlow === "cancel-run" || enableParserWorker;

if (enableParserWorker) {
  process.env.PAPERPIPE_E2E_ENABLE_PARSER_WORKER = "1";
}

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*workbench-debug\.spec\.ts/,
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: frontendBaseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    headless: true,
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
        ...(enableFakeWorker
          ? {
              E2E_ENABLE_FAKE_WORKER: "1",
              ...(enableParserWorker ? { PAPERPIPE_E2E_ENABLE_PARSER_WORKER: "1" } : {}),
            }
          : {}),
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

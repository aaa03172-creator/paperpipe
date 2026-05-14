import { defineConfig } from "@playwright/test";
import { resolvePort } from "./playwright.port-utils";

const mockFrontendPort = resolvePort("E2E_MOCK_FRONTEND_PORT", "43173");
const mockFrontendBaseUrl = `http://127.0.0.1:${mockFrontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*mock\.spec\.ts/,
  timeout: 45_000,
  use: {
    baseURL: mockFrontendBaseUrl,
    trace: "on-first-retry",
    headless: true,
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${mockFrontendPort}`,
    url: mockFrontendBaseUrl,
    timeout: 120_000,
    reuseExistingServer: false,
    cwd: ".",
    env: {
      LATTICE_UI_BACKEND_URL: "http://127.0.0.1:8999",
      VITE_FORCE_MOCK: "1",
    },
  },
});

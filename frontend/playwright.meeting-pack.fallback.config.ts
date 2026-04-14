import { defineConfig } from "@playwright/test";
import { resolvePort } from "./playwright.port-utils";

const fallbackFrontendPort = resolvePort("E2E_MEETING_PACK_FALLBACK_FRONTEND_PORT", "43176");
const fallbackFrontendBaseUrl = `http://127.0.0.1:${fallbackFrontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*meeting-pack\.fallback\.spec\.ts/,
  timeout: 45_000,
  use: {
    baseURL: fallbackFrontendBaseUrl,
    trace: "on-first-retry",
    headless: true,
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${fallbackFrontendPort}`,
    url: fallbackFrontendBaseUrl,
    timeout: 120_000,
    reuseExistingServer: false,
    cwd: ".",
    env: {
      VITE_API_BASE_URL: "http://127.0.0.1:8999",
      VITE_AUTO_MOCK_FALLBACK: "1",
    },
  },
});

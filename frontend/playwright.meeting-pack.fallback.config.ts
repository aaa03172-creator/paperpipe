import { defineConfig } from "@playwright/test";
import { resolvePort } from "./playwright.port-utils";

const frontendPort = resolvePort("E2E_MEETING_PACK_FALLBACK_FRONTEND_PORT", "43176");
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /meeting-pack\.fallback\.spec\.ts/,
  timeout: 45_000,
  use: {
    baseURL: frontendBaseUrl,
    trace: "on-first-retry",
    headless: true,
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
    url: frontendBaseUrl,
    timeout: 120_000,
    reuseExistingServer: false,
    cwd: ".",
    env: {
      LATTICE_UI_BACKEND_URL: "http://127.0.0.1:8999",
      VITE_AUTO_MOCK_FALLBACK: "1",
    },
  },
});

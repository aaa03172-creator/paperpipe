import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*backend\.spec\.ts/,
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:43174",
    trace: "on-first-retry",
    headless: true,
  },
  webServer: [
    {
      command: "./frontend/scripts/run_backend_for_e2e.sh",
      url: "http://127.0.0.1:18080/health",
      timeout: 120_000,
      reuseExistingServer: false,
      cwd: "..",
      env: {
        E2E_BACKEND_PORT: "18080",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 43174",
      url: "http://127.0.0.1:43174",
      timeout: 120_000,
      reuseExistingServer: false,
      cwd: ".",
      env: {
        VITE_API_BASE_URL: "http://127.0.0.1:18080",
      },
    },
  ],
});

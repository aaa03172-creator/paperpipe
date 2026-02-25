import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*backend\.spec\.ts/,
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:4174",
    trace: "on-first-retry",
    headless: true,
  },
  webServer: [
    {
      command: "./frontend/scripts/run_backend_for_e2e.sh",
      url: "http://127.0.0.1:8000/health",
      timeout: 120_000,
      reuseExistingServer: true,
      cwd: "..",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4174",
      url: "http://127.0.0.1:4174",
      timeout: 120_000,
      reuseExistingServer: true,
      cwd: ".",
      env: {
        VITE_API_BASE_URL: "http://127.0.0.1:8000",
      },
    },
  ],
});

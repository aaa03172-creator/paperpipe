import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*mock\.spec\.ts/,
  timeout: 45_000,
  use: {
    baseURL: "http://127.0.0.1:43173",
    trace: "on-first-retry",
    headless: true,
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 43173",
    url: "http://127.0.0.1:43173",
    timeout: 120_000,
    reuseExistingServer: false,
    cwd: ".",
    env: {
      VITE_API_BASE_URL: "http://127.0.0.1:8999",
      VITE_FORCE_MOCK: "1",
    },
  },
});

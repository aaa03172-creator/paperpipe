import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";
import { resolvePort } from "./playwright.port-utils";

const frontendDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendDir, "..");

function resolveVerificationPython(): string {
  const resolverScript = resolve(repoRoot, "scripts/resolve_verification_python.py");
  for (const candidate of ["python3", "python"]) {
    try {
      return execFileSync(
        candidate,
        [resolverScript, "--require-module", "fastapi", "--require-module", "uvicorn"],
        {
          cwd: repoRoot,
          encoding: "utf-8",
        },
      ).trim();
    } catch {
      continue;
    }
  }
  throw new Error("python3/python not found");
}

const backendPort = resolvePort("E2E_BACKEND_PORT", "18080");
const frontendPort = resolvePort("E2E_FRONTEND_PORT", "43174");
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";
const verificationPython = resolveVerificationPython();
const backendCommand = `${JSON.stringify(verificationPython)} ./scripts/run_backend_for_real_smoke.py`;

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
      command: backendCommand,
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

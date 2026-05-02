import { expect, test, type Page } from "@playwright/test";
import { promises as fs } from "node:fs";

const runParserWorkerLane = process.env.PAPERPIPE_E2E_ENABLE_PARSER_WORKER === "1";
const backendPort = process.env.E2E_BACKEND_PORT ?? "18080";
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const REVIEW_WORKBENCH_SUBTITLE =
  "Review evidence, saved checks, and claim flags before regenerating or exporting downstream artifacts.";
const MAX_DEBUG_EVENTS = 50;

interface ConsoleEventRow {
  type: string;
  text: string;
  location?: {
    url?: string;
    lineNumber?: number;
    columnNumber?: number;
  };
}

interface NetworkEventRow {
  url: string;
  method: string;
  status?: number;
  errorText?: string;
}

interface PageErrorRow {
  message: string;
  stack?: string;
}

interface BrowserDebugCollector {
  consoleEvents: ConsoleEventRow[];
  failedRequests: NetworkEventRow[];
  failedResponses: NetworkEventRow[];
  pageErrors: PageErrorRow[];
}

const collectors = new WeakMap<Page, BrowserDebugCollector>();

function pushCapped<T>(items: T[], value: T): void {
  if (items.length >= MAX_DEBUG_EVENTS) {
    return;
  }
  items.push(value);
}

test.beforeEach(async ({ page }) => {
  const collector: BrowserDebugCollector = {
    consoleEvents: [],
    failedRequests: [],
    failedResponses: [],
    pageErrors: [],
  };
  collectors.set(page, collector);

  page.on("console", (message) => {
    pushCapped(collector.consoleEvents, {
      type: message.type(),
      text: message.text(),
      location: message.location(),
    });
  });

  page.on("pageerror", (error) => {
    pushCapped(collector.pageErrors, {
      message: error.message,
      stack: error.stack,
    });
  });

  page.on("requestfailed", (request) => {
    pushCapped(collector.failedRequests, {
      url: request.url(),
      method: request.method(),
      errorText: request.failure()?.errorText,
    });
  });

  page.on("response", (response) => {
    if (response.status() < 400) {
      return;
    }
    pushCapped(collector.failedResponses, {
      url: response.url(),
      method: response.request().method(),
      status: response.status(),
    });
  });
});

test.afterEach(async ({ page }, testInfo) => {
  const collector = collectors.get(page);
  const summaryPath = testInfo.outputPath("browser-debug-summary.json");
  await fs.writeFile(
    summaryPath,
    JSON.stringify(
      {
        title: testInfo.title,
        status: testInfo.status,
        expectedStatus: testInfo.expectedStatus,
        finalUrl: page.url(),
        consoleEvents: collector?.consoleEvents ?? [],
        pageErrors: collector?.pageErrors ?? [],
        failedRequests: collector?.failedRequests ?? [],
        failedResponses: collector?.failedResponses ?? [],
      },
      null,
      2,
    ),
    "utf-8",
  );
  await testInfo.attach("browser-debug-summary", {
    path: summaryPath,
    contentType: "application/json",
  });

  if (testInfo.status !== testInfo.expectedStatus) {
    const screenshotPath = testInfo.outputPath("browser-debug-failure.png");
    await page.screenshot({ path: screenshotPath, fullPage: true });
    await testInfo.attach("browser-debug-failure", {
      path: screenshotPath,
      contentType: "image/png",
    });
  }
});

test("workbench debug cancel run flow", async ({ page, request }) => {
  const paperId = "paper-e2e-rebuild-001";
  const enqueueResponse = await request.post(`${backendBaseUrl}/jobs/deepread`, {
    data: { paper_id: paperId },
  });
  expect(enqueueResponse.ok()).toBeTruthy();
  const enqueuePayload = (await enqueueResponse.json()) as {
    job_id?: string;
    status?: string;
  };
  expect(typeof enqueuePayload.job_id).toBe("string");
  expect(enqueuePayload.status).toBe("queued");
  const jobId = enqueuePayload.job_id!;

  await page.goto(`/workbench/${paperId}`);

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cancel run" })).toBeVisible();

  await page.getByRole("button", { name: "Terminal logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Cancel run" }).click();

  await expect(page.getByTestId("cancel-run-success")).toContainText(
    "The current deep read was cancelled. Existing saved artifacts stay as-is.",
  );
  await expect(page.getByRole("button", { name: "Run deep read" })).toBeVisible();
  await expect(terminalDrawer.locator("pre")).toContainText(`deepread cancelled (${jobId})`, { timeout: 15_000 });
});

test("workbench debug parser fallback flow", async ({ page, request }) => {
  test.skip(!runParserWorkerLane, "requires parser worker debug lane");

  await page.goto("/workbench/paper-e2e-001?parser_backend=docling");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await page.getByRole("button", { name: /Run deep read/i }).first().click();

  await expect
    .poll(async () => {
      const response = await request.get(`${backendBaseUrl}/jobs?paper_id=paper-e2e-001`);
      if (!response.ok()) {
        return "request_failed";
      }
      const payload = (await response.json()) as unknown;
      const jobs =
        Array.isArray(payload)
          ? payload
          : payload && typeof payload === "object" && Array.isArray((payload as { jobs?: unknown[] }).jobs)
            ? (payload as { jobs: unknown[] }).jobs
            : [];
      return jobs.some((job) => {
        if (!job || typeof job !== "object") {
          return false;
        }
        const row = job as { requested_parser_backend?: unknown; parser_backend?: unknown; status?: unknown };
        return (
          row.requested_parser_backend === "docling" &&
          row.parser_backend === "fitz_pdfplumber" &&
          row.status === "completed"
        );
      })
        ? "completed"
        : "pending";
    }, { timeout: 15_000 })
    .toBe("completed");

  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  if (!(await terminalDrawer.getByText("Terminal Logs", { exact: true }).isVisible().catch(() => false))) {
    await page.getByRole("button", { name: /^Terminal logs$/ }).first().click({ force: true });
  }
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();
  await expect
    .poll(async () => (await terminalDrawer.locator("pre").textContent()) ?? "", { timeout: 15_000 })
    .toMatch(/deepread enqueued|User queued deep read/);
  await expect
    .poll(async () => (await terminalDrawer.locator("pre").textContent()) ?? "", { timeout: 15_000 })
    .toMatch(/resolved parser backend: fitz_pdfplumber|\[INFO\] completed/);
  await expect(page.getByTestId("workbench-parser-selection").first()).toContainText(
    "Document reader PDF text (requested Docling)",
  );
});

test("workbench debug repair stats flow", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-repair-001");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  const repairButton = page.getByRole("button", { name: "Refresh checks", exact: true });
  const statsSnapshotSummary = page.locator("summary").filter({ hasText: "Saved checks" });
  await expect(page.getByText("Obsidian sync payload preview")).toBeVisible();
  await expect(page.getByTestId("repair-stats-warning")).toContainText(
    "Saved note checks are missing or empty.",
    { timeout: 15_000 },
  );
  await expect(repairButton).toBeVisible();
  await expect(statsSnapshotSummary).toHaveCount(0);

  await page.getByRole("button", { name: "Terminal logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await repairButton.click();

  await expect(terminalDrawer.locator("pre")).toContainText("repair-stats summary", { timeout: 15_000 });
  await expect(repairButton).toHaveCount(0);
  await expect(page.getByTestId("repair-stats-success")).toContainText(
    "Saved checks rebuilt from the current saved claims.",
  );
  await expect(page.getByTestId("workbench-ops-reason")).toContainText("checks are ready.");
  await expect(statsSnapshotSummary).toBeVisible();
});

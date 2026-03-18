import { expect, test } from "@playwright/test";

test("mock mode fallback renders full phase3 flow", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/workbench\//);

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  await expect(page.getByLabel("Reasoning").first()).toBeVisible();
  await expect(page.getByLabel("Profile").first()).toBeVisible();

  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.getByText("Cell 1 Claim")).toBeVisible();

  await page.getByRole("button", { name: "Show Terminal Logs" }).click();
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Deep Read Run" }).click();
  await expect(terminalDrawer.locator("pre")).toContainText("deepread enqueued", { timeout: 15_000 });
});

test("encoded paper id route does not crash in workbench", async ({ page }) => {
  await page.goto("/workbench/paper%25id");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  await expect(page.getByText("Invalid paper id.")).toHaveCount(0);
});

test("paper notes query state syncs with URL params", async ({ page }) => {
  await page.goto("/papers?q=alzheimer&sort=confidence&order=asc&page=3");

  await expect(page.locator('input[placeholder="title / alias / slug"]')).toHaveValue("alzheimer");
  await expect(page.locator("select").nth(1)).toHaveValue("confidence");
  await expect(page).toHaveURL(/\/papers\?q=alzheimer&sort=confidence&order=asc$/);

  await page.locator('input[placeholder="title / alias / slug"]').fill("biomarker");
  await expect(page).toHaveURL(/\/papers\?q=biomarker&sort=confidence&order=asc$/);

  await page.getByRole("button", { name: "Toggle sort order" }).click();
  await expect(page).toHaveURL(/\/papers\?q=biomarker&sort=confidence$/);
});

test("issue button routes with focus=issues and selects risk claim", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await page.locator("tbody tr").first().locator("td").nth(2).getByRole("button").click();

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(page).toHaveURL(/focus=issues/);
  await expect(page.getByTestId("content-review-notice")).toContainText("3 content review flags available.");
  await expect(page.getByTestId("content-review-notice")).toContainText("Issue focus is enabled.");
  await expect(page.getByText("Claim Link · p.1")).toBeVisible();
  await expect(highlight).toBeVisible();

  const viewerBox = await viewer.boundingBox();
  const beforeBox = await highlight.boundingBox();
  expect(viewerBox).not.toBeNull();
  expect(beforeBox).not.toBeNull();
  if (viewerBox && beforeBox) {
    expect(beforeBox.width).toBeGreaterThan(24);
    expect(beforeBox.height).toBeGreaterThan(24);
    expect(beforeBox.width).toBeLessThan(viewerBox.width * 0.95);
    expect(beforeBox.height).toBeLessThan(viewerBox.height * 0.95);
    expect(beforeBox.x).toBeGreaterThanOrEqual(viewerBox.x - 2);
    expect(beforeBox.y).toBeGreaterThanOrEqual(viewerBox.y - 2);
    expect(beforeBox.x + beforeBox.width).toBeLessThanOrEqual(viewerBox.x + viewerBox.width + 2);
    expect(beforeBox.y + beforeBox.height).toBeLessThanOrEqual(viewerBox.y + viewerBox.height + 2);
  }

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await claimsPanel.getByRole("button").first().click();

  await expect(page.getByText("Claim Link · p.1")).toBeVisible();
  await expect(highlight).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]')).toHaveCount(1);

  const afterBox = await highlight.boundingBox();
  expect(afterBox).not.toBeNull();
  if (beforeBox && afterBox) {
    const movedDelta =
      Math.abs(beforeBox.x - afterBox.x) +
      Math.abs(beforeBox.y - afterBox.y) +
      Math.abs(beforeBox.width - afterBox.width) +
      Math.abs(beforeBox.height - afterBox.height);
    expect(movedDelta).toBeGreaterThan(12);
  }
});

test("not analyzed papers do not masquerade as clear content review", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  const row = page.locator("tbody tr").filter({ hasText: "Systems Omics Review for Metabolic Resilience" }).first();
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review unavailable");
  await expect(row.getByTestId("triage-review-badge")).toContainText("Unavailable");
  await expect(row.getByTestId("triage-review-hint")).toContainText("Content review has not been generated");
  await expect(row.getByTestId("triage-review-detail")).toContainText("Not analyzed");
});

test("runtime guard shows fallback and missing-text notices when claim evidence is incomplete", async ({ page }) => {
  await page.goto("/workbench/paper-2025-nutrition");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await expect(page.getByTestId("claim-guard-fallback")).toBeVisible();
  await expect(page.getByTestId("claim-guard-text-missing")).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByText("Missing evidence")).toBeVisible();
  await expect(claimsPanel.getByText("Text missing", { exact: true })).toBeVisible();
});

test("obsidian stats snapshot click jumps to mapped claim highlight", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Claim Link · p.1")).toBeVisible();

  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(mirrorPanel).toBeVisible();

  const targetCheck = mirrorPanel.getByRole("button").filter({ hasText: "effect-size" }).first();
  await expect(targetCheck).toBeVisible();
  await targetCheck.click();

  await expect(page.getByText("Claim Link · p.1")).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
  await page.screenshot({ path: "../tmp_verify_obsidian_stats_jump.png", fullPage: true });
});

test("duplicate claim highlights prefer bbox anchor over text fallback", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel).toBeVisible();

  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();
  await expect(pdfPanel.getByText("Text Match · p.4")).toHaveCount(0);
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
});

test("stats snapshot disambiguates target claim by text signal", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();

  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  const targetCheck = mirrorPanel.getByRole("button").filter({ hasText: "effect-size-disambiguation" }).first();
  await expect(targetCheck).toBeVisible();
  await targetCheck.click();

  await expect(pdfPanel.getByText("Claim Link · p.2")).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
});

test("mirror grounding badges surface resolved and review-needed evidence states", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(mirrorPanel).toBeVisible();

  await expect(mirrorPanel.getByTestId("workbench-mirror-claim-grounding-claim-1")).toContainText("Grounded");
  await expect(mirrorPanel.getByTestId("workbench-mirror-stat-grounding-mock-check-2")).toContainText("Needs review");
});

test("timeline surfaces user-triggered actions distinctly", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  const timelinePanel = page.locator("section").filter({ hasText: "Timeline" }).first();
  await expect(timelinePanel).toBeVisible();

  await expect(timelinePanel.getByTestId("timeline-pinned-user-action")).toContainText("User queued deep read");
  await expect(timelinePanel.getByTestId("timeline-source-user-action").first()).toContainText("USER");
  await expect(timelinePanel.getByTestId("timeline-row-user-action").first()).toContainText("User queued deep read");
});

test("notebook artifact normalization supports zero-based pages and mixed bbox units", async ({ page }) => {
  await page.goto("/workbench/paper-2026-notebook-normalized");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(viewer).toBeVisible();
  await expect(highlight).toBeVisible();

  const viewerBox = await viewer.boundingBox();
  const highlightBox = await highlight.boundingBox();
  expect(viewerBox).not.toBeNull();
  expect(highlightBox).not.toBeNull();
  if (viewerBox && highlightBox) {
    expect(highlightBox.width).toBeGreaterThan(viewerBox.width * 0.08);
    expect(highlightBox.height).toBeGreaterThan(viewerBox.height * 0.08);
    expect(highlightBox.x).toBeGreaterThanOrEqual(viewerBox.x - 2);
    expect(highlightBox.y).toBeGreaterThanOrEqual(viewerBox.y - 2);
    expect(highlightBox.x + highlightBox.width).toBeLessThanOrEqual(viewerBox.x + viewerBox.width + 2);
    expect(highlightBox.y + highlightBox.height).toBeLessThanOrEqual(viewerBox.y + viewerBox.height + 2);
  }

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await claimsPanel.getByRole("button").nth(1).click();
  await expect(pdfPanel.getByText("Claim Link · p.2")).toBeVisible();
  const secondHighlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(secondHighlight).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]')).toHaveCount(1);

  const secondHighlightBox = await secondHighlight.boundingBox();
  expect(secondHighlightBox).not.toBeNull();
  if (viewerBox && secondHighlightBox) {
    expect(secondHighlightBox.width).toBeGreaterThan(viewerBox.width * 0.2);
    expect(secondHighlightBox.height).toBeGreaterThan(viewerBox.height * 0.15);
    expect(secondHighlightBox.x + secondHighlightBox.width).toBeLessThanOrEqual(viewerBox.x + viewerBox.width + 2);
    expect(secondHighlightBox.y + secondHighlightBox.height).toBeLessThanOrEqual(viewerBox.y + viewerBox.height + 2);
  }
});

test.describe("mobile UX scenarios", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("mobile triage cards and workbench collapsed controls work", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
    await expect(page.getByText(/^Mock mode$/)).toBeVisible();

    const firstMobileCard = page.locator("article").filter({ hasText: "Open Workbench" }).first();
    await expect(firstMobileCard).toBeVisible();
    await firstMobileCard.getByRole("button", { name: "Open Workbench" }).click();

    await expect(page).toHaveURL(/\/workbench\//);
    await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();

    const controlsSummary = page.locator('summary:has-text("Run & View Controls")').first();
    await expect(controlsSummary).toBeVisible();
    await controlsSummary.click();

    const runViewControls = controlsSummary.locator("xpath=..");
    await expect(runViewControls.getByLabel("Reasoning")).toBeVisible();
    await expect(runViewControls.getByLabel("Profile")).toBeVisible();
    await expect(page.getByRole("button", { name: "Deep Read Run" }).first()).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
    await expect(page.getByText("Pinned Events")).toBeVisible();

    const railSummary = page.getByRole("button", { name: /Papers ·/ }).first();
    await expect(railSummary).toBeVisible();
  });
});

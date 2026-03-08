import { expect, test } from "@playwright/test";

test("mock mode fallback renders full phase3 flow", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/workbench\//);

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

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
  await expect(page.getByText("Issue focus enabled: prioritizing risk-related claims.")).toBeVisible();
  await expect(page.getByText("Claim Link · p.5")).toBeVisible();
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
  }

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await claimsPanel.getByRole("button").first().click();

  await expect(page.getByText("Claim Link · p.3")).toBeVisible();
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

test("runtime guard shows fallback and missing-text notices when claim evidence is incomplete", async ({ page }) => {
  await page.goto("/workbench/paper-2025-nutrition");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await expect(page.getByTestId("claim-guard-fallback")).toBeVisible();
  await expect(page.getByTestId("claim-guard-text-missing")).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByText("Missing evidence")).toBeVisible();
  await expect(claimsPanel.getByText("Text missing").first()).toBeVisible();
});

test("obsidian stats snapshot click jumps to mapped claim highlight", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Claim Link · p.3")).toBeVisible();

  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(mirrorPanel).toBeVisible();

  const targetCheck = mirrorPanel.getByRole("button").filter({ hasText: "effect-size" }).first();
  await expect(targetCheck).toBeVisible();
  await targetCheck.click();

  await expect(page.getByText("Claim Link · p.4")).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
  await page.screenshot({ path: "../tmp_verify_obsidian_stats_jump.png", fullPage: true });
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

    await expect(page.getByRole("button", { name: "Deep Read Run" }).first()).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
    await expect(page.getByText("Pinned Events")).toBeVisible();

    const railSummary = page.getByRole("button", { name: /Papers ·/ }).first();
    await expect(railSummary).toBeVisible();
  });
});

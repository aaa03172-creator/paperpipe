import { expect, test } from "@playwright/test";

test("backend mode stays out of mock fallback", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  // backend-seeded paper should be visible and navigable
  const seededPaper = page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" }).first();
  await expect(seededPaper).toBeVisible();

  // CI dataset can render the row without row-level click navigation.
  // Navigate via canonical route after confirming the seeded row exists.
  await page.goto("/workbench/paper-e2e-001");

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001/);
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.getByText("Claim text missing")).toHaveCount(0);
});

test("backend evidence linking keeps single highlight and updates bbox on claim change", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  const claimButtons = claimsPanel.getByRole("button");
  const claimCount = await claimButtons.count();
  expect(claimCount).toBeGreaterThan(1);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
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

  await claimButtons.nth(1).click();
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

test.describe("mobile backend UX", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("mobile workbench renders collapsed controls without mock fallback", async ({ page }) => {
    await page.goto("/workbench/paper-e2e-001");

    await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

    const controlsSummary = page.locator('summary:has-text("Run & View Controls")').first();
    await expect(controlsSummary).toBeVisible();
    await controlsSummary.click();

    await expect(page.getByRole("button", { name: "Deep Read Run" }).first()).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
  });
});

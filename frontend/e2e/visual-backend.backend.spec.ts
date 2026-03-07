import { expect, test, Page } from "@playwright/test";

async function openBackendWorkbenchAndSelectSecondClaim(page: Page) {
  await page.goto("/workbench/paper-e2e-001");
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button")).toHaveCount(3);
  await claimsPanel.getByRole("button").nth(1).click();
  await expect(page.locator('[data-testid="claim-highlight"]')).toHaveCount(1);
}

async function openBackendPaperNotes(page: Page) {
  await page.goto("/papers");
  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
}

test("visual regression (backend, desktop): paper notes list layout", async ({ page }) => {
  await openBackendPaperNotes(page);

  const notesPage = page.locator("div.min-h-screen").first();
  await expect(notesPage).toHaveScreenshot("backend-desktop-paper-notes-list.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 2800,
  });
});

test("visual regression (backend, desktop): workbench rail layout", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  const rail = page.locator("aside").filter({ hasText: "Navigation Rail" }).first();
  await expect(rail).toHaveScreenshot("backend-desktop-workbench-rail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 1800,
  });
});

test("visual regression (backend, desktop): claim highlight in pdf viewer", async ({ page }) => {
  await openBackendWorkbenchAndSelectSecondClaim(page);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  await expect(viewer).toHaveScreenshot("backend-desktop-claim-highlight.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 1200,
  });
});

test.describe("mobile visual regression (backend)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("claim highlight in pdf viewer", async ({ page }) => {
    await openBackendWorkbenchAndSelectSecondClaim(page);

    const viewer = page.locator('[data-testid="pdf-viewer"]').first();
    await expect(viewer).toHaveScreenshot("backend-mobile-claim-highlight.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 1200,
    });
  });

  test("paper notes list layout", async ({ page }) => {
    await openBackendPaperNotes(page);

    const notesPage = page.locator("div.min-h-screen").first();
    await expect(notesPage).toHaveScreenshot("backend-mobile-paper-notes-list.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 2800,
    });
  });
});

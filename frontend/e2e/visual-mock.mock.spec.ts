import { expect, test, Page } from "@playwright/test";

async function openMockWorkbenchAndSelectSecondClaim(page: Page) {
  await page.goto("/workbench/paper-2023-imaging");
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode/)).toBeVisible();
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await claimsPanel.getByRole("button").nth(1).click();
  await expect(page.locator('[data-testid="claim-highlight"]')).toHaveCount(1);
}

test("visual regression (mock, desktop): claim highlight in pdf viewer", async ({ page }) => {
  await openMockWorkbenchAndSelectSecondClaim(page);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  await expect(viewer).toHaveScreenshot("mock-desktop-claim-highlight.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.03,
  });
});

test.describe("mobile visual regression (mock)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("claim highlight in pdf viewer", async ({ page }) => {
    await openMockWorkbenchAndSelectSecondClaim(page);

    const viewer = page.locator('[data-testid="pdf-viewer"]').first();
    await expect(viewer).toHaveScreenshot("mock-mobile-claim-highlight.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.03,
    });
  });
});

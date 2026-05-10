import { expect, test, Page } from "@playwright/test";

const REVIEW_WORKBENCH_SUBTITLE =
  "Review evidence, saved checks, and claim flags before regenerating or exporting downstream artifacts.";

async function openMockWorkbenchAndSelectSecondClaim(page: Page) {
  await page.goto("/workbench/paper-2023-imaging");
  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  await expect(viewer).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await claimsPanel.getByRole("button").nth(1).click();
  await viewer.scrollIntoViewIfNeeded();
  await expect(viewer.locator('[data-testid="claim-highlight"]')).toHaveCount(1);
}

async function getStablePdfPage(page: Page) {
  const pdfPage = page.getByRole("region", { name: /^Page 1$/ }).first();
  await expect(pdfPage).toBeVisible();
  return pdfPage;
}

test("visual regression (mock, desktop): claim highlight in pdf viewer", async ({ page }) => {
  await openMockWorkbenchAndSelectSecondClaim(page);

  const pdfPage = await getStablePdfPage(page);
  await expect(pdfPage).toHaveScreenshot("mock-desktop-claim-highlight.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 1200,
  });
});

test.describe("mobile visual regression (mock)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("claim highlight in pdf viewer", async ({ page }) => {
    await openMockWorkbenchAndSelectSecondClaim(page);

    const pdfPage = await getStablePdfPage(page);
    await expect(pdfPage).toHaveScreenshot("mock-mobile-claim-highlight.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 1200,
    });
  });
});

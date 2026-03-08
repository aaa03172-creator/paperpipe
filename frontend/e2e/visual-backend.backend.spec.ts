import { expect, test, Page } from "@playwright/test";

async function openBackendWorkbenchAndSelectSecondClaim(page: Page) {
  await page.goto("/workbench/paper-e2e-001");
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button")).toHaveCount(3);
  await claimsPanel.getByRole("button").nth(1).click();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
}

async function openBackendPaperNotes(page: Page) {
  await page.goto("/papers");
  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
}

async function openBackendPaperNoteDetail(page: Page) {
  await page.goto("/papers/zoteroduboisAlzheimerDiseaseClinicalBiological2024");
  await expect(
    page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
  ).toBeVisible();
}

test("visual regression (backend, desktop): paper notes list layout", async ({ page }) => {
  await openBackendPaperNotes(page);

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
});

test("visual regression (backend, desktop): paper note detail layout", async ({ page }) => {
  await openBackendPaperNoteDetail(page);

  await expect(page.locator("aside").filter({ hasText: "Properties" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "References" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open in Workbench" }).first()).toBeVisible();
});

test("visual regression (backend, desktop): workbench rail layout", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  const rail = page.locator("aside").filter({ hasText: "Navigation Rail" }).first();
  await expect(rail).toBeVisible();
  await expect(rail.getByPlaceholder("Search papers")).toBeVisible();
  await expect(rail.getByRole("button", { name: /E2E Seed Paper/i })).toBeVisible();
});

test("visual regression (backend, desktop): claim highlight in pdf viewer", async ({ page }) => {
  await openBackendWorkbenchAndSelectSecondClaim(page);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  await expect(viewer).toHaveScreenshot("backend-desktop-claim-highlight.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 1600,
  });
});

test.describe("mobile visual regression (backend)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("claim highlight in pdf viewer", async ({ page }) => {
    await page.goto("/workbench/paper-e2e-001");
    await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
    const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
    await expect(claimsPanel.getByRole("button").first()).toBeVisible();
  });

  test("paper notes list layout", async ({ page }) => {
    await openBackendPaperNotes(page);
    await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
    await expect(page.locator("article a[href^=\"/papers/\"]").first()).toBeVisible();
  });

  test("paper note detail layout", async ({ page }) => {
    await openBackendPaperNoteDetail(page);
    await expect(page.locator("aside").filter({ hasText: "Properties" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Related Papers" })).toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

const runSoftGateCanary = process.env.PAPERPIPE_E2E_CANARY === "1";

test("backend mode stays out of mock fallback", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  // backend-seeded paper should be visible and navigable
  const seededPaper = page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" }).first();
  await expect(seededPaper).toBeVisible();
  await seededPaper.click();

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
    expect(beforeBox.x).toBeGreaterThanOrEqual(viewerBox.x - 2);
    expect(beforeBox.y).toBeGreaterThanOrEqual(viewerBox.y - 2);
    expect(beforeBox.x + beforeBox.width).toBeLessThanOrEqual(viewerBox.x + viewerBox.width + 2);
    expect(beforeBox.y + beforeBox.height).toBeLessThanOrEqual(viewerBox.y + viewerBox.height + 2);
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

    await expect(page.getByRole("button", { name: /Deep Read(?: Run)?/ }).first()).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
  });
});

test("paper notes detail renders properties, markdown, related papers, and references", async ({ page }) => {
  await page.goto("/papers/zoteroduboisAlzheimerDiseaseClinicalBiological2024");

  await expect(
    page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
  ).toBeVisible();
  const propertiesPanel = page.locator("aside").filter({ hasText: "Properties" }).first();
  await expect(propertiesPanel.getByRole("heading", { name: "Properties" })).toBeVisible();
  await expect(propertiesPanel.getByText("INDEXED", { exact: true })).toBeVisible();
  await expect(propertiesPanel.getByText("Medicine/Neurology", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "One-Line Summary" })).toBeVisible();

  const relatedHeading = page.getByRole("heading", { name: "Related Papers" }).first();
  await expect(relatedHeading).toBeVisible();
  const relatedSection = relatedHeading.locator("xpath=ancestor::section[1]");
  const firstRelatedItem = relatedSection.locator("li").first();
  await expect(firstRelatedItem).toBeVisible();
  await expect(firstRelatedItem).toContainText(/shared tags:/i);
  const relatedLink = firstRelatedItem.getByRole("link").first();
  await expect(relatedLink).toBeVisible();
  await expect(relatedLink).toHaveAttribute("href", /\/papers\//);

  const referencesHeading = page.getByRole("heading", { name: "References" }).first();
  await expect(referencesHeading).toBeVisible();
  const referencesSection = referencesHeading.locator("xpath=ancestor::section[1]");
  const openPdfLink = referencesSection.getByRole("link", { name: /Open PDF/i }).first();
  await expect(openPdfLink).toBeVisible();
  await expect(openPdfLink).toHaveAttribute("href", /^(file:|https?:\/\/)/);

  const workbenchLink = page.getByRole("link", { name: "Open in Workbench" }).first();
  await expect(workbenchLink).toBeVisible();
  await expect(workbenchLink).toHaveAttribute("href", /\/workbench\/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024$/);

  await relatedLink.click();
  await expect(page).toHaveURL(/\/papers\/.+$/);
  await expect(page.getByRole("banner").getByRole("heading")).toBeVisible();
});

test("soft-gate canary: intentional backend e2e failure drill", async () => {
  test.skip(!runSoftGateCanary, "Set PAPERPIPE_E2E_CANARY=1 to run intentional failure drill.");
  expect(1).toBe(2);
});

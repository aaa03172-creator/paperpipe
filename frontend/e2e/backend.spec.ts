import { expect, test } from "@playwright/test";

test("backend mode stays out of mock fallback", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  // backend-seeded paper should be visible and navigable
  const seededPaper = page.getByText("E2E Seed Paper").first();
  await expect(seededPaper).toBeVisible();
  await seededPaper.click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001/);
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await expect(page.locator('iframe[title="Paper PDF"]')).toBeVisible();
});

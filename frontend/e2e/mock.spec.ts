import { expect, test } from "@playwright/test";

test("mock mode fallback renders full phase3 flow", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/workbench\//);

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await expect(page.locator('iframe[title="Paper PDF"]')).toBeVisible();
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

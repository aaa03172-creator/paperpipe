import { expect, test } from "@playwright/test";

test("chart pack viewer filters saved packs and opens warning-forward detail in mock mode", async ({ page }) => {
  await page.goto("/chart-packs");

  await expect(page.getByRole("heading", { name: "Chart Packs", exact: true })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  await expect(page.getByText("Verification and measurement chart pack")).toBeVisible();

  await page.locator('input[placeholder="Search title or chart pack id"]').fill("status");
  await expect(page.getByText("Status count review pack")).toBeVisible();
  await expect(page.getByText("Verification and measurement chart pack")).toHaveCount(0);

  await page.locator('input[placeholder="Search title or chart pack id"]').fill("verification");
  await expect(page.getByText("Verification and measurement chart pack")).toBeVisible();

  const targetCard = page.locator("article").filter({ hasText: "Verification and measurement chart pack" }).first();
  await targetCard.getByRole("button", { name: "Open chart pack" }).click();

  await expect(page).toHaveURL(/\/chart-packs\/chartpack_/);
  await expect(page.getByRole("heading", { name: "Verification and measurement chart pack", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Charts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Caution Notes" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Render Env" })).toBeVisible();
  const verificationCard = page.locator("article").filter({ hasText: "Verification scatter" }).first();
  await expect(verificationCard).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Measurement line" }).first()).toBeVisible();
  await expect(verificationCard.getByText("Approximate reported p values were skipped from the scatter snapshot.")).toBeVisible();
  await expect(page.getByText("Deterministic template-driven spec builder over saved artifact snapshots.")).toBeVisible();

  const csvExport = page.getByRole("link", { name: "Export CSV" }).first();
  await expect(csvExport).toBeVisible();
  await expect(csvExport).toHaveAttribute("download", /chart_01_reported-vs-computed-p-scatter\.csv/);
  await expect(csvExport).toHaveAttribute("href", /data:text\/csv/);

  const specExport = page.getByRole("link", { name: "Open spec JSON" }).first();
  await expect(specExport).toBeVisible();
  await expect(specExport).toHaveAttribute("download", /chart_01_reported-vs-computed-p-scatter\.json/);
  await expect(specExport).toHaveAttribute("href", /data:application\/json/);
});

test("chart pack viewer keeps second mock pack detail aligned with the selected index item", async ({ page }) => {
  await page.goto("/chart-packs");

  await page.locator('input[placeholder="Search title or chart pack id"]').fill("status");
  const targetCard = page.locator("article").filter({ hasText: "Status count review pack" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("1 charts")).toBeVisible();
  await expect(targetCard.getByText("0 warnings")).toBeVisible();

  await targetCard.getByRole("button", { name: "Open chart pack" }).click();

  await expect(page).toHaveURL(/\/chart-packs\/chartpack_20260319T221500Z_mock5678/);
  await expect(page.getByRole("heading", { name: "Status count review pack", exact: true })).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Verification status counts" }).first()).toBeVisible();
  await expect(page.getByText("No pack-level warnings saved.")).toBeVisible();
  await expect(page.getByText("No caution notes saved for this chart pack.")).toBeVisible();

  const csvExport = page.getByRole("link", { name: "Export CSV" }).first();
  await expect(csvExport).toHaveAttribute("download", /chart_01_stats-check-status-counts\.csv/);
  await expect(csvExport).toHaveAttribute("href", /data:text\/csv/);
});

import { expect, test, type Locator } from "@playwright/test";

async function expectImageLoaded(locator: Locator): Promise<void> {
  await expect(locator).toBeVisible();
  await expect
    .poll(async () =>
      locator.evaluate((node) => {
        const img = node as HTMLImageElement;
        return img.complete && img.naturalWidth > 0 && img.naturalHeight > 0;
      }),
    )
    .toBe(true);
}

test("chart pack viewer filters saved packs and opens warning-forward detail in mock mode", async ({ page }) => {
  await page.goto("/chart-packs");
  await page.waitForLoadState("networkidle");

  await expect(page.getByRole("heading", { name: "Chart Packs", exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/^Mock mode$/)).toBeVisible({ timeout: 15_000 });
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
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("Derived artifact");
  await expect(page.getByRole("heading", { name: "Charts" })).toBeVisible();
  const reviewPriorityHeading = page.getByRole("heading", { name: "Review priority" });
  const reviewPriorityCard = page.getByTestId("chart-pack-review-priority-card");
  const qualityGateHeading = page.getByRole("heading", { name: "Quality gate" });
  const qualityGateCard = page.getByTestId("chart-pack-quality-gate-card");
  const cautionNotesHeading = page.getByRole("heading", { name: "Caution Notes" });
  const snapshotHeading = page.getByRole("heading", { name: "Snapshot" });
  await expect(reviewPriorityHeading).toBeVisible();
  await expect(qualityGateHeading).toBeVisible();
  await expect(reviewPriorityCard).toContainText("Review warning-marked charts before export or downstream reuse.");
  await expect(reviewPriorityCard).toContainText(
    "Read the caution notes, then inspect warning-marked chart cards and source-item review links before treating this pack as reusable.",
  );
  await expect(reviewPriorityCard).toContainText("Warnings 1");
  await expect(reviewPriorityCard).toContainText("Caution notes 3");
  await expect(reviewPriorityCard).toContainText("Warning charts 1");
  await expect(qualityGateCard).toContainText("This chart pack still needs review before downstream reuse.");
  await expect(qualityGateCard).toContainText("Status warn");
  await expect(qualityGateCard).toContainText("Bundle ready yes");
  await expect(qualityGateCard).toContainText("Handoff ready no");
  await expect(qualityGateCard).toContainText("CHART_WARNING_PRESENT");
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

  const svgExport = page.getByRole("link", { name: "Open SVG" }).first();
  await expect(svgExport).toBeVisible();
  await expect(svgExport).toHaveAttribute("href", /data:image\/svg\+xml/);
  await expectImageLoaded(verificationCard.getByTestId("chart-render-preview-chart_01_reported-vs-computed-p-scatter"));
  await expect(verificationCard.getByText("Mock preview from saved CSV/spec")).toBeVisible();
  await expect(
    verificationCard.getByText(
      "Mock mode synthesizes a local preview from saved CSV/spec so this card mirrors the live render surface without hiding its derived status.",
    ),
  ).toBeVisible();

  const reviewPriorityBox = await reviewPriorityHeading.boundingBox();
  const qualityGateBox = await qualityGateHeading.boundingBox();
  const cautionNotesBox = await cautionNotesHeading.boundingBox();
  const snapshotBox = await snapshotHeading.boundingBox();
  expect(reviewPriorityBox).not.toBeNull();
  expect(qualityGateBox).not.toBeNull();
  expect(cautionNotesBox).not.toBeNull();
  expect(snapshotBox).not.toBeNull();
  expect(reviewPriorityBox!.y).toBeLessThan(qualityGateBox!.y);
  expect(qualityGateBox!.y).toBeLessThan(cautionNotesBox!.y);
  expect(cautionNotesBox!.y).toBeLessThan(snapshotBox!.y);
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
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("Derived artifact");
  await expect(page.locator("article").filter({ hasText: "Verification status counts" }).first()).toBeVisible();
  const reviewPriorityHeading = page.getByRole("heading", { name: "Review priority" });
  const reviewPriorityCard = page.getByTestId("chart-pack-review-priority-card");
  const qualityGateCard = page.getByTestId("chart-pack-quality-gate-card");
  const snapshotHeading = page.getByRole("heading", { name: "Snapshot" });
  await expect(reviewPriorityHeading).toBeVisible();
  await expect(reviewPriorityCard).toContainText("No pack-level warnings or caution notes are saved.");
  await expect(reviewPriorityCard).toContainText(
    "A quick source-item review is still the safest final check before exporting CSV/spec bundles or reusing charts downstream.",
  );
  await expect(reviewPriorityCard).toContainText("Warnings 0");
  await expect(reviewPriorityCard).toContainText("Caution notes 0");
  await expect(reviewPriorityCard).toContainText("Warning charts 0");
  await expect(qualityGateCard).toContainText("Saved bundle checks passed for this chart pack.");
  await expect(qualityGateCard).toContainText("Status pass");
  await expect(qualityGateCard).toContainText("Bundle ready yes");
  await expect(qualityGateCard).toContainText("Handoff ready yes");
  await expect(page.getByText("No pack-level warnings saved.")).toBeVisible();
  await expect(page.getByText("No caution notes saved for this chart pack.")).toBeVisible();

  const reviewPriorityBox = await reviewPriorityHeading.boundingBox();
  const snapshotBox = await snapshotHeading.boundingBox();
  expect(reviewPriorityBox).not.toBeNull();
  expect(snapshotBox).not.toBeNull();
  expect(reviewPriorityBox!.y).toBeLessThan(snapshotBox!.y);

  const csvExport = page.getByRole("link", { name: "Export CSV" }).first();
  await expect(csvExport).toHaveAttribute("download", /chart_01_stats-check-status-counts\.csv/);
  await expect(csvExport).toHaveAttribute("href", /data:text\/csv/);
  await expect(page.getByRole("link", { name: "Open SVG" }).first()).toHaveAttribute("href", /data:image\/svg\+xml/);
  await expectImageLoaded(page.getByTestId("chart-render-preview-chart_01_stats-check-status-counts"));
});

test("chart pack viewer can create a new chart pack in mock mode", async ({ page }) => {
  await page.goto("/chart-packs");

  await expect(page.getByText("Recent saved runs", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Ketogenic Intervention and Glucose Variability: Randomized Trial/i }).click();
  await expect(page.getByLabel("Chart pack paper id")).toHaveValue("paper-2024-glucose");
  await expect(page.getByLabel("Chart pack run id")).toHaveValue("run-002");
  await page.getByLabel("Chart pack title").fill("Mock generated chart pack");
  await page.getByLabel("Chart title").fill("Mock generated status chart");
  await page.getByRole("button", { name: "Create chart pack" }).click();

  await expect(page).toHaveURL(/\/chart-packs\/chartpack_/);
  await expect(page.getByRole("heading", { name: "Mock generated chart pack", exact: true })).toBeVisible();
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("Derived artifact");
  await expect(page.locator("article").filter({ hasText: "Mock generated status chart" }).first()).toBeVisible();
  await expect(page.getByText("stats_report / paper-2024-glucose / run-002")).toBeVisible();
  await expect(page.getByTestId("chart-pack-review-priority-card")).toContainText(
    "No pack-level warnings or caution notes are saved.",
  );
  await expect(page.getByTestId("chart-pack-quality-gate-card")).toContainText(
    "Saved bundle checks passed for this chart pack.",
  );
  await expect(page.getByText("No pack-level warnings saved.")).toBeVisible();

  const csvExport = page.getByRole("link", { name: "Export CSV" }).first();
  await expect(csvExport).toHaveAttribute("download", /chart_01_stats-check-status-counts\.csv/);
  await expect(csvExport).toHaveAttribute("href", /data:text\/csv/);
  await expect(page.getByRole("link", { name: "Open SVG" }).first()).toHaveAttribute("href", /data:image\/svg\+xml/);
  await expectImageLoaded(page.getByTestId(/chart-render-preview-chart_01_/));
});

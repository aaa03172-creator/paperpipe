import { expect, test } from "@playwright/test";

test("method comparison viewer filters saved comparisons and opens evidence-linked detail in mock mode", async ({ page }) => {
  await page.goto("/method-comparisons");

  await expect(page.getByRole("heading", { name: "Method Comparisons" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  await expect(page.getByText("Ketogenic vs coaching intervention comparison")).toBeVisible();

  await page.locator('input[placeholder="Search title or comparison id"]').fill("imaging");
  await expect(page.getByText("Imaging outcome assay comparison")).toBeVisible();
  await expect(page.getByText("Ketogenic vs coaching intervention comparison")).toHaveCount(0);

  await page.locator('input[placeholder="Search title or comparison id"]').fill("ketogenic");
  await expect(page.getByText("Ketogenic vs coaching intervention comparison")).toBeVisible();

  const targetCard = page.locator("article").filter({ hasText: "Ketogenic vs coaching intervention comparison" }).first();
  await targetCard.getByRole("button", { name: "Open comparison" }).click();

  await expect(page).toHaveURL(/\/method-comparisons\/methodcmp_/);
  await expect(page.getByRole("heading", { name: "Ketogenic vs coaching intervention comparison", exact: true })).toBeVisible();
  await expect(page.getByTestId("method-comparison-header-context")).toContainText("Derived artifact");
  await expect(page.getByRole("heading", { name: "Review priority" })).toBeVisible();
  const reviewPriorityCard = page.getByTestId("method-comparison-review-priority-card");
  const reviewPriority = page.getByTestId("method-comparison-review-priority");
  await expect(reviewPriority).toContainText(
    "Review warnings and conflict-backed cells before export.",
  );
  await expect(reviewPriorityCard).toContainText("Warnings 1");
  await expect(reviewPriorityCard).toContainText("Conflict 1");
  await expect(page.getByRole("heading", { name: "Comparison Grid" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence Trace" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source Discipline" })).toBeVisible();
  await expect(page.getByText("Comparator cell for paper-2025-nutrition remains conflict-backed")).toBeVisible();
  await expect(page.getByText("claimset.resolved.json").first()).toBeVisible();

  const exportLink = page.getByRole("link", { name: "Export CSV" });
  await expect(exportLink).toBeVisible();
  await expect(exportLink).toHaveAttribute("download", /methodcmp_.*\.csv/);
  await expect(exportLink).toHaveAttribute("href", /data:text\/csv/);

  const openNoteLink = page.getByRole("link", { name: "Open note" }).first();
  await expect(openNoteLink).toBeVisible();
  await openNoteLink.click();

  await expect(page).toHaveURL(/\/papers\//);
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
});

test("method comparison viewer can create a new comparison in mock mode", async ({ page }) => {
  await page.goto("/method-comparisons");

  await expect(page.getByRole("heading", { name: "Method Comparisons" })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await expect(page.getByText("Recent papers", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Ketogenic Intervention and Glucose Variability: Randomized Trial/i }).click();
  await page.getByRole("button", { name: /Nutrition Adherence Signals in Longitudinal Telemetry/i }).click();
  await expect(page.getByLabel("Method comparison paper ids")).toHaveValue("paper-2024-glucose\npaper-2025-nutrition");
  await page.getByLabel("Method comparison title").fill("Mock generated method comparison");
  await page.getByRole("button", { name: "Create comparison" }).click();

  await expect(page).toHaveURL(/\/method-comparisons\/methodcmp_/);
  await expect(page.getByRole("heading", { name: "Mock generated method comparison", exact: true })).toBeVisible();
  await expect(page.getByTestId("method-comparison-header-context")).toContainText("Derived artifact");
  await expect(page.getByRole("heading", { name: "Review priority" })).toBeVisible();
  await expect(page.getByTestId("method-comparison-review-priority")).toContainText(
    "Review warnings and conflict-backed cells before export.",
  );
  await expect(page.getByRole("heading", { name: "Comparison Grid" })).toBeVisible();
  await expect(page.getByText("Comparator cell for paper-2025-nutrition should be reviewed before export.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute("href", /data:text\/csv/);
});

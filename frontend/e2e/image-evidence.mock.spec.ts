import { expect, test } from "@playwright/test";

test("image evidence viewer filters saved bundles and opens warning-forward detail in mock mode", async ({ page }) => {
  await page.goto("/image-evidence");
  await page.waitForLoadState("networkidle");

  await expect(page.getByRole("heading", { name: "Image Evidence", exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/^Mock mode$/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Representative hippocampal ROI image")).toBeVisible();

  await page.locator('input[placeholder="Search title or image evidence id"]').fill("omero");
  await expect(page.getByText("OMERO brightfield plate image")).toBeVisible();
  await expect(page.getByText("Representative hippocampal ROI image")).toHaveCount(0);

  await page.locator('input[placeholder="Search title or image evidence id"]').fill("representative");
  await expect(page.getByText("Representative hippocampal ROI image")).toBeVisible();

  const targetCard = page.locator("article").filter({ hasText: "Representative hippocampal ROI image" }).first();
  await targetCard.getByRole("button", { name: "Open bundle" }).click();

  await expect(page).toHaveURL(/\/image-evidence\/imageev_/);
  await expect(page.getByRole("heading", { name: "Representative hippocampal ROI image", exact: true })).toBeVisible();
  await expect(page.getByTestId("image-evidence-header-context")).toContainText("Derived artifact");
  await expect(page.getByRole("heading", { name: "Bundle Review" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Warnings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Derived Outputs" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "View State" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Trust Boundary" })).toBeVisible();
  await expect(page.getByText("Bundle captures a representative crop rather than the full acquisition stack.")).toBeVisible();
  await expect(page.locator("pre").filter({ hasText: "/Users/jangseongjin/mock-data/imaging/hippocampus-alpha.tif" }).first()).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Thumbnail" }).first()).toBeVisible();
  await expect(page.getByText("GFP")).toBeVisible();
  await expect(page.getByText("roi_outline")).toBeVisible();

  const noteLink = page.getByRole("link", { name: "Open note" });
  await expect(noteLink).toBeVisible();
  await noteLink.click();

  await expect(page).toHaveURL(/\/papers\/leeKetogenicIntervention2024/);
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
});

test("image evidence viewer keeps second mock bundle detail aligned with the selected index item", async ({ page }) => {
  await page.goto("/image-evidence");

  await page.locator('input[placeholder="Search title or image evidence id"]').fill("omero");
  const targetCard = page.locator("article").filter({ hasText: "OMERO brightfield plate image" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("Clean bundle")).toBeVisible();

  await targetCard.getByRole("button", { name: "Open bundle" }).click();

  await expect(page).toHaveURL(/\/image-evidence\/imageev_20260322_mock5678/);
  await expect(page.getByRole("heading", { name: "OMERO brightfield plate image", exact: true })).toBeVisible();
  await expect(page.getByText("No bundle warnings saved.")).toBeVisible();
  await expect(page.getByText("No derived outputs registered.")).toBeVisible();
  await expect(page.getByText("No view state saved for this bundle.")).toBeVisible();
  await expect(page.locator("pre").filter({ hasText: "omero://dataset/42/image/7" }).first()).toBeVisible();
});

import { expect, test } from "@playwright/test";

test("protocol knowledge inspector filters saved cards and opens version-forward detail in mock mode", async ({ page }) => {
  await page.goto("/protocol-cards");

  await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  await expect(page.getByText("Primary cortical assay protocol")).toBeVisible();

  await page.locator('input[placeholder="Search title or protocol id"]').fill("brightfield");
  await expect(page.getByText("Reference brightfield stain workflow")).toBeVisible();
  await expect(page.getByText("Primary cortical assay protocol")).toHaveCount(0);

  await page.locator('input[placeholder="Search title or protocol id"]').fill("cortical");
  const targetCard = page.locator("article").filter({ hasText: "Primary cortical assay protocol" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("protver_cortical_assay_v2")).toBeVisible();
  await expect(targetCard.getByText("Draft")).toBeVisible();

  await targetCard.getByRole("button", { name: "Open protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByRole("heading", { name: "Primary cortical assay protocol", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Version review" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Version history" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source refs" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Trust boundary" })).toBeVisible();
  await expect(page.getByText("Selected as current version")).toBeVisible();
  await expect(page.getByText("Clarified media timing and readout naming after note reconciliation.")).toBeVisible();
  await page.getByRole("heading", { name: "Materials, equipment, and cautions" }).scrollIntoViewIfNeeded();
  await expect(page.getByText("Do not merge operator adaptation with paper truth downstream without citation.")).toBeVisible();

  const noteLink = page.getByRole("link", { name: "Open note" });
  await expect(noteLink).toBeVisible();
  await noteLink.click();

  await expect(page).toHaveURL(/\/papers\/leeKetogenicIntervention2024/);
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
});

test("protocol knowledge inspector keeps second mock card detail aligned with the selected index item", async ({ page }) => {
  await page.goto("/protocol-cards");

  await page.locator('input[placeholder="Search title or protocol id"]').fill("brightfield");
  const targetCard = page.locator("article").filter({ hasText: "Reference brightfield stain workflow" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("Verified by user")).toBeVisible();
  await expect(targetCard.getByText("protver_brightfield_reference_v1")).toBeVisible();

  await targetCard.getByRole("button", { name: "Open protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_20260322T213000Z_mock5678/);
  await expect(page.getByRole("heading", { name: "Reference brightfield stain workflow", exact: true })).toBeVisible();
  await expect(page.getByText("Verified by user")).toBeVisible();
  await expect(page.getByText("Approved as stable reference snapshot.")).toBeVisible();
  await expect(page.getByText("No key-step summary saved for this version.")).toHaveCount(0);
  await expect(page.getByText("Stable reference card for note-level reuse.")).toBeVisible();
});

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
  await expect(page.getByTestId("protocol-card-header-context")).toContainText("Derived artifact");
  await expect(page.getByRole("heading", { name: "Version review" })).toBeVisible();
  await expect(page.getByTestId("protocol-card-review-state-card")).toContainText("Review state");
  await expect(page.getByTestId("protocol-card-review-state-card")).toContainText("Protocol cards are reusable review artifacts");
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
  await expect(page.getByText("Verified by user").first()).toBeVisible();
  await expect(page.getByText("Approved as stable reference snapshot.")).toBeVisible();
  await expect(page.getByText("No key-step summary saved for this version.")).toHaveCount(0);
  await expect(page.getByText("Stable reference card for note-level reuse.")).toBeVisible();
});

test("protocol knowledge inspector empty search state explains the next action and can clear search", async ({ page }) => {
  await page.goto("/protocol-cards");

  await page.locator('input[placeholder="Search title or protocol id"]').fill("zzzz-nothing");
  await expect(page.getByText("No saved protocol cards matched this search yet. Clear the search or start a new protocol card from the left.")).toBeVisible();
  const clearSearchButton = page.getByRole("button", { name: "Clear search" });
  await expect(clearSearchButton).toBeVisible();
  await clearSearchButton.click();

  await expect(page.getByText("Primary cortical assay protocol")).toBeVisible();
  await expect(page.getByText("Reference brightfield stain workflow")).toBeVisible();
});

test("protocol knowledge inspector can create a new protocol card in mock mode", async ({ page }) => {
  await page.goto("/protocol-cards");

  await expect(page.getByText("Recent notes", { exact: true })).toBeVisible();
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Still needed before save");
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Protocol title");
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Current version snapshot");
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText(
    "The rest of this form is optional or already defaulted",
  );
  await expect(page.getByTestId("protocol-card-create-optional-context")).toContainText(
    "Optional context and review details are not required to save.",
  );
  await expect(page.getByText("Defaults are already safe for most note-backed saves.")).toBeVisible();
  const recentNoteChoice = page.getByRole("button", {
    name: "Use recent note Ketogenic Intervention and Glucose Variability: Randomized Trial",
  });
  await expect(recentNoteChoice).toContainText("paper-2024-glucose");
  await recentNoteChoice.click();
  await expect(page.getByTestId("protocol-card-create-context")).toContainText("Current note context");
  await expect(page.getByTestId("protocol-card-create-context")).toContainText(
    "Ketogenic Intervention and Glucose Variability: Randomized Trial",
  );
  await expect(page.getByTestId("protocol-card-create-context")).toContainText("paper-2024-glucose");
  const createContextBox = await page.getByTestId("protocol-card-create-context").boundingBox();
  const manualFallbackBox = await page
    .getByText(
      "Manual note-context fallback. Fill the linked note slug or paper ID below only when recent notes do not match the review thread you want.",
      { exact: true },
    )
    .boundingBox();
  expect(createContextBox).not.toBeNull();
  expect(manualFallbackBox).not.toBeNull();
  expect((createContextBox?.y ?? 0) + (createContextBox?.height ?? 0)).toBeLessThan(manualFallbackBox?.y ?? Number.POSITIVE_INFINITY);
  await expect(page.getByRole("button", { name: "Clear note context" })).toBeVisible();
  await expect(page.getByLabel("Protocol card linked note slug")).toHaveValue("ketogenicInterventionGlucoseVariability2024");
  await expect(page.getByLabel("Protocol card linked paper id")).toHaveValue("paper-2024-glucose");
  await expect(page.getByTestId("protocol-card-title-guidance")).toContainText(
    "Required before save. Give this saved snapshot a short review title.",
  );
  await expect(page.getByTestId("protocol-card-snapshot-guidance")).toContainText(
    "Required before save. Add the current protocol wording or step summary.",
  );
  await page.getByRole("button", { name: "Create protocol card" }).click();
  await expect(page.getByLabel("Protocol card title")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Protocol card version snapshot")).toHaveAttribute("aria-invalid", "true");
  await page.getByLabel("Protocol card title").fill("Mock browser-created protocol");
  await page.getByLabel("Protocol card source kind").selectOption("paper_derived");
  await page.getByLabel("Protocol card current version status").selectOption("active");
  await page.getByLabel("Protocol card version snapshot").fill(
    "Step 1: prepare cortical neurons.\nStep 2: apply ketone ester pulse.\nStep 3: collect BHB readout.",
  );
  await page.getByLabel("Protocol card key steps").fill(
    "Prepare cortical neurons\nApply ketone ester pulse\nCollect BHB readout",
  );
  await expect(page.getByTestId("protocol-card-title-guidance")).toContainText("Saved card heading looks ready.");
  await expect(page.getByTestId("protocol-card-snapshot-guidance")).toContainText(
    "Current version snapshot looks ready.",
  );
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Ready to save");
  await page.getByRole("button", { name: "Create protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByRole("heading", { name: "Mock browser-created protocol", exact: true })).toBeVisible();
  await expect(page.getByText("Selected as current version")).toBeVisible();
  await expect(page.locator("li").filter({ hasText: "Prepare cortical neurons" }).first()).toBeVisible();
  await expect(page.getByText("Linked note slug: ketogenicInterventionGlucoseVariability2024")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open note" })).toHaveAttribute(
    "href",
    /\/papers\/ketogenicInterventionGlucoseVariability2024$/,
  );
});

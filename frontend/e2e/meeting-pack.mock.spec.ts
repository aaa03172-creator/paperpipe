import { expect, test } from "@playwright/test";

test("meeting pack inspector filters saved packs and runs guarded draft actions in mock mode", async ({ page }) => {
  await page.goto("/meeting-packs");

  await expect(page.getByRole("banner").getByRole("heading", { name: "Saved meeting packs" })).toBeVisible();
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("When to use");
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("Derived from");
  await expect(page.getByRole("heading", { name: "Start a new draft" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Open a saved pack by ID" })).toBeVisible();

  await page.getByLabel("Search saved meeting packs").fill("proposal");
  await expect(page.getByText("Butyrate follow-up proposal draft")).toBeVisible();
  await expect(page.getByText("SCFA journal club debug draft")).toHaveCount(0);

  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByRole("button", { name: "With trace" }).click();
  await expect(page.getByText("SCFA journal club debug draft")).toBeVisible();
  await expect(page.getByText("Butyrate follow-up proposal draft")).toHaveCount(0);

  const targetCard = page.locator("article").filter({ hasText: "SCFA journal club debug draft" }).first();
  await expect(targetCard.getByText("Lab Meeting", { exact: true })).toBeVisible();
  await targetCard.getByRole("button", { name: /^Open pack$/ }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(page.getByRole("heading", { name: "SCFA journal club debug draft", exact: true })).toBeVisible();
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("When to use");
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("Derived from");
  await expect(page.getByRole("heading", { name: "Continue from this draft" })).toBeVisible();
  await expect(page.getByText("Continue in note").first()).toBeVisible();
  await expect(page.getByText("Output mode family")).toBeVisible();
  await expect(page.getByText("Concrete mode shapes this draft directly.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Regenerate draft" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rerender markdown" })).toBeVisible();

  await page.getByRole("button", { name: "Rerender markdown" }).click();
  await expect(page.getByText("Saved markdown rerendered from the current meeting pack JSON.")).toBeVisible();

  await page.getByRole("button", { name: "Regenerate draft" }).click();
  await expect(page.getByText("Draft regenerated from the saved selector set.")).toBeVisible();
});

test("meeting pack index can start a new draft from a paper slug in mock mode", async ({ page }) => {
  await page.goto("/meeting-packs");

  await page.getByLabel("Meeting pack paper slug").fill("zoterocoricTargetingProdromalAlzheimer2015");
  await page.getByLabel("Meeting pack draft title").fill("Prodromal Alzheimer kickoff");
  await page.getByLabel("Meeting pack draft mode").selectOption("journal_club");
  await page.getByLabel("Meeting pack max slides").selectOption("7");
  await page.getByRole("button", { name: "Create draft" }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(
    page.getByText(
      "Temporary fallback draft created from the entered paper slug. It only stays available in this browser session.",
      { exact: false },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Prodromal Alzheimer kickoff", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Source slug: zoterocoricTargetingProdromalAlzheimer2015", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Journal Club", { exact: true }).first()).toBeVisible();
});

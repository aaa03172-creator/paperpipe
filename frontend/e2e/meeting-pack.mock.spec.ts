import { expect, test } from "@playwright/test";

test("meeting pack inspector filters saved packs and runs guarded draft actions in mock mode", async ({ page }) => {
  await page.goto("/meeting-packs");

  await expect(page.getByRole("banner").getByRole("heading", { name: "Saved meeting packs" })).toBeVisible();
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("When to use");
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("Derived from");
  await expect(page.getByRole("heading", { name: "Start a new draft" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Open a saved pack by ID" })).toBeVisible();
  await expect(page.getByTestId("meeting-pack-index-day-group")).toHaveCount(1);
  await expect(page.getByTestId("meeting-pack-index-day-group").first()).toHaveAttribute("data-day-key", "2026-03-17");
  await expect(page.getByTestId("meeting-pack-index-day-group").first()).toContainText("3 drafts");
  await expect(page.getByTestId("meeting-pack-index-title-group")).toHaveCount(2);
  await expect(
    page.getByTestId("meeting-pack-index-title-group").filter({ hasText: "SCFA journal club debug draft" }),
  ).toContainText("2 drafts");
  await expect(
    page.getByTestId("meeting-pack-index-title-group").filter({ hasText: "Butyrate follow-up proposal draft" }),
  ).toContainText("1 draft");
  await expect(page.getByText("Browser generated meeting draft", { exact: true })).toHaveCount(0);

  await page.getByLabel("Search saved meeting packs").fill("proposal");
  await expect(page.getByText("Butyrate follow-up proposal draft")).toBeVisible();
  await expect(page.getByText("SCFA journal club debug draft")).toHaveCount(0);
  await expect(page.getByTestId("meeting-pack-index-summary")).toContainText(
    "Showing 1 matching saved packs from 3 total.",
  );
  await expect(page.getByTestId("meeting-pack-index-day-group")).toHaveCount(1);
  await expect(page.getByTestId("meeting-pack-index-day-group").first()).toContainText("1 matching draft");
  await expect(page.getByTestId("meeting-pack-index-title-group")).toHaveCount(1);

  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByRole("button", { name: "With trace" }).click();
  await expect(page.getByText("SCFA journal club debug draft")).toBeVisible();
  await expect(page.getByText("Butyrate follow-up proposal draft")).toHaveCount(0);
  await expect(page.getByTestId("meeting-pack-index-summary")).toContainText(
    "Showing 1 matching saved packs from 3 total.",
  );

  const targetGroup = page
    .getByTestId("meeting-pack-index-title-group")
    .filter({ hasText: "SCFA journal club debug draft" })
    .first();
  await expect(targetGroup).toContainText("1 matching draft");
  const targetCard = targetGroup.getByTestId("meeting-pack-index-row").first();
  await expect(targetCard.getByTestId("meeting-pack-index-identity")).toHaveText(/Saved .*:\d{2}\.\d{3}/);
  await expect(targetCard.getByText("Lab Meeting", { exact: true })).toBeVisible();
  await targetCard.getByRole("button", { name: /^Open pack$/ }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(page.getByRole("heading", { name: "SCFA journal club debug draft", exact: true })).toBeVisible();
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("Derived artifact");
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("When to use");
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("Derived from");
  const detailRail = page.locator("main > div").nth(1);
  await expect(detailRail.getByRole("heading").nth(0)).toHaveText("Review state");
  await expect(detailRail.getByRole("heading").nth(1)).toHaveText("Continue from this draft");
  await expect(detailRail.getByRole("heading").nth(2)).toHaveText("Validation");
  await expect(page.getByRole("heading", { name: "Continue from this draft" })).toBeVisible();
  await expect(page.getByText("Continue in note").first()).toBeVisible();
  await expect(page.getByTestId("meeting-pack-recommended-order")).toContainText("Recommended order");
  await expect(page.getByText("Output mode family")).toBeVisible();
  await expect(page.getByText("Concrete mode shapes this draft directly.")).toBeVisible();
  const draftMaintenance = page.getByTestId("meeting-pack-draft-maintenance");
  await expect(draftMaintenance).toContainText("Draft maintenance");
  await expect(page.getByRole("button", { name: "Regenerate draft" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Rerender markdown" })).toHaveCount(0);

  await draftMaintenance.locator("summary").click();
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
    page.getByText("Fallback meeting draft created from the entered paper slug.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Prodromal Alzheimer kickoff", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Source slug: zoterocoricTargetingProdromalAlzheimer2015", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Journal Club", { exact: true }).first()).toBeVisible();
});

test("meeting pack create treats the generic browser title as a source-aware default in mock mode", async ({ page }) => {
  await page.goto("/meeting-packs");

  await page.getByLabel("Meeting pack paper slug").fill("zoterocoricTargetingProdromalAlzheimer2015");
  await page.getByLabel("Meeting pack draft title").fill("Browser generated meeting draft");
  await page.getByLabel("Meeting pack draft mode").selectOption("journal_club");
  await page.getByLabel("Meeting pack max slides").selectOption("7");
  await page.getByRole("button", { name: "Create draft" }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: "zoterocoricTargetingProdromalAlzheimer2015",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("Browser generated meeting draft", { exact: true })).toHaveCount(0);
});

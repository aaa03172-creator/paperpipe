import { expect, test } from "@playwright/test";

test("meeting pack inspector filters saved packs and runs guarded draft actions in mock mode", async ({ page }) => {
  await page.goto("/meeting-packs");

  await expect(page.getByRole("heading", { name: "Saved Meeting Pack Inspector" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Saved packs" })).toBeVisible();

  await page.getByLabel("Search saved meeting packs").fill("proposal");
  await expect(page.getByText("Butyrate follow-up proposal draft")).toBeVisible();
  await expect(page.getByText("SCFA journal club debug draft")).toHaveCount(0);

  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByRole("button", { name: "With trace" }).click();
  await expect(page.getByText("SCFA journal club debug draft")).toBeVisible();
  await expect(page.getByText("Butyrate follow-up proposal draft")).toHaveCount(0);
  await expect(page.getByText("Lab Meeting")).toBeVisible();

  const targetCard = page.locator("article").filter({ hasText: "SCFA journal club debug draft" }).first();
  await targetCard.getByRole("button", { name: /^Open inspector$/ }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(page.getByRole("heading", { name: "SCFA journal club debug draft", exact: true })).toBeVisible();
  await expect(page.getByText("Output mode family")).toBeVisible();
  await expect(page.getByText("Concrete mode shapes this draft directly.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Regenerate draft" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rerender markdown" })).toBeVisible();

  await page.getByRole("button", { name: "Rerender markdown" }).click();
  await expect(page.getByText("Saved markdown rerendered from the current meeting pack JSON.")).toBeVisible();

  await page.getByRole("button", { name: "Regenerate draft" }).click();
  await expect(page.getByText("Draft regenerated from the saved selector set.")).toBeVisible();
});

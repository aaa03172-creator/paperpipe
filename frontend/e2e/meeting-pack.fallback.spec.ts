import { expect, test } from "@playwright/test";

test("meeting pack create auto-fallback keeps the generated draft reachable when the backend is unavailable", async ({
  page,
}) => {
  await page.goto("/meeting-packs");

  await expect(page.getByRole("banner").getByRole("heading", { name: "Saved meeting packs" })).toBeVisible();
  await expect(page.getByText("meeting pack index unavailable, mock drafts loaded")).toBeVisible();

  await page.getByLabel("Meeting pack paper slug").fill("zoterocoricTargetingProdromalAlzheimer2015");
  await page.getByLabel("Meeting pack draft title").fill("Fallback continuity draft");
  await page.getByLabel("Meeting pack draft mode").selectOption("journal_club");
  await page.getByRole("button", { name: "Create draft" }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(
    page.getByText("Fallback meeting draft created from the entered paper slug.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fallback continuity draft", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Continue from this draft" })).toBeVisible();
  await expect(page.getByText("Continue in note").first()).toBeVisible();
  await expect(page.getByText("Regenerate unavailable")).toBeVisible();
  await expect(page.getByText("Strategy: unavailable")).toBeVisible();
  await expect(page.getByText("Draft actions stay unavailable until the live backend is reachable again.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Regenerate draft" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Rerender markdown" })).toBeDisabled();
});

import { expect, test } from "@playwright/test";

test("meeting pack create falls back for proxy-style backend downtime", async ({ page }) => {
  await page.route("**/api/meeting-packs/generate", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "text/plain",
      body: "",
    });
  });

  await page.goto("/meeting-packs");

  await expect(page.getByRole("banner").getByRole("heading", { name: "Saved meeting packs" })).toBeVisible();
  await page.getByLabel("Meeting pack paper slug").fill("zoterocoricTargetingProdromalAlzheimer2015");
  await page.getByLabel("Meeting pack draft title").fill("Fallback continuity draft");
  await page.getByLabel("Meeting pack draft mode").selectOption("journal_club");
  await page.getByLabel("Meeting pack max slides").selectOption("7");
  await page.getByRole("button", { name: "Create draft" }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(
    page.getByText("Fallback meeting draft created from the entered paper slug.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fallback continuity draft", exact: true })).toBeVisible();
  await expect(page.getByText("/meeting-packs/generate -> 500")).toHaveCount(0);
});

test("meeting pack create surfaces live backend failures with a response body", async ({ page }) => {
  await page.route("**/api/meeting-packs/generate", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Meeting Pack generation crashed while building the saved draft",
      }),
    });
  });

  await page.goto("/meeting-packs");

  await page.getByLabel("Meeting pack paper slug").fill("zoterocoricTargetingProdromalAlzheimer2015");
  await page.getByLabel("Meeting pack draft title").fill("Server error fallback should not succeed");
  await page.getByRole("button", { name: "Create draft" }).click();

  await expect(page).toHaveURL(/\/meeting-packs$/);
  await expect(page.getByText("/meeting-packs/generate -> 500")).toBeVisible();
  await expect(page.getByText("Meeting Pack generation crashed while building the saved draft")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Server error fallback should not succeed", exact: true }),
  ).toHaveCount(0);
});

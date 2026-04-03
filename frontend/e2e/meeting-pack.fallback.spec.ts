import { expect, test } from "@playwright/test";
import {
  createMockMeetingPack,
  getMockMeetingPack,
  getMockMeetingPackTrace,
  getMockMeetingPackValidation,
} from "../src/app/lib/mock";

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

test("meeting pack create surfaces backend 401 instead of silently falling back to a mock draft", async ({
  page,
}) => {
  await page.route("**/api/meeting-packs/generate", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error_code: "UNAUTHORIZED",
        message: "Missing or invalid X-API-Key",
      }),
    });
  });

  await page.goto("/meeting-packs");

  await page.getByLabel("Meeting pack paper slug").fill("zoterocoricTargetingProdromalAlzheimer2015");
  await page.getByLabel("Meeting pack draft title").fill("Unauthorized fallback should not succeed");
  await page.getByRole("button", { name: "Create draft" }).click();

  await expect(page).toHaveURL(/\/meeting-packs$/);
  await expect(page.getByText("/meeting-packs/generate -> 401")).toBeVisible();
  await expect(page.getByText("Missing or invalid X-API-Key")).toBeVisible();
  await expect(
    page.getByText("Fallback meeting draft created from the entered paper slug.", { exact: false }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Unauthorized fallback should not succeed", exact: true }),
  ).toHaveCount(0);
});

test("meeting pack index surfaces backend 400 instead of silently showing the mock library", async ({
  page,
}) => {
  await page.route("**/api/meeting-packs", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Failed to load Meeting Pack from storage/meeting_packs/broken-pack/meeting_pack.json",
      }),
    });
  });

  await page.goto("/meeting-packs");

  await expect(page.getByText("/meeting-packs -> 400")).toBeVisible();
  await expect(page.getByText("Failed to load Meeting Pack from storage/meeting_packs/broken-pack/meeting_pack.json")).toBeVisible();
  await expect(page.getByText("meeting pack index unavailable, mock drafts loaded")).toHaveCount(0);
});

test("meeting pack detail surfaces backend 400 instead of swapping in a mock draft", async ({
  page,
}) => {
  await page.route("**/api/meeting-packs/broken-pack", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Failed to load Meeting Pack from storage/meeting_packs/broken-pack/meeting_pack.json",
      }),
    });
  });
  await page.route("**/api/meeting-packs/broken-pack/trace", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Corrupt retrieval trace metadata",
      }),
    });
  });
  await page.route("**/api/meeting-packs/broken-pack/validate", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Cannot validate malformed meeting pack",
      }),
    });
  });

  await page.goto("/meeting-packs/broken-pack");

  await expect(page.getByRole("heading", { name: "Unable to load pack" })).toBeVisible();
  await expect(page.getByText("/meeting-packs/broken-pack -> 400")).toBeVisible();
  await expect(page.getByText("Failed to load Meeting Pack from storage/meeting_packs/broken-pack/meeting_pack.json")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Continue from this draft" })).toHaveCount(0);
});

test("meeting pack detail surfaces trace availability failure instead of mixing in a mock trace", async ({
  page,
}) => {
  const packResponse = createMockMeetingPack({
    mode: "journal_club",
    title: "Saved pack trace outage",
    source_items: [{ type: "paper_slug", ref: "zoterocoricTargetingProdromalAlzheimer2015" }],
    max_slides: 6,
  });
  const packId = packResponse.pack.id;

  await page.route(`**/api/meeting-packs/${packId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(packResponse),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/trace`, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Meeting Pack trace temporarily unavailable",
      }),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/validate`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(getMockMeetingPackValidation(packId)),
    });
  });

  await page.goto(`/meeting-packs/${packId}`);

  await expect(page.getByRole("heading", { name: "Unable to load pack" })).toBeVisible();
  await expect(page.getByText(`/meeting-packs/${packId}/trace -> 503`)).toBeVisible();
  await expect(page.getByText("Meeting Pack trace temporarily unavailable")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Saved pack trace outage", exact: true })).toHaveCount(0);
  await expect(page.getByText("meeting pack trace unavailable, mock trace loaded")).toHaveCount(0);
});

test("meeting pack detail surfaces validation availability failure instead of mixing in mock readiness", async ({
  page,
}) => {
  const packResponse = createMockMeetingPack({
    mode: "journal_club",
    title: "Saved pack validation outage",
    source_items: [{ type: "paper_slug", ref: "zoterocoricTargetingProdromalAlzheimer2015" }],
    max_slides: 6,
  });
  const packId = packResponse.pack.id;

  await page.route(`**/api/meeting-packs/${packId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(packResponse),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/trace`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(getMockMeetingPackTrace(packId)),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/validate`, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Meeting Pack validation temporarily unavailable",
      }),
    });
  });

  await page.goto(`/meeting-packs/${packId}`);

  await expect(page.getByRole("heading", { name: "Unable to load pack" })).toBeVisible();
  await expect(page.getByText(`/meeting-packs/${packId}/validate -> 503`)).toBeVisible();
  await expect(page.getByText("Meeting Pack validation temporarily unavailable")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Saved pack validation outage", exact: true })).toHaveCount(0);
  await expect(page.getByText("meeting pack validation unavailable, mock validation loaded")).toHaveCount(0);
});

test("meeting pack rerender stays successful when trace refresh flaps after the write", async ({
  page,
}) => {
  const packId = "saved-pack-rerender-refresh-warning";
  const packResponse = getMockMeetingPack(packId);
  const validationResponse = getMockMeetingPackValidation(packId);
  let failTraceRefresh = false;

  await page.route(`**/api/meeting-packs/${packId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(packResponse),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/trace`, async (route) => {
    if (failTraceRefresh) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Meeting Pack trace refresh temporarily unavailable",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(getMockMeetingPackTrace(packId)),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/validate`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(validationResponse),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/rerender`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(packResponse),
    });
  });

  await page.goto(`/meeting-packs/${packId}`);
  await expect(page.getByRole("heading", { name: "SCFA journal club debug draft", exact: true })).toBeVisible();

  failTraceRefresh = true;
  await page.getByRole("button", { name: "Rerender markdown" }).click();

  await expect(
    page.getByText(
      "Saved markdown rerendered from the current meeting pack JSON. Trace could not be refreshed. Reload this pack once the backend is reachable again.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "SCFA journal club debug draft", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Unable to load pack" })).toHaveCount(0);
});

test("meeting pack regenerate stays successful when validation refresh flaps after the write", async ({
  page,
}) => {
  const packId = "saved-pack-regenerate-refresh-warning";
  const packResponse = getMockMeetingPack(packId);
  let failValidationRefresh = false;

  await page.route(`**/api/meeting-packs/${packId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(packResponse),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/trace`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(getMockMeetingPackTrace(packId)),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/validate`, async (route) => {
    if (failValidationRefresh) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Meeting Pack validation refresh temporarily unavailable",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(getMockMeetingPackValidation(packId)),
    });
  });
  await page.route(`**/api/meeting-packs/${packId}/regenerate`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(packResponse),
    });
  });

  await page.goto(`/meeting-packs/${packId}`);
  await expect(page.getByRole("heading", { name: "SCFA journal club debug draft", exact: true })).toBeVisible();

  failValidationRefresh = true;
  await page.getByRole("button", { name: "Regenerate draft" }).click();

  await expect(
    page.getByText(
      "Draft regenerated from the saved selector set. Validation could not be refreshed. Reload this pack once the backend is reachable again.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "SCFA journal club debug draft", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Unable to load pack" })).toHaveCount(0);
});

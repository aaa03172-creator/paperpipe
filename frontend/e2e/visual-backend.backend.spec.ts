import { expect, test, Page, type APIRequestContext } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const visualBackendPort = process.env.E2E_BACKEND_PORT ?? "18080";
const visualBackendBaseUrl = `http://127.0.0.1:${visualBackendPort}`;
const visualNoteSlug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024";
const visualSpecDir = path.dirname(fileURLToPath(import.meta.url));
const visualImageEvidenceFixtureRawPath = path.resolve(
  visualSpecDir,
  "..",
  "..",
  "tests",
  "fixtures",
  "image_evidence_case",
  "raw",
  "local-alpha.tif",
);
const visualImageEvidenceMissingRawPath = path.resolve(
  visualSpecDir,
  "..",
  ".e2e-backend-runtime",
  "missing",
  "visual-absent-local-alpha.tif",
);

async function registerBackendImageEvidenceVisualFixture(request: APIRequestContext): Promise<string> {
  const imageEvidenceId = "imageev_backend_visual_fixture";
  const response = await request.post(`${visualBackendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "Backend visual image evidence fixture",
      paper_id: "paper-e2e-note-backed-bbox-001",
      paper_slug: visualNoteSlug,
      source_ref: {
        source_kind: "local_file",
        local_path: visualImageEvidenceFixtureRawPath,
        source_label: "Microscope Alpha",
      },
      content_format: "image/tiff",
      checksum: {
        algorithm: "sha256",
        value: "deadbeef",
      },
      metadata: {
        width_px: 512,
        height_px: 512,
        channel_count: 2,
        modality: "fluorescence",
        acquisition_note: "Representative ROI export for backend visual regression.",
      },
      view_state: {
        active_channels: ["GFP", "DAPI"],
        zoom_level: 2.0,
        viewport: {
          x: 16,
          y: 32,
          width: 128,
          height: 128,
        },
        visible_overlays: ["roi_outline"],
        selected_region_labels: ["roi-1"],
        note: "Operator-saved ROI viewport.",
      },
      linked_claim_refs: [
        {
          claim_id: "claim-visual-image-001",
          note: "Representative image only.",
        },
      ],
      linked_artifact_refs: [
        {
          artifact_kind: "meeting_pack",
          artifact_id: "meeting-visual-image-001",
          note: "Linked for downstream review.",
        },
      ],
      derived_outputs: [
        {
          derived_output_id: "thumb_local",
          kind: "thumbnail",
          source_image_evidence_id: imageEvidenceId,
          created_by: "visual-fixture",
          created_at: "2026-03-22T12:05:00+00:00",
          tool_name: "napari",
          tool_version: "0.5.4",
          bundle_ref: {
            kind: "derived_file",
            path: "derivatives/thumb_local.png",
          },
          view_state_ref: {
            kind: "view_state_json",
            path: "view_state.json",
          },
          note: "Representative thumbnail only.",
        },
      ],
      handoff_targets: [
        {
          target: "napari",
          openable_ref: visualImageEvidenceFixtureRawPath,
          view_state_ref: {
            kind: "view_state_json",
            path: "view_state.json",
          },
          notes: "Open with saved viewport.",
        },
      ],
      warnings: [
        {
          code: "REPRESENTATIVE_ONLY",
          severity: "warning",
          message: "Bundle captures a representative crop rather than the full acquisition stack.",
        },
      ],
    },
  });
  expect(response.ok()).toBeTruthy();
  return imageEvidenceId;
}

async function registerBackendImageEvidenceVisualCleanFixture(request: APIRequestContext): Promise<string> {
  const imageEvidenceId = "imageev_backend_visual_clean_fixture";
  const response = await request.post(`${visualBackendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "Backend visual OMERO clean bundle",
      paper_id: "paper-e2e-001",
      source_ref: {
        source_kind: "external_image_ref",
        external_ref: "omero://dataset/42/image/7",
        source_label: "OMERO image 7",
      },
      content_format: "image/png",
      metadata: {
        width_px: 1024,
        height_px: 768,
        modality: "brightfield",
      },
      handoff_targets: [
        {
          target: "omero",
          openable_ref: "omero://dataset/42/image/7",
          notes: "Open in external viewer.",
        },
      ],
    },
  });
  expect(response.ok()).toBeTruthy();
  return imageEvidenceId;
}

async function registerBackendImageEvidenceVisualMissingFixture(request: APIRequestContext): Promise<string> {
  const imageEvidenceId = "imageev_backend_visual_missing_fixture";
  const response = await request.post(`${visualBackendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "Backend visual missing local bundle",
      paper_id: "paper-e2e-001",
      source_ref: {
        source_kind: "local_file",
        local_path: visualImageEvidenceMissingRawPath,
        source_label: "Missing microscope export",
      },
      content_format: "image/tiff",
      metadata: {
        modality: "fluorescence",
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  return imageEvidenceId;
}

async function openBackendWorkbenchAndSelectSecondClaim(page: Page) {
  await page.goto("/workbench/paper-e2e-001");
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button")).toHaveCount(3);
  await claimsPanel.getByRole("button").nth(1).click();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
}

async function openBackendPaperNotes(page: Page) {
  await page.goto("/papers");
  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
}

async function openBackendPaperNoteDetail(page: Page) {
  await page.goto("/papers/zoteroduboisAlzheimerDiseaseClinicalBiological2024");
  await expect(
    page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
  ).toBeVisible();
}

async function openBackendImageEvidenceDetail(page: Page, request: APIRequestContext) {
  const imageEvidenceId = await registerBackendImageEvidenceVisualFixture(request);
  await page.goto(`/image-evidence/${imageEvidenceId}`);
  await expect(page.getByRole("heading", { name: "Backend visual image evidence fixture" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
}

async function openBackendImageEvidenceIndex(page: Page, request: APIRequestContext) {
  await registerBackendImageEvidenceVisualFixture(request);
  await registerBackendImageEvidenceVisualCleanFixture(request);
  await registerBackendImageEvidenceVisualMissingFixture(request);
  await page.goto("/image-evidence");
  await expect(page.getByRole("heading", { name: "Image Evidence", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or image evidence id"]').fill("Backend visual");
  await expect(page.locator("article").filter({ hasText: "Backend visual image evidence fixture" }).first()).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Backend visual OMERO clean bundle" }).first()).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Backend visual missing local bundle" }).first()).toBeVisible();
}

test("visual regression (backend, desktop): paper notes list layout", async ({ page }) => {
  await openBackendPaperNotes(page);

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  await expect(page.getByTestId("paper-notes-tag-command")).toBeVisible();
  await expect(page.getByTestId("paper-notes-structured-toggle")).toBeVisible();
  await expect(page.getByTestId("paper-note-list-row").first()).toBeVisible();
});

test("visual regression (backend, desktop): paper note detail layout", async ({ page }) => {
  await openBackendPaperNoteDetail(page);

  await expect(page.locator("aside").filter({ hasText: "Properties" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "References" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open in Workbench" }).first()).toBeVisible();
  await expect(page.getByTestId("paper-note-structured-state-notice")).toBeVisible();
});

test("visual regression (backend, desktop): workbench rail layout", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  const rail = page.locator("aside").filter({ hasText: "Navigation Rail" }).first();
  await expect(rail).toBeVisible();
  await expect(rail.getByPlaceholder("Search papers")).toBeVisible();
  await expect(rail.getByRole("button", { name: /E2E Seed Paper/i })).toBeVisible();
});

test("visual regression (backend, desktop): claim highlight in pdf viewer", async ({ page }) => {
  await openBackendWorkbenchAndSelectSecondClaim(page);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
});

test("visual regression (backend, desktop): image evidence detail layout", async ({ page, request }) => {
  await openBackendImageEvidenceDetail(page, request);

  const createdValue = page.getByText(/^Created$/).locator("xpath=../div[last()]");
  await expect(page).toHaveScreenshot("backend-desktop-image-evidence-detail.png", {
    animations: "disabled",
    caret: "hide",
    mask: [createdValue],
    maxDiffPixels: 4200,
  });
});

test("visual regression (backend, desktop): image evidence index layout", async ({ page, request }) => {
  await openBackendImageEvidenceIndex(page, request);

  const createdSummaries = page.locator("article").locator("text=/^Created:/");
  await expect(page).toHaveScreenshot("backend-desktop-image-evidence-index.png", {
    animations: "disabled",
    caret: "hide",
    mask: [createdSummaries],
    maxDiffPixels: 5200,
  });
});

test.describe("mobile visual regression (backend)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("claim highlight in pdf viewer", async ({ page }) => {
    await page.goto("/workbench/paper-e2e-001");
    await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
    const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
    await expect(claimsPanel.getByRole("button").first()).toBeVisible();
  });

  test("paper notes list layout", async ({ page }) => {
    await openBackendPaperNotes(page);
    await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
    await expect(page.locator("article a[href^=\"/papers/\"]").first()).toBeVisible();
  });

  test("paper note detail layout", async ({ page }) => {
    await openBackendPaperNoteDetail(page);
    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Review details" })).toBeVisible();
    await expect(sheet.getByTestId("paper-note-structured-state-notice")).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Related Papers", exact: true })).toBeVisible();
  });

  test("image evidence detail layout", async ({ page, request }) => {
    await openBackendImageEvidenceDetail(page, request);

    const createdValue = page.getByText(/^Created$/).locator("xpath=../div[last()]");
    await expect(page).toHaveScreenshot("backend-mobile-image-evidence-detail.png", {
      animations: "disabled",
      caret: "hide",
      mask: [createdValue],
      maxDiffPixels: 4200,
    });
  });

  test("image evidence index layout", async ({ page, request }) => {
    await openBackendImageEvidenceIndex(page, request);

    const createdSummaries = page.locator("article").locator("text=/^Created:/");
    await expect(page).toHaveScreenshot("backend-mobile-image-evidence-index.png", {
      animations: "disabled",
      caret: "hide",
      mask: [createdSummaries],
      maxDiffPixels: 5200,
    });
  });
});

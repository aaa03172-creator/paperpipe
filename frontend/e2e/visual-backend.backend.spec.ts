import { expect, test, Page, type APIRequestContext, type Locator } from "@playwright/test";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const visualBackendPort = process.env.E2E_BACKEND_PORT ?? "18080";
const visualBackendBaseUrl = `http://127.0.0.1:${visualBackendPort}`;
const REVIEW_WORKBENCH_SUBTITLE =
  "Review evidence, saved checks, and claim flags before regenerating or exporting downstream artifacts.";
const visualNoteSlug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024";
const visualMeetingPackPrimarySlug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024";
const visualMeetingPackSecondarySlug = "zoteroe2eNoteBackedBBox2026";
const visualMethodComparisonAlphaPaperId = "paper-e2e-methodcmp-alpha-001";
const visualMethodComparisonBetaPaperId = "paper-e2e-methodcmp-beta-001";
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
const visualImageEvidenceFixtureDerivedPath = path.resolve(
  visualSpecDir,
  "..",
  "..",
  "tests",
  "fixtures",
  "image_evidence_case",
  "derived",
  "thumb_local.png",
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
  const thumbLocal = await fs.readFile(visualImageEvidenceFixtureDerivedPath);
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
      derivative_artifacts: {
        "derivatives/thumb_local.png": thumbLocal.toString("base64"),
      },
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

interface MethodComparisonVisualFixtureOptions {
  comparisonId: string;
  title: string;
  fieldIds: string[];
  paperIds?: string[];
}

interface ChartPackVisualFixtureOptions {
  chartPackId: string;
  title: string;
  chartTitle: string;
}

interface ProtocolCardVisualFixtureOptions {
  protocolId: string;
  title: string;
  secondaryTitle?: string;
}

interface MeetingPackVisualFixtureOptions {
  title: string;
  mode: "journal_club" | "literature_update" | "project_progress_update" | "experiment_proposal";
  paperSlug: string;
}

const visualMeetingPackIndexSearchToken = "Backend visual index";
const visualMeetingPackIndexPrimaryTitle = "Backend visual index meeting pack fixture";
const visualMeetingPackIndexSecondaryTitle = "Backend visual index project update pack";
const visualMeetingPackIndexOverflowCount = 24;

async function generateBackendMethodComparisonVisualFixture(
  request: APIRequestContext,
  options: MethodComparisonVisualFixtureOptions,
): Promise<MethodComparisonVisualFixtureOptions> {
  const existing = await request.get(`${visualBackendBaseUrl}/method-comparisons/${options.comparisonId}`);
  if (existing.ok()) {
    return options;
  }
  const visualVaultPath = path.resolve(visualSpecDir, "..", ".e2e-backend-runtime", "obsidian");
  await fs.mkdir(visualVaultPath, { recursive: true });
  const response = await request.post(`${visualBackendBaseUrl}/method-comparisons/generate`, {
    data: {
      comparison_id: options.comparisonId,
      title: options.title,
      paper_ids: options.paperIds ?? [visualMethodComparisonBetaPaperId, visualMethodComparisonAlphaPaperId],
      field_ids: options.fieldIds,
    },
  });
  expect(
    response.ok(),
    `method comparison visual fixture generation failed (${response.status()}): ${await response.text()}`,
  ).toBeTruthy();
  return options;
}

async function generateBackendChartPackVisualFixture(
  request: APIRequestContext,
  options: ChartPackVisualFixtureOptions,
): Promise<ChartPackVisualFixtureOptions> {
  const response = await request.post(`${visualBackendBaseUrl}/chart-packs/generate`, {
    data: {
      chart_pack_id: options.chartPackId,
      title: options.title,
      charts: [
        {
          title: options.chartTitle,
          template_id: "stats_check_status_counts",
          source_ref: {
            source_kind: "stats_report",
            paper_id: "paper-e2e-001",
            run_id: "run_e2e_fixture_001",
          },
          field_mappings: [
            { target_field: "status", source_field: "status" },
            { target_field: "value", source_field: "count" },
          ],
          sort: { field: "status", direction: "asc" },
        },
      ],
    },
  });
  expect(response.ok()).toBeTruthy();
  return options;
}

async function generateBackendProtocolCardVisualFixture(
  request: APIRequestContext,
  options: ProtocolCardVisualFixtureOptions,
): Promise<ProtocolCardVisualFixtureOptions> {
  const response = await request.post(`${visualBackendBaseUrl}/protocol-cards`, {
    data: {
      protocol_id: options.protocolId,
      title: options.title,
      purpose: "Backend visual regression protocol bundle.",
      context: "Read-first protocol knowledge fixture for inspector snapshots.",
      source_kind: "paper_derived",
      linked_paper_ids: ["paper-e2e-note-backed-bbox-001"],
      linked_note_slugs: [visualNoteSlug],
      current_version_id: `protver_${options.protocolId}_v2`,
      validation_status: "reviewed",
      created_at: "2026-03-23T01:30:00+00:00",
      updated_at: "2026-03-23T02:15:00+00:00",
      versions: [
        {
          version_id: `protver_${options.protocolId}_v1`,
          version_number: 1,
          key_steps_summary: ["Prepare assay plate", "Apply draft treatment pulse"],
          materials: ["Ketone ester", "Neurobasal medium"],
          equipment: ["CO2 incubator"],
          critical_conditions: ["37 C", "5% CO2"],
          readouts: ["Beta-hydroxybutyrate"],
          cautions: ["Draft version kept for historical comparison."],
          content_snapshot: "Step 1: prepare assay plate.\nStep 2: apply draft treatment pulse.",
          change_reason: "Initial protocol-card extraction for backend visual regression.",
          status: "draft",
          created_by: "operator",
          created_at: "2026-03-23T01:35:00+00:00",
          source_refs: [
            {
              paper_slug: visualNoteSlug,
              claim_id: "claim-visual-protocol-001",
              run_id: "run-visual-protocol-001",
              locator: {
                page: 4,
                section: "Methods",
                chunk_id: "visual-method-01",
              },
            },
          ],
          note: "Draft snapshot before reviewer alignment.",
        },
        {
          version_id: `protver_${options.protocolId}_v2`,
          version_number: 2,
          key_steps_summary: ["Prepare assay plate", "Apply ketone pulse", "Collect BHB readout"],
          materials: ["Ketone ester", "Neurobasal medium", "PBS"],
          equipment: ["CO2 incubator", "Plate reader"],
          critical_conditions: ["37 C", "5% CO2", "15 minute pulse"],
          readouts: ["Beta-hydroxybutyrate", "Cell viability"],
          cautions: ["Do not treat saved protocol cards as execution-ready SOPs."],
          content_snapshot: "Step 1: prepare assay plate.\nStep 2: apply ketone pulse.\nStep 3: collect BHB readout.",
          change_reason: "Aligned current version with reviewer-facing note phrasing.",
          status: "active",
          created_by: "reviewer",
          created_at: "2026-03-23T02:00:00+00:00",
          source_refs: [
            {
              paper_slug: visualNoteSlug,
              claim_id: "claim-visual-protocol-002",
              run_id: "run-visual-protocol-002",
              locator: {
                page: 5,
                section: "Methods",
                chunk_id: "visual-method-02",
              },
            },
          ],
          note: "Current reviewer-aligned snapshot for downstream reference.",
        },
      ],
    },
  });
  expect(response.ok()).toBeTruthy();

  if (options.secondaryTitle) {
    const secondaryResponse = await request.post(`${visualBackendBaseUrl}/protocol-cards`, {
      data: {
        protocol_id: `${options.protocolId}_reference`,
        title: options.secondaryTitle,
        purpose: "Reference bundle for index visual regression.",
        context: "Secondary protocol card to exercise search/index layout.",
        source_kind: "internal_adaptation",
        validation_status: "verified_by_user",
        created_at: "2026-03-22T21:00:00+00:00",
        updated_at: "2026-03-22T22:15:00+00:00",
        versions: [
          {
            version_id: `protver_${options.protocolId}_reference_v1`,
            version_number: 1,
            key_steps_summary: ["Stain fixed slices", "Wash and mount"],
            critical_conditions: ["Room temperature"],
            readouts: ["Brightfield image"],
            content_snapshot: "Step 1: stain fixed slices.\nStep 2: wash and mount.",
            change_reason: "Approved reference snapshot.",
            status: "active",
            created_by: "reviewer",
            created_at: "2026-03-22T22:00:00+00:00",
            source_refs: [
              {
                paper_slug: visualNoteSlug,
                claim_id: "claim-visual-protocol-010",
              },
            ],
            note: "Stable reference card for visual-regression coverage.",
          },
        ],
      },
    });
    expect(secondaryResponse.ok()).toBeTruthy();
  }

  return options;
}

async function generateBackendMeetingPackVisualFixture(
  request: APIRequestContext,
  options: MeetingPackVisualFixtureOptions,
): Promise<{ packId: string; title: string }> {
  const existing = await request.get(`${visualBackendBaseUrl}/meeting-packs`);
  if (existing.ok()) {
    const payload = (await existing.json()) as {
      items?: Array<{ pack_id?: string; title?: string; mode?: string }>;
    };
    const match = payload.items?.find(
      (item) => item.title === options.title && item.mode === options.mode && item.pack_id,
    );
    if (match?.pack_id) {
      return { packId: match.pack_id, title: options.title };
    }
  }
  const response = await request.post(`${visualBackendBaseUrl}/meeting-packs/generate`, {
    data: {
      mode: options.mode,
      title: options.title,
      source_items: [{ type: "paper_slug", ref: options.paperSlug }],
      max_slides: 5,
    },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { pack?: { id?: string; title?: string } };
  expect(payload.pack?.id).toBeTruthy();
  expect(payload.pack?.title).toBe(options.title);
  return { packId: payload.pack?.id ?? "", title: options.title };
}

async function openBackendWorkbenchAndSelectSecondClaim(page: Page) {
  await openBackendWorkbench(page);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel).toBeVisible();
  await expect(claimsPanel.getByRole("button")).toHaveCount(3);
  const secondClaimButton = claimsPanel.getByRole("button").nth(1);
  await secondClaimButton.click();
  await viewer.scrollIntoViewIfNeeded();
  await expect(secondClaimButton).toHaveClass(/surface-selected/, { timeout: 15_000 });
  await expect(page.getByText("Claim Link · p.1").first()).toBeVisible();
}

async function getStablePdfPage(page: Page) {
  const pdfPage = page.getByRole("region", { name: /^Page 1$/ }).first();
  await expect(pdfPage).toBeVisible();
  await expect
    .poll(
      async () => {
        const box = await pdfPage.boundingBox();
        return box?.width ?? 0;
      },
      { message: "PDF page should settle to the responsive viewer width" },
    )
    .toBeLessThan(700);
  return pdfPage;
}

async function gotoUntilLive(
  page: Page,
  path: string,
  assertReady: () => Promise<void>,
  attempts = 3,
) {
  let lastError: unknown = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    await page.goto(path);
    try {
      await assertReady();
      return;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error(`Failed to open live route: ${path}`);
}

async function openBackendWorkbench(page: Page) {
  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
    await expect(page.locator("section").filter({ hasText: "Synthesis / Artifact" }).first()).toBeVisible();
    await expect(page.locator("section").filter({ hasText: "Timeline" }).first()).toBeVisible();
  });
  const claimHighlight = page
    .locator('[data-testid="claim-highlight"], [data-testid="claim-search-highlight"], [data-testid="claim-approx-highlight"]')
    .first();
  try {
    await expect(claimHighlight).toBeVisible({ timeout: 15_000 });
  } catch {
    await expect(page.getByText("Claim Link · p.1").first()).toBeVisible();
  }
}

async function openBackendPaperNotes(page: Page) {
  await gotoUntilLive(page, "/papers?q=Structured%20Skills%20ClaimSet", async () => {
    await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Loading notes...")).toHaveCount(0);
    await expect(
      page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first(),
    ).toBeVisible({ timeout: 15_000 });
  });
  await expect(
    page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first(),
  ).toBeVisible();
}

async function openBackendTriage(page: Page) {
  await page.goto("/");
  await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByText("Loading triage queue...")).toHaveCount(0);
}

async function openBackendRuntimeReadiness(page: Page) {
  await gotoUntilLive(page, "/ready", async () => {
    await expect(page.getByRole("heading", { name: "Check whether this workspace is ready for real runs" })).toBeVisible();
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByTestId("runtime-readiness-product-loop")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("runtime-readiness-check-config_file")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("runtime-readiness-suggested-fixes")).toBeVisible({ timeout: 15_000 });
  });
}

async function openBackendPaperNoteDetail(page: Page) {
  await gotoUntilLive(page, "/papers/zoteroduboisAlzheimerDiseaseClinicalBiological2024", async () => {
    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible();
  });
}

async function openStructuredBackendPaperNoteDetail(page: Page) {
  await gotoUntilLive(page, "/papers/zoterostructuredSkillsClaimset2026", async () => {
    await expect(page.getByText("Loading note...")).toHaveCount(0);
    await expect(
      page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" }),
    ).toBeVisible({ timeout: 15_000 });
  });
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

async function openBackendMethodComparisonDetail(page: Page, request: APIRequestContext) {
  const fixture = await generateBackendMethodComparisonVisualFixture(request, {
    comparisonId: "methodcmp_backend_visual_fixture",
    title: "Backend visual method comparison fixture",
    fieldIds: ["intervention", "duration_or_timepoint", "sample_size"],
  });
  await page.goto(`/method-comparisons/${fixture.comparisonId}`);
  await expect(page.getByRole("heading", { name: fixture.title })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Comparison Grid" })).toBeVisible();
}

async function openBackendMethodComparisonIndex(page: Page, request: APIRequestContext) {
  await generateBackendMethodComparisonVisualFixture(request, {
    comparisonId: "methodcmp_backend_visual_fixture",
    title: "Backend visual method comparison fixture",
    fieldIds: ["intervention", "duration_or_timepoint", "sample_size"],
  });
  await generateBackendMethodComparisonVisualFixture(request, {
    comparisonId: "methodcmp_backend_visual_clean_fixture",
    title: "Backend visual clean method comparison",
    fieldIds: ["intervention", "duration_or_timepoint"],
    paperIds: [visualMethodComparisonAlphaPaperId],
  });
  await page.goto("/method-comparisons");
  await expect(page.getByRole("heading", { name: "Method Comparisons", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or comparison id"]').fill("Backend visual");
  await expect(page.locator("article").filter({ hasText: "Backend visual method comparison fixture" }).first()).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Backend visual clean method comparison" }).first()).toBeVisible();
}

async function openBackendChartPackDetail(page: Page, request: APIRequestContext) {
  const fixture = await generateBackendChartPackVisualFixture(request, {
    chartPackId: "chartpack_backend_visual_fixture",
    title: "Backend visual chart pack fixture",
    chartTitle: "Backend visual verification status counts",
  });
  await page.goto(`/chart-packs/${fixture.chartPackId}`);
  await expect(page.getByRole("heading", { name: fixture.title })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Charts" })).toBeVisible();
}

async function openBackendChartPackIndex(page: Page, request: APIRequestContext) {
  await generateBackendChartPackVisualFixture(request, {
    chartPackId: "chartpack_backend_visual_fixture",
    title: "Backend visual chart pack fixture",
    chartTitle: "Backend visual verification status counts",
  });
  await generateBackendChartPackVisualFixture(request, {
    chartPackId: "chartpack_backend_visual_clean_fixture",
    title: "Backend visual clean chart pack",
    chartTitle: "Backend visual clean status summary",
  });
  await page.goto("/chart-packs");
  await expect(page.getByRole("heading", { name: "Chart Packs", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or chart pack id"]').fill("Backend visual");
  await expect(page.locator("article").filter({ hasText: "Backend visual chart pack fixture" }).first()).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Backend visual clean chart pack" }).first()).toBeVisible();
}

async function openBackendProtocolCardDetail(page: Page, request: APIRequestContext) {
  const fixture = await generateBackendProtocolCardVisualFixture(request, {
    protocolId: "protocol_backend_visual_fixture",
    title: "Backend visual protocol fixture",
  });
  await page.goto(`/protocol-cards/${fixture.protocolId}`);
  await expect(page.getByRole("heading", { name: fixture.title })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Version review" })).toBeVisible();
}

async function openBackendProtocolCardIndex(page: Page, request: APIRequestContext) {
  await generateBackendProtocolCardVisualFixture(request, {
    protocolId: "protocol_backend_visual_fixture",
    title: "Backend visual protocol fixture",
    secondaryTitle: "Backend visual brightfield reference",
  });
  await page.goto("/protocol-cards");
  await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or protocol id"]').fill("Backend visual");
  await expect(page.locator("article").filter({ hasText: "Backend visual protocol fixture" }).first()).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Backend visual brightfield reference" }).first()).toBeVisible();
}

async function openBackendMeetingPackDetail(page: Page, request: APIRequestContext) {
  const fixture = await generateBackendMeetingPackVisualFixture(request, {
    title: "Backend visual meeting pack fixture",
    mode: "journal_club",
    paperSlug: visualMeetingPackPrimarySlug,
  });
  await page.goto(`/meeting-packs/${fixture.packId}`);
  await expect(page.getByRole("banner").getByRole("heading", { name: fixture.title })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Draft summary" })).toBeVisible();
}

async function openBackendMeetingPackIndex(page: Page, request: APIRequestContext) {
  for (let index = 0; index < visualMeetingPackIndexOverflowCount; index += 1) {
    await generateBackendMeetingPackVisualFixture(request, {
      title: `${visualMeetingPackIndexSearchToken} overflow draft ${String(index + 1).padStart(2, "0")}`,
      mode: index % 2 === 0 ? "journal_club" : "project_progress_update",
      paperSlug: index % 2 === 0 ? visualMeetingPackPrimarySlug : visualMeetingPackSecondarySlug,
    });
  }
  await generateBackendMeetingPackVisualFixture(request, {
    title: visualMeetingPackIndexSecondaryTitle,
    mode: "project_progress_update",
    paperSlug: visualMeetingPackSecondarySlug,
  });
  await generateBackendMeetingPackVisualFixture(request, {
    title: visualMeetingPackIndexPrimaryTitle,
    mode: "journal_club",
    paperSlug: visualMeetingPackPrimarySlug,
  });
  await page.goto("/meeting-packs?meeting_pack_visible_limit=2");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Saved meeting packs" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.getByLabel("Search saved meeting packs").fill(visualMeetingPackIndexSearchToken);
  await expect(page.getByText(visualMeetingPackIndexPrimaryTitle, { exact: true }).first()).toBeVisible();
  await expect(page.getByText(visualMeetingPackIndexSecondaryTitle, { exact: true }).first()).toBeVisible();
}

async function stabilizeMeetingPackIndexVisualCopy(page: Page) {
  const visibleRows = page.getByTestId("meeting-pack-index-row");
  await expect(visibleRows).toHaveCount(2);

  const rowIdentityValues = [
    "Saved 12:00:00.000 PM",
    "Saved 12:05:00.000 PM",
  ];
  const packIdValues = [
    "meetingpack_backend_visual_index_fixture",
    "meetingpack_backend_visual_index_project_update",
  ];
  const stableRowCount = Math.min(await visibleRows.count(), rowIdentityValues.length);
  for (let index = 0; index < stableRowCount; index += 1) {
    const row = visibleRows.nth(index);
    await row.getByTestId("meeting-pack-index-identity").evaluate((node, nextValue) => {
      node.textContent = nextValue;
    }, rowIdentityValues[index]);
    await row.locator(".font-mono").first().evaluate((node, nextValue) => {
      node.textContent = nextValue;
    }, packIdValues[index]);
  }
}

async function replaceFirstLabeledDetailValue(page: Page, label: RegExp, value: string) {
  const fieldValue = page.getByText(label).locator("xpath=../div[last()]");
  if (await fieldValue.count()) {
    await fieldValue.first().evaluate((node, nextValue) => {
      node.textContent = nextValue;
    }, value);
  }
}

async function replaceSummaryLineValues(locator: Locator, values: string[]) {
  if ((await locator.count()) === 0) {
    return;
  }
  await locator.evaluateAll((nodes, nextValues) => {
    nodes.forEach((node, index) => {
      node.textContent = nextValues[index] ?? nextValues[nextValues.length - 1] ?? "";
    });
  }, values);
}

async function stabilizeMeetingPackDetailVisualCopy(page: Page) {
  await replaceFirstLabeledDetailValue(page, /^Created$/, "Apr 17, 2026, 12:00 PM");

  const packIdField = page.locator(".font-mono").filter({ hasText: /^meetingpack_/ }).first();
  if (await packIdField.count()) {
    await packIdField.evaluate((node) => {
      node.textContent = "meetingpack_visual_fixture";
    });
  }

  const packIdInput = page.getByLabel("Meeting pack ID");
  if (await packIdInput.count()) {
    await packIdInput.evaluate((node) => {
      if (node instanceof HTMLInputElement) {
        node.value = "meetingpack_visual_fixture";
      }
    });
  }
}

async function stabilizePaperNoteDetailVisualCopy(page: Page) {
  await replaceSummaryLineValues(
    page.getByTestId("paper-note-workspace-context-note").locator("text=/^updated /i"),
    ["updated Apr 17, 2026, 12:00 PM"],
  );
  await replaceSummaryLineValues(
    page.getByTestId("paper-note-workspace-context-state").locator("text=/^updated /i"),
    ["updated Apr 17, 2026, 12:05 PM"],
  );
  await replaceSummaryLineValues(
    page.getByTestId("paper-note-review-snapshot").locator("text=/^updated /i"),
    ["updated Apr 17, 2026, 12:05 PM"],
  );
  await replaceSummaryLineValues(
    page.locator("text=/^saved state /i"),
    ["saved state Apr 17, 2026, 12:05 PM"],
  );
}

async function stabilizePaperNotesListVisualCopy(page: Page) {
  await replaceSummaryLineValues(page.getByTestId("paper-note-list-processed-date"), [
    "Apr 17, 2026",
    "Apr 16, 2026",
    "Apr 15, 2026",
    "Apr 14, 2026",
    "Apr 13, 2026",
    "Apr 12, 2026",
  ]);
}

async function stabilizeMethodComparisonDetailVisualCopy(page: Page) {
  await replaceFirstLabeledDetailValue(page, /^Created$/, "Apr 17, 2026, 12:00 PM");
  await replaceFirstLabeledDetailValue(page, /^Generated$/, "Apr 17, 2026, 12:05 PM");
}

async function stabilizeChartPackDetailVisualCopy(page: Page) {
  await replaceFirstLabeledDetailValue(page, /^Created$/, "Apr 17, 2026, 12:00 PM");
  await replaceFirstLabeledDetailValue(page, /^Generated$/, "Apr 17, 2026, 12:05 PM");
}

async function stabilizeImageEvidenceDetailVisualCopy(page: Page) {
  await replaceFirstLabeledDetailValue(page, /^Created$/, "Apr 17, 2026, 12:00 PM");
}

async function stabilizeImageEvidenceIndexVisualCopy(page: Page) {
  await replaceSummaryLineValues(page.locator("article").locator("text=/^Created:/"), [
    "Created: Apr 17, 2026, 12:00 PM",
    "Created: Apr 17, 2026, 12:05 PM",
    "Created: Apr 17, 2026, 12:10 PM",
  ]);
}

async function stabilizeMethodComparisonIndexVisualCopy(page: Page) {
  await replaceSummaryLineValues(page.locator("article").locator("text=/^Created:/"), [
    "Created: Apr 17, 2026, 12:00 PM",
    "Created: Apr 17, 2026, 12:10 PM",
  ]);
  await replaceSummaryLineValues(page.locator("article").locator("text=/^Generated:/"), [
    "Generated: Apr 17, 2026, 12:05 PM",
    "Generated: Apr 17, 2026, 12:15 PM",
  ]);
}

async function stabilizeChartPackIndexVisualCopy(page: Page) {
  await replaceSummaryLineValues(page.locator("article").locator("text=/^Created:/"), [
    "Created: Apr 17, 2026, 12:00 PM",
    "Created: Apr 17, 2026, 12:10 PM",
  ]);
  await replaceSummaryLineValues(page.locator("article").locator("text=/^Generated:/"), [
    "Generated: Apr 17, 2026, 12:05 PM",
    "Generated: Apr 17, 2026, 12:15 PM",
  ]);
}

async function stabilizeProtocolCardDetailVisualCopy(page: Page) {
  await replaceSummaryLineValues(page.getByTestId("protocol-card-detail-created-at"), [
    "Apr 17, 2026, 12:00 PM",
  ]);
  await replaceSummaryLineValues(page.getByTestId("protocol-card-detail-version-created-at"), [
    "1 source refs · Apr 17, 2026, 12:00 PM",
    "1 source refs · Apr 17, 2026, 12:05 PM",
  ]);
  await replaceSummaryLineValues(page.getByTestId("protocol-card-detail-attachment-saved-at"), [
    "Apr 17, 2026, 12:10 PM",
  ]);
}

async function stabilizeProtocolCardIndexVisualCopy(page: Page) {
  await replaceSummaryLineValues(page.getByTestId("protocol-card-index-updated-at"), [
    "Apr 17, 2026, 12:00 PM",
    "Apr 17, 2026, 12:05 PM",
  ]);
}

async function stabilizeWorkbenchTimelineVisualCopy(page: Page) {
  await replaceSummaryLineValues(
    page
      .locator("section")
      .filter({ hasText: "Timeline" })
      .first()
      .locator("text=/^(?:[0-1]?\\d|2[0-3]):[0-5]\\d(?::[0-5]\\d)?(?:\\s?[AP]M)?$/"),
    [
      "12:00:00 PM",
      "12:02:00 PM",
      "12:04:00 PM",
      "12:06:00 PM",
      "12:08:00 PM",
      "12:10:00 PM",
      "12:12:00 PM",
      "12:14:00 PM",
    ],
  );
}

async function stabilizeWorkbenchShellVisualCopy(page: Page) {
  await stabilizeWorkbenchTimelineVisualCopy(page);
  await replaceSummaryLineValues(page.getByTestId("workbench-paper-synthesis-updated-at"), [
    "Updated Apr 17, 2026, 12:00 PM. Open the raw markdown when you need the derived note itself.",
  ]);
}

async function stabilizeWorkbenchRailVisualCopy(page: Page) {
  await replaceSummaryLineValues(page.getByTestId("rail-review-detail"), [
    "Evidence-backed review summary stays visible for rail layout coverage.",
  ]);
  await replaceSummaryLineValues(page.getByTestId("rail-ops-reason"), [
    "Saved note review is ready for downstream evidence follow-up.",
    "Saved note review needs follow-up before downstream reuse.",
    "Claim review remains available for this paper.",
  ]);
}

async function stabilizeTriageDashboardVisualCopy(page: Page) {
  const resumeCard = page.getByTestId("home-resume-card");
  if (await resumeCard.count()) {
    await resumeCard.getByTestId("home-resume-title").evaluate((node) => {
      node.textContent = "Current evidence review";
    });
    await resumeCard.getByTestId("home-resume-next-action").evaluate((node) => {
      node.textContent = "Next: Continue evidence review.";
    });
    const resumeHint = resumeCard.getByTestId("home-resume-hint");
    if (await resumeHint.count()) {
      await resumeHint.evaluate((node) => {
        node.textContent = "Saved checks need attention before export.";
      });
    }
    await resumeCard.getByTestId("home-resume-state-badge").evaluate((node) => {
      node.textContent = "Blocked";
      node.className =
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium gap-1 border-[var(--pp-warning-border)] bg-[var(--pp-warning-bg)] text-[var(--pp-warning-text)]";
    });
    const accessBadge = resumeCard.getByTestId("home-resume-access-badge");
    if (await accessBadge.count()) {
      await accessBadge.evaluate((node) => {
        node.textContent = "Local PDF";
        node.className =
          "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium gap-1 border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]";
      });
    }
    const resumeMeta = resumeCard.locator("div.min-w-0").first();
    await resumeMeta.evaluate((node) => {
      node.textContent = "Updated Apr 17, 2026 · Open saved PDF";
    });
  }

  await page.getByTestId("home-workspace-context-saved-notes").evaluate((node) => {
    node.textContent = "15";
  });
  await page.getByTestId("home-workspace-context-structured-notes").evaluate((node) => {
    node.textContent = "6";
  });
  await page.getByTestId("home-workspace-context-needs-review").evaluate((node) => {
    node.textContent = "8";
  });
  await page.getByTestId("home-workspace-context-blocked").evaluate((node) => {
    node.textContent = "5";
  });
  await page.getByTestId("home-workspace-context-summary").evaluate((node) => {
    node.textContent =
      "This home stays paper-first. Saved notes, paper markers, and current review load show what is already active and what to pick up next.";
  });
  await page.getByTestId("home-workspace-marker-detail").evaluate((node) => {
    node.textContent = "4 papers already carry paper-level judgment. 1 includes a private note.";
  });
  await page.getByTestId("home-workspace-marker-starred").locator("p").nth(1).evaluate((node) => {
    node.textContent = "2";
  });
  await page.getByTestId("home-workspace-marker-revisit").locator("p").nth(1).evaluate((node) => {
    node.textContent = "1";
  });
  await page.getByTestId("home-workspace-marker-needs-verification").locator("p").nth(1).evaluate((node) => {
    node.textContent = "3";
  });
  await page.getByTestId("home-workspace-marker-experiment-relevant").locator("p").nth(1).evaluate((node) => {
    node.textContent = "2";
  });
  await page.getByTestId("home-workspace-context-detail").evaluate((node) => {
    node.textContent = "Latest note updated Apr 17, 2026";
  });

  await replaceSummaryLineValues(page.getByTestId("triage-updated-at"), [
    "Updated: Apr 17, 2026, 12:00 PM",
    "Updated: Apr 17, 2026, 12:05 PM",
    "Updated: Apr 17, 2026, 12:10 PM",
    "Updated: Apr 17, 2026, 12:15 PM",
    "Updated: Apr 17, 2026, 12:20 PM",
    "Updated: Apr 17, 2026, 12:25 PM",
  ]);
}

async function hideVisualScrollbars(page: Page) {
  await page.addStyleTag({
    content: `
      html {
        scrollbar-width: none;
      }
      body {
        scrollbar-width: none;
      }
      *::-webkit-scrollbar {
        width: 0 !important;
        height: 0 !important;
        display: none !important;
      }
    `,
  });
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("pp-theme", "dark");
  });
  await page.emulateMedia({ colorScheme: "dark" });
});

test("visual regression (backend, desktop): paper notes list layout", async ({ page }) => {
  await openBackendPaperNotes(page);
  await stabilizePaperNotesListVisualCopy(page);

  await expect(page).toHaveScreenshot("backend-desktop-paper-notes-list.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 13000,
  });
});

test("visual regression (backend, desktop): triage dashboard layout", async ({ page }) => {
  await openBackendTriage(page);
  await hideVisualScrollbars(page);
  const searchBox = page.getByRole("textbox", { name: "Search papers" });
  await searchBox.fill("E2E");
  await searchBox.evaluate((element) => {
    if (element instanceof HTMLElement) {
      element.blur();
    }
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  await stabilizeTriageDashboardVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-triage-dashboard.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 32000,
  });
});

test("visual regression (backend, desktop): runtime readiness layout", async ({ page }) => {
  await openBackendRuntimeReadiness(page);
  await hideVisualScrollbars(page);

  await expect(page).toHaveScreenshot("backend-desktop-runtime-readiness.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 5200,
  });
});

test("visual regression (backend, desktop): paper note detail layout", async ({ page }) => {
  await openBackendPaperNoteDetail(page);
  await stabilizePaperNoteDetailVisualCopy(page);

  await expect(page).toHaveScreenshot("backend-desktop-paper-note-detail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 3200,
  });
});

test("visual regression (backend, desktop): structured paper note detail layout", async ({ page }) => {
  await openStructuredBackendPaperNoteDetail(page);
  await stabilizePaperNoteDetailVisualCopy(page);

  await expect(page).toHaveScreenshot("backend-desktop-paper-note-detail-structured.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 4500,
  });
});

test("visual regression (backend, desktop): workbench shell layout", async ({ page }) => {
  await openBackendWorkbench(page);
  await stabilizeWorkbenchShellVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-workbench-shell.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 7600,
  });
});

test("visual regression (backend, desktop): workbench rail layout", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");
  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.getByRole("textbox", { name: "Search papers" }).fill("E2E");
  await hideVisualScrollbars(page);
  await stabilizeWorkbenchRailVisualCopy(page);

  const rail = page
    .locator("aside")
    .filter({ has: page.getByRole("textbox", { name: "Search papers" }) })
    .first();
  await expect(rail).toHaveScreenshot("backend-desktop-workbench-rail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 4000,
  });
});

test("visual regression (backend, desktop): claim highlight in pdf viewer", async ({ page }) => {
  await openBackendWorkbenchAndSelectSecondClaim(page);

  const pdfPage = await getStablePdfPage(page);
  await expect(pdfPage).toHaveScreenshot("backend-desktop-claim-highlight.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 1600,
  });
});

test("visual regression (backend, desktop): image evidence detail layout", async ({ page, request }) => {
  await openBackendImageEvidenceDetail(page, request);
  await stabilizeImageEvidenceDetailVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-image-evidence-detail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 4200,
  });
});

test("visual regression (backend, desktop): image evidence index layout", async ({ page, request }) => {
  await openBackendImageEvidenceIndex(page, request);
  await stabilizeImageEvidenceIndexVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-image-evidence-index.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 5200,
  });
});

test("visual regression (backend, desktop): method comparison detail layout", async ({ page, request }) => {
  await openBackendMethodComparisonDetail(page, request);
  await stabilizeMethodComparisonDetailVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-method-comparison-detail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 5200,
  });
});

test("visual regression (backend, desktop): method comparison index layout", async ({ page, request }) => {
  await openBackendMethodComparisonIndex(page, request);
  await stabilizeMethodComparisonIndexVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-method-comparison-index.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 6200,
  });
});

test("visual regression (backend, desktop): chart pack detail layout", async ({ page, request }) => {
  await openBackendChartPackDetail(page, request);
  await stabilizeChartPackDetailVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-chart-pack-detail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 6200,
  });
});

test("visual regression (backend, desktop): chart pack index layout", async ({ page, request }) => {
  await openBackendChartPackIndex(page, request);
  await stabilizeChartPackIndexVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-chart-pack-index.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 6200,
  });
});

test("visual regression (backend, desktop): protocol knowledge detail layout", async ({ page, request }) => {
  await openBackendProtocolCardDetail(page, request);
  await stabilizeProtocolCardDetailVisualCopy(page);

  await expect(page).toHaveScreenshot("backend-desktop-protocol-card-detail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 6200,
  });
});

test("visual regression (backend, desktop): protocol knowledge index layout", async ({ page, request }) => {
  await openBackendProtocolCardIndex(page, request);
  await stabilizeProtocolCardIndexVisualCopy(page);

  await expect(page).toHaveScreenshot("backend-desktop-protocol-card-index.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 6800,
  });
});

test("visual regression (backend, desktop): meeting pack detail layout", async ({ page, request }) => {
  await openBackendMeetingPackDetail(page, request);
  await stabilizeMeetingPackDetailVisualCopy(page);
  await expect(page).toHaveScreenshot("backend-desktop-meeting-pack-detail.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 7200,
  });
});

test("visual regression (backend, desktop): meeting pack index layout", async ({ page, request }) => {
  await openBackendMeetingPackIndex(page, request);
  await stabilizeMeetingPackIndexVisualCopy(page);

  await expect(page).toHaveScreenshot("backend-desktop-meeting-pack-index.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 7200,
  });
});

test.describe("mobile visual regression (backend)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("claim highlight in pdf viewer", async ({ page }) => {
    await openBackendWorkbenchAndSelectSecondClaim(page);

    const pdfPage = await getStablePdfPage(page);
    await expect(pdfPage).toHaveScreenshot("backend-mobile-claim-highlight.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 1200,
    });
  });

  test("paper notes list layout", async ({ page }) => {
    await openBackendPaperNotes(page);
    await stabilizePaperNotesListVisualCopy(page);

    await expect(page).toHaveScreenshot("backend-mobile-paper-notes-list.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 3500,
    });
  });

  test("triage dashboard layout", async ({ page }) => {
    await openBackendTriage(page);
    const searchBox = page.getByRole("textbox", { name: "Search papers" });
    await searchBox.fill("E2E");
    await searchBox.evaluate((element) => {
      if (element instanceof HTMLElement) {
        element.blur();
      }
    });
    await page.evaluate(() => window.scrollTo(0, 0));
    await stabilizeTriageDashboardVisualCopy(page);

    await expect(page).toHaveScreenshot("backend-mobile-triage-dashboard.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 4200,
    });
  });

  test("runtime readiness layout", async ({ page }) => {
    await openBackendRuntimeReadiness(page);

    await expect(page).toHaveScreenshot("backend-mobile-runtime-readiness.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 5200,
    });
  });

  test("paper note detail layout", async ({ page }) => {
    await openBackendPaperNoteDetail(page);
    await stabilizePaperNoteDetailVisualCopy(page);

    await expect(page).toHaveScreenshot("backend-mobile-paper-note-detail.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 3500,
    });
  });

  test("structured paper note detail layout", async ({ page }) => {
    await openStructuredBackendPaperNoteDetail(page);
    await stabilizePaperNoteDetailVisualCopy(page);

    await expect(page).toHaveScreenshot("backend-mobile-paper-note-detail-structured.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 4200,
    });
  });

  test("workbench shell layout", async ({ page }) => {
    test.slow();
    await openBackendWorkbench(page);
    await stabilizeWorkbenchShellVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-workbench-shell.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 6200,
    });
  });

  test("image evidence detail layout", async ({ page, request }) => {
    await openBackendImageEvidenceDetail(page, request);
    await stabilizeImageEvidenceDetailVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-image-evidence-detail.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 4200,
    });
  });

  test("image evidence index layout", async ({ page, request }) => {
    await openBackendImageEvidenceIndex(page, request);
    await stabilizeImageEvidenceIndexVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-image-evidence-index.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 5200,
    });
  });

  test("method comparison detail layout", async ({ page, request }) => {
    await openBackendMethodComparisonDetail(page, request);
    await stabilizeMethodComparisonDetailVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-method-comparison-detail.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 5200,
    });
  });

  test("method comparison index layout", async ({ page, request }) => {
    await openBackendMethodComparisonIndex(page, request);
    await stabilizeMethodComparisonIndexVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-method-comparison-index.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 6200,
    });
  });

  test("chart pack detail layout", async ({ page, request }) => {
    await openBackendChartPackDetail(page, request);
    await stabilizeChartPackDetailVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-chart-pack-detail.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 6200,
    });
  });

  test("chart pack index layout", async ({ page, request }) => {
    await openBackendChartPackIndex(page, request);
    await stabilizeChartPackIndexVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-chart-pack-index.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 6200,
    });
  });

  test("protocol knowledge detail layout", async ({ page, request }) => {
    await openBackendProtocolCardDetail(page, request);
    await stabilizeProtocolCardDetailVisualCopy(page);

    await expect(page).toHaveScreenshot("backend-mobile-protocol-card-detail.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 6200,
    });
  });

  test("protocol knowledge index layout", async ({ page, request }) => {
    await openBackendProtocolCardIndex(page, request);
    await stabilizeProtocolCardIndexVisualCopy(page);

    await expect(page).toHaveScreenshot("backend-mobile-protocol-card-index.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 6800,
    });
  });

  test("meeting pack detail layout", async ({ page, request }) => {
    await openBackendMeetingPackDetail(page, request);
    await stabilizeMeetingPackDetailVisualCopy(page);
    await expect(page).toHaveScreenshot("backend-mobile-meeting-pack-detail.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 7200,
    });
  });

  test("meeting pack index layout", async ({ page, request }) => {
    await openBackendMeetingPackIndex(page, request);
    await stabilizeMeetingPackIndexVisualCopy(page);

    await expect(page).toHaveScreenshot("backend-mobile-meeting-pack-index.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 18000,
    });
  });
});

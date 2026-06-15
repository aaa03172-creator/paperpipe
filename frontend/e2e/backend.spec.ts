import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const runSoftGateCanary = process.env.PAPERPIPE_E2E_CANARY === "1";
const runRealSmoke = process.env.PAPERPIPE_REAL_SMOKE === "1";
const requireRealSmokeCandidates = process.env.PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES === "1";
const runParserWorkerLane = process.env.PAPERPIPE_E2E_ENABLE_PARSER_WORKER === "1";
const backendPort = process.env.E2E_BACKEND_PORT ?? "18080";
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const noteSlug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024";
const canonicalDuboisNoteSlug = "Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation";
const noteBackedWorkbenchPaperId = "paper-e2e-note-backed-bbox-001";
const noteBackedWorkbenchSlug = "zoteroe2eNoteBackedBBox2026";
const parserFallbackWorkbenchPaperId = "paper-e2e-parser-fallback-001";
const methodComparisonAlphaPaperId = "paper-e2e-methodcmp-alpha-001";
const methodComparisonBetaPaperId = "paper-e2e-methodcmp-beta-001";
const structuredNoteSlug = "zoterostructuredSkillsClaimset2026";
const missingStateNoteSlug = "zoteroduboisAmnesticMCIProdromal2004";
const actionNoteSlug = "zoteroliveValidateCitations2026";
const quietActionNoteSlug = "zoteroquietValidateCitations2026";
const runId = "skill-20260226T130003000000+0000-critical_appraisal";
const claimId = "claim_c0ffee000001";
const evidenceId = "evidence_deadbeef0001";
const structuredRunId = "skill-20260309T090000Z-critical_appraisal";
const structuredClaimId = "claim_structured_001";
const structuredEvidenceId = "evidence_structured_001";
const realSmokeHealthyClearPaperId = "zotero:duboisAlzheimerDiseaseClinicalBiological2024";
const realSmokeActionNeededClearPaperId = "zotero:parkDiscoveryDualactionSmall2022";
const realSmokeProtocolCardPaperId = "zotero:chandraGutMicrobiomeAlzheimers2023";
const realSmokeMethodComparisonTitle = "Current runtime method comparison smoke";
const realSmokeImageEvidenceTitle = "Current runtime image evidence smoke";
const realSmokeChartPackTitle = "Current runtime chart pack smoke";
const REVIEW_WORKBENCH_SUBTITLE =
  "Review evidence, saved checks, and claim flags before regenerating or exporting downstream artifacts.";
const PAPER_NOTE_REVIEW_MODE_SUMMARY =
  "Review mode lifts actions, run history, and saved claims ahead of supporting context.";
const PAPER_NOTE_READ_MODE_SUMMARY =
  "Read mode keeps related papers, references, and reading context closer to the markdown flow.";
const e2eSpecDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(e2eSpecDir, "..", "..");
const e2eVaultPath = path.resolve(e2eSpecDir, "..", ".e2e-backend-runtime", "obsidian");
const samplePdfPath = path.resolve(e2eSpecDir, "..", "public", "sample.pdf");
const realCloudUploadPdfPath = path.resolve(
  e2eSpecDir,
  "..",
  ".e2e-backend-runtime",
  "fixtures",
  "real-cloud-upload.pdf",
);
const e2eMethodComparisonsRoot = path.resolve(
  e2eSpecDir,
  "..",
  ".e2e-backend-runtime",
  "storage",
  "method_comparisons",
);
const e2eChartPacksRoot = path.resolve(
  e2eSpecDir,
  "..",
  ".e2e-backend-runtime",
  "storage",
  "chart_packs",
);
const e2eImageEvidenceRoot = path.resolve(
  e2eSpecDir,
  "..",
  ".e2e-backend-runtime",
  "storage",
  "image_evidence",
);
const e2eProtocolCardsRoot = path.resolve(
  e2eSpecDir,
  "..",
  ".e2e-backend-runtime",
  "storage",
  "protocol_cards",
);
const imageEvidenceFixtureRawPath = path.resolve(
  e2eSpecDir,
  "..",
  "..",
  "tests",
  "fixtures",
  "image_evidence_case",
  "raw",
  "local-alpha.tif",
);
const imageEvidenceFixtureDerivedPath = path.resolve(
  e2eSpecDir,
  "..",
  "..",
  "tests",
  "fixtures",
  "image_evidence_case",
  "derived",
  "thumb_local.png",
);
const imageEvidenceMissingRawPath = path.resolve(
  e2eSpecDir,
  "..",
  ".e2e-backend-runtime",
  "missing",
  "absent-local-alpha.tif",
);
const imageEvidenceFixtureDisplayPath = maskedRepoLocalPath(imageEvidenceFixtureRawPath);
const imageEvidenceMissingDisplayPath = maskedRepoLocalPath(imageEvidenceMissingRawPath);

function focusDomId(kind: "run" | "claim" | "evidence", id: string): string {
  return `#pp-focus-${kind}-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function encodedFocus(kind: "run" | "claim" | "evidence", id: string): string {
  return `${kind}%3A${encodeURIComponent(id)}`;
}

function notePathFor(slug: string): string {
  return path.join(e2eVaultPath, "Inbox", "PaperPipe", `${slug}.md`);
}

function maskedRepoLocalPath(rawPath: string): string {
  const relative = path.relative(repoRoot, rawPath);
  if (relative.startsWith("..")) {
    return `.../${path.basename(rawPath)}`;
  }
  return `./${relative.split(path.sep).join("/")}`;
}

async function imageEvidenceFixtureDerivedArtifacts(): Promise<Record<string, string>> {
  const thumbLocal = await fs.readFile(imageEvidenceFixtureDerivedPath);
  return {
    "derivatives/thumb_local.png": thumbLocal.toString("base64"),
  };
}

function buildMinimalPdfBuffer(lines: string[]): Buffer {
  const escapedLines = lines.map((line) => line.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)"));
  const textCommands = escapedLines.map((line, index) => `1 0 0 1 54 ${720 - index * 24} Tm (${line}) Tj`).join("\n");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(`BT\n/F1 14 Tf\n${textCommands}\nET`, "ascii")} >>\nstream\nBT\n/F1 14 Tf\n${textCommands}\nET\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  for (const [index, object] of objects.entries()) {
    offsets.push(Buffer.byteLength(pdf, "ascii"));
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  }
  const xrefOffset = Buffer.byteLength(pdf, "ascii");
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Root 1 0 R /Size ${objects.length + 1} >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(pdf, "ascii");
}

async function ensureRealCloudUploadPdfFixture(): Promise<string> {
  await fs.mkdir(path.dirname(realCloudUploadPdfPath), { recursive: true });
  await fs.writeFile(
    realCloudUploadPdfPath,
    buildMinimalPdfBuffer([
      "Real Cloud Upload Title",
      "Abstract",
      "This abstract proves the cloud page processor used actual PDF text extraction.",
      "Introduction",
      "The body snippet should mention hippocampal signal, methods context, and real extracted content.",
    ]),
  );
  return realCloudUploadPdfPath;
}

function statePathFor(slug: string): string {
  return path.join(e2eVaultPath, ".pp", slug, "state.json");
}

function runsDirFor(slug: string): string {
  return path.join(e2eVaultPath, ".pp", slug, "runs");
}

function repairStatsReportPath(): string {
  return path.resolve(
    e2eSpecDir,
    "..",
    ".e2e-backend-runtime",
    "storage",
    "artifacts",
    "paper-e2e-repair-001",
    "run_e2e_repair_001",
    "stats_report.json",
  );
}

async function ensureRepairFixtureMissingStats(): Promise<void> {
  await fs.unlink(repairStatsReportPath()).catch(() => undefined);
}

async function writeProtocolAttachmentFixture(filename: string, content: string): Promise<string> {
  const attachmentDir = path.resolve(e2eSpecDir, "..", ".e2e-backend-runtime", "attachments");
  await fs.mkdir(attachmentDir, { recursive: true });
  const attachmentPath = path.join(attachmentDir, filename);
  await fs.writeFile(attachmentPath, content, "utf-8");
  return attachmentPath;
}

async function searchPaperList(page: Page, query: string): Promise<void> {
  const search = page.getByLabel("Search papers").first();
  await search.fill(query);
}

async function gotoUntilLive(page: Page, url: string, assertReady: () => Promise<void>, attempts = 3): Promise<void> {
  let lastError: unknown = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    await page.goto(url);
    try {
      await assertReady();
      return;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error(`Failed to open live route: ${url}`);
}

async function openWorkbenchLive(
  page: Page,
  url: string,
  assertReady?: () => Promise<void>,
  attempts = 3,
): Promise<void> {
  await gotoUntilLive(
    page,
    url,
    async () => {
      await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
      if (assertReady) {
        await assertReady();
      }
    },
    attempts,
  );
}

async function openHomeLive(page: Page, assertReady?: () => Promise<void>, attempts = 3): Promise<void> {
  await gotoUntilLive(
    page,
    "/",
    async () => {
      await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
      if (assertReady) {
        await assertReady();
      }
    },
    attempts,
  );
}

function boxesOverlap(
  first: { x: number; y: number; width: number; height: number },
  second: { x: number; y: number; width: number; height: number },
): boolean {
  return !(
    first.x + first.width <= second.x ||
    second.x + second.width <= first.x ||
    first.y + first.height <= second.y ||
    second.y + second.height <= first.y
  );
}

async function expectNoUiOverlap(first: Locator, second: Locator, description: string): Promise<void> {
  await expect(first).toBeVisible();
  await expect(second).toBeVisible();

  const [firstBox, secondBox] = await Promise.all([first.boundingBox(), second.boundingBox()]);
  expect(firstBox, `${description}: first box should be measurable`).not.toBeNull();
  expect(secondBox, `${description}: second box should be measurable`).not.toBeNull();

  if (!firstBox || !secondBox) {
    return;
  }

  expect(boxesOverlap(firstBox, secondBox), description).toBe(false);
}

async function expectHeadingOrder(container: Locator, headings: string[], description: string): Promise<void> {
  const positions = await container.getByRole("heading").evaluateAll(
    (nodes, expectedHeadings) => {
      const labels = nodes.map((node) => node.textContent?.trim() ?? "");
      return (expectedHeadings as string[]).map((heading) => labels.findIndex((label) => label === heading));
    },
    headings,
  );

  for (const [index, position] of positions.entries()) {
    expect(position, `${description}: ${headings[index]} should be present`).toBeGreaterThanOrEqual(0);
  }
  for (let index = 1; index < positions.length; index += 1) {
    expect(positions[index - 1], `${description}: ${headings[index - 1]} should appear before ${headings[index]}`).toBeLessThan(
      positions[index],
    );
  }
}

async function expectImageLoaded(locator: Locator, description: string): Promise<void> {
  await expect(locator, description).toBeVisible();
  await expect
    .poll(
      async () =>
        locator.evaluate((node) => {
          const img = node as HTMLImageElement;
          return img.complete && img.naturalWidth > 0 && img.naturalHeight > 0;
        }),
      { message: description },
    )
    .toBe(true);
}

interface FocusSnapshot {
  tag: string;
  type: string;
  name: string;
  text: string;
  href: string;
  aria: string;
  placeholder: string;
  testid: string;
}

async function captureTabOrder(page: Page, steps: number): Promise<FocusSnapshot[]> {
  const snapshots: FocusSnapshot[] = [];
  await page.waitForLoadState("networkidle");
  for (let index = 0; index < steps; index += 1) {
    await page.keyboard.press("Tab");
    const snapshot = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el) {
        return null;
      }
      const labels = "labels" in el && el.labels ? Array.from(el.labels) : [];
      const labelText = labels
        .map((label) => (label.textContent ?? "").replace(/\s+/g, " ").trim())
        .join(" ")
        .trim();
      const text = (el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 100);
      const aria = el.getAttribute("aria-label") ?? "";
      const placeholder = el.getAttribute("placeholder") ?? "";
      return {
        tag: el.tagName,
        type: el.getAttribute("type") ?? "",
        name: aria || labelText || placeholder || text,
        text,
        href: el.getAttribute("href") ?? "",
        aria,
        placeholder,
        testid: el.getAttribute("data-testid") ?? "",
      };
    });
    expect(snapshot, `tab stop ${index + 1} should resolve to an active element`).not.toBeNull();
    if (snapshot) {
      snapshots.push(snapshot);
    }
  }
  return snapshots;
}

function requireFocusIndex(
  stops: FocusSnapshot[],
  predicate: (entry: FocusSnapshot) => boolean,
  description: string,
): number {
  const index = stops.findIndex(predicate);
  expect(index, description).toBeGreaterThanOrEqual(0);
  return index;
}

interface BackendPaperSummary {
  paper_id?: string;
  pdf_exists?: boolean;
}

interface BackendArtifactEntry {
  exists?: boolean;
  data?: unknown;
}

interface BackendArtifactBundle {
  files?: Record<string, BackendArtifactEntry>;
}

interface BackendJobDetail {
  bootstrap_meta_path?: string | null;
  artifact_document_written?: boolean | null;
  artifact_claimset_written?: boolean | null;
  artifact_stats_written?: boolean | null;
  claimset_readiness?: string | null;
}

interface RealSmokeCandidate {
  paperId: string;
  firstClaimIndex: number;
  secondClaimIndex: number;
}

interface RealSmokeResolvedNote {
  paperId: string;
  slug: string;
}

interface BackendUserAction {
  action_type?: string;
  source?: string;
  payload?: Record<string, unknown> | null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function resolveClaimEntries(claimsetPayload: unknown): Array<Record<string, unknown>> {
  const root = asRecord(claimsetPayload);
  if (!root) {
    return [];
  }
  if (Array.isArray(root.claims)) {
    return root.claims.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null);
  }
  const nested = asRecord(root.claimset);
  if (!nested || !Array.isArray(nested.claims)) {
    return [];
  }
  return nested.claims.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null);
}

function resolveClaimPage(rawClaim: Record<string, unknown>): number | null {
  const evidenceArray = Array.isArray(rawClaim.evidence_spans)
    ? rawClaim.evidence_spans
    : Array.isArray(rawClaim.evidence)
      ? rawClaim.evidence
      : [];
  const firstEvidence = evidenceArray.length > 0 ? asRecord(evidenceArray[0]) : null;
  if (!firstEvidence) {
    return null;
  }
  const rawPage = asFiniteNumber(firstEvidence.page) ?? asFiniteNumber(firstEvidence.page_index);
  if (rawPage === null) {
    return null;
  }
  return Math.max(0, Math.round(rawPage));
}

function pickDistinctPageClaimPair(claimsetPayload: unknown): { firstClaimIndex: number; secondClaimIndex: number } | null {
  const claims = resolveClaimEntries(claimsetPayload);
  const pageEntries = claims
    .map((claim, index) => ({ index, page: resolveClaimPage(claim) }))
    .filter((item): item is { index: number; page: number } => item.page !== null);

  if (pageEntries.length < 2) {
    return null;
  }

  const hasZeroBasedHint = pageEntries.some((item) => item.page === 0);
  const displayEntries = pageEntries.map((item) => ({
    index: item.index,
    displayPage: hasZeroBasedHint ? item.page + 1 : Math.max(item.page, 1),
  }));

  const first = displayEntries[0];
  const second = displayEntries.find((item) => item.displayPage !== first.displayPage);
  if (!second) {
    return null;
  }
  return {
    firstClaimIndex: first.index,
    secondClaimIndex: second.index,
  };
}

async function getNonFixtureSmokeCandidates(request: APIRequestContext, limit = 3): Promise<RealSmokeCandidate[]> {
  const papersResponse = await request.get(`${backendBaseUrl}/papers`);
  if (!papersResponse.ok()) {
    return [];
  }

  const payload = (await papersResponse.json()) as unknown;
  if (!Array.isArray(payload)) {
    return [];
  }

  const paperIds = payload
    .map((item) => (item && typeof item === "object" ? (item as BackendPaperSummary) : null))
    .filter((item): item is BackendPaperSummary => item !== null)
    .filter((item) => typeof item.paper_id === "string" && item.paper_id.trim().length > 0)
    .filter((item) => item.paper_id!.startsWith("paper-e2e-") === false)
    .filter((item) => item.pdf_exists === true)
    .map((item) => item.paper_id!.trim())
    .slice(0, 30);

  const selected: RealSmokeCandidate[] = [];
  for (const paperId of paperIds) {
    const artifactsResponse = await request.get(`${backendBaseUrl}/artifacts/${encodeURIComponent(paperId)}/latest`);
    if (!artifactsResponse.ok()) {
      continue;
    }
    const artifacts = (await artifactsResponse.json()) as BackendArtifactBundle;
    const claimsetPayload = artifacts.files?.claimset_resolved?.data ?? artifacts.files?.claimset?.data;
    if (!claimsetPayload) {
      continue;
    }
    const pair = pickDistinctPageClaimPair(claimsetPayload);
    if (!pair) {
      continue;
    }
    selected.push({
      paperId,
      firstClaimIndex: pair.firstClaimIndex,
      secondClaimIndex: pair.secondClaimIndex,
    });
    if (selected.length >= limit) {
      break;
    }
  }
  return selected;
}

async function resolveRealSmokeNote(request: APIRequestContext, paperId: string): Promise<RealSmokeResolvedNote | null> {
  const response = await request.get(
    `${backendBaseUrl}/paper-notes/resolve-by-paper-id?paper_id=${encodeURIComponent(paperId)}`,
  );
  if (!response.ok()) {
    return null;
  }
  const payload = asRecord(await response.json());
  const slug = typeof payload?.slug === "string" ? payload.slug.trim() : "";
  if (!slug) {
    return null;
  }
  return { paperId, slug };
}

async function waitForOptionalVisible(locator: Locator, timeout = 10_000): Promise<boolean> {
  try {
    await locator.waitFor({ state: "visible", timeout });
    return true;
  } catch {
    return false;
  }
}

async function listUserActions(request: APIRequestContext, paperId: string): Promise<BackendUserAction[]> {
  const response = await request.get(`${backendBaseUrl}/user-actions?paper_id=${encodeURIComponent(paperId)}&limit=200`);
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as unknown;
  const root = asRecord(payload);
  if (!root || !Array.isArray(root.actions)) {
    return [];
  }
  return root.actions
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item) => ({
      action_type: typeof item.action_type === "string" ? item.action_type : undefined,
      source: typeof item.source === "string" ? item.source : undefined,
      payload: asRecord(item.payload),
    }));
}

test("backend mode stays out of mock fallback", async ({ page }) => {
  await gotoUntilLive(page, "/", async () => {
    await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Continue current work", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Workspace context", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Queue lens", exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Saved outputs", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("home-saved-outputs-summary")).toContainText(
      "Open saved outputs after you finish the current paper thread, whether that means reading, review, or blocker repair.",
      { timeout: 15_000 },
    );
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });
  await searchPaperList(page, "Missing Stats");
  await expect(page.locator("tr").filter({ hasText: "E2E List Missing Stats Paper" }).first()).toBeVisible({
    timeout: 15_000,
  });

  // backend-seeded paper should be visible and navigable
  await searchPaperList(page, "Seed Paper");
  const seededPaper = page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" }).first();
  await expect(seededPaper).toBeVisible();
  await seededPaper.click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001/);
  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByTestId("workbench-review-actions")).toContainText("Review actions");
  const sessionControls = page.getByTestId("workbench-session-controls");
  await expect(sessionControls).toBeVisible();
  await sessionControls.locator("summary").click();
  await expect(sessionControls.getByLabel("Reading style")).toBeVisible();
  await expect(sessionControls.getByLabel("Context profile")).toBeVisible();
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.getByText("Obsidian sync payload preview")).toBeVisible();
  await expect(page.getByText("Claim text missing")).toHaveCount(0);
});

test("backend triage separates content review cues from operational state", async ({ page }) => {
  await gotoUntilLive(page, "/", async () => {
    await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("columnheader", { name: "Claim review" })).toBeVisible({ timeout: 15_000 });
  });

  await searchPaperList(page, "Missing Stats");
  const row = page.locator("tbody tr").filter({ hasText: "E2E List Missing Stats Paper" }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(row.getByTestId("triage-ops-badge")).toContainText("Action needed");
  await expect(row.getByTestId("triage-access-badge")).toContainText("Local PDF");
  await expect(row.getByTestId("triage-access-link")).toContainText("Open saved PDF");
  await expect(row.getByTestId("triage-primary-action")).toContainText("Repair stats");
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review clear");
  await expect(row.getByTestId("triage-review-hint")).toContainText("No claim review flags");
});

test("backend triage access links keep open and institution routes in user language", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-open-001",
          title: "Open Access Route Paper",
          updated_at: "2026-04-18T09:00:00Z",
          issues: 0,
          issues_state: "clear",
          access_summary: {
            status_label: "open",
            open_access_url: "https://example.org/papers/open-access-route-paper.pdf",
          },
        },
        {
          paper_id: "paper-inst-001",
          title: "Institution Access Route Paper",
          updated_at: "2026-04-18T09:05:00Z",
          issues: 0,
          issues_state: "clear",
          access_summary: {
            status_label: "institution_required",
            institution_access_url: "https://proxy.example.edu/login?url=https://doi.org/10.1000/example",
          },
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 0,
        structured_notes: 0,
        latest_note_updated_at: null,
        note_context_limited: false,
        note_slug_by_paper_id: {},
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page);

  const openAccessRow = page.locator("tbody tr").filter({ hasText: "Open Access Route Paper" }).first();
  await expect(openAccessRow).toBeVisible();
  await expect(openAccessRow.getByTestId("triage-access-badge")).toContainText("Open access");
  await expect(openAccessRow.getByTestId("triage-access-link")).toContainText("Open available PDF");
  await expect(openAccessRow.getByTestId("triage-access-link")).toHaveAttribute(
    "href",
    "https://example.org/papers/open-access-route-paper.pdf",
  );

  const institutionRow = page.locator("tbody tr").filter({ hasText: "Institution Access Route Paper" }).first();
  await expect(institutionRow).toBeVisible();
  await expect(institutionRow.getByTestId("triage-access-badge")).toContainText("Institution route");
  await expect(institutionRow.getByTestId("triage-access-link")).toContainText("Open institution page");
  await expect(institutionRow.getByTestId("triage-access-link")).toHaveAttribute(
    "href",
    "https://proxy.example.edu/login?url=https://doi.org/10.1000/example",
  );
});

test("backend triage summarizes repair, review, and ready buckets", async ({ page }) => {
  await page.goto("/");

  const summaryStrip = page.getByTestId("triage-summary-strip");
  await expect(summaryStrip).toBeVisible();

  const rows = page.locator("tbody tr");
  const rowCount = await rows.count();
  let repairCount = 0;
  let reviewCount = 0;
  let readyCount = 0;

  for (let index = 0; index < rowCount; index += 1) {
    const row = rows.nth(index);
    const opsBadge = row.getByTestId("triage-ops-badge");
    const opsLabel = (await opsBadge.count()) > 0 ? ((await opsBadge.textContent()) ?? "") : "";
    const reviewLabel = (await row.getByTestId("triage-review-badge").textContent()) ?? "";

    if (opsLabel.includes("Action needed")) {
      repairCount += 1;
      continue;
    }

    if (reviewLabel.includes("Clear")) {
      readyCount += 1;
      continue;
    }

    reviewCount += 1;
  }

  const repairSummary = page.getByTestId("triage-summary-repair");
  const reviewSummary = page.getByTestId("triage-summary-review");
  const readySummary = page.getByTestId("triage-summary-ready");

  await expect(repairSummary).toContainText("Needs repair");
  await expect(reviewSummary).toContainText("Needs review");
  await expect(readySummary).toContainText("Ready");
  await expect(repairSummary).toContainText(String(repairCount));
  await expect(reviewSummary).toContainText(String(reviewCount));
  await expect(readySummary).toContainText(String(readyCount));
});

test("backend workspace context keeps global counts while search filters the action list", async ({ page }) => {
  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-workspace-context-summary")).toContainText(
      "Saved notes show where to reopen reading",
    );
    await expect(page.getByTestId("home-workspace-context-detail")).toContainText("Latest saved note updated");
    await expect(page.getByTestId("home-workspace-context-detail")).toContainText(
      "Reopen a saved note to keep reading, or move into review when a paper needs evidence work.",
    );
  });

  const savedNotes = ((await page.getByTestId("home-workspace-context-saved-notes").textContent()) ?? "").trim();
  const structuredNotes = ((await page.getByTestId("home-workspace-context-structured-notes").textContent()) ?? "").trim();
  const needsReview = ((await page.getByTestId("home-workspace-context-needs-review").textContent()) ?? "").trim();
  const blocked = ((await page.getByTestId("home-workspace-context-blocked").textContent()) ?? "").trim();

  expect(savedNotes.length).toBeGreaterThan(0);
  expect(structuredNotes.length).toBeGreaterThan(0);
  expect(needsReview.length).toBeGreaterThan(0);
  expect(blocked.length).toBeGreaterThan(0);

  await expect(page.getByTestId("home-workspace-context-detail")).not.toContainText("temporarily unavailable");
  await expect(page.getByTestId("home-workspace-context-action-list-link")).toContainText("Jump to queue lens");

  await page.getByLabel("Search papers").first().fill("Missing Stats");

  await expect(page.locator("tbody tr").filter({ hasText: "E2E List Missing Stats Paper" }).first()).toBeVisible();
  await expect(page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" })).toHaveCount(0);

  await expect(page.getByTestId("home-workspace-context-saved-notes")).toHaveText(savedNotes);
  await expect(page.getByTestId("home-workspace-context-structured-notes")).toHaveText(structuredNotes);
  await expect(page.getByTestId("home-workspace-context-needs-review")).toHaveText(needsReview);
  await expect(page.getByTestId("home-workspace-context-blocked")).toHaveText(blocked);
});

test("backend home start-here strip points first-time users to manual import", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 0,
        structured_notes: 0,
        latest_note_updated_at: null,
        note_context_limited: false,
        note_slug_by_paper_id: {},
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page);

  await expect(
    page.getByText(
      "Bring a PDF into Paper Notes, land in the saved note, then open the workbench when you need grounded claims, source-backed evidence, or saved outputs.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByText("Start here", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "If you are new here, import one paper, land in its saved note, then continue in review when you need evidence work.",
      { exact: true },
    ),
  ).toBeVisible();

  const addPdfLink = page.locator("a").filter({ hasText: "Add your PDF" }).first();
  await expect(addPdfLink).toHaveAttribute("href", "/papers#import-pdf");
  await expect(addPdfLink).toContainText("Import one paper, open the saved note right away, then continue into review when you need evidence work.");

  const browseNotesLink = page.locator("a").filter({ hasText: "Browse Paper Notes" }).first();
  await expect(browseNotesLink).toHaveAttribute("href", "/papers");
  await expect(browseNotesLink).toContainText(
    "Open saved notes, keep reading, or move into review when a paper needs evidence work.",
  );

  await expect(page.getByTestId("home-workspace-context-detail")).toContainText(
    "No saved note context yet. Import one paper, land in the saved note, then continue into review.",
  );
  await expect(page.getByTestId("home-workspace-context-summary")).toContainText(
    "This home still starts from papers. Import one paper, land in the saved note, then use review load to decide what to continue next.",
  );
  await expect(page.getByTestId("home-saved-outputs-summary")).toContainText(
    "Open saved outputs after you finish the current paper thread, whether that means reading, review, or blocker repair.",
  );
});

test("backend home workspace context keeps saved-note return path clear", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-context-001",
          title: "Workspace Context Paper",
          updated_at: "2026-04-17T10:15:00Z",
          issues: 1,
          issues_label: "1 evidence gap",
          issues_state: "flagged",
          access_summary: {
            status_label: "user_imported_pdf",
            local_pdf_url: "/papers/paper-context-001/pdf",
          },
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 4,
        structured_notes: 3,
        latest_note_updated_at: "2026-04-17T10:15:00Z",
        note_context_limited: false,
        note_slug_by_paper_id: {
          "paper-context-001": "workspace-context-note",
        },
        marker_summary: {
          marked_papers: 2,
          note_backed_papers: 1,
          starred: 1,
          triage_counts: {
            revisit: 1,
            needs_verification: 1,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-workspace-context-summary")).toContainText(
      "This home stays paper-first. Saved notes show where to reopen reading, paper markers show what is already active, and review load shows what may need evidence work next.",
    );
    await expect(page.getByTestId("home-workspace-context-detail")).toContainText("Latest saved note updated");
    await expect(page.getByTestId("home-workspace-context-detail")).toContainText(
      "Reopen a saved note to keep reading, or move into review when a paper needs evidence work.",
    );
  });
  await expect(page.getByTestId("home-workspace-context-saved-notes")).toHaveText("4");
  await expect(page.getByTestId("home-workspace-context-structured-notes")).toHaveText("3");
  await expect(page.getByTestId("home-workspace-context-needs-review")).toHaveText("1");
  await expect(page.getByTestId("home-workspace-context-blocked")).toHaveText("0");
});

test("backend home workspace context keeps limited note context handoff clear", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-limited-001",
          title: "Workspace Limited Context Paper",
          updated_at: "2026-04-17T10:30:00Z",
          issues: 2,
          issues_label: "2 review checks",
          issues_state: "flagged",
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 5,
        structured_notes: 4,
        latest_note_updated_at: "2026-04-17T10:30:00Z",
        note_context_limited: true,
        note_slug_by_paper_id: {},
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-workspace-context-summary")).toContainText(
      "Saved note context is limited right now, so reopen reading from Paper Notes directly while current review load still reflects the live workspace.",
    );
    await expect(page.getByTestId("home-workspace-context-detail")).toContainText(
      "Saved note detail is limited on this machine. Browse Paper Notes directly to reopen a saved note or verify note-level detail before moving into review.",
    );
  });
  await expect(page.getByTestId("home-workspace-marker-limited")).toContainText(
    "Open Paper Notes directly to reopen a saved note or check starred and triaged papers right now.",
  );
  await expect(page.getByTestId("home-workspace-context-saved-notes")).toHaveText("Unavailable");
  await expect(page.getByTestId("home-workspace-context-structured-notes")).toHaveText("Unavailable");
  await expect(page.getByTestId("home-workspace-context-needs-review")).toHaveText("1");
  await expect(page.getByTestId("home-workspace-context-blocked")).toHaveText("0");
  await expect(page.getByTestId("home-workspace-context-action-list-link")).toContainText("Jump to queue lens");
});

test("backend home resume card keeps saved-note reading handoff clear", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-reading-001",
          title: "Resume Reading Paper",
          updated_at: "2026-04-17T09:00:00Z",
          issues: 0,
          issues_state: "clear",
          access_summary: {
            status_label: "user_imported_pdf",
            local_pdf_url: "/papers/paper-reading-001/pdf",
          },
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 1,
        structured_notes: 0,
        latest_note_updated_at: "2026-04-17T09:00:00Z",
        note_context_limited: false,
        note_slug_by_paper_id: {
          "paper-reading-001": "resume-reading-note",
        },
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-resume-card")).toBeVisible();
  });

  const resumeCard = page.getByTestId("home-resume-card");
  await expect(resumeCard).toBeVisible();
  await expect(resumeCard.getByTestId("home-resume-title")).toContainText("Resume Reading Paper");
  await expect(resumeCard.getByTestId("home-resume-next-action")).toContainText("Next: Reopen the saved note and keep reading.");
  await expect(resumeCard.getByTestId("home-resume-hint")).toContainText(
    "Land in the saved note first, then move into review when you need deeper evidence validation.",
  );
  await expect(resumeCard.getByTestId("home-resume-cta")).toContainText("Resume reading");
  await expect(resumeCard).toContainText("Local PDF");
  await expect(resumeCard.getByRole("link", { name: "Open saved PDF" })).toHaveAttribute("href", "/api/papers/paper-reading-001/pdf");
});

test("backend home resume card keeps saved-note review handoff clear", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-review-001",
          title: "Resume Review Paper",
          updated_at: "2026-04-17T09:30:00Z",
          issues: 2,
          issues_label: "2 mapping ambiguities",
          issues_state: "flagged",
          access_summary: {
            status_label: "user_imported_pdf",
            local_pdf_url: "/papers/paper-review-001/pdf",
          },
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 1,
        structured_notes: 1,
        latest_note_updated_at: "2026-04-17T09:30:00Z",
        note_context_limited: false,
        note_slug_by_paper_id: {
          "paper-review-001": "resume-review-note",
        },
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-resume-card")).toBeVisible();
  });

  const resumeCard = page.getByTestId("home-resume-card");
  await expect(resumeCard).toBeVisible();
  await expect(resumeCard.getByTestId("home-resume-title")).toContainText("Resume Review Paper");
  await expect(resumeCard.getByTestId("home-resume-next-action")).toContainText(
    "Next: Continue review from the saved note thread.",
  );
  await expect(resumeCard.getByTestId("home-resume-hint")).toContainText("2 mapping ambiguities");
  await expect(resumeCard.getByTestId("home-resume-cta")).toContainText("Resume review");
  await expect(resumeCard).toContainText("Local PDF");
  await expect(resumeCard.getByRole("link", { name: "Open saved PDF" })).toHaveAttribute("href", "/api/papers/paper-review-001/pdf");
});

test("backend home resume card keeps saved-note blocker handoff clear", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-blocked-001",
          title: "Resume Blocked Paper",
          issues: 0,
          issues_state: "clear",
          access_summary: {
            status_label: "user_imported_pdf",
            local_pdf_url: "/papers/paper-blocked-001/pdf",
          },
          ops_summary: {
            state: "action_needed",
            label: "Action needed",
            reason: "Saved note checks are missing or empty.",
            recommended_action: "repair_stats",
            has_claimset: true,
            has_stats_report: false,
            stats_check_count: 0,
          },
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 1,
        structured_notes: 1,
        latest_note_updated_at: "2026-04-17T09:45:00Z",
        note_context_limited: false,
        note_slug_by_paper_id: {
          "paper-blocked-001": "resume-blocked-note",
        },
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-resume-card")).toBeVisible();
  });

  const resumeCard = page.getByTestId("home-resume-card");
  await expect(resumeCard).toBeVisible();
  await expect(resumeCard.getByTestId("home-resume-title")).toContainText("Resume Blocked Paper");
  await expect(resumeCard.getByTestId("home-resume-next-action")).toContainText(
    "Next: Repair saved note checks before review.",
  );
  await expect(resumeCard.getByTestId("home-resume-hint")).toContainText(
    "Saved note checks are missing or empty. Open the workbench to refresh the saved note checks.",
  );
  await expect(resumeCard).toContainText("Continue from the latest saved note or review thread.");
  await expect(resumeCard.getByTestId("home-resume-cta")).toContainText("Fix blocker");
  await expect(resumeCard).toContainText("Local PDF");
  await expect(resumeCard.getByRole("link", { name: "Open saved PDF" })).toHaveAttribute("href", "/api/papers/paper-blocked-001/pdf");
});

test("backend home resume card keeps institution access links in user language", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-institution-001",
          title: "Resume Institution Access Paper",
          updated_at: "2026-04-18T10:00:00Z",
          issues: 1,
          issues_label: "1 evidence gap",
          issues_state: "flagged",
          access_summary: {
            status_label: "institution_required",
            institution_access_url: "https://proxy.example.edu/login?url=https://doi.org/10.1000/institution-paper",
          },
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 0,
        structured_notes: 0,
        latest_note_updated_at: null,
        note_context_limited: false,
        note_slug_by_paper_id: {},
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-resume-card")).toBeVisible();
  });

  const resumeCard = page.getByTestId("home-resume-card");
  await expect(resumeCard).toBeVisible();
  await expect(resumeCard.getByTestId("home-resume-title")).toContainText("Resume Institution Access Paper");
  await expect(resumeCard.getByTestId("home-resume-next-action")).toContainText(
    "Next: Review flagged claims and evidence.",
  );
  await expect(resumeCard.getByTestId("home-resume-hint")).toContainText("1 evidence gap");
  await expect(resumeCard.getByTestId("home-resume-cta")).toContainText("Resume review");
  await expect(resumeCard).toContainText("Institution route");
  await expect(resumeCard.getByRole("link", { name: "Open institution page" })).toHaveAttribute(
    "href",
    "https://proxy.example.edu/login?url=https://doi.org/10.1000/institution-paper",
  );
});

test("backend home resume card keeps open-access links in user language", async ({ page }) => {
  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          paper_id: "paper-open-access-001",
          title: "Resume Open Access Paper",
          updated_at: "2026-04-18T10:10:00Z",
          issues: 1,
          issues_label: "1 evidence gap",
          issues_state: "flagged",
          access_summary: {
            status_label: "open",
            open_access_url: "https://example.org/papers/resume-open-access-paper.pdf",
          },
        },
      ]),
    });
  });
  await page.route("**/paper-notes/home-context*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        saved_notes: 0,
        structured_notes: 0,
        latest_note_updated_at: null,
        note_context_limited: false,
        note_slug_by_paper_id: {},
        marker_summary: {
          marked_papers: 0,
          note_backed_papers: 0,
          starred: 0,
          triage_counts: {
            revisit: 0,
            needs_verification: 0,
            experiment_relevant: 0,
          },
        },
      }),
    });
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-resume-card")).toBeVisible();
  });

  const resumeCard = page.getByTestId("home-resume-card");
  await expect(resumeCard).toBeVisible();
  await expect(resumeCard.getByTestId("home-resume-title")).toContainText("Resume Open Access Paper");
  await expect(resumeCard.getByTestId("home-resume-next-action")).toContainText(
    "Next: Review flagged claims and evidence.",
  );
  await expect(resumeCard.getByTestId("home-resume-hint")).toContainText("1 evidence gap");
  await expect(resumeCard.getByTestId("home-resume-cta")).toContainText("Resume review");
  await expect(resumeCard).toContainText("Open access");
  await expect(resumeCard.getByRole("link", { name: "Open available PDF" })).toHaveAttribute(
    "href",
    "https://example.org/papers/resume-open-access-paper.pdf",
  );
});

test("backend home derives workspace context without requesting workspace-summary", async ({ page }) => {
  let workspaceSummaryRequestCount = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/workspace-summary")) {
      workspaceSummaryRequestCount += 1;
    }
  });

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-workspace-context-detail")).toContainText("Latest saved note updated");
  });
  await page.waitForTimeout(250);

  expect(workspaceSummaryRequestCount).toBe(0);
});

test("backend home workspace context surfaces paper-level marker aggregation", async ({ page, request }) => {
  const homeContextResponse = await request.get(`${backendBaseUrl}/paper-notes/home-context`);
  expect(homeContextResponse.ok()).toBeTruthy();
  const homeContextPayload = asRecord(await homeContextResponse.json());
  const markerSummary = asRecord(homeContextPayload?.marker_summary);
  expect(markerSummary).not.toBeNull();

  const markedPapers = asFiniteNumber(markerSummary?.marked_papers) ?? 0;
  const noteBackedPapers = asFiniteNumber(markerSummary?.note_backed_papers) ?? 0;
  const starred = asFiniteNumber(markerSummary?.starred) ?? 0;
  const triageCounts = asRecord(markerSummary?.triage_counts);
  const revisit = asFiniteNumber(triageCounts?.revisit) ?? 0;
  const needsVerification = asFiniteNumber(triageCounts?.needs_verification) ?? 0;
  const experimentRelevant = asFiniteNumber(triageCounts?.experiment_relevant) ?? 0;

  await openHomeLive(page, async () => {
    await expect(page.getByTestId("home-workspace-marker-summary")).toContainText("Paper markers");
  });

  const markerSummaryCard = page.getByTestId("home-workspace-marker-summary");
  await expect(markerSummaryCard).toContainText("Paper markers");

  if (markedPapers <= 0) {
    await expect(markerSummaryCard.getByTestId("home-workspace-marker-detail")).toContainText(
      "No paper-level markers yet.",
    );
  } else {
    const markedPhrase = markedPapers === 1 ? "paper already carries" : "papers already carry";
    const notePhrase =
      noteBackedPapers <= 0
        ? "No private paper note saved yet."
        : noteBackedPapers === 1
          ? "1 includes a private note."
          : `${noteBackedPapers} include a private note.`;
    await expect(markerSummaryCard.getByTestId("home-workspace-marker-detail")).toContainText(
      `${markedPapers} ${markedPhrase} paper-level judgment. ${notePhrase}`,
    );
  }

  await expect(markerSummaryCard.getByTestId("home-workspace-marker-starred")).toContainText(String(starred));
  await expect(markerSummaryCard.getByTestId("home-workspace-marker-starred")).toHaveAttribute("href", "/papers?starred=1");
  await expect(markerSummaryCard.getByTestId("home-workspace-marker-revisit")).toContainText(String(revisit));
  await expect(markerSummaryCard.getByTestId("home-workspace-marker-needs-verification")).toContainText(
    String(needsVerification),
  );
  await expect(markerSummaryCard.getByTestId("home-workspace-marker-experiment-relevant")).toContainText(
    String(experimentRelevant),
  );
});

test("backend method comparison viewer loads a generated comparison and keeps export on the real csv route", async ({
  page,
  request,
}) => {
  const comparisonId = "methodcmp_backend_e2e_multi_fixture";
  const response = await request.post(`${backendBaseUrl}/method-comparisons/generate`, {
    data: {
      comparison_id: comparisonId,
      title: "E2E Multi-paper Method Comparison",
      paper_ids: [methodComparisonBetaPaperId, methodComparisonAlphaPaperId],
      field_ids: ["intervention", "duration_or_timepoint", "sample_size"],
    },
  });

  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as {
    comparison?: {
      comparison_id?: string;
      title?: string;
      rows?: Array<{
        paper_id?: string;
        title?: string;
        cells?: Array<{ field_id?: string; value?: string | number | null; status?: string }>;
      }>;
    };
  };
  expect(payload.comparison?.comparison_id).toBe(comparisonId);
  expect(payload.comparison?.rows?.map((row) => row.paper_id)).toEqual([
    methodComparisonBetaPaperId,
    methodComparisonAlphaPaperId,
  ]);
  expect(payload.comparison?.rows?.[0]?.title).toBe("E2E Method Comparison Beta");
  expect(payload.comparison?.rows?.[1]?.title).toBe("E2E Method Comparison Alpha");
  expect(payload.comparison?.rows?.[0]?.cells?.map((cell) => cell.field_id)).toEqual([
    "intervention",
    "duration_or_timepoint",
    "sample_size",
  ]);
  const comparisonJsonPath = path.join(e2eMethodComparisonsRoot, comparisonId, "comparison.json");
  await expect
    .poll(async () => {
      try {
        await fs.access(comparisonJsonPath);
        return true;
      } catch {
        return false;
      }
    })
    .toBe(true);

  const exportResponse = await request.get(`${backendBaseUrl}/method-comparisons/${comparisonId}/export.csv`);
  expect(exportResponse.ok()).toBeTruthy();
  expect(exportResponse.headers()["content-disposition"]).toContain(`attachment; filename="${comparisonId}.csv"`);
  const exportText = await exportResponse.text();
  expect(exportText).toContain(
    "paper_id,paper_slug,citekey,title,intervention,intervention__status,intervention__refs,duration_or_timepoint,duration_or_timepoint__status,duration_or_timepoint__refs,sample_size,sample_size__status,sample_size__refs",
  );
  const exportLines = exportText.trim().split("\n");
  expect(exportLines[1]).toContain(methodComparisonBetaPaperId);
  expect(exportLines[1]).toContain("MCT oil");
  expect(exportLines[1]).toContain("week 24");
  expect(exportLines[2]).toContain(methodComparisonAlphaPaperId);
  expect(exportLines[2]).toContain("Ketone ester");
  expect(exportLines[2]).toContain("12 weeks");

  await page.goto(`/method-comparisons/${comparisonId}`);
  await page.waitForLoadState("networkidle");

  await expect(page.getByRole("heading", { name: "E2E Multi-paper Method Comparison" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByTestId("method-comparison-header-context")).toContainText("Derived artifact");
  await expect(page.getByRole("heading", { name: "Review priority" })).toBeVisible();
  const reviewPriorityCard = page.getByTestId("method-comparison-review-priority-card");
  const reviewPriority = page.getByTestId("method-comparison-review-priority");
  await expect(reviewPriority).toContainText(
    "No warnings or unresolved cells are saved in this snapshot.",
  );
  await expect(reviewPriorityCard).toContainText("Warnings 0");
  await expect(reviewPriorityCard).toContainText("Conflict 0");
  await expect(reviewPriorityCard).toContainText("Missing 0");
  await expect(page.getByRole("heading", { name: "Comparison Grid" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source Discipline" })).toBeVisible();
  const comparisonTable = page.locator("table").first();
  await expect(comparisonTable.getByText("E2E Method Comparison Beta", { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText("E2E Method Comparison Alpha", { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText("MCT oil", { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText("Ketone ester", { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText("week 24", { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText("12 weeks", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    new RegExp(`/method-comparisons/${comparisonId}/export\\.csv$`),
  );
  await expect(page.getByRole("link", { name: "Open note" })).toHaveCount(2);
});

test("backend method comparison index can create a new comparison from the browser", async ({ page }) => {
  await gotoUntilLive(page, "/method-comparisons", async () => {
    await expect(page.getByRole("heading", { name: "Method Comparisons" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Create comparison" })).toBeVisible();
  });

  await page.getByLabel("Method comparison paper ids").fill(
    `${methodComparisonAlphaPaperId}\n${methodComparisonBetaPaperId}`,
  );
  await page.getByLabel("Method comparison title").fill("Browser generated method comparison");
  await Promise.all([
    page.waitForURL(/\/method-comparisons\/methodcmp_/, { timeout: 15_000 }),
    page.getByRole("button", { name: "Create comparison" }).click(),
  ]);

  await expect(page).toHaveURL(/\/method-comparisons\/methodcmp_/);
  await expect(page.getByRole("heading", { name: "Browser generated method comparison", exact: true })).toBeVisible();
  await expect(page.getByTestId("method-comparison-header-context")).toContainText("Derived artifact");
  await expect(page.getByTestId("method-comparison-header-context")).toContainText("When to use");
  await expect(page.getByTestId("method-comparison-header-context")).toContainText("Derived from");
  await expect(page.getByRole("heading", { name: "Review priority" })).toBeVisible();
  await expect(page.getByTestId("method-comparison-review-priority")).toContainText(
    "No warnings or unresolved cells are saved in this snapshot.",
  );
  const comparisonTable = page.locator("table").first();
  await expect(comparisonTable.getByText("E2E Method Comparison Alpha", { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText("E2E Method Comparison Beta", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    /\/method-comparisons\/methodcmp_[^/]+\/export\.csv$/,
  );
});

test("backend method comparison index keeps search-miss guidance distinct from an empty lane", async ({ page }) => {
  const comparisonTitle = "Search-miss browser method comparison";

  await gotoUntilLive(page, "/method-comparisons", async () => {
    await expect(page.getByRole("heading", { name: "Method Comparisons" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Create comparison" })).toBeVisible();
  });

  await page.getByLabel("Method comparison paper ids").fill(
    `${methodComparisonAlphaPaperId}\n${methodComparisonBetaPaperId}`,
  );
  await page.getByLabel("Method comparison title").fill(comparisonTitle);
  await Promise.all([
    page.waitForURL(/\/method-comparisons\/methodcmp_/, { timeout: 15_000 }),
    page.getByRole("button", { name: "Create comparison" }).click(),
  ]);

  await expect(page.getByRole("heading", { name: comparisonTitle, exact: true })).toBeVisible();

  await gotoUntilLive(page, "/method-comparisons", async () => {
    await expect(page.getByRole("heading", { name: "Method Comparisons" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  await expect(page.getByText(comparisonTitle, { exact: true })).toBeVisible();

  const searchInput = page.getByPlaceholder("Search title or comparison id");
  await searchInput.fill("no comparison should match this query");

  await expect(page.getByText("No comparisons match the current search.", { exact: true })).toBeVisible();
  await expect(page.getByText(comparisonTitle, { exact: true })).toHaveCount(0);
  await expect(page.getByText(/^\d+ saved derived comparison/)).toBeVisible();
  await expect(page.getByText("No saved derived comparisons yet. Save one to compare papers and evidence here.")).toHaveCount(0);

  await searchInput.fill(comparisonTitle);
  await expect(page.getByText(comparisonTitle, { exact: true })).toBeVisible();
});

test("backend chart pack viewer loads a generated chart pack and keeps exports on real routes", async ({
  page,
  request,
}) => {
  const chartPackId = "chartpack_backend_e2e_fixture";
  const response = await request.post(`${backendBaseUrl}/chart-packs/generate`, {
    data: {
      chart_pack_id: chartPackId,
      title: "E2E Status Chart Pack",
      charts: [
        {
          title: "Verification status counts",
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
  const payload = (await response.json()) as {
    chart_pack?: {
      chart_pack_id?: string;
      title?: string;
      charts?: Array<{
        chart_id?: string;
        title?: string;
        template_id?: string;
      }>;
    };
    quality_gate?: {
      overall_status?: "pass" | "warn" | "fail";
      bundle_ready?: boolean;
      handoff_ready?: boolean;
      reason_codes?: string[];
    };
    data_snapshots?: Record<string, string>;
    specs?: Record<string, { mark?: string; encoding?: Record<string, unknown> }>;
  };
  expect(payload.chart_pack?.chart_pack_id).toBe(chartPackId);
  expect(payload.chart_pack?.title).toBe("E2E Status Chart Pack");
  expect(payload.chart_pack?.charts?.map((chart) => chart.chart_id)).toEqual([
    "chart_01_stats-check-status-counts",
  ]);
  expect(payload.data_snapshots?.["chart_01_stats-check-status-counts"]).toContain("status,value");
  expect(payload.specs?.["chart_01_stats-check-status-counts"]?.mark).toBe("bar");
  expect(payload.quality_gate?.overall_status).toBe("pass");
  expect(payload.quality_gate?.bundle_ready).toBe(true);
  expect(payload.quality_gate?.handoff_ready).toBe(true);

  const chartPackJsonPath = path.join(e2eChartPacksRoot, chartPackId, "chart_pack.json");
  await expect
    .poll(async () => {
      try {
        await fs.access(chartPackJsonPath);
        return true;
      } catch {
        return false;
      }
    })
    .toBe(true);

  const csvExportResponse = await request.get(
    `${backendBaseUrl}/chart-packs/${chartPackId}/charts/chart_01_stats-check-status-counts/data.csv`,
  );
  expect(csvExportResponse.ok()).toBeTruthy();
  expect(csvExportResponse.headers()["content-disposition"]).toContain(
    'attachment; filename="chartpack_backend_e2e_fixture_chart_01_stats-check-status-counts.csv"',
  );
  const csvExportText = await csvExportResponse.text();
  expect(csvExportText).toContain("status,value");
  expect(csvExportText).toContain("verified,2");

  const specExportResponse = await request.get(
    `${backendBaseUrl}/chart-packs/${chartPackId}/charts/chart_01_stats-check-status-counts/spec.json`,
  );
  expect(specExportResponse.ok()).toBeTruthy();
  expect(specExportResponse.headers()["content-disposition"]).toContain(
    'attachment; filename="chartpack_backend_e2e_fixture_chart_01_stats-check-status-counts.json"',
  );
  const specExportPayload = (await specExportResponse.json()) as {
    mark?: string;
    encoding?: Record<string, unknown>;
  };
  expect(specExportPayload.mark).toBe("bar");
  expect(specExportPayload.encoding).toEqual({ x: "status", y: "value" });

  await page.goto(`/chart-packs/${chartPackId}`);

  await expect(page.getByRole("heading", { name: "E2E Status Chart Pack" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("Derived artifact");
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("When to use");
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("Derived from");
  await expect(page.getByRole("heading", { name: "Charts" })).toBeVisible();
  const reviewPriorityHeading = page.getByRole("heading", { name: "Review priority" });
  const reviewPriorityCard = page.getByTestId("chart-pack-review-priority-card");
  const qualityGateHeading = page.getByRole("heading", { name: "Quality gate" });
  const qualityGateCard = page.getByTestId("chart-pack-quality-gate-card");
  const snapshotHeading = page.getByRole("heading", { name: "Snapshot" });
  await expect(reviewPriorityHeading).toBeVisible();
  await expect(qualityGateHeading).toBeVisible();
  await expect(reviewPriorityCard).toContainText("No pack-level warnings or caution notes are saved.");
  await expect(reviewPriorityCard).toContainText(
    "A quick source-item review is still the safest final check before exporting CSV/spec bundles or reusing charts downstream.",
  );
  await expect(reviewPriorityCard).toContainText("Warnings 0");
  await expect(reviewPriorityCard).toContainText("Caution notes 0");
  await expect(reviewPriorityCard).toContainText("Warning charts 0");
  await expect(qualityGateCard).toContainText("Saved bundle checks passed for this chart pack.");
  await expect(qualityGateCard).toContainText("Status pass");
  await expect(qualityGateCard).toContainText("Bundle ready yes");
  await expect(qualityGateCard).toContainText("Handoff ready yes");
  await expect(page.getByRole("heading", { name: "Render Env" })).toBeVisible();
  const chartCard = page.locator("article").filter({ hasText: "Verification status counts" }).first();
  await expect(chartCard).toBeVisible();
  await expect(chartCard.getByText("stats_report / paper-e2e-001 / run_e2e_fixture_001")).toBeVisible();
  await expect(chartCard.getByText("bar · x=status · y=value · 1 row")).toBeVisible();
  await expect(chartCard.getByText("verified")).toBeVisible();
  await expect(chartCard.getByRole("cell", { name: "2" })).toBeVisible();
  await expect(page.getByText("No pack-level warnings saved.")).toBeVisible();
  await expect(page.getByText("No caution notes saved for this chart pack.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Export CSV" }).first()).toHaveAttribute(
    "href",
    new RegExp(`/chart-packs/${chartPackId}/charts/chart_01_stats-check-status-counts/data\\.csv$`),
  );
  await expect(page.getByRole("link", { name: "Open spec JSON" }).first()).toHaveAttribute(
    "href",
    new RegExp(`/chart-packs/${chartPackId}/charts/chart_01_stats-check-status-counts/spec\\.json$`),
  );
  await expect(page.getByRole("link", { name: "Open SVG" }).first()).toHaveAttribute(
    "href",
    new RegExp(`/chart-packs/${chartPackId}/charts/chart_01_stats-check-status-counts/render\\.svg$`),
  );
  await expect(page.getByText("Saved SVG render")).toBeVisible();
  await expect(
    page.getByText(
      "This preview comes from the saved bundle render. Keep warnings, transforms, and source lineage above it as the stronger review context.",
    ),
  ).toBeVisible();
  await expect(page.getByTestId("chart-render-preview-chart_01_stats-check-status-counts")).toHaveAttribute(
    "src",
    new RegExp(`/chart-packs/${chartPackId}/charts/chart_01_stats-check-status-counts/render\\.svg$`),
  );
  await expectImageLoaded(
    page.getByTestId("chart-render-preview-chart_01_stats-check-status-counts"),
    "chart pack live preview should load the saved SVG render",
  );

  const reviewPriorityBox = await reviewPriorityHeading.boundingBox();
  const qualityGateBox = await qualityGateHeading.boundingBox();
  const snapshotBox = await snapshotHeading.boundingBox();
  expect(reviewPriorityBox).not.toBeNull();
  expect(qualityGateBox).not.toBeNull();
  expect(snapshotBox).not.toBeNull();
  expect(reviewPriorityBox!.y).toBeLessThan(qualityGateBox!.y);
  expect(qualityGateBox!.y).toBeLessThan(snapshotBox!.y);
});

test("backend chart pack index can create a new chart pack from the browser", async ({ page }) => {
  await page.goto("/chart-packs");

  await expect(page.getByRole("heading", { name: "Chart Packs", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await page.getByLabel("Chart pack paper id").fill("paper-e2e-001");
  await page.getByLabel("Chart pack run id").fill("run_e2e_fixture_001");
  await page.getByLabel("Chart pack title").fill("Browser generated chart pack");
  await page.getByLabel("Chart title").fill("Browser generated status chart");
  await page.getByRole("button", { name: "Create chart pack" }).click();

  await expect(page).toHaveURL(/\/chart-packs\/chartpack_/);
  await expect(page.getByRole("heading", { name: "Browser generated chart pack", exact: true })).toBeVisible();
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("Derived artifact");
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("When to use");
  await expect(page.getByTestId("chart-pack-header-context")).toContainText("Derived from");
  await expect(page.getByTestId("chart-pack-review-priority-card")).toContainText(
    "No pack-level warnings or caution notes are saved.",
  );
  await expect(page.getByTestId("chart-pack-quality-gate-card")).toContainText(
    "Saved bundle checks passed for this chart pack.",
  );
  await expect(page.locator("article").filter({ hasText: "Browser generated status chart" }).first()).toBeVisible();
  await expect(page.getByText("stats_report / paper-e2e-001 / run_e2e_fixture_001")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open review", exact: true })).toHaveAttribute("href", "/workbench/paper-e2e-001");
  await expect(page.getByRole("link", { name: "Export CSV" }).first()).toHaveAttribute(
    "href",
    /\/chart-packs\/chartpack_[^/]+\/charts\/chart_01_stats-check-status-counts\/data\.csv$/,
  );

  await page.getByRole("link", { name: "Open review", exact: true }).click();
  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001$/);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
});

test("backend chart pack quick-pick journey stays connected in the browser", async ({ page }) => {
  await gotoUntilLive(page, "/chart-packs", async () => {
    await expect(page.getByRole("heading", { name: "Chart Packs", exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByText("Recent saved runs", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /E2E Note-backed BBox Fixture run_e2e_note_backed_bbox_001/i }).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  const recentRunButton = page.getByRole("button", { name: /E2E Note-backed BBox Fixture run_e2e_note_backed_bbox_001/i }).first();
  await recentRunButton.click();

  await expect(page.getByLabel("Chart pack paper id")).toHaveValue("paper-e2e-note-backed-bbox-001");
  await expect(page.getByLabel("Chart pack run id")).toHaveValue("run_e2e_note_backed_bbox_001");

  await page.getByLabel("Chart pack title").fill("Quick-pick journey chart pack");
  await page.getByLabel("Chart title").fill("Quick-pick journey chart");
  await page.getByRole("button", { name: "Create chart pack" }).click();

  await expect(page).toHaveURL(/\/chart-packs\/chartpack_/);
  await expect(page.getByRole("heading", { name: "Quick-pick journey chart pack", exact: true })).toBeVisible();
  await expect(page.getByText("stats_report / paper-e2e-note-backed-bbox-001 / run_e2e_note_backed_bbox_001")).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
});

test("backend chart pack index explains missing saved runs in user language", async ({ page }) => {
  await page.goto("/chart-packs");

  await expect(page.getByRole("heading", { name: "Chart Packs", exact: true })).toBeVisible();

  await page.getByLabel("Chart pack paper id").fill("paper-missing-001");
  await page.getByLabel("Chart pack run id").fill("run-missing-001");
  await page.getByRole("button", { name: "Create chart pack" }).click();

  await expect(
    page.getByText(
      "We couldn't find a saved stats report for paper-missing-001 / run-missing-001. Open that paper in the workbench, run or refresh checks, then try this latest run again.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/chart-packs$/);
});

test("backend meeting pack create keeps the continuation card and note handoff on the real route", async ({ page }) => {
  await page.goto("/meeting-packs");

  await expect(page.getByRole("banner").getByRole("heading", { name: "Saved meeting packs", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await page.getByLabel("Meeting pack paper slug").fill(noteSlug);
  await page.getByLabel("Meeting pack draft title").fill("Browser generated meeting draft");
  await page.getByLabel("Meeting pack draft mode").selectOption("journal_club");
  await page.getByLabel("Meeting pack max slides").selectOption("7");
  await page.getByRole("button", { name: "Create draft" }).click();

  await page.waitForURL(/\/meeting-packs\/meetingpack_/, { timeout: 15_000 });
  await expect(
    page.getByRole("banner").getByRole("heading", { name: canonicalDuboisNoteSlug, exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("Derived artifact");
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("When to use");
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText("Derived from");
  const meetingPackRail = page.locator("main > div").nth(1);
  await expect(meetingPackRail.getByRole("heading").nth(0)).toHaveText("Review state");
  await expect(meetingPackRail.getByRole("heading").nth(1)).toHaveText("Continue from this draft");
  await expect(meetingPackRail.getByRole("heading").nth(2)).toHaveText("Validation");
  await expect(page.getByRole("heading", { name: "Continue from this draft" })).toBeVisible();
  await expect(page.getByText("Continue in note").first()).toBeVisible();
  await expect(page.getByTestId("meeting-pack-recommended-order")).toContainText("Recommended order");
  const draftMaintenance = page.getByTestId("meeting-pack-draft-maintenance");
  await expect(draftMaintenance).toContainText("Draft maintenance");
  await expect(page.getByRole("button", { name: "Regenerate draft" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Rerender markdown" })).toHaveCount(0);
  const continueInNoteLink = page.getByRole("link", { name: "Continue in note" }).first();
  await expect(continueInNoteLink).toContainText(canonicalDuboisNoteSlug);
  await expect(continueInNoteLink).toHaveAttribute(
    "href",
    new RegExp(
      `/papers/(?:${encodeURIComponent(canonicalDuboisNoteSlug)}|${encodeURIComponent(noteSlug)})$`,
    ),
  );
  await draftMaintenance.locator("summary").click();
  await expect(page.getByRole("button", { name: "Regenerate draft" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rerender markdown" })).toBeVisible();
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    page.getByRole("button", { name: "Regenerate draft" }),
    "global Home should stay clear of the meeting pack regenerate action",
  );
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    page.getByRole("button", { name: "Rerender markdown" }),
    "global Home should stay clear of the meeting pack rerender action",
  );
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    page.getByRole("link", { name: "Continue in note" }).first(),
    "global Home should stay clear of the meeting pack note handoff",
  );

  await page.getByRole("button", { name: "Rerender markdown" }).click();
  await expect(page.getByText("Saved markdown rerendered from the current meeting pack JSON.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Continue from this draft" })).toBeVisible();
  await expect(page.getByText("Continue in note").first()).toBeVisible();

  await page.getByRole("button", { name: "Regenerate draft" }).click();
  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(page.getByText("Draft regenerated from the saved selector set.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Continue from this draft" })).toBeVisible();
  await expect(page.getByText("Continue in note").first()).toBeVisible();

  await continueInNoteLink.click();

  await expect(
    page,
  ).toHaveURL(new RegExp(`/papers/(?:${encodeURIComponent(canonicalDuboisNoteSlug)}|${encodeURIComponent(noteSlug)})$`));
  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: /Alzheimer Disease as a Clinical-Biological Construct/i,
    }),
  ).toBeVisible();
  const openReviewLink = page.getByRole("link", { name: "Open review" }).first();
  await expect(openReviewLink).toHaveAttribute(
    "href",
    `/workbench/${encodeURIComponent("zotero:duboisAlzheimerDiseaseClinicalBiological2024")}`,
  );
  await openReviewLink.click();
  await expect(page).toHaveURL(
    `/workbench/${encodeURIComponent("zotero:duboisAlzheimerDiseaseClinicalBiological2024")}`,
  );
  await expect(page.getByTestId("workbench-access-badge")).toContainText("Local PDF");
  await expect(page.getByTestId("workbench-access-link")).toContainText("Open saved PDF");
  await expect(page.getByRole("link", { name: "Continue in note" }).first()).toHaveAttribute("href", /\/papers\/.+$/);
  await expect(page.getByText("Placeholder PDF active")).toHaveCount(0);
  await expect(page.getByTestId("pdf-viewer")).toBeVisible();
});

test("backend chart pack viewer keeps warning-heavy scatter packs honest on the real route", async ({
  page,
  request,
}) => {
  const chartPackId = "chartpack_backend_warning_fixture";
  const warningPaperId = "paper-e2e-chart-warning-001";
  const warningRunId = "run_e2e_chart_warning_001";
  const warningArtifactDir = path.resolve(
    e2eSpecDir,
    "..",
    "..",
    "storage",
    "artifacts",
    warningPaperId,
    warningRunId,
  );

  await fs.mkdir(warningArtifactDir, { recursive: true });
  await fs.writeFile(
    path.join(warningArtifactDir, "stats_report.json"),
    JSON.stringify(
      {
        doc_id: "doc-warning-001",
        run_id: warningRunId,
        checks: [
          {
            check_id: "warn-1",
            test_type: "anova",
            reported_p: "< 0.01",
            computed_p: 0.009,
            code: "print('ok')",
            outputs: "ok",
            verdict: "verified",
          },
        ],
      },
      null,
      2,
    ),
    "utf-8",
  );

  const response = await request.post(`${backendBaseUrl}/chart-packs/generate`, {
    data: {
      chart_pack_id: chartPackId,
      title: "E2E Warning Scatter Pack",
      charts: [
        {
          title: "Approximate p scatter",
          template_id: "reported_vs_computed_p_scatter",
          source_ref: {
            source_kind: "stats_report",
            paper_id: warningPaperId,
            run_id: warningRunId,
          },
          field_mappings: [
            { target_field: "reported_p", source_field: "reported_p" },
            { target_field: "computed_p", source_field: "computed_p" },
          ],
        },
      ],
    },
  });

  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as {
    chart_pack?: {
      chart_pack_id?: string;
      warnings?: Array<{ code?: string }>;
      caution_notes?: string[];
      charts?: Array<{ warnings?: Array<{ code?: string }> }>;
    };
    quality_gate?: {
      overall_status?: "pass" | "warn" | "fail";
      bundle_ready?: boolean;
      handoff_ready?: boolean;
      reason_codes?: string[];
    };
    data_snapshots?: Record<string, string>;
  };
  expect(payload.chart_pack?.chart_pack_id).toBe(chartPackId);
  expect(payload.chart_pack?.warnings?.map((warning) => warning.code)).toEqual([
    "stats_p_pairs_skipped",
    "no_chartable_pairs",
    "empty_snapshot",
  ]);
  expect(payload.chart_pack?.charts?.[0]?.warnings?.map((warning) => warning.code)).toEqual([
    "stats_p_pairs_skipped",
    "no_chartable_pairs",
    "empty_snapshot",
  ]);
  expect(payload.chart_pack?.caution_notes).toEqual([
    "Some charts include warning states; inspect source lineage before reuse.",
    "Reported/computed p charts include only exact numeric pairs and skip approximate values.",
  ]);
  expect(payload.data_snapshots?.["chart_01_reported-vs-computed-p-scatter"]).toBe("reported_p,computed_p\n");
  expect(payload.quality_gate?.overall_status).toBe("warn");
  expect(payload.quality_gate?.bundle_ready).toBe(true);
  expect(payload.quality_gate?.handoff_ready).toBe(false);
  expect(payload.quality_gate?.reason_codes).toEqual(["CHART_WARNING_PRESENT"]);

  await page.goto(`/chart-packs/${chartPackId}`);

  await expect(page.getByRole("heading", { name: "E2E Warning Scatter Pack" })).toBeVisible();
  const reviewPriorityHeading = page.getByRole("heading", { name: "Review priority" });
  const reviewPriorityCard = page.getByTestId("chart-pack-review-priority-card");
  const qualityGateHeading = page.getByRole("heading", { name: "Quality gate" });
  const qualityGateCard = page.getByTestId("chart-pack-quality-gate-card");
  const cautionNotesHeading = page.getByRole("heading", { name: "Caution Notes" });
  const snapshotHeading = page.getByRole("heading", { name: "Snapshot" });
  await expect(reviewPriorityHeading).toBeVisible();
  await expect(qualityGateHeading).toBeVisible();
  await expect(reviewPriorityCard).toContainText("Review warning-marked charts before export or downstream reuse.");
  await expect(reviewPriorityCard).toContainText(
    "Read the caution notes, then inspect warning-marked chart cards and source-item review links before treating this pack as reusable.",
  );
  await expect(reviewPriorityCard).toContainText("Warnings 3");
  await expect(reviewPriorityCard).toContainText("Caution notes 2");
  await expect(reviewPriorityCard).toContainText("Warning charts 1");
  await expect(qualityGateCard).toContainText("This chart pack still needs review before downstream reuse.");
  await expect(qualityGateCard).toContainText("Status warn");
  await expect(qualityGateCard).toContainText("Bundle ready yes");
  await expect(qualityGateCard).toContainText("Handoff ready no");
  await expect(qualityGateCard).toContainText("CHART_WARNING_PRESENT");
  const chartCard = page.locator("article").filter({ hasText: "Approximate p scatter" }).first();
  await expect(chartCard).toBeVisible();
  await expect(chartCard.getByText("3 warning")).toBeVisible();
  await expect(chartCard.getByText("stats_report / paper-e2e-chart-warning-001 / run_e2e_chart_warning_001")).toBeVisible();
  await expect(chartCard.getByText("point · x=reported_p · y=computed_p · 0 rows")).toBeVisible();
  await expect(chartCard.getByText("stats_p_pairs_skipped")).toBeVisible();
  await expect(chartCard.getByText("no_chartable_pairs")).toBeVisible();
  await expect(chartCard.getByText("empty_snapshot")).toBeVisible();
  await expect(chartCard.getByRole("link", { name: "Open SVG" })).toHaveAttribute(
    "href",
    new RegExp(`/chart-packs/${chartPackId}/charts/chart_01_reported-vs-computed-p-scatter/render\\.svg$`),
  );
  await expect(chartCard.getByTestId("chart-render-preview-chart_01_reported-vs-computed-p-scatter")).toHaveAttribute(
    "src",
    new RegExp(`/chart-packs/${chartPackId}/charts/chart_01_reported-vs-computed-p-scatter/render\\.svg$`),
  );
  await expectImageLoaded(
    chartCard.getByTestId("chart-render-preview-chart_01_reported-vs-computed-p-scatter"),
    "warning-heavy scatter preview should still load the saved SVG render",
  );
  await expect(
    page.getByText("Some charts include warning states; inspect source lineage before reuse.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Reported/computed p charts include only exact numeric pairs and skip approximate values.", {
      exact: true,
    }),
  ).toBeVisible();
  const snapshotTable = chartCard.getByRole("table");
  await expect(snapshotTable.getByRole("columnheader", { name: "reported_p" })).toBeVisible();
  await expect(snapshotTable.getByRole("columnheader", { name: "computed_p" })).toBeVisible();

  const reviewPriorityBox = await reviewPriorityHeading.boundingBox();
  const qualityGateBox = await qualityGateHeading.boundingBox();
  const cautionNotesBox = await cautionNotesHeading.boundingBox();
  const snapshotBox = await snapshotHeading.boundingBox();
  expect(reviewPriorityBox).not.toBeNull();
  expect(qualityGateBox).not.toBeNull();
  expect(cautionNotesBox).not.toBeNull();
  expect(snapshotBox).not.toBeNull();
  expect(reviewPriorityBox!.y).toBeLessThan(qualityGateBox!.y);
  expect(qualityGateBox!.y).toBeLessThan(cautionNotesBox!.y);
  expect(cautionNotesBox!.y).toBeLessThan(snapshotBox!.y);
});

test("backend paper notes index can import a local PDF from the browser", async ({ page }) => {
  await page.goto("/papers");

  await expect(page.getByRole("heading", { name: "Paper Notes", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Home" })).toHaveCount(0);
  await expect(page.getByText("Add your own PDF", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Import PDF" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Check automatic pickup setup" })).toBeVisible();
  await page.locator('[data-testid="paper-notes-import-input"]').setInputFiles(samplePdfPath);
  await expect(page).toHaveURL(/\/papers\/sample(?:-[a-f0-9]{8})?$/, { timeout: 15_000 });
  const importGuidance = page.getByTestId("paper-note-import-guidance");
  await expect(importGuidance).toContainText("This note is already saved in Lattice.");
  await expect(importGuidance).toContainText("This note came from a local PDF on this machine.");
  await expect(importGuidance.getByTestId("paper-note-import-guidance-paper-id")).toContainText(/userpdf-[a-f0-9]+/);
  await expect(importGuidance.getByTestId("paper-note-import-guidance-copy-paper-id")).toHaveText("Copy ID");
  await expect(importGuidance.getByTestId("paper-note-import-guidance-open-review")).toHaveAttribute(
    "href",
    /\/workbench\/userpdf-[a-f0-9]+$/,
  );
  await expect(importGuidance.getByTestId("paper-note-import-guidance-queue-deepread")).toHaveText("Queue deep read");
  await importGuidance.getByTestId("paper-note-import-guidance-queue-deepread").click();
  await expect(importGuidance.getByTestId("paper-note-import-guidance-deepread-message")).toContainText(
    "Deep read queued",
    { timeout: 15_000 },
  );
  await expect(importGuidance.getByTestId("paper-note-import-guidance-deepread-message")).toContainText(
    "Open review to watch progress.",
    { timeout: 15_000 },
  );
  const queuedStatus = importGuidance.getByTestId("paper-note-import-guidance-deepread-status");
  await expect(queuedStatus).toContainText("Status Queued");
  await expect(queuedStatus).toContainText("Stage queued");
  await expect(queuedStatus).toContainText("Progress 0%");
  await expect(importGuidance.getByTestId("paper-note-import-guidance-deepread-status-guidance")).toContainText(
    "Queued on the local worker",
  );
  await expect(queuedStatus).toContainText(/Run run[-_]/);
  await expect(queuedStatus).toContainText(/Job [0-9a-f-]{36}/);
  await expect(importGuidance.getByTestId("paper-note-import-guidance-open-pdf")).toHaveAttribute(
    "href",
    /\/api\/papers\/userpdf-[a-f0-9]+\/pdf$/,
  );
  await expect(page.getByText("Imported from a local PDF on this machine.", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open PDF" })).toHaveAttribute("href", /\/api\/papers\/userpdf-[a-f0-9]+\/pdf$/);
  await expect(page.getByText("Mock mode")).toHaveCount(0);
});

test("backend cloud PDF upload opens a cloud paper page with extracted title abstract and body text", async ({ page }) => {
  const pdfPath = await ensureRealCloudUploadPdfFixture();
  await page.goto("/papers");

  await expect(page.getByRole("heading", { name: "Paper Notes", exact: true })).toBeVisible();
  await expect(page.getByTestId("cloud-paper-upload-button")).toBeVisible();
  await page.getByTestId("cloud-paper-upload-input").setInputFiles(pdfPath);

  await expect(page).toHaveURL(/\/papers\/paper_mock_[^/?]+\?source=cloud$/, { timeout: 15_000 });
  await expect(page.getByTestId("cloud-paper-detail-viewer")).toBeVisible({ timeout: 15_000 });
  const cloudPage = page.getByTestId("cloud-paper-page-blocks");
  await expect(cloudPage).toContainText("Real Cloud Upload Title", { timeout: 15_000 });
  await expect(cloudPage).toContainText("This abstract proves the cloud page processor used actual PDF text extraction.");
  await expect(cloudPage).toContainText("hippocampal signal");
  await expect(cloudPage).not.toContainText("Mock processed page text");
});

test("backend protocol knowledge inspector loads a saved protocol card and keeps note handoff on the real route", async ({
  page,
  request,
}) => {
  const protocolId = "protocol_backend_e2e_fixture";
  const currentVersionId = "protver_backend_e2e_fixture_v2";
  const draftVersionId = "protver_backend_e2e_fixture_v1";
  const response = await request.post(`${backendBaseUrl}/protocol-cards`, {
    data: {
      protocol_id: protocolId,
      title: "E2E cortical ketone assay protocol",
      purpose: "Review note-backed assay steps before downstream reuse.",
      context: "Read-first protocol bundle for backend inspector coverage.",
      source_kind: "paper_derived",
      linked_paper_ids: [noteBackedWorkbenchPaperId],
      linked_note_slugs: [noteSlug],
      current_version_id: currentVersionId,
      validation_status: "reviewed",
      versions: [
        {
          version_id: draftVersionId,
          version_number: 1,
          key_steps_summary: ["Prepare cortical neurons", "Apply ketone ester pulse"],
          materials: ["Ketone ester", "Neurobasal medium"],
          equipment: ["CO2 incubator"],
          critical_conditions: ["37 C", "5% CO2"],
          readouts: ["Beta-hydroxybutyrate"],
          cautions: ["Initial draft requires operator review."],
          content_snapshot: "Step 1: prepare cortical neurons.\nStep 2: apply ketone ester pulse.",
          change_reason: "Initial extraction from note-backed assay wording.",
          status: "draft",
          created_by: "operator",
          created_at: "2026-03-23T01:00:00+00:00",
          source_refs: [
            {
              paper_slug: noteSlug,
              claim_id: "claim-e2e-protocol-001",
              run_id: "run-e2e-protocol-001",
              locator: {
                page: 4,
                section: "Methods",
                chunk_id: "meth-01",
              },
            },
          ],
          note: "Draft snapshot before reviewer cleanup.",
        },
        {
          version_id: currentVersionId,
          version_number: 2,
          key_steps_summary: ["Prepare cortical neurons", "Apply ketone ester pulse", "Collect BHB readout"],
          materials: ["Ketone ester", "Neurobasal medium", "PBS"],
          equipment: ["CO2 incubator", "Plate reader"],
          critical_conditions: ["37 C", "5% CO2", "15 minute pulse"],
          readouts: ["Beta-hydroxybutyrate", "Cell viability"],
          cautions: ["Do not reuse as execution-ready SOP without source note check."],
          content_snapshot:
            "Step 1: prepare cortical neurons.\nStep 2: apply ketone ester pulse.\nStep 3: collect BHB readout.",
          change_reason: "Aligned current version with note-backed assay wording.",
          status: "active",
          created_by: "reviewer",
          created_at: "2026-03-23T02:00:00+00:00",
          source_refs: [
            {
              paper_slug: noteSlug,
              claim_id: "claim-e2e-protocol-002",
              run_id: "run-e2e-protocol-002",
              locator: {
                page: 5,
                section: "Methods",
                chunk_id: "meth-02",
              },
            },
          ],
          note: "Current reviewer-aligned snapshot for downstream reference.",
        },
      ],
    },
  });

  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as {
    protocol_card?: {
      protocol_id?: string;
      title?: string;
      current_version_id?: string;
      validation_status?: string;
    };
    versions?: Array<{ version_id?: string; status?: string; source_refs?: Array<{ paper_slug?: string }> }>;
    markdown?: string;
  };
  expect(payload.protocol_card?.protocol_id).toBe(protocolId);
  expect(payload.protocol_card?.title).toBe("E2E cortical ketone assay protocol");
  expect(payload.protocol_card?.current_version_id).toBe(currentVersionId);
  expect(payload.protocol_card?.validation_status).toBe("reviewed");
  expect(payload.versions?.map((item) => item.version_id)).toEqual([draftVersionId, currentVersionId]);
  expect(payload.versions?.[1]?.status).toBe("active");
  expect(payload.versions?.[1]?.source_refs?.[0]?.paper_slug).toBe(noteSlug);
  expect(payload.markdown).toContain("# E2E cortical ketone assay protocol");

  const indexResponse = await request.get(`${backendBaseUrl}/protocol-cards`);
  expect(indexResponse.ok()).toBeTruthy();
  const indexPayload = (await indexResponse.json()) as {
    total?: number;
    items?: Array<{ protocol_id?: string; title?: string; current_version_id?: string; version_count?: number }>;
  };
  expect(indexPayload.total).toBeGreaterThanOrEqual(1);
  expect(indexPayload.items?.find((item) => item.protocol_id === protocolId)).toMatchObject({
    protocol_id: protocolId,
    title: "E2E cortical ketone assay protocol",
    current_version_id: currentVersionId,
    version_count: 2,
  });

  const versionsResponse = await request.get(`${backendBaseUrl}/protocol-cards/${protocolId}/versions`);
  expect(versionsResponse.ok()).toBeTruthy();
  const versionsPayload = (await versionsResponse.json()) as {
    total?: number;
    items?: Array<{ version_id?: string }>;
  };
  expect(versionsPayload.total).toBe(2);
  expect(versionsPayload.items?.map((item) => item.version_id)).toEqual([draftVersionId, currentVersionId]);

  const versionItemResponse = await request.get(`${backendBaseUrl}/protocol-cards/${protocolId}/versions/${draftVersionId}`);
  expect(versionItemResponse.ok()).toBeTruthy();
  const versionItemPayload = (await versionItemResponse.json()) as {
    version_id?: string;
    change_reason?: string;
    status?: string;
  };
  expect(versionItemPayload.version_id).toBe(draftVersionId);
  expect(versionItemPayload.change_reason).toBe("Initial extraction from note-backed assay wording.");
  expect(versionItemPayload.status).toBe("draft");

  const protocolCardJsonPath = path.join(e2eProtocolCardsRoot, protocolId, "protocol_card.json");
  await expect
    .poll(async () => {
      try {
        await fs.access(protocolCardJsonPath);
        return true;
      } catch {
        return false;
      }
    })
    .toBe(true);

  await page.goto("/protocol-cards");

  await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or protocol id"]').fill("cortical ketone");
  const targetCard = page.locator("article").filter({ hasText: "E2E cortical ketone assay protocol" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("Reviewed", { exact: true })).toBeVisible();
  await expect(targetCard.getByText(currentVersionId)).toBeVisible();
  await targetCard.getByRole("button", { name: "Open protocol card" }).click();

  await expect(page).toHaveURL(new RegExp(`/protocol-cards/${protocolId}$`));
  await expect(page.getByRole("heading", { name: "E2E cortical ketone assay protocol", exact: true })).toBeVisible();
  await expect(page.getByTestId("protocol-card-header-context")).toContainText("Derived artifact");
  await expect(page.getByTestId("protocol-card-header-context")).toContainText("When to use");
  await expect(page.getByTestId("protocol-card-header-context")).toContainText("Derived from");
  await expect(page.getByRole("heading", { name: "Version review" })).toBeVisible();
  await expect(page.getByTestId("protocol-card-review-state-card")).toContainText("Review state");
  await expect(page.getByTestId("protocol-card-review-state-card")).toContainText("Protocol cards are reusable review artifacts");
  await expect(page.getByRole("heading", { name: "Version history" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source refs" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Trust boundary" })).toBeVisible();
  await expect(page.getByText("Selected as current version")).toBeVisible();
  await expect(page.getByText("Aligned current version with note-backed assay wording.", { exact: true })).toBeVisible();
  await expect(
    page.locator("li").filter({ hasText: "Do not reuse as execution-ready SOP without source note check." }).first(),
  ).toBeVisible();
  await expect(page.getByText("Claim claim-e2e-protocol-002")).toBeVisible();
  await expect(page.getByText("p.5 · Methods · meth-02")).toBeVisible();

  const draftVersionButton = page.getByRole("button").filter({ hasText: draftVersionId }).first();
  await expect(draftVersionButton).toBeVisible();
  await draftVersionButton.click();

  await expect(page.getByText("Historical version selected")).toBeVisible();
  await expect(page.getByText("Initial extraction from note-backed assay wording.", { exact: true })).toBeVisible();
  await expect(
    page.locator("li").filter({ hasText: "Initial draft requires operator review." }).first(),
  ).toBeVisible();
  await expect(page.getByText("Claim claim-e2e-protocol-001")).toBeVisible();
  await expect(page.getByText("p.4 · Methods · meth-01")).toBeVisible();

  await page.getByRole("link", { name: "Open note" }).click();

  await expect(page).toHaveURL(new RegExp(`/papers/${noteSlug}$`));
  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: /Alzheimer Disease as a Clinical-Biological Construct/i,
    }),
  ).toBeVisible();
});

test("backend protocol knowledge index can create a new protocol card from the browser", async ({ page }) => {
  await page.goto("/protocol-cards");

  await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await page.getByLabel("Protocol card title").fill("Browser created protocol card");
  await page.getByLabel("Protocol card purpose").fill("Keep one browser-started protocol snapshot for downstream review.");
  await page.getByLabel("Protocol card linked note slug").fill(noteSlug);
  await page.getByLabel("Protocol card linked paper id").fill(noteBackedWorkbenchPaperId);
  await page.getByLabel("Protocol card source kind").selectOption("paper_derived");
  await page.getByLabel("Protocol card current version status").selectOption("active");
  await page.getByLabel("Protocol card version snapshot").fill(
    "Step 1: prepare cortical neurons.\nStep 2: apply ketone ester pulse.\nStep 3: collect BHB readout.",
  );
  await page.getByLabel("Protocol card key steps").fill(
    "Prepare cortical neurons\nApply ketone ester pulse\nCollect BHB readout",
  );
  await page.getByRole("button", { name: "Create protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByRole("heading", { name: "Browser created protocol card", exact: true })).toBeVisible();
  await expect(page.getByTestId("protocol-card-header-context")).toContainText("Derived artifact");
  await expect(page.getByText("Selected as current version")).toBeVisible();
  await expect(
    page.getByText("Initial protocol snapshot created from the browser review surface.", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("li").filter({ hasText: "Prepare cortical neurons" }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Open note" })).toHaveAttribute(
    "href",
    new RegExp(`/papers/${noteSlug}$`),
  );
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    page.getByRole("link", { name: "Open note" }),
    "global Home should stay clear of the protocol card note handoff",
  );
});

test("backend protocol knowledge index can seed a standalone draft from an uploaded attachment", async ({ page }) => {
  const attachmentPath = await writeProtocolAttachmentFixture(
    "standalone-protocol.txt",
    ["- Warm media", "- Incubate for 15 minutes", "- Measure viability"].join("\n"),
  );

  await gotoUntilLive(page, "/protocol-cards", async () => {
    await expect(page.getByTestId("protocol-card-attachment-help")).toContainText(
      "Upload a file, image, or document to seed this protocol draft from external material.",
      { timeout: 15_000 },
    );
  });
  await page.getByTestId("protocol-card-attachment-input").setInputFiles(attachmentPath);

  await expect(page.getByTestId("protocol-card-attachment-notice")).toContainText("Attachment draft loaded");
  await expect(page.getByTestId("protocol-card-attachment-notice")).toContainText("standalone-protocol.txt");
  await expect(page.getByTestId("protocol-card-attachment-metadata")).toContainText("raw_source");
  await expect(page.getByTestId("protocol-card-attachment-metadata")).toContainText("succeeded");
  await expect(page.getByTestId("protocol-card-attachment-preview")).toContainText("Warm media");
  await expect(page.getByTestId("protocol-card-attachment-open-bundle")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_/,
  );
  await expect(page.getByTestId("protocol-card-attachment-open-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source$/,
  );
  await expect(page.getByTestId("protocol-card-attachment-open-source")).toHaveAttribute("data-priority", "primary");
  await expect(page.getByTestId("protocol-card-attachment-download-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source\?download=1$/,
  );
  await expect(page.getByTestId("protocol-card-attachment-download-source")).toHaveAttribute(
    "data-priority",
    "secondary",
  );
  await expect(page.getByTestId("protocol-card-attachment-open-markdown")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/extracted-markdown$/,
  );
  await expect(page.getByLabel("Protocol card source kind")).toHaveValue("internal_adaptation");
  await expect(page.getByLabel("Protocol card title")).toHaveValue("standalone-protocol protocol draft");
  await expect(page.getByLabel("Protocol card linked note slug")).toHaveValue("");
  await expect(page.getByLabel("Protocol card linked paper id")).toHaveValue("");
  await expect(page.getByLabel("Protocol card version snapshot")).toContainText("Warm media");
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Ready to save");

  await page.getByRole("button", { name: "Create protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByRole("heading", { name: "standalone-protocol protocol draft", exact: true })).toBeVisible();
  await expect(page.getByText("Selected as current version")).toBeVisible();
  await expect(page.getByTestId("protocol-card-detail-attachments")).toContainText("Attachment provenance");
  await expect(page.getByTestId("protocol-card-detail-attachment-item")).toContainText("standalone-protocol.txt");
  await expect(page.getByTestId("protocol-card-detail-attachment-metadata")).toContainText("raw_source");
  await expect(page.getByTestId("protocol-card-detail-attachment-preview")).toContainText("Warm media");
  await expect(page.getByTestId("protocol-card-detail-attachment-open-bundle")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-open-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source$/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-open-source")).toHaveAttribute(
    "data-priority",
    "primary",
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-download-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source\?download=1$/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-download-source")).toHaveAttribute(
    "data-priority",
    "secondary",
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-open-markdown")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/extracted-markdown$/,
  );
});

test("backend protocol knowledge detail keeps extraction-failed attachment warnings visible after save", async ({ page }) => {
  await page.goto("/protocol-cards");

  await page.getByTestId("protocol-card-attachment-input").setInputFiles({
    name: "opaque-protocol.bin",
    mimeType: "application/octet-stream",
    buffer: Buffer.from([0xff, 0x00, 0x13, 0x37, 0x7f, 0x41, 0x42, 0x43]),
  });

  await expect(page.getByTestId("protocol-card-attachment-notice")).toContainText("Attachment draft loaded");
  await expect(page.getByTestId("protocol-card-attachment-notice")).toContainText(
    "Automatic text extraction was unavailable",
  );
  await expect(page.getByTestId("protocol-card-attachment-metadata")).toContainText("failed");
  await expect(page.getByTestId("protocol-card-attachment-preview")).toHaveCount(0);
  await expect(page.getByTestId("protocol-card-attachment-open-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source$/,
  );
  await expect(page.getByTestId("protocol-card-attachment-open-source")).toHaveAttribute("data-priority", "secondary");
  await expect(page.getByTestId("protocol-card-attachment-download-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source\?download=1$/,
  );
  await expect(page.getByTestId("protocol-card-attachment-download-source")).toHaveAttribute(
    "data-priority",
    "primary",
  );
  await expect(page.getByTestId("protocol-card-attachment-open-markdown")).toHaveCount(0);
  await expect(page.getByLabel("Protocol card title")).toHaveValue("opaque-protocol protocol draft");
  await expect(page.getByLabel("Protocol card version snapshot")).toContainText("Uploaded attachment bundle");

  await page.getByRole("button", { name: "Create protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByTestId("protocol-card-detail-attachments")).toContainText("Attachment provenance");
  await expect(page.getByTestId("protocol-card-detail-attachment-item")).toContainText("opaque-protocol.bin");
  await expect(page.getByTestId("protocol-card-detail-attachment-metadata")).toContainText("failed");
  await expect(page.getByTestId("protocol-card-detail-attachment-warnings")).toContainText(
    "ATTACHMENT_EXTRACTION_UNAVAILABLE",
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-warnings")).toContainText(
    "Review the uploaded raw source directly before reuse.",
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-open-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source$/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-open-source")).toHaveAttribute(
    "data-priority",
    "secondary",
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-download-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source\?download=1$/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-download-source")).toHaveAttribute(
    "data-priority",
    "primary",
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-preview")).toHaveCount(0);
  await expect(page.getByTestId("protocol-card-detail-attachment-open-markdown")).toHaveCount(0);
});

test("backend paper note detail can start a protocol card with note context from the browser", async ({ page }) => {
  await gotoUntilLive(page, `/papers/${noteSlug}`, async () => {
    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible({ timeout: 15_000 });
  });

  const protocolStartLink = page.getByRole("link", { name: "Save protocol card" }).first();
  await expect(protocolStartLink).toBeVisible();
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    protocolStartLink,
    "global Home should stay clear of the paper detail protocol card handoff",
  );
  await protocolStartLink.click();

  await expect(page).toHaveURL(/\/protocol-cards\?/);
  await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible();
  await expect(page.getByLabel("Protocol card linked note slug")).toHaveValue(noteSlug);
  await expect(page.getByLabel("Protocol card linked paper id")).not.toHaveValue("");
  await expect(page.getByTestId("protocol-card-create-context")).toContainText("Current note context");
  await expect(page.getByTestId("protocol-card-create-context")).toContainText(noteSlug);
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
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Still needed before save");
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Protocol title");
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Current version snapshot");

  await page.getByLabel("Protocol card title").fill("Paper-detail started protocol card");
  await page.getByLabel("Protocol card version snapshot").fill(
    "Step 1: prepare cortical neurons.\nStep 2: apply ketone ester pulse.\nStep 3: collect BHB readout.",
  );
  await page.getByLabel("Protocol card key steps").fill(
    "Prepare cortical neurons\nApply ketone ester pulse\nCollect BHB readout",
  );
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Ready to save");
  await page.getByRole("button", { name: "Create protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByRole("heading", { name: "Paper-detail started protocol card", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open note" })).toHaveAttribute(
    "href",
    new RegExp(`/papers/${noteSlug}$`),
  );
});

test("backend paper note detail can attach a protocol file and hand off a mixed draft", async ({ page }) => {
  const attachmentPath = await writeProtocolAttachmentFixture(
    "note-augmented-protocol.txt",
    ["- Warm media", "- Measure viability", "- Capture BHB readout"].join("\n"),
  );

  await page.goto(`/papers/${noteSlug}`);

  await expect(page.getByTestId("paper-note-protocol-attachment-hint")).toContainText(
    "Attach protocol text, images, or documents",
  );
  await page.getByTestId("paper-note-protocol-attachment-input").setInputFiles(attachmentPath);

  await expect(page).toHaveURL(/\/protocol-cards\?/);
  await expect(page.getByTestId("protocol-card-attachment-notice")).toContainText("Attachment merged with note context");
  await expect(page.getByTestId("protocol-card-attachment-notice")).toContainText("note-augmented-protocol.txt");
  await expect(page.getByTestId("protocol-card-attachment-preview")).toContainText("Warm media");
  await expect(page.getByTestId("protocol-card-attachment-open-bundle")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_/,
  );
  await expect(page.getByTestId("protocol-card-attachment-open-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source$/,
  );
  await expect(page.getByTestId("protocol-card-attachment-open-source")).toHaveAttribute("data-priority", "primary");
  await expect(page.getByTestId("protocol-card-attachment-download-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source\?download=1$/,
  );
  await expect(page.getByTestId("protocol-card-attachment-download-source")).toHaveAttribute(
    "data-priority",
    "secondary",
  );
  await expect(page.getByTestId("protocol-card-attachment-open-markdown")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/extracted-markdown$/,
  );
  await expect(page.getByLabel("Protocol card source kind")).toHaveValue("mixed");
  await expect(page.getByTestId("protocol-card-create-context")).toContainText("Current note context");
  await expect(page.getByLabel("Protocol card linked note slug")).toHaveValue(noteSlug);
  await expect(page.getByLabel("Protocol card linked paper id")).not.toHaveValue("");
  await expect(page.getByLabel("Protocol card version snapshot")).toContainText(
    "## Attached Material: note-augmented-protocol.txt",
  );
  await expect(page.getByTestId("protocol-card-create-readiness")).toContainText("Ready to save");
  await page.getByRole("button", { name: "Create protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByTestId("protocol-card-detail-attachments")).toContainText("Attachment provenance");
  await expect(page.getByTestId("protocol-card-detail-attachment-item")).toContainText("note-augmented-protocol.txt");
  await expect(page.getByTestId("protocol-card-detail-attachment-preview")).toContainText("Warm media");
  await expect(page.getByTestId("protocol-card-detail-attachment-open-bundle")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-open-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source$/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-open-source")).toHaveAttribute(
    "data-priority",
    "primary",
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-download-source")).toHaveAttribute(
    "href",
    /\/protocol-cards\/attachments\/protatt_[^/]+\/source\?download=1$/,
  );
  await expect(page.getByTestId("protocol-card-detail-attachment-download-source")).toHaveAttribute(
    "data-priority",
    "secondary",
  );
  await expect(page.getByRole("link", { name: "Open note" })).toHaveAttribute(
    "href",
    new RegExp(`/papers/${noteSlug}$`),
  );
});

test("backend keyboard focus keeps primary actions ahead of static content on core routes", async ({
  page,
  request,
}) => {
  test.slow();
  await page.goto("/papers");
  const paperStops = await captureTabOrder(page, 10);
  expect(paperStops[0]).toMatchObject({ tag: "BUTTON", text: "Import PDF", testid: "paper-notes-import-button" });
  expect(paperStops[1]).toMatchObject({ tag: "A", text: "Check automatic pickup setup" });
  expect(paperStops[1]?.href).toContain("/ready");
  expect(paperStops[2]).toMatchObject({ tag: "INPUT", name: "Search papers", placeholder: "Title, alias, or slug" });
  expect(paperStops[3]).toMatchObject({ tag: "INPUT", name: "Search tags" });
  const statusIndex = requireFocusIndex(paperStops, (entry) => entry.tag === "SELECT" && entry.name === "Status", "status filter should be focusable near the top controls");
  const sortIndex = requireFocusIndex(paperStops, (entry) => entry.tag === "SELECT" && entry.name === "Sort", "sort control should be focusable near the top controls");
  const sortOrderIndex = requireFocusIndex(paperStops, (entry) => entry.tag === "BUTTON" && entry.name === "Toggle sort order", "sort direction toggle should stay in the early control cluster");
  const pageSizeIndex = requireFocusIndex(paperStops, (entry) => entry.tag === "SELECT" && entry.name === "Page size", "page size control should stay in the early control cluster");
  const starredIndex = requireFocusIndex(paperStops, (entry) => entry.tag === "BUTTON" && entry.testid === "paper-notes-starred-toggle", "starred toggle should stay ahead of static result content");
  expect(statusIndex).toBeGreaterThan(3);
  expect(sortIndex).toBeGreaterThan(statusIndex);
  expect(sortOrderIndex).toBeGreaterThan(sortIndex);
  expect(pageSizeIndex).toBeGreaterThan(sortOrderIndex);
  expect(starredIndex).toBeGreaterThan(pageSizeIndex);
  expect(paperStops.slice(0, 10).some((entry) => entry.testid === "paper-notes-tag-option")).toBe(false);

  await page.goto(`/papers/${noteSlug}`);
  const noteStops = await captureTabOrder(page, 6);
  expect(noteStops).toEqual([
    expect.objectContaining({ tag: "A", text: "Home" }),
    expect.objectContaining({ tag: "A", text: "Back to list" }),
    expect.objectContaining({ tag: "A", text: "Runtime checks" }),
    expect.objectContaining({ tag: "A", text: "Save protocol card" }),
    expect.objectContaining({ tag: "BUTTON", text: "Attach protocol file" }),
    expect.objectContaining({ tag: "A", text: "Open review" }),
  ]);
  expect(noteStops[1]?.href).toContain("/papers");
  expect(noteStops[2]?.href).toContain("/ready");
  expect(noteStops[5]?.href).toContain("/workbench/");

  await page.goto(`/workbench/${encodeURIComponent(`zotero:duboisAlzheimerDiseaseClinicalBiological2024`)}`);
  const workbenchStops = await captureTabOrder(page, 20);
  expect(workbenchStops[0]).toMatchObject({ tag: "A", text: "Home" });
  expect(workbenchStops.slice(0, 5)).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ tag: "A", text: "Open saved PDF" }),
      expect.objectContaining({ tag: "A", text: "Continue in note" }),
      expect.objectContaining({ tag: "A", text: "Runtime checks" }),
    ]),
  );
  const runtimeChecksStop = workbenchStops.find((entry) => entry.text === "Runtime checks");
  expect(runtimeChecksStop?.href).toContain("/ready");
  const openPdfStop = workbenchStops.find((entry) => entry.text === "Open saved PDF");
  expect(openPdfStop?.href).toContain("/papers/");
  const noteHandoffStop = workbenchStops.find((entry) => entry.text === "Continue in note");
  expect(noteHandoffStop?.href).toContain("/papers/");
  const verifyChecksStop = workbenchStops.find((entry) => entry.name === "Verify checks");
  const freshRetrievalStop = workbenchStops.find((entry) => entry.name === "Fresh retrieval");
  const sessionControlsStop = workbenchStops.find((entry) => entry.text === "Session controls");
  const searchPapersStop = workbenchStops.find((entry) => entry.name === "Search papers");
  const jumpDocumentStop = workbenchStops.find((entry) => entry.name === "Jump to document panel");
  const jumpArtifactStop = workbenchStops.find((entry) => entry.name === "Jump to artifact panel");
  const jumpTimelineStop = workbenchStops.find((entry) => entry.name === "Jump to timeline");
  expect(workbenchStops.map((entry) => entry.text)).toContain("Run deep read");
  expect(workbenchStops.map((entry) => entry.text)).toContain("Refresh");
  expect(sessionControlsStop).toMatchObject({ tag: "SUMMARY", text: "Session controls" });
  expect(verifyChecksStop).toBeUndefined();
  expect(freshRetrievalStop).toBeUndefined();
  expect(searchPapersStop).toMatchObject({ tag: "INPUT", name: "Search papers" });
  expect(jumpDocumentStop).toMatchObject({ tag: "BUTTON", name: "Jump to document panel" });
  expect(jumpArtifactStop).toMatchObject({ tag: "BUTTON", name: "Jump to artifact panel" });
  expect(jumpTimelineStop).toMatchObject({ tag: "BUTTON", name: "Jump to timeline" });
  const sessionControls = page.getByTestId("workbench-session-controls");
  await sessionControls.locator("summary").click();
  await expect(sessionControls.getByLabel("Verify checks")).toBeVisible();
  await expect(sessionControls.getByLabel("Fresh retrieval")).toBeVisible();
  await expect(sessionControls.getByLabel("Theme")).toBeVisible();
  await expect(sessionControls.getByLabel("Panel density")).toBeVisible();
  await expect(sessionControls.getByLabel("Evidence highlight")).toBeVisible();
  await page.getByRole("button", { name: "Jump to artifact panel" }).click();
  await expect(page.locator("#workbench-artifact-panel")).toBeFocused();
  const artifactPanelStops = await captureTabOrder(page, 6);
  expect(artifactPanelStops.some((entry) => entry.tag === "PRE")).toBe(false);
  expect(artifactPanelStops.map((entry) => entry.text)).toContain("Sync to Obsidian");
  await page.getByRole("button", { name: "Jump to timeline" }).click();
  await expect(page.locator("#workbench-timeline-panel")).toBeFocused();

  const imageEvidenceId = "imageev_backend_focus_fixture";
  const response = await request.post(`${backendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "Keyboard focus image evidence fixture",
      paper_id: noteBackedWorkbenchPaperId,
      paper_slug: noteSlug,
      source_ref: {
        source_kind: "local_file",
        local_path: imageEvidenceFixtureRawPath,
        source_label: "Microscope Alpha",
      },
      content_format: "image/tiff",
      metadata: {
        width_px: 512,
        height_px: 512,
        channel_count: 2,
        modality: "fluorescence",
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
      },
      linked_artifact_refs: [
        {
          artifact_kind: "meeting_pack",
          artifact_id: "meeting-focus-fixture-001",
          note: "Linked for downstream review.",
        },
      ],
      handoff_targets: [
        {
          target: "napari",
          openable_ref: imageEvidenceFixtureRawPath,
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
          message: "Representative image only.",
        },
      ],
    },
  });
  expect(response.ok()).toBeTruthy();

  await page.goto(`/image-evidence/${imageEvidenceId}`);
  const imageStops = await captureTabOrder(page, 10);
  expect(imageStops.map((entry) => entry.tag)).not.toContain("PRE");
  expect(imageStops.some((entry) => entry.href.includes(`/papers/${noteSlug}`))).toBeTruthy();
  expect(imageStops.some((entry) => entry.href.includes("/meeting-packs"))).toBeTruthy();
});

test("backend paper note to workbench to protocol create journey stays connected in the browser", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  await gotoUntilLive(page, `/papers/${noteSlug}`, async () => {
    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible({ timeout: 15_000 });
  });

  await expect(page.getByRole("link", { name: "Runtime checks" })).toBeVisible();

  const workbenchLink = page.getByRole("link", { name: "Open review" }).first();
  await expect(workbenchLink).toBeVisible();
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    workbenchLink,
    "global Home should stay clear of the paper detail workbench handoff",
  );
  await workbenchLink.click();

  await expect(page).toHaveURL(/\/workbench\/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024$/);
  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Runtime checks" })).toBeVisible();
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    page.getByRole("button", { name: "Run deep read" }),
    "global Home should stay clear of the workbench primary run action",
  );
  await page.waitForLoadState("networkidle");
  expect(
    consoleErrors.filter(
      (entry) =>
        entry.includes("Failed to load resource") &&
        (entry.includes("/api/papers/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024") ||
          entry.includes("/api/papers/duboisAlzheimerDiseaseClinicalBiological2024") ||
          entry.includes("/api/artifacts/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024/latest") ||
          entry.includes("/api/papers/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024/pdf") ||
          entry.includes("/api/papers/duboisAlzheimerDiseaseClinicalBiological2024/pdf") ||
          entry.includes(
            "/api/obsidian/mirror?paper_id=zotero%3AduboisAlzheimerDiseaseClinicalBiological2024",
          ) ||
          entry.includes("/api/obsidian/mirror?paper_id=duboisAlzheimerDiseaseClinicalBiological2024")),
    ),
  ).toEqual([]);

  await page.goto("/protocol-cards");

  await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible();
  await expect(page.getByText("Recent notes", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }).click();

  await expect(page.getByLabel("Protocol card linked note slug")).toHaveValue(noteSlug);
  await expect(page.getByLabel("Protocol card linked paper id")).not.toHaveValue("");

  await page.getByLabel("Protocol card title").fill("Journey-smoke protocol card");
  await page.getByLabel("Protocol card version snapshot").fill(
    "Step 1: prepare cortical neurons.\nStep 2: apply ketone ester pulse.\nStep 3: collect BHB readout.",
  );
  await page.getByLabel("Protocol card key steps").fill(
    "Prepare cortical neurons\nApply ketone ester pulse\nCollect BHB readout",
  );
  await page.getByRole("button", { name: "Create protocol card" }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByRole("heading", { name: "Journey-smoke protocol card", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open note" })).toHaveAttribute(
    "href",
    new RegExp(`/papers/${noteSlug}$`),
  );
});

test("backend image evidence viewer loads a registered bundle and keeps note handoff on the real route", async ({
  page,
  request,
}) => {
  const imageEvidenceId = "imageev_backend_e2e_fixture";
  const derivativeArtifacts = await imageEvidenceFixtureDerivedArtifacts();
  const response = await request.post(`${backendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "E2E hippocampal ROI bundle",
      paper_id: noteBackedWorkbenchPaperId,
      paper_slug: noteSlug,
      source_ref: {
        source_kind: "local_file",
        local_path: imageEvidenceFixtureRawPath,
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
        acquisition_note: "Representative ROI export for e2e viewer coverage.",
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
          claim_id: "claim-e2e-image-001",
          note: "Representative image only.",
        },
      ],
      linked_artifact_refs: [
        {
          artifact_kind: "meeting_pack",
          artifact_id: "meeting-e2e-image-001",
          note: "Linked for downstream review.",
        },
      ],
      derived_outputs: [
        {
          derived_output_id: "thumb_local",
          kind: "thumbnail",
          source_image_evidence_id: imageEvidenceId,
          created_by: "e2e-fixture",
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
      derivative_artifacts: derivativeArtifacts,
      handoff_targets: [
        {
          target: "napari",
          openable_ref: imageEvidenceFixtureRawPath,
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
  const payload = (await response.json()) as {
    image_evidence?: {
      image_evidence_id?: string;
      title?: string;
      paper_slug?: string | null;
      warnings?: Array<{ code?: string }>;
      derived_outputs?: Array<{ derived_output_id?: string; bundle_ref?: { path?: string } | null }>;
    };
    view_state?: {
      active_channels?: string[];
      visible_overlays?: string[];
    } | null;
    handoff_targets?: Array<{ target?: string; openable_ref?: string }>;
  };
  expect(payload.image_evidence?.image_evidence_id).toBe(imageEvidenceId);
  expect(payload.image_evidence?.title).toBe("E2E hippocampal ROI bundle");
  expect(payload.image_evidence?.paper_slug).toBe(noteSlug);
  expect(payload.image_evidence?.warnings?.map((warning) => warning.code)).toEqual([
    "REPRESENTATIVE_ONLY",
    "CHECKSUM_MISMATCH",
  ]);
  expect(payload.image_evidence?.derived_outputs?.[0]?.derived_output_id).toBe("thumb_local");
  expect(payload.image_evidence?.derived_outputs?.[0]?.bundle_ref?.path).toBe("derivatives/thumb_local.png");
  expect(payload.view_state?.active_channels).toEqual(["GFP", "DAPI"]);
  expect(payload.view_state?.visible_overlays).toEqual(["roi_outline"]);
  expect(payload.handoff_targets?.[0]?.target).toBe("napari");
  expect(payload.handoff_targets?.[0]?.openable_ref).toBe(imageEvidenceFixtureDisplayPath);

  const indexResponse = await request.get(`${backendBaseUrl}/image-evidence`);
  expect(indexResponse.ok()).toBeTruthy();
  const indexPayload = (await indexResponse.json()) as {
    items?: Array<{ image_evidence_id?: string; title?: string; warning_count?: number }>;
  };
  expect(indexPayload.items?.find((item) => item.image_evidence_id === imageEvidenceId)).toMatchObject({
    image_evidence_id: imageEvidenceId,
    title: "E2E hippocampal ROI bundle",
    warning_count: 2,
  });

  const imageEvidenceJsonPath = path.join(e2eImageEvidenceRoot, imageEvidenceId, "image_evidence.json");
  await expect
    .poll(async () => {
      try {
        await fs.access(imageEvidenceJsonPath);
        return true;
      } catch {
        return false;
      }
    })
    .toBe(true);

  await gotoUntilLive(page, `/image-evidence/${imageEvidenceId}`, async () => {
    await expect(page.getByRole("heading", { name: "E2E hippocampal ROI bundle", exact: true })).toBeVisible({
      timeout: 15_000,
    });
  });

  await expect(page).toHaveURL(new RegExp(`/image-evidence/${imageEvidenceId}$`));
  await expect(page.getByRole("heading", { name: "E2E hippocampal ROI bundle", exact: true })).toBeVisible();
  await expect(page.getByTestId("image-evidence-header-context")).toContainText("Derived artifact");
  await expect(page.getByTestId("image-evidence-header-context")).toContainText("When to use");
  await expect(page.getByTestId("image-evidence-header-context")).toContainText("Derived from");
  await expect(page.getByRole("heading", { name: "Bundle Review" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Warnings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Derived Outputs" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "View State" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Handoff Targets" })).toBeVisible();
  await expect(page.getByText("Continue in note", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Continue after note review")).toBeVisible();
  const meetingPackFollowUp = page.getByRole("link", { name: /Meeting packs meeting_pack \/ meeting-e2e-image-001/i });
  await expect(meetingPackFollowUp).toBeVisible();
  await expect(meetingPackFollowUp).toHaveAttribute("href", "/meeting-packs");
  await expect(page.getByText("Reopen the meeting draft when this image needs discussion-ready framing", { exact: false })).toBeVisible();
  await expect(page.getByText("Saved targets preserve viewer context after note review.", { exact: false })).toBeVisible();
  const imageEvidenceRail = page.locator("aside");
  await expect(imageEvidenceRail.getByRole("heading").nth(0)).toHaveText("Bundle Summary");
  await expect(imageEvidenceRail.getByRole("heading").nth(1)).toHaveText("Trust Boundary");
  await expect(imageEvidenceRail.getByRole("heading").nth(2)).toHaveText("Metadata");
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    page.getByRole("link", { name: "Open note" }),
    "global Home should stay clear of the image evidence note handoff",
  );
  await expectNoUiOverlap(
    page.getByRole("link", { name: "Home" }),
    meetingPackFollowUp,
    "global Home should stay clear of the image evidence downstream lane handoff",
  );
  await expect(page.getByRole("heading", { name: "Trust Boundary" })).toBeVisible();
  await expect(page.locator("pre").filter({ hasText: imageEvidenceFixtureDisplayPath }).first()).toBeVisible();
  await expect(page.getByText("REPRESENTATIVE_ONLY")).toBeVisible();
  await expect(page.getByText("CHECKSUM_MISMATCH")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Bundle captures a representative crop rather than the full acquisition stack.")).toBeVisible();
  const derivedOutputCard = page.locator("article").filter({ hasText: "thumb_local" }).first();
  await expect(derivedOutputCard).toBeVisible();
  await expect(derivedOutputCard.getByText("Thumbnail", { exact: true })).toBeVisible();
  await expect(derivedOutputCard.getByText("derivatives/thumb_local.png")).toBeVisible();
  await expect(page.getByText("GFP")).toBeVisible();
  await expect(page.getByText("roi_outline")).toBeVisible();
  await expect(page.getByText("Representative ROI export for e2e viewer coverage.")).toBeVisible();
  await expect(page.getByText("Open with saved viewport.")).toBeVisible();

  await page.getByRole("link", { name: "Open note" }).click();

  await expect(page).toHaveURL(new RegExp(`/papers/${noteSlug}$`));
  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: /Alzheimer Disease as a Clinical-Biological Construct/i,
    }),
  ).toBeVisible();
});

test("backend image evidence viewer keeps a clean external bundle aligned with real detail state", async ({
  page,
  request,
}) => {
  const imageEvidenceId = "imageev_backend_e2e_external_fixture";
  const response = await request.post(`${backendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "E2E OMERO clean bundle",
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
  const payload = (await response.json()) as {
    image_evidence?: {
      image_evidence_id?: string;
      title?: string;
      warnings?: Array<{ code?: string }>;
      derived_outputs?: Array<{ derived_output_id?: string }>;
    };
    view_state?: unknown;
    handoff_targets?: Array<{ target?: string; openable_ref?: string }>;
  };
  expect(payload.image_evidence?.image_evidence_id).toBe(imageEvidenceId);
  expect(payload.image_evidence?.title).toBe("E2E OMERO clean bundle");
  expect(payload.image_evidence?.warnings ?? []).toEqual([]);
  expect(payload.image_evidence?.derived_outputs ?? []).toEqual([]);
  expect(payload.view_state ?? null).toBeNull();
  expect(payload.handoff_targets?.[0]?.target).toBe("omero");
  expect(payload.handoff_targets?.[0]?.openable_ref).toBe("omero://dataset/42/image/7");

  const indexResponse = await request.get(`${backendBaseUrl}/image-evidence`);
  expect(indexResponse.ok()).toBeTruthy();
  const indexPayload = (await indexResponse.json()) as {
    items?: Array<{ image_evidence_id?: string; title?: string; warning_count?: number; has_view_state?: boolean }>;
  };
  expect(indexPayload.items?.find((item) => item.image_evidence_id === imageEvidenceId)).toMatchObject({
    image_evidence_id: imageEvidenceId,
    title: "E2E OMERO clean bundle",
    warning_count: 0,
    has_view_state: false,
  });

  const imageEvidenceJsonPath = path.join(e2eImageEvidenceRoot, imageEvidenceId, "image_evidence.json");
  await expect
    .poll(async () => {
      try {
        await fs.access(imageEvidenceJsonPath);
        return true;
      } catch {
        return false;
      }
    })
    .toBe(true);

  await page.goto("/image-evidence");

  await expect(page.getByRole("heading", { name: "Image Evidence", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or image evidence id"]').fill("omero clean");
  const targetCard = page.locator("article").filter({ hasText: "E2E OMERO clean bundle" }).first();
  await expect(targetCard).toBeVisible({ timeout: 15_000 });
  await expect(targetCard.getByText("Clean bundle", { exact: true })).toBeVisible();
  await targetCard.getByRole("button", { name: "Open bundle" }).click();

  await expect(page).toHaveURL(new RegExp(`/image-evidence/${imageEvidenceId}$`));
  await expect(page.getByRole("heading", { name: "E2E OMERO clean bundle", exact: true })).toBeVisible();
  await expect(page.getByText("No bundle warnings saved.")).toBeVisible();
  await expect(page.getByText("No derived outputs registered.")).toBeVisible();
  await expect(page.getByText("No view state saved for this bundle.")).toBeVisible();
  await expect(page.locator("pre").filter({ hasText: "omero://dataset/42/image/7" }).first()).toBeVisible();
  await expect(page.getByText("Open in external viewer.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open note" })).toHaveCount(0);
});

test("backend image evidence viewer surfaces missing-local-file warnings on the real route", async ({
  page,
  request,
}) => {
  const imageEvidenceId = "imageev_backend_e2e_missing_local_fixture";
  const response = await request.post(`${backendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "E2E missing local image bundle",
      paper_id: "paper-e2e-001",
      source_ref: {
        source_kind: "local_file",
        local_path: imageEvidenceMissingRawPath,
        source_label: "Missing microscope export",
      },
      content_format: "image/tiff",
      metadata: {
        modality: "fluorescence",
      },
    },
  });

  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as {
    image_evidence?: {
      image_evidence_id?: string;
      title?: string;
      warnings?: Array<{ code?: string; message?: string }>;
    };
    view_state?: unknown;
    handoff_targets?: Array<{ target?: string }>;
  };
  expect(payload.image_evidence?.image_evidence_id).toBe(imageEvidenceId);
  expect(payload.image_evidence?.title).toBe("E2E missing local image bundle");
  expect(payload.image_evidence?.warnings?.map((warning) => warning.code)).toEqual(["LOCAL_SOURCE_MISSING"]);
  expect(payload.image_evidence?.warnings?.[0]?.message).toContain(imageEvidenceMissingDisplayPath);
  expect(payload.view_state ?? null).toBeNull();
  expect(payload.handoff_targets ?? []).toEqual([]);

  const indexResponse = await request.get(`${backendBaseUrl}/image-evidence`);
  expect(indexResponse.ok()).toBeTruthy();
  const indexPayload = (await indexResponse.json()) as {
    items?: Array<{
      image_evidence_id?: string;
      title?: string;
      warning_count?: number;
      has_view_state?: boolean;
      has_handoff?: boolean;
    }>;
  };
  expect(indexPayload.items?.find((item) => item.image_evidence_id === imageEvidenceId)).toMatchObject({
    image_evidence_id: imageEvidenceId,
    title: "E2E missing local image bundle",
    warning_count: 1,
    has_view_state: false,
    has_handoff: false,
  });

  const imageEvidenceJsonPath = path.join(e2eImageEvidenceRoot, imageEvidenceId, "image_evidence.json");
  await expect
    .poll(async () => {
      try {
        await fs.access(imageEvidenceJsonPath);
        return true;
      } catch {
        return false;
      }
    })
    .toBe(true);

  await page.goto("/image-evidence");

  await expect(page.getByRole("heading", { name: "Image Evidence", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or image evidence id"]').fill("missing local");
  const targetCard = page.locator("article").filter({ hasText: "E2E missing local image bundle" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("1 warning", { exact: true })).toBeVisible();
  await targetCard.getByRole("button", { name: "Open bundle" }).click();

  await expect(page).toHaveURL(new RegExp(`/image-evidence/${imageEvidenceId}$`));
  await expect(page.getByRole("heading", { name: "E2E missing local image bundle", exact: true })).toBeVisible();
  await expect(page.locator("pre").filter({ hasText: imageEvidenceMissingDisplayPath }).first()).toBeVisible();
  await expect(page.getByText("LOCAL_SOURCE_MISSING")).toBeVisible();
  await expect(page.getByText(`Local source file does not exist: ${imageEvidenceMissingDisplayPath}`)).toBeVisible();
  await expect(page.getByText("No derived outputs registered.")).toBeVisible();
  await expect(page.getByText("No view state saved for this bundle.")).toBeVisible();
  await expect(page.getByText("No handoff targets saved for this bundle.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open note" })).toHaveCount(0);
});

test("backend triage content review action carries flagged context into workbench", async ({ page }) => {
  await openHomeLive(page);

  await searchPaperList(page, "Content Review");
  const row = page.locator("tbody tr").filter({ hasText: "E2E Content Review Paper" }).first();
  await expect(row.getByTestId("triage-ops-badge")).toContainText("Healthy", { timeout: 15_000 });
  await expect(row.getByTestId("triage-primary-action")).toContainText("Review 2 issues", { timeout: 15_000 });
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review 2 issues", { timeout: 15_000 });
  await expect(row.getByTestId("triage-review-detail")).toContainText("2 mapping ambiguities", { timeout: 15_000 });
  await row.getByTestId("triage-content-review-button").click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-content-review-001\?focus=issues/);
  await expect(page.getByTestId("content-review-notice")).toContainText("2 flagged review issues remain in focus.", { timeout: 15_000 });
  await expect(page.getByTestId("content-review-notice-detail")).toContainText("2 mapping ambiguities");
  await expect(page.getByTestId("content-review-notice")).toContainText("Risk focus is on.");
  await expect(page.getByTestId("workbench-content-review-badge")).toContainText("2 flagged");
  await expect(page.getByTestId("workbench-content-review-hint")).toContainText("Claim review flags are separate from saved checks.");
  await expect(page.getByTestId("workbench-content-review-detail")).toContainText("2 mapping ambiguities");
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Healthy");
});

test("backend keeps unavailable content review distinct from clear state", async ({ page }) => {
  await openHomeLive(page);

  await searchPaperList(page, "Content Review");
  const row = page.locator("tbody tr").filter({ hasText: "E2E Content Review Unavailable Paper" }).first();
  await expect(row.getByTestId("triage-ops-badge")).toContainText("Healthy", { timeout: 15_000 });
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review unavailable", { timeout: 15_000 });
  await expect(row.getByTestId("triage-content-review-button")).toBeDisabled();
  await expect(row.getByTestId("triage-review-badge")).toContainText("Unavailable");
  await expect(row.getByTestId("triage-review-hint")).toContainText("Claim review has not been generated");
  await expect(row.getByTestId("triage-review-detail")).toContainText("Not analyzed");
  await row.click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-content-review-unavailable-001$/);
  await expect(page.getByTestId("content-review-notice")).toContainText("Claim review is not available yet.");
  await expect(page.getByTestId("content-review-notice-detail")).toContainText("Not analyzed");
  await expect(page.getByTestId("content-review-notice")).toContainText("Continue with saved checks");
  await expect(page.getByTestId("workbench-content-review-badge")).toContainText("Unavailable");
  await expect(page.getByTestId("workbench-content-review-hint")).toContainText("Claim review has not been generated");
  await expect(page.getByTestId("workbench-content-review-detail")).toContainText("Not analyzed");
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Healthy");
});

test("backend seeded fixture bootstrap meta matches available artifacts", async ({ request }) => {
  const response = await request.get(`${backendBaseUrl}/jobs/job-e2e-fixture-001`);
  expect(response.ok()).toBeTruthy();

  const payload = (await response.json()) as BackendJobDetail;
  expect(payload.bootstrap_meta_path).toBeTruthy();
  expect(payload.artifact_document_written).toBe(true);
  expect(payload.artifact_claimset_written).toBe(true);
  expect(payload.artifact_stats_written).toBe(true);
  expect(payload.claimset_readiness).toBe("ready");
});

test("backend real-paper smoke keeps claim jump and highlight rendering stable", async ({ page, request }) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");
  const candidates = await getNonFixtureSmokeCandidates(request, 3);
  if (candidates.length === 0) {
    if (requireRealSmokeCandidates) {
      throw new Error("No non-fixture paper with distinct claim pages available for real smoke");
    }
    test.skip(true, "No non-fixture paper with distinct claim pages available");
  }

  let validated = 0;
  for (const candidate of candidates) {
    const { paperId, firstClaimIndex, secondClaimIndex } = candidate;
    await openWorkbenchLive(
      page,
      `/workbench/${encodeURIComponent(paperId)}`,
      async () => {
        await expect(page.locator('[data-testid="pdf-viewer"]').first()).toBeVisible({ timeout: 15_000 });
      },
      3,
    );

    const viewer = page.locator('[data-testid="pdf-viewer"]').first();
    if (!(await waitForOptionalVisible(viewer))) {
      continue;
    }

    const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
    if (!(await waitForOptionalVisible(claimsPanel))) {
      continue;
    }

    const claimButtons = claimsPanel.getByRole("button");
    if (!(await waitForOptionalVisible(claimButtons.nth(secondClaimIndex)))) {
      continue;
    }
    const claimCount = await claimButtons.count();
    if (claimCount <= secondClaimIndex) {
      continue;
    }

    const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
    const linkBadge = pdfPanel.getByText(/(Claim Link|Text Match) · p\.\d+/).first();

    const highlightLike = page
      .locator('[data-testid="claim-highlight"], [data-testid="claim-search-highlight"], [data-testid="claim-approx-highlight"]')
      .first();

    await claimButtons.nth(firstClaimIndex).click();
    await expect(linkBadge).toBeVisible({ timeout: 10_000 });
    if (!(await waitForOptionalVisible(highlightLike, 10_000))) {
      continue;
    }
    const firstBadgeText = (await linkBadge.textContent()) ?? "";

    await claimButtons.nth(secondClaimIndex).click();
    await expect(linkBadge).toBeVisible({ timeout: 10_000 });
    if (!(await waitForOptionalVisible(highlightLike, 10_000))) {
      continue;
    }
    const secondBadgeText = (await linkBadge.textContent()) ?? "";
    expect(secondBadgeText).toMatch(/p\.\d+/);
    if (secondBadgeText.trim() === firstBadgeText.trim()) {
      continue;
    }

    validated += 1;
  }

  expect(validated).toBeGreaterThan(0);
});

test("backend real-paper smoke keeps healthy and action-needed clear-state contracts distinct", async ({ page, request }) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  const healthyNote = await resolveRealSmokeNote(request, realSmokeHealthyClearPaperId);
  const actionNeededNote = await resolveRealSmokeNote(request, realSmokeActionNeededClearPaperId);
  if (!healthyNote || !actionNeededNote) {
    if (requireRealSmokeCandidates) {
      throw new Error("Required real-paper clear-state smoke candidates are unavailable");
    }
    test.skip(true, "Required real-paper clear-state smoke candidates are unavailable");
  }

  await gotoUntilLive(
    page,
    `/papers/${encodeURIComponent(healthyNote.slug)}`,
    async () => {
      await expect(page.getByTestId("paper-note-review-ops-badge")).toContainText("Healthy", { timeout: 15_000 });
    },
    3,
  );
  await expect(page.getByTestId("paper-note-review-ops-reason")).toContainText(
    "Saved claims and note checks are available.",
  );
  await expect(page.getByTestId("paper-note-review-bridge-status")).toContainText(
    "Saved claims are available, but evidence depth is still thin.",
  );
  await expect(page.getByRole("link", { name: "Open review" }).first()).toHaveAttribute(
    "href",
    `/workbench/${encodeURIComponent(healthyNote.paperId)}`,
  );

  await openWorkbenchLive(page, `/workbench/${encodeURIComponent(healthyNote.paperId)}`);
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Healthy");
  await expect(page.getByTestId("workbench-ops-reason")).toContainText("Saved claims and note checks are available.");
  await expect(page.getByTestId("workbench-workspace-context")).toContainText(
    "No claim review flags are recorded in the current paper summary.",
  );

  await gotoUntilLive(
    page,
    `/papers/${encodeURIComponent(actionNeededNote.slug)}`,
    async () => {
      await expect(page.getByTestId("paper-note-review-summary")).toContainText("remain unresolved", {
        timeout: 15_000,
      });
    },
    3,
  );
  await expect(page.getByTestId("paper-note-review-bridge-status")).toContainText(
    "Unresolved evidence is still blocking downstream trust.",
  );
  await expect(page.getByRole("link", { name: "Open review" }).first()).toHaveAttribute(
    "href",
    `/workbench/${encodeURIComponent(actionNeededNote.paperId)}`,
  );

  await openWorkbenchLive(page, `/workbench/${encodeURIComponent(actionNeededNote.paperId)}`);
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Action needed");
  await expect(page.getByTestId("workbench-ops-reason")).toContainText("Saved note checks are missing or empty.");
  await expect(page.getByTestId("workbench-workspace-context")).toContainText(
    "No claim review flags are recorded in the current paper summary.",
  );
});

test("backend real-paper smoke keeps live runtime readiness handoff clear when the workspace is healthy", async ({
  page,
}) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  await gotoUntilLive(
    page,
    "/ready",
    async () => {
      await expect(page.getByRole("heading", { name: "Check whether this workspace is ready for real runs" })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("runtime-readiness-overall")).toContainText("Ready");
    },
    3,
  );

  await expect(page.getByTestId("runtime-readiness-next-step")).toContainText(
    "This machine looks ready for the current paper-first loop.",
  );
  await expect(page.getByTestId("runtime-readiness-open-papers")).toHaveAttribute("href", "/papers");
  await expect(page.getByTestId("runtime-readiness-open-meeting-packs")).toHaveAttribute("href", "/meeting-packs");
  await expect(page.getByTestId("runtime-readiness-product-loop")).toContainText("Meeting Packs.");
  await expect(page.getByTestId("runtime-readiness-research-dna-note")).toContainText("paperpipe research-dna");
  await expect(page.getByTestId("runtime-readiness-suggested-fixes")).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-fallback")).toHaveCount(0);
});

test("backend real-paper smoke keeps live paper-notes list ops handoffs aligned for healthy and action-needed notes", async ({
  page,
  request,
}) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  const healthyNote = await resolveRealSmokeNote(request, realSmokeHealthyClearPaperId);
  const actionNeededNote = await resolveRealSmokeNote(request, realSmokeActionNeededClearPaperId);
  if (!healthyNote || !actionNeededNote) {
    if (requireRealSmokeCandidates) {
      throw new Error("Required real-paper paper-notes list smoke candidates are unavailable");
    }
    test.skip(true, "Required real-paper paper-notes list smoke candidates are unavailable");
  }

  await gotoUntilLive(
    page,
    "/papers",
    async () => {
      await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
      await expect(page.getByTestId("paper-notes-visible-summary")).toContainText("Visible now");
    },
    3,
  );

  await searchPaperList(page, "Clinical-Biological Construct");
  const healthyRow = page.getByTestId("paper-note-list-row").filter({ hasText: "Clinical-Biological Construct" }).first();
  await expect(healthyRow).toBeVisible({ timeout: 15_000 });
  await expect(healthyRow.getByTestId("paper-note-ops-badge")).toContainText("Healthy");
  await expect(healthyRow.getByTestId("paper-note-next-action-review")).toHaveAttribute(
    "href",
    `/workbench/${encodeURIComponent(healthyNote.paperId)}`,
  );
  await expect(healthyRow.getByTestId("paper-note-next-action-note")).toHaveAttribute(
    "href",
    new RegExp(`/papers/${encodeURIComponent(healthyNote.slug)}(?:\\?|$)`),
  );

  await searchPaperList(page, "dual-action small molecule");
  const actionNeededRow = page
    .getByTestId("paper-note-list-row")
    .filter({
      has: page.locator(
        `a[href="/papers/${encodeURIComponent(
          "Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer s disease mice",
        )}"]`,
      ),
    })
    .first();
  await expect(actionNeededRow).toBeVisible({ timeout: 15_000 });
  await expect(actionNeededRow.getByTestId("paper-note-ops-badge")).toContainText("Action needed");
  await expect(actionNeededRow.getByTestId("paper-note-next-action-review")).toHaveAttribute(
    "href",
    `/workbench/${encodeURIComponent(actionNeededNote.paperId)}`,
  );
  await expect(actionNeededRow.getByTestId("paper-note-next-action-note")).toHaveAttribute(
    "href",
    new RegExp(`/papers/${encodeURIComponent(actionNeededNote.slug)}(?:\\?|$)`),
  );
});

test("backend real-paper smoke keeps paper-detail handoffs aligned for a note-backed paper", async ({ page, request }) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  const healthyNote = await resolveRealSmokeNote(request, realSmokeHealthyClearPaperId);
  if (!healthyNote) {
    if (requireRealSmokeCandidates) {
      throw new Error("Required real-paper note-backed detail smoke candidate is unavailable");
    }
    test.skip(true, "Required real-paper note-backed detail smoke candidate is unavailable");
  }

  await gotoUntilLive(
    page,
    `/papers/${encodeURIComponent(healthyNote.slug)}`,
    async () => {
      await expect(page.getByRole("banner").getByRole("heading")).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId("paper-note-review-ops-badge")).toContainText("Healthy", { timeout: 15_000 });
    },
    3,
  );

  await expect(page.getByRole("link", { name: "Open review" }).first()).toHaveAttribute(
    "href",
    `/workbench/${encodeURIComponent(healthyNote.paperId)}`,
  );

  const protocolStartLink = page.getByRole("link", { name: "Save protocol card" }).first();
  await expect(protocolStartLink).toHaveAttribute("href", /\/protocol-cards\?/);
  await expect(protocolStartLink).toHaveAttribute("href", new RegExp(encodeURIComponent(healthyNote.paperId)));
  await protocolStartLink.click();

  await expect(page).toHaveURL(/\/protocol-cards\?/);
  await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible();
  await expect(page.getByLabel("Protocol card linked note slug")).toHaveValue(healthyNote.slug);
  await expect(page.getByLabel("Protocol card linked paper id")).toHaveValue(healthyNote.paperId);
  await expect(page.getByTestId("protocol-card-create-context")).toContainText("Current note context");
  await expect(page.getByTestId("protocol-card-create-context")).toContainText(healthyNote.slug);
});

test("backend real-paper smoke keeps saved meeting-pack note handoff aligned for a note-backed paper", async ({ page }) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  await gotoUntilLive(
    page,
    "/meeting-packs",
    async () => {
      await expect(page.getByRole("banner").getByRole("heading", { name: "Saved meeting packs", exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
    },
    3,
  );

  await page.getByLabel("Search saved meeting packs").fill("Clinical-Biological Construct");
  await expect(page.getByTestId("meeting-pack-index-summary")).toContainText("matching saved packs");
  const firstMatchingPack = page.getByTestId("meeting-pack-index-row").first();
  await expect(firstMatchingPack).toBeVisible({ timeout: 15_000 });
  await firstMatchingPack.getByRole("button", { name: "Open pack", exact: true }).click();

  await expect(page).toHaveURL(/\/meeting-packs\/meetingpack_/);
  await expect(
    page.getByRole("banner").getByRole("heading", { name: canonicalDuboisNoteSlug, exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("meeting-pack-header-context")).toContainText(
    "Canonical evidence lives upstream in linked paper notes.",
  );

  const continueInNoteLink = page.getByRole("link", { name: "Continue in note" }).first();
  await expect(continueInNoteLink).toContainText(canonicalDuboisNoteSlug);
  await expect(continueInNoteLink).toHaveAttribute(
    "href",
    new RegExp(`/papers/${encodeURIComponent(canonicalDuboisNoteSlug)}$`),
  );
  await continueInNoteLink.click();

  await expect(page).toHaveURL(new RegExp(`/papers/${encodeURIComponent(canonicalDuboisNoteSlug)}$`));
  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: /Alzheimer Disease as a Clinical-Biological Construct/i,
    }),
  ).toBeVisible();
});

test("backend real-paper smoke keeps saved protocol-card note handoff aligned for a note-backed paper", async ({
  page,
  request,
}) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  const protocolNote = await resolveRealSmokeNote(request, realSmokeProtocolCardPaperId);
  if (!protocolNote) {
    if (requireRealSmokeCandidates) {
      throw new Error("Required real-paper protocol-card smoke candidate is unavailable");
    }
    test.skip(true, "Required real-paper protocol-card smoke candidate is unavailable");
  }

  await gotoUntilLive(
    page,
    "/protocol-cards",
    async () => {
      await expect(page.getByRole("heading", { name: "Protocol Cards", exact: true })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
    },
    3,
  );

  await page.getByPlaceholder("Search title or protocol id").fill("Chandra protocol");
  const firstMatchingCard = page.locator("article").filter({ hasText: "Chandra protocol card" }).first();
  await expect(firstMatchingCard).toBeVisible({ timeout: 15_000 });
  await firstMatchingCard.getByRole("button", { name: "Open protocol card", exact: true }).click();

  await expect(page).toHaveURL(/\/protocol-cards\/protocol_/);
  await expect(page.getByTestId("protocol-card-header-context")).toContainText(
    "Canonical evidence lives upstream in the linked paper note.",
  );

  const openNoteLink = page.getByRole("link", { name: "Open note" }).first();
  await expect(openNoteLink).toHaveAttribute(
    "href",
    new RegExp(`/papers/${encodeURIComponent(protocolNote.slug)}$`),
  );
  await openNoteLink.click();

  await expect(page).toHaveURL(new RegExp(`/papers/${encodeURIComponent(protocolNote.slug)}$`));
  await expect(page.getByRole("banner").getByRole("heading")).toContainText(/gut microbiome/i);
});

test("backend real-paper smoke keeps saved method-comparison note handoff aligned for a note-backed paper", async ({
  page,
  request,
}) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  const actionNeededNote = await resolveRealSmokeNote(request, realSmokeActionNeededClearPaperId);
  if (!actionNeededNote) {
    if (requireRealSmokeCandidates) {
      throw new Error("Required real-paper method-comparison smoke candidate is unavailable");
    }
    test.skip(true, "Required real-paper method-comparison smoke candidate is unavailable");
  }

  await gotoUntilLive(
    page,
    "/method-comparisons",
    async () => {
      await expect(page.getByRole("heading", { name: "Method Comparisons", exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
    },
    3,
  );

  await page.getByPlaceholder("Search title or comparison id").fill(realSmokeMethodComparisonTitle);
  const comparisonCard = page.locator("article").filter({ hasText: realSmokeMethodComparisonTitle }).first();
  await expect(comparisonCard).toBeVisible({ timeout: 15_000 });
  await comparisonCard.getByRole("button", { name: "Open comparison", exact: true }).click();

  await expect(page).toHaveURL(/\/method-comparisons\/methodcmp_/);
  await expect(page.getByRole("banner").getByRole("heading", { name: realSmokeMethodComparisonTitle, exact: true })).toBeVisible();
  await expect(page.getByTestId("method-comparison-header-context")).toContainText(
    "Canonical evidence lives upstream",
  );

  const expectedNoteLink = page.locator(`a[href$="/papers/${encodeURIComponent(actionNeededNote.slug)}"]`).first();
  await expect(expectedNoteLink).toContainText("Open note");
  await expectedNoteLink.click();

  await expect(page).toHaveURL(new RegExp(`/papers/${encodeURIComponent(actionNeededNote.slug)}$`));
  await expect(page.getByRole("banner").getByRole("heading")).toContainText(/dual-action small molecule/i);
});

test("backend real-paper smoke keeps saved image-evidence note handoff aligned for a note-backed paper", async ({
  page,
  request,
}) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  const healthyNote = await resolveRealSmokeNote(request, realSmokeHealthyClearPaperId);
  if (!healthyNote) {
    if (requireRealSmokeCandidates) {
      throw new Error("Required real-paper image-evidence smoke candidate is unavailable");
    }
    test.skip(true, "Required real-paper image-evidence smoke candidate is unavailable");
  }

  await gotoUntilLive(
    page,
    "/image-evidence",
    async () => {
      await expect(page.getByRole("heading", { name: "Image Evidence", exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
    },
    3,
  );

  await page.getByPlaceholder("Search title or image evidence id").fill(realSmokeImageEvidenceTitle);
  const imageBundleCard = page.locator("article").filter({ hasText: realSmokeImageEvidenceTitle }).first();
  await expect(imageBundleCard).toBeVisible({ timeout: 15_000 });
  await imageBundleCard.getByRole("button", { name: "Open bundle", exact: true }).click();

  await expect(page).toHaveURL(/\/image-evidence\/imageev_/);
  await expect(page.getByRole("banner").getByRole("heading", { name: realSmokeImageEvidenceTitle, exact: true })).toBeVisible();
  await expect(page.getByTestId("image-evidence-header-context")).toContainText("Canonical evidence lives upstream");
  await expect(page.getByText("Continue in note", { exact: true })).toBeVisible();

  const openNoteLink = page.getByRole("link", { name: "Open note", exact: true }).first();
  const expectedNoteRoute = new RegExp(
    `/papers/(?:${encodeURIComponent(healthyNote.slug)}|${encodeURIComponent(noteSlug)})$`,
  );
  await expect(openNoteLink).toHaveAttribute(
    "href",
    expectedNoteRoute,
  );
  await openNoteLink.click();

  await expect(page).toHaveURL(expectedNoteRoute);
  await expect(page.getByRole("banner").getByRole("heading")).toContainText(
    /Clinical-Biological Construct|Alzheimer Disease/i,
  );
});

test("backend real-paper smoke keeps saved chart-pack lineage aligned for downstream reuse", async ({ page }) => {
  test.skip(!runRealSmoke, "Set PAPERPIPE_REAL_SMOKE=1 to run real-paper smoke");

  await gotoUntilLive(
    page,
    "/chart-packs",
    async () => {
      await expect(page.getByRole("heading", { name: "Chart Packs", exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
    },
    3,
  );

  await page.getByPlaceholder("Search title or chart pack id").fill(realSmokeChartPackTitle);
  const chartPackCard = page.locator("article").filter({ hasText: realSmokeChartPackTitle }).first();
  await expect(chartPackCard).toBeVisible({ timeout: 15_000 });
  await chartPackCard.getByRole("button", { name: "Open chart pack", exact: true }).click();

  await expect(page).toHaveURL(/\/chart-packs\/chartpack_/);
  await expect(page.getByRole("banner").getByRole("heading", { name: realSmokeChartPackTitle, exact: true })).toBeVisible();
  await expect(page.getByTestId("chart-pack-header-context")).toContainText(
    "Derived from 1 saved source ref anchored on zotero:hanssonAlzheimersAssociationAppropriate2022 / run_20260223_140928.",
  );
  await expect(page.getByTestId("chart-pack-review-priority")).toContainText(
    "No pack-level warnings or caution notes are saved.",
  );
  await expect(page.getByTestId("chart-pack-quality-gate-card")).toContainText(
    "No saved quality-gate checks are available for this chart pack.",
  );
  await expect(page.getByRole("link", { name: "Export CSV", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Open spec JSON", exact: true }).first()).toBeVisible();
  await expect(
    page.getByText("zotero:hanssonAlzheimersAssociationAppropriate2022 / run_20260223_140928", { exact: true }).last(),
  ).toBeVisible();
});

test("backend evidence linking keeps single highlight and updates bbox on claim change", async ({ page }) => {
  await openWorkbenchLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible({ timeout: 15_000 });
  });

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  const claimButtons = claimsPanel.getByRole("button");
  const claimCount = await claimButtons.count();
  expect(claimCount).toBeGreaterThan(1);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(highlight).toBeVisible();

  const viewerBox = await viewer.boundingBox();
  const beforeBox = await highlight.boundingBox();
  expect(viewerBox).not.toBeNull();
  expect(beforeBox).not.toBeNull();
  if (viewerBox && beforeBox) {
    expect(beforeBox.width).toBeGreaterThan(24);
    expect(beforeBox.height).toBeGreaterThan(24);
    expect(beforeBox.width).toBeLessThan(viewerBox.width * 0.95);
    expect(beforeBox.height).toBeLessThan(viewerBox.height * 0.95);
    expect(beforeBox.x).toBeGreaterThanOrEqual(viewerBox.x - 2);
    expect(beforeBox.y).toBeGreaterThanOrEqual(viewerBox.y - 2);
    expect(beforeBox.x + beforeBox.width).toBeLessThanOrEqual(viewerBox.x + viewerBox.width + 2);
    expect(beforeBox.y + beforeBox.height).toBeLessThanOrEqual(viewerBox.y + viewerBox.height + 2);
  }

  await claimButtons.nth(1).click();
  await expect(highlight).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]')).toHaveCount(1);

  const afterBox = await highlight.boundingBox();
  expect(afterBox).not.toBeNull();
  if (viewerBox && beforeBox && afterBox) {
    expect(afterBox.width).toBeGreaterThan(viewerBox.width * 0.2);
    expect(afterBox.height).toBeGreaterThan(viewerBox.height * 0.15);
    const movedDelta =
      Math.abs(beforeBox.x - afterBox.x) +
      Math.abs(beforeBox.y - afterBox.y) +
      Math.abs(beforeBox.width - afterBox.width) +
      Math.abs(beforeBox.height - afterBox.height);
    expect(movedDelta).toBeGreaterThan(12);
  }
});

test("backend workbench prefers canonical structured bbox highlight over stale artifact text-match fallback", async ({ page }) => {
  await openWorkbenchLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchPaperId)}`, async () => {
    await expect(page.locator('[data-testid="pdf-viewer"]').first()).toBeVisible({ timeout: 15_000 });
  });
  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  await expect(viewer).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button", { name: /The intervention shows an initial improvement window during early follow-up\./ })).toBeVisible();
  await expect(claimsPanel.getByText("Stale artifact claim should be replaced by canonical sidecar state.")).toHaveCount(0);

  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();
  await expect(pdfPanel.getByText("Text Match")).toHaveCount(0);

  await viewer.scrollIntoViewIfNeeded();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(highlight).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('[data-testid="claim-search-highlight"]')).toHaveCount(0);

  const highlightBox = await highlight.boundingBox();
  expect(highlightBox).not.toBeNull();
  if (highlightBox) {
    expect(highlightBox.width).toBeGreaterThan(24);
    expect(highlightBox.height).toBeGreaterThan(24);
  }
});

test("backend workbench surfaces saved section reopen signal in the header context", async ({ page }) => {
  await gotoUntilLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchPaperId)}`, async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByTestId("workbench-section-navigation-signal")).toContainText("Saved signal ready", {
      timeout: 15_000,
    });
  });

  await expect(page.getByTestId("workbench-workspace-context")).toContainText("Saved review state");
  await expect(page.getByTestId("workbench-paper-id-copy-row")).toContainText(noteBackedWorkbenchPaperId);
  await expect(page.getByTestId("workbench-copy-paper-id")).toHaveText("Copy ID");
  await expect(page.getByTestId("workbench-section-navigation-signal")).toContainText("Saved signal ready");
  await expect(page.getByTestId("workbench-section-navigation-signal-detail")).toContainText("saved section groups");
});

test("backend stats snapshot disambiguates claim target by text signal", async ({ page }) => {
  await openWorkbenchLive(page, "/workbench/paper-e2e-001");

  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(mirrorPanel).toBeVisible();

  const targetCheck = mirrorPanel.getByRole("button").filter({ hasText: "effect-size-disambiguation" }).first();
  await expect(targetCheck).toBeVisible();
  await targetCheck.click();

  await expect(page.getByText("Claim Link · p.2")).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
});

test("backend evidence review gestures append user actions", async ({ page, request }) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  });

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(claimsPanel).toBeVisible();
  await expect(mirrorPanel).toBeVisible();

  await claimsPanel.getByRole("button").nth(1).click();
  await mirrorPanel.locator("details").filter({ hasText: "Claims Snapshot" }).first().getByRole("button").first().click();
  await mirrorPanel.getByRole("button").filter({ hasText: "effect-size-disambiguation" }).first().click();

  await expect
    .poll(
      async () => {
        const actions = await listUserActions(request, "paper-e2e-001");
        return {
          selectClaim: actions.some(
            (action) =>
              action.action_type === "workbench_select_claim" &&
              action.source === "ui" &&
              action.payload?.origin === "claim_list" &&
              action.payload?.run_id === "run_e2e_fixture_001",
          ),
          mirrorJump: actions.some(
            (action) =>
              action.action_type === "workbench_jump_mirror_claim" &&
              action.source === "ui" &&
              action.payload?.origin === "mirror_claim" &&
              action.payload?.run_id === "run_e2e_fixture_001",
          ),
          statsJump: actions.some(
            (action) =>
              action.action_type === "workbench_jump_stats_check" &&
              action.source === "ui" &&
              action.payload?.origin === "stats_snapshot" &&
              action.payload?.run_id === "run_e2e_fixture_001",
          ),
        };
      },
      { timeout: 15_000 },
    )
    .toEqual({
      selectClaim: true,
      mirrorJump: true,
      statsJump: true,
    });
});

test("backend cross-page claim change keeps viewer mounted and re-targets highlight", async ({ page }) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.locator('[data-testid="pdf-viewer"]').first()).toBeVisible({ timeout: 15_000 });
  });

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel).toBeVisible();
  const claimButtons = claimsPanel.getByRole("button");
  await expect(claimButtons).toHaveCount(3);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  await expect(viewer).toBeVisible();

  await claimButtons.nth(2).click();

  await expect(page.getByText("Claim Link · p.2")).toBeVisible();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(highlight).toBeVisible();

  const viewerBox = await viewer.boundingBox();
  const highlightBox = await highlight.boundingBox();
  expect(viewerBox).not.toBeNull();
  expect(highlightBox).not.toBeNull();
  if (viewerBox && highlightBox) {
    expect(highlightBox.width).toBeGreaterThan(24);
    expect(highlightBox.height).toBeGreaterThan(24);
    expect(highlightBox.x).toBeGreaterThanOrEqual(viewerBox.x - 2);
    expect(highlightBox.y).toBeGreaterThanOrEqual(viewerBox.y - 2);
    expect(highlightBox.x + highlightBox.width).toBeLessThanOrEqual(viewerBox.x + viewerBox.width + 2);
    expect(highlightBox.y + highlightBox.height).toBeLessThanOrEqual(viewerBox.y + viewerBox.height + 2);
  }
});

test("backend timeline falls back to all when status events are unavailable", async ({ page }) => {
  await ensureRepairFixtureMissingStats();
  await gotoUntilLive(page, "/workbench/paper-e2e-repair-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  const timelinePanel = page.locator("#workbench-timeline-panel");
  await expect(timelinePanel).toBeVisible();
  await expect(timelinePanel.getByRole("button", { name: "Show status timeline events" })).toHaveText(
    /Status \(\d+\)/,
    { timeout: 15_000 },
  );
  await expect(timelinePanel.getByText("No events in this filter yet.")).toHaveCount(0);
  await expect(timelinePanel.locator("ul").last().locator("li").first()).toBeVisible();
});

test("backend timeline surfaces user-triggered actions distinctly", async ({ page }) => {
  await openWorkbenchLive(page, "/workbench/paper-e2e-001");

  const timelinePanel = page.locator("section").filter({ hasText: "Timeline" }).first();
  await expect(timelinePanel).toBeVisible();
  await expect(timelinePanel.getByTestId("timeline-pinned-user-action")).toContainText("User");
  await expect(timelinePanel.getByTestId("timeline-source-user-action").first()).toContainText("USER");
  await expect(timelinePanel.getByTestId("timeline-row-user-action").getByText("User queued deep read")).toBeVisible();
});

test("backend timeline jump keeps filter controls ahead of pinned and event content", async ({ page }) => {
  await openWorkbenchLive(page, "/workbench/paper-e2e-001");

  await page.getByRole("button", { name: "Jump to timeline" }).click();
  await expect(page.locator("#workbench-timeline-panel")).toBeFocused();

  const timelineStops = await captureTabOrder(page, 4);
  expect(timelineStops).toEqual([
    expect.objectContaining({ tag: "BUTTON", name: "Show all timeline events" }),
    expect.objectContaining({ tag: "BUTTON", name: "Show status timeline events" }),
    expect.objectContaining({ tag: "BUTTON", name: "Show error timeline events" }),
    expect.objectContaining({ tag: "BUTTON", name: "Show done timeline events" }),
  ]);
  expect(timelineStops.some((entry) => entry.testid === "timeline-row-user-action")).toBe(false);
});

test("backend repair stats action appears only when stats artifact is missing and hides after repair", async ({ page }) => {
  await ensureRepairFixtureMissingStats();
  await gotoUntilLive(page, "/workbench/paper-e2e-repair-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByTestId("repair-stats-warning")).toContainText("Saved note checks are missing or empty.", {
      timeout: 15_000,
    });
  });

  const repairButton = page.getByRole("button", { name: "Refresh checks", exact: true });
  const statsSnapshotSummary = page.locator("summary").filter({ hasText: "Saved checks" });
  await expect(page.getByText("Obsidian sync payload preview")).toBeVisible();
  await expect(repairButton).toBeVisible();
  await expect(statsSnapshotSummary).toHaveCount(0);

  await page.getByRole("button", { name: "Terminal logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await repairButton.click();

  await expect(terminalDrawer.locator("pre")).toContainText("repair-stats summary", { timeout: 15_000 });
  await expect(repairButton).toHaveCount(0);
  await expect(page.getByTestId("repair-stats-success")).toContainText("Saved checks rebuilt from the current saved claims.");
  await expect(page.getByTestId("repair-stats-success")).toContainText(
    "The current paper now uses the refreshed checks.",
  );
  await expect(page.getByTestId("workbench-ops-reason")).toContainText("checks are ready.");
  await expect(statsSnapshotSummary).toBeVisible();
});

test("backend rebuild stats action stays under advanced controls and overwrites the current snapshot", async ({ page }) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-rebuild-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Refresh checks", exact: true })).toHaveCount(0);
    await expect(page.getByTestId("repair-stats-warning")).toHaveCount(0);
    const savedChecksSection = page.locator("summary").filter({ hasText: "Saved checks" }).first().locator("xpath=ancestor::details[1]");
    await expect(savedChecksSection).toContainText("LEGACY_STATS_FIXTURE", { timeout: 15_000 });
  });

  const statsSnapshotSummary = page.locator("summary").filter({ hasText: "Saved checks" }).first();
  const statsSnapshotSection = statsSnapshotSummary.locator("xpath=ancestor::details[1]");
  const sessionControls = page.getByTestId("workbench-session-controls");
  await sessionControls.locator("summary").click();

  const advancedActions = sessionControls
    .getByTestId("stats-advanced-controls")
    .filter({ hasText: "Review maintenance" })
    .first();
  await expect(advancedActions).toBeVisible();
  const advancedSummary = advancedActions.locator("summary").first();
  if (await advancedSummary.count()) {
    await advancedSummary.click();
  }

  const rebuildButton = advancedActions.getByRole("button", { name: "Rebuild saved checks", exact: true });
  await expect(rebuildButton).toBeVisible();
  await expect(advancedActions).toContainText("Rebuild saved checks from the latest saved claims");

  await page.getByRole("button", { name: "Terminal logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await rebuildButton.click();

  await expect(page.getByTestId("rebuild-stats-warning")).toContainText("Rebuilding saved checks...");
  await expect(terminalDrawer.locator("pre")).toContainText("repair-stats summary: mode=rebuild", { timeout: 15_000 });
  await expect(page.getByTestId("rebuild-stats-success")).toContainText("Existing saved checks were replaced from the current saved claims.");
  await expect(page.getByTestId("rebuild-stats-success")).toContainText(
    "The current paper now uses the refreshed checks.",
  );
  await expect(statsSnapshotSection).toContainText("AUTO_GENERATED_FROM_CLAIMSET");
  await expect(statsSnapshotSection).not.toContainText("LEGACY_STATS_FIXTURE");
});

test("backend workbench can cancel an active deep read run from the browser", async ({ page, request }) => {
  const paperId = "paper-e2e-rebuild-001";
  const enqueueResponse = await request.post(`${backendBaseUrl}/jobs/deepread`, {
    data: { paper_id: paperId },
  });
  expect(enqueueResponse.ok()).toBeTruthy();
  const enqueuePayload = (await enqueueResponse.json()) as {
    job_id?: string;
    status?: string;
  };
  expect(typeof enqueuePayload.job_id).toBe("string");
  expect(enqueuePayload.status).toBe("queued");
  const jobId = enqueuePayload.job_id!;

  await gotoUntilLive(page, `/workbench/${paperId}`, async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Cancel run" })).toBeVisible({ timeout: 15_000 });
  });

  await page.getByRole("button", { name: "Terminal logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Cancel run" }).click();

  await expect(page.getByTestId("cancel-run-success")).toContainText(
    "The current deep read was cancelled. Existing saved artifacts stay as-is.",
  );
  await expect(page.getByRole("button", { name: "Run deep read" })).toBeVisible();
  await expect(terminalDrawer.locator("pre")).toContainText("cancelled", { timeout: 15_000 });

  await expect
    .poll(async () => {
      const jobResponse = await request.get(`${backendBaseUrl}/jobs/${jobId}`);
      if (!jobResponse.ok()) {
        return "request_failed";
      }
      const payload = (await jobResponse.json()) as { status?: string };
      return payload.status ?? "missing";
    })
    .toBe("cancelled");

  await expect
    .poll(async () => {
      const actions = await listUserActions(request, paperId);
      return actions.some(
        (action) =>
          action.action_type === "deepread_cancel_requested" &&
          action.source === "workbench" &&
          action.payload?.job_id === jobId,
      );
    })
    .toBe(true);
});

test("backend runtime readiness page surfaces live runtime checks in the browser", async ({ page }) => {
  await page.goto("/ready");

  await expect(page.getByRole("heading", { name: "Check whether this workspace is ready for real runs" })).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-product-loop")).toContainText("Current product loop");
  await expect(page.getByTestId("runtime-readiness-overall")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-config_file")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("runtime-readiness-check-watch_folder")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("runtime-readiness-check-downloads_watch_dir")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("runtime-readiness-check-pdf_storage_dir")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("runtime-readiness-check-ui_bundle")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("runtime-readiness-open-papers")).toContainText("Open Paper Notes");
  await expect(page.getByTestId("runtime-readiness-open-papers")).toHaveAttribute("href", "/papers#import-pdf");
  await expect(page.getByTestId("runtime-readiness-product-loop")).toContainText("Import or reopen a paper, land in the saved note");
  await expect(page.getByTestId("runtime-readiness-next-step")).toContainText("open the saved note right away");
  await expect(page.getByTestId("runtime-readiness-suggested-fixes")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-fix-pickup")).toContainText("Use manual import while pickup is unavailable");
  await expect(page.getByTestId("runtime-readiness-fix-pickup")).toContainText("open the saved note right away");
  await expect(page.getByTestId("runtime-readiness-fix-pickup").getByRole("link", { name: "Open Import PDF" })).toHaveAttribute(
    "href",
    "/papers#import-pdf",
  );
  await expect(page.getByTestId("runtime-readiness-fallback")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Reload checks" })).toBeVisible();
});

test("backend runtime readiness page keeps the ready-state handoff clear when checks are healthy", async ({ page }) => {
  await page.route("**/health/ready", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        checks: [
          {
            name: "config_file",
            status: "ok",
            detail: "Config file is available for the live runtime.",
            path: "/tmp/paperpipe/config.yaml",
          },
          {
            name: "watch_folder",
            status: "ok",
            detail: "Automatic pickup watch folder is configured.",
            path: "/tmp/paperpipe/watch",
          },
          {
            name: "downloads_watch_dir",
            status: "ok",
            detail: "Downloads watch folder is configured.",
            path: "/tmp/paperpipe/downloads",
          },
          {
            name: "pdf_storage_dir",
            status: "ok",
            detail: "Imported PDFs have writable storage.",
            path: "/tmp/paperpipe/pdfs",
          },
          {
            name: "backend_entrypoint",
            status: "ok",
            detail: "Backend entrypoint imports cleanly.",
          },
          {
            name: "ui_bundle",
            status: "ok",
            detail: "Frontend bundle is present for the current app entry.",
          },
        ],
      }),
    });
  });

  await page.goto("/ready");

  await expect(page.getByRole("heading", { name: "Check whether this workspace is ready for real runs" })).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-overall")).toContainText("Ready");
  await expect(page.getByTestId("runtime-readiness-next-step")).toContainText(
    "This machine looks ready for the current paper-first loop.",
  );
  await expect(page.getByTestId("runtime-readiness-open-papers")).toHaveAttribute("href", "/papers");
  await expect(page.getByTestId("runtime-readiness-open-meeting-packs")).toHaveAttribute("href", "/meeting-packs");
  await expect(page.getByTestId("runtime-readiness-product-loop")).toContainText("Meeting Packs");
  await expect(page.getByTestId("runtime-readiness-research-dna-note")).toContainText("paperpipe research-dna");
  await expect(page.getByTestId("runtime-readiness-check-watch_folder")).toContainText(
    "Automatic pickup watch folder is configured.",
  );
  await expect(page.getByTestId("runtime-readiness-suggested-fixes")).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-fallback")).toHaveCount(0);
});

test("backend runtime readiness page keeps the fallback handoff clear when the endpoint is unavailable", async ({ page }) => {
  await page.route("**/health/ready", async (route) => {
    await route.abort();
  });

  await page.goto("/ready");

  await expect(page.getByRole("heading", { name: "Check whether this workspace is ready for real runs" })).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-fallback")).toContainText("Showing diagnostic fallback");
  await expect(page.getByTestId("runtime-readiness-overall")).toContainText("Blocked");
  await expect(page.getByTestId("runtime-readiness-check-runtime_readiness")).toContainText(
    "Runtime checks could not be loaded.",
  );
  await expect(page.getByTestId("runtime-readiness-next-step")).toContainText(
    "Restore the live backend signal first",
  );
  await expect(page.getByTestId("runtime-readiness-open-papers")).toHaveAttribute("href", "/papers");
  await expect(page.getByTestId("runtime-readiness-open-meeting-packs")).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-suggested-fixes")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-fix-live-backend")).toContainText(
    "Restore the live backend signal",
  );
  await expect(page.getByTestId("runtime-readiness-fix-live-backend")).toContainText(
    "Disable forced mock mode or start the live backend",
  );
});

test("paper notes import anchor focuses the manual import fallback on the live route", async ({ page }) => {
  await page.goto("/papers#import-pdf");

  await expect(page.getByRole("heading", { name: "Paper Notes", exact: true })).toBeVisible();
  await expect(page.getByTestId("paper-notes-import-callout")).toBeVisible();
  await expect(page.getByTestId("paper-notes-import-button")).toBeFocused();
});

test("backend settings API key field supports clipboard paste on the live route", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "LLM provider" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.getByLabel("Provider").selectOption("gemini");
  await expect(page.getByRole("textbox", { name: "Model", exact: true })).toHaveValue("gemini-2.5-flash");
  await page.evaluate(() => navigator.clipboard.writeText("sk-lattice-backend-paste-key"));
  await page.getByRole("button", { name: "Paste key" }).click();

  await expect(page.getByLabel("API key")).toHaveValue("sk-lattice-backend-paste-key");
  await expect(page.getByText("API key pasted. Save settings when ready.")).toBeVisible();
});

test("backend sync to obsidian uses the same inline feedback pattern as other workbench actions", async ({ page }) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  const syncButton = page.getByRole("button", { name: "Sync to Obsidian", exact: true });
  await expect(syncButton).toBeVisible();
  await expect(syncButton).toBeEnabled();
  await syncButton.click();

  await page.getByRole("button", { name: "Terminal logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();
  await expect(terminalDrawer.locator("pre")).toContainText("obsidian-sync summary", { timeout: 15_000 });
  await expect(page.getByTestId("sync-obsidian-success")).toContainText("Obsidian sync completed.");
});

test("backend workbench reuses the same operational state summary language as list and rail", async ({ page }) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-list-missing-stats-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
  });

  await expect(page.getByText("Mock mode")).toHaveCount(0);
  const selectedRailPaper = page.locator("aside").getByRole("button").filter({ hasText: "E2E List Missing Stats Paper" }).first();
  await expect(selectedRailPaper).toBeVisible({ timeout: 15_000 });
  await expect(selectedRailPaper.getByTestId("rail-access-badge")).toContainText("Local PDF");
  await expect(selectedRailPaper.getByTestId("rail-ops-badge")).toContainText("Action needed");
  await expect(selectedRailPaper.getByTestId("rail-ops-reason")).toContainText("Saved note checks are missing or empty.");
  await expect(page.getByTestId("workbench-access-badge")).toContainText("Local PDF");
  await expect(page.getByTestId("workbench-access-link")).toContainText("Open saved PDF");
  await expect(page.getByTestId("workbench-ops-summary")).toBeVisible();
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Action needed");
  await expect(page.getByTestId("workbench-ops-reason")).toContainText("Saved note checks are missing or empty.");
  await expect(page.getByTestId("workbench-workspace-context")).toContainText("Claim review");
  await expect(page.getByTestId("workbench-workspace-context")).toContainText(
    "No claim review flags are recorded in the current paper summary.",
  );
  await expect(page.getByTestId("workbench-header-review-badge")).toHaveCount(0);
});

test("backend workbench keeps shared access labels aligned across rail and header", async ({ page }) => {
  const openAccessUrl = "https://example.org/papers/e2e-seed-paper.pdf";
  const institutionAccessUrl = "https://proxy.example.edu/login?url=https://doi.org/10.1000/e2e-list-missing-stats";

  await page.route("**/papers/rail?*", async (route) => {
    const response = await route.fetch();
    const payload = (await response.json()) as Array<Record<string, unknown>>;
    const updatedPayload = payload.map((paper) => {
      if (paper.paper_id === "paper-e2e-001") {
        return {
          ...paper,
          access_summary: {
            status_label: "open",
            open_access_url: openAccessUrl,
          },
        };
      }
      if (paper.paper_id === "paper-e2e-list-missing-stats-001") {
        return {
          ...paper,
          access_summary: {
            status_label: "institution_required",
            institution_access_url: institutionAccessUrl,
          },
        };
      }
      return paper;
    });
    await route.fulfill({
      response,
      json: updatedPayload,
    });
  });

  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  const selectedRailPaper = page.locator("aside").getByRole("button").filter({ hasText: "E2E Seed Paper" }).first();
  await expect(selectedRailPaper).toBeVisible({ timeout: 15_000 });
  await expect(selectedRailPaper.getByTestId("rail-access-badge")).toContainText("Open access");

  const institutionRailPaper = page
    .locator("aside")
    .getByRole("button")
    .filter({ hasText: "E2E List Missing Stats Paper" })
    .first();
  await expect(institutionRailPaper).toBeVisible({ timeout: 15_000 });
  await expect(institutionRailPaper.getByTestId("rail-access-badge")).toContainText("Institution route");

  await expect(page.getByTestId("workbench-workspace-context")).toContainText("Access");
  await expect(page.getByTestId("workbench-access-badge")).toContainText("Open access");
  await expect(page.getByTestId("workbench-access-link")).toContainText("Open available PDF");
  await expect(page.getByTestId("workbench-access-link")).toHaveAttribute("href", openAccessUrl);
});

test("backend workbench surfaces the latest compiled knowledge card for note-backed papers", async ({ page, request }) => {
  const synthesisResponse = await request.get(
    `${backendBaseUrl}/paper-syntheses?paper_slug=${encodeURIComponent(noteBackedWorkbenchSlug)}`,
  );
  expect(synthesisResponse.ok()).toBeTruthy();
  const synthesisPayload = (await synthesisResponse.json()) as {
    items: Array<{
      synthesis_id: string;
      readiness: string;
      freshness: string;
      source_ref_count: number;
      evidence_ref_count: number;
      warning_count: number;
      lineage_summary: {
        answer_route: string;
        present_required_source_kinds: string[];
        review_artifact_kinds: string[];
      };
    }>;
    total: number;
  };
  expect(synthesisPayload.total).toBeGreaterThan(0);
  const latest = synthesisPayload.items[0];
  expect(latest).toBeTruthy();

  await openWorkbenchLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchPaperId)}`, async () => {
    await expect(page.getByTestId("workbench-paper-synthesis")).toBeVisible({ timeout: 15_000 });
  });
  const compiledKnowledgeCard = page.getByTestId("workbench-paper-synthesis");
  await expect(compiledKnowledgeCard).toBeVisible();
  await expect(compiledKnowledgeCard).toContainText("Compiled knowledge");
  await expect(compiledKnowledgeCard).toContainText("Non-canonical");
  await expect(compiledKnowledgeCard).toContainText(latest.readiness.replaceAll("_", " "));
  await expect(compiledKnowledgeCard).toContainText(latest.freshness);
  await expect(compiledKnowledgeCard).toContainText(String(latest.source_ref_count));
  await expect(compiledKnowledgeCard).toContainText(String(latest.evidence_ref_count));
  await expect(compiledKnowledgeCard).toContainText(String(latest.warning_count));
  await expect(compiledKnowledgeCard.getByTestId("workbench-paper-synthesis-answer-route")).toContainText(
    "Canonical state -> upstream evidence",
  );
  await expect(compiledKnowledgeCard.getByTestId("workbench-paper-synthesis-lineage")).toContainText("structured state");
  await expect(compiledKnowledgeCard.getByTestId("workbench-paper-synthesis-lineage")).toContainText("resolved claimset");
  await expect(compiledKnowledgeCard.getByTestId("workbench-paper-synthesis-lineage")).toContainText("run metadata");
  if (latest.lineage_summary.review_artifact_kinds.includes("quality_gate")) {
    await expect(compiledKnowledgeCard.getByTestId("workbench-paper-synthesis-lineage")).toContainText("quality gate");
  }
  if (latest.lineage_summary.review_artifact_kinds.includes("acceptance_contract")) {
    await expect(compiledKnowledgeCard.getByTestId("workbench-paper-synthesis-lineage")).toContainText("acceptance contract");
  }
  await expect(compiledKnowledgeCard.getByRole("link", { name: "Open markdown" })).toHaveAttribute(
    "href",
    `/api/paper-syntheses/${latest.synthesis_id}/markdown`,
  );
});

test("backend workbench can inspect compiled knowledge source refs without leaving the card", async ({ page, request }) => {
  const synthesisResponse = await request.get(
    `${backendBaseUrl}/paper-syntheses?paper_slug=${encodeURIComponent(noteBackedWorkbenchSlug)}`,
  );
  expect(synthesisResponse.ok()).toBeTruthy();
  const synthesisPayload = (await synthesisResponse.json()) as {
    items: Array<{
      synthesis_id: string;
      lineage_summary: {
        answer_route: string;
      };
    }>;
    total: number;
  };
  expect(synthesisPayload.total).toBeGreaterThan(0);
  const latest = synthesisPayload.items[0];
  expect(latest).toBeTruthy();

  const detailResponse = await request.get(
    `${backendBaseUrl}/paper-syntheses/${encodeURIComponent(latest.synthesis_id)}/manifest`,
  );
  expect(detailResponse.ok()).toBeTruthy();
  const detailPayload = (await detailResponse.json()) as {
    source_refs: Array<{
      kind: string;
      path?: string | null;
    }>;
  };
  expect(detailPayload.source_refs.length).toBeGreaterThanOrEqual(3);

  const countMatchingActions = (actions: BackendUserAction[]): number =>
    actions.filter(
      (action) =>
        action.action_type === "workbench_open_paper_synthesis_source_refs" &&
        action.source === "ui" &&
        action.payload?.origin === "compiled_knowledge_card" &&
        action.payload?.paper_slug === noteBackedWorkbenchSlug &&
        action.payload?.synthesis_id === latest.synthesis_id &&
        action.payload?.answer_route === latest.lineage_summary.answer_route,
    ).length;

  const baselineActions = countMatchingActions(await listUserActions(request, noteBackedWorkbenchPaperId));

  await openWorkbenchLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchPaperId)}`, async () => {
    await expect(page.getByTestId("workbench-paper-synthesis")).toBeVisible({ timeout: 15_000 });
  });

  const compiledKnowledgeCard = page.getByTestId("workbench-paper-synthesis");
  await expect(compiledKnowledgeCard).toBeVisible();
  await compiledKnowledgeCard.getByText("Inspect source refs", { exact: true }).click();

  const sourceRefsPanel = compiledKnowledgeCard.getByTestId("workbench-paper-synthesis-source-refs");
  await expect(sourceRefsPanel.getByTestId("workbench-paper-synthesis-source-ref")).toHaveCount(
    detailPayload.source_refs.length,
  );
  await expect(sourceRefsPanel).toContainText("structured state");
  await expect(sourceRefsPanel).toContainText("resolved claimset");
  await expect(sourceRefsPanel).toContainText("run metadata");
  for (const ref of detailPayload.source_refs) {
    const fileName = ref.path?.split("/").pop();
    if (fileName) {
      await expect(sourceRefsPanel).toContainText(fileName);
    }
  }

  await expect
    .poll(async () => countMatchingActions(await listUserActions(request, noteBackedWorkbenchPaperId)))
    .toBe(baselineActions + 1);
});

test("backend workbench logs compiled knowledge markdown opens as auditable user actions", async ({ page, request }) => {
  const synthesisResponse = await request.get(
    `${backendBaseUrl}/paper-syntheses?paper_slug=${encodeURIComponent(noteBackedWorkbenchSlug)}`,
  );
  expect(synthesisResponse.ok()).toBeTruthy();
  const synthesisPayload = (await synthesisResponse.json()) as {
    items: Array<{
      synthesis_id: string;
      readiness: string;
      freshness: string;
    }>;
    total: number;
  };
  expect(synthesisPayload.total).toBeGreaterThan(0);
  const latest = synthesisPayload.items[0];
  expect(latest).toBeTruthy();

  const countMatchingActions = (actions: BackendUserAction[]): number =>
    actions.filter(
      (action) =>
        action.action_type === "workbench_open_paper_synthesis_markdown" &&
        action.source === "ui" &&
        action.payload?.origin === "compiled_knowledge_card" &&
        action.payload?.paper_slug === noteBackedWorkbenchSlug &&
        action.payload?.synthesis_id === latest.synthesis_id &&
        action.payload?.readiness === latest.readiness &&
        action.payload?.freshness === latest.freshness &&
        action.payload?.run_id === "run_e2e_note_backed_bbox_001",
    ).length;

  const baselineActions = countMatchingActions(await listUserActions(request, noteBackedWorkbenchPaperId));

  await openWorkbenchLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchPaperId)}`, async () => {
    await expect(page.getByTestId("workbench-paper-synthesis")).toBeVisible({ timeout: 15_000 });
  });

  const compiledKnowledgeCard = page.getByTestId("workbench-paper-synthesis");
  await expect(compiledKnowledgeCard).toBeVisible();
  const openMarkdownLink = compiledKnowledgeCard.getByRole("link", { name: "Open markdown" });
  const [popup] = await Promise.all([page.waitForEvent("popup"), openMarkdownLink.click()]);
  await expect(popup).toHaveURL(new RegExp(`/api/paper-syntheses/${latest.synthesis_id}/markdown$`));
  await popup.close();

  await expect
    .poll(async () => countMatchingActions(await listUserActions(request, noteBackedWorkbenchPaperId)))
    .toBe(baselineActions + 1);
});

test("backend workbench keeps the compiled knowledge card honest when no synthesis is saved", async ({ page, request }) => {
  const synthesisResponse = await request.get(`${backendBaseUrl}/paper-syntheses?paper_slug=${encodeURIComponent(noteSlug)}`);
  expect(synthesisResponse.ok()).toBeTruthy();
  const synthesisPayload = (await synthesisResponse.json()) as { items: unknown[]; total: number };
  expect(synthesisPayload.total).toBe(0);

  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByTestId("workbench-paper-synthesis")).toBeVisible({ timeout: 15_000 });
  });

  const compiledKnowledgeCard = page.getByTestId("workbench-paper-synthesis");
  await expect(compiledKnowledgeCard).toBeVisible();
  await expect(compiledKnowledgeCard).toContainText("Compiled knowledge");
  await expect(compiledKnowledgeCard).toContainText(
    "This optional lane holds compiled markdown only. It never replaces canonical state or raw-source review.",
  );
  await expect(compiledKnowledgeCard).toContainText("No saved paper synthesis is available for this paper yet.");
  await expect(compiledKnowledgeCard.getByRole("link", { name: "Open markdown" })).toHaveCount(0);
});

test("backend workbench shows inference boundary summary", async ({ page }) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByTestId("workbench-inference-summary")).toBeVisible({ timeout: 15_000 });
  });

  const inferenceCard = page.getByTestId("workbench-inference-summary");
  await expect(inferenceCard).toBeVisible();
  await expect(inferenceCard.getByTestId("workbench-inference-backend")).toContainText("backend: mixed");
  await expect(inferenceCard.getByTestId("workbench-inference-payload")).toContainText("payload: mixed");
  await expect(inferenceCard.getByTestId("workbench-inference-redaction")).toContainText("redaction applied");
  await expect(inferenceCard.getByTestId("workbench-inference-lane-reader")).toContainText("local only");
  await expect(inferenceCard.getByTestId("workbench-inference-lane-clinical_extraction")).toContainText(
    "external allowed",
  );
  await expect(inferenceCard.getByTestId("workbench-inference-lane-clinical_extraction")).toContainText("openai");
  await expect(inferenceCard.getByTestId("workbench-inference-lane-clinical_extraction")).toContainText(
    "gpt-5.4-mini",
  );
});

test("backend workbench shows requested and resolved parser backends separately", async ({ page }) => {
  await openWorkbenchLive(page, `/workbench/${encodeURIComponent(parserFallbackWorkbenchPaperId)}`);
  await expect(page.getByTestId("workbench-parser-selection").first()).toContainText(
    "Document reader PDF text (requested Docling)",
  );

  await page.getByRole("button", { name: "Terminal logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();
  await expect(terminalDrawer.locator("pre")).toContainText(
    "document reader selected: PDF text (requested Docling)",
  );
});

test("backend workbench does not infer requested parser from route query when persisted job metadata is absent", async ({
  page,
}) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-repair-001?parser_backend=docling", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  await expect(page.getByTestId("workbench-parser-selection")).toHaveCount(0);
});

test("backend workbench reuses the live paper list when selecting another paper", async ({ page }) => {
  let papersRequestCount = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/papers/rail?limit=5000")) {
      papersRequestCount += 1;
    }
  });

  await openWorkbenchLive(page, "/workbench/paper-e2e-001");
  await page.waitForTimeout(250);
  const initialPapersRequestCount = papersRequestCount;
  expect(initialPapersRequestCount).toBeGreaterThan(0);

  await searchPaperList(page, "Note-backed BBox");
  await page.getByRole("button", { name: /E2E Note-backed BBox Fixture/i }).click();

  await expect(page).toHaveURL(new RegExp(`/workbench/${noteBackedWorkbenchPaperId}$`));
  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await page.waitForTimeout(250);
  expect(papersRequestCount).toBe(initialPapersRequestCount);
});

test("backend home to workbench navigation reuses the live paper list", async ({ page }) => {
  let papersRequestCount = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/papers/rail?limit=5000")) {
      papersRequestCount += 1;
    }
  });

  await openHomeLive(page);
  await page.waitForTimeout(250);
  const initialPapersRequestCount = papersRequestCount;
  expect(initialPapersRequestCount).toBeGreaterThan(0);

  await searchPaperList(page, "Seed Paper");
  const seededPaper = page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" }).first();
  await seededPaper.click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001$/);
  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await page.waitForTimeout(250);
  expect(papersRequestCount).toBe(initialPapersRequestCount);
});

test("backend workbench to home navigation reuses the live paper list", async ({ page }) => {
  let papersRequestCount = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/papers/rail?limit=5000")) {
      papersRequestCount += 1;
    }
  });

  await openWorkbenchLive(page, "/workbench/paper-e2e-001");
  await page.waitForTimeout(250);
  const initialPapersRequestCount = papersRequestCount;
  expect(initialPapersRequestCount).toBeGreaterThan(0);

  await page.getByRole("link", { name: "Home" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible();
  await page.waitForTimeout(250);
  expect(papersRequestCount).toBe(initialPapersRequestCount);
});

test("backend workbench refresh avoids an extra note-detail fallback lookup when canonical paper detail exists", async ({
  page,
}) => {
  let noteDetailFallbackRequestCount = 0;
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/api/paper-notes/") && !url.includes("/api/paper-notes/resolve-by-paper-id")) {
      noteDetailFallbackRequestCount += 1;
    }
  });

  await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });
  await page.waitForTimeout(250);
  const initialNoteDetailFallbackRequestCount = noteDetailFallbackRequestCount;

  await page.getByRole("button", { name: "Refresh", exact: true }).click();

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await page.waitForTimeout(250);
  expect(noteDetailFallbackRequestCount).toBe(initialNoteDetailFallbackRequestCount);
});

test("backend workbench canonicalizes stripped note-backed paper ids in the route", async ({ page }) => {
  await gotoUntilLive(page, "/workbench/duboisAlzheimerDiseaseClinicalBiological2024", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });
  await expect(page).toHaveURL(/\/workbench\/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024$/);
});

test("backend workbench canonicalizes slug-backed note routes from rail note identity without a slug structured lookup", async ({
  page,
}) => {
  let slugResolveRequestCount = 0;
  let canonicalResolveRequestCount = 0;
  let slugPaperDetailRequestCount = 0;
  page.on("request", (request) => {
    const url = request.url();
    if (
      url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}`) &&
      !url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}/pdf`)
    ) {
      slugPaperDetailRequestCount += 1;
    }
    if (!url.includes("/api/paper-notes/resolve-by-paper-id")) {
      return;
    }
    if (url.includes(`paper_id=${encodeURIComponent(noteBackedWorkbenchSlug)}`)) {
      slugResolveRequestCount += 1;
    }
    if (url.includes(`paper_id=${encodeURIComponent(noteBackedWorkbenchPaperId)}`)) {
      canonicalResolveRequestCount += 1;
    }
  });

  await page.goto(`/workbench/${encodeURIComponent(noteBackedWorkbenchSlug)}`);

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`/workbench/${noteBackedWorkbenchPaperId}$`));
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
  expect(slugPaperDetailRequestCount).toBe(0);
  expect(slugResolveRequestCount).toBe(0);
  expect(canonicalResolveRequestCount).toBeGreaterThanOrEqual(1);
  expect(canonicalResolveRequestCount).toBeLessThanOrEqual(2);
});

test("backend workbench uses slug paper detail directly after a slug structured lookup miss when rail cache is unavailable", async ({
  page,
}) => {
  let slugPaperDetailRequestCount = 0;
  let canonicalPaperDetailRequestCount = 0;
  let slugResolveRequestCount = 0;

  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.route(
    `**/paper-notes/resolve-by-paper-id?paper_id=${encodeURIComponent(noteBackedWorkbenchSlug)}`,
    async (route) => {
      slugResolveRequestCount += 1;
      if (slugResolveRequestCount === 1) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "not found" }),
        });
        return;
      }
      await route.fallback();
    },
  );

  page.on("request", (request) => {
    const url = request.url();
    if (
      url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}`) &&
      !url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}/pdf`)
    ) {
      slugPaperDetailRequestCount += 1;
    }
    if (
      url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchPaperId)}`) &&
      !url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchPaperId)}/pdf`)
    ) {
      canonicalPaperDetailRequestCount += 1;
    }
  });

  await gotoUntilLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchSlug)}`, async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  await expect(page).toHaveURL(new RegExp(`/workbench/${noteBackedWorkbenchPaperId}$`));
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
  expect(slugPaperDetailRequestCount).toBe(1);
  expect(canonicalPaperDetailRequestCount).toBe(0);
  expect(slugResolveRequestCount).toBe(1);
});

test("backend workbench reuses canonical structured lookup before note-detail synthesis when the first slug lookup misses", async ({
  page,
}) => {
  let slugStructuredLookupRequestCount = 0;
  let canonicalStructuredLookupRequestCount = 0;
  let slugPaperDetailRequestCount = 0;
  let canonicalPaperDetailRequestCount = 0;
  let slugNoteDetailRequestCount = 0;

  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.route(
    `**/paper-notes/resolve-by-paper-id?paper_id=${encodeURIComponent(noteBackedWorkbenchSlug)}`,
    async (route) => {
      slugStructuredLookupRequestCount += 1;
      if (slugStructuredLookupRequestCount === 1) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "not found" }),
        });
        return;
      }
      await route.fallback();
    },
  );

  await page.route(
    `**/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}`,
    async (route) => {
      if (route.request().url().includes(`/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}/pdf`)) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not found" }),
      });
    },
  );

  page.on("request", (request) => {
    const url = request.url();
    if (
      url.includes("/api/paper-notes/resolve-by-paper-id") &&
      url.includes(`paper_id=${encodeURIComponent(noteBackedWorkbenchPaperId)}`)
    ) {
      canonicalStructuredLookupRequestCount += 1;
    }
    if (
      url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}`) &&
      !url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}/pdf`)
    ) {
      slugPaperDetailRequestCount += 1;
    }
    if (
      url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchPaperId)}`) &&
      !url.includes(`/api/papers/${encodeURIComponent(noteBackedWorkbenchPaperId)}/pdf`)
    ) {
      canonicalPaperDetailRequestCount += 1;
    }
    if (url.includes(`/api/paper-notes/${encodeURIComponent(noteBackedWorkbenchSlug)}`)) {
      slugNoteDetailRequestCount += 1;
    }
  });

  await gotoUntilLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchSlug)}`, async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  await expect(page).toHaveURL(new RegExp(`/workbench/${noteBackedWorkbenchPaperId}$`));
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
  expect(slugStructuredLookupRequestCount).toBe(1);
  expect(canonicalStructuredLookupRequestCount).toBe(1);
  expect(slugPaperDetailRequestCount).toBe(1);
  expect(canonicalPaperDetailRequestCount).toBe(0);
  expect(slugNoteDetailRequestCount).toBe(0);
});

test("backend workbench synthesizes from structured lookup without note-detail fetch when canonical paper detail is missing", async ({
  page,
}) => {
  let slugStructuredLookupRequestCount = 0;
  let canonicalStructuredLookupRequestCount = 0;
  let slugNoteDetailRequestCount = 0;
  let canonicalPaperDetailRequestCount = 0;

  await page.route("**/papers/rail?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.route(
    `**/paper-notes/resolve-by-paper-id?paper_id=${encodeURIComponent(noteBackedWorkbenchSlug)}`,
    async (route) => {
      slugStructuredLookupRequestCount += 1;
      if (slugStructuredLookupRequestCount === 1) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "not found" }),
        });
        return;
      }
      await route.fallback();
    },
  );

  await page.route(
    `**/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}`,
    async (route) => {
      if (route.request().url().includes(`/papers/${encodeURIComponent(noteBackedWorkbenchSlug)}/pdf`)) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not found" }),
      });
    },
  );

  await page.route(
    `**/papers/${encodeURIComponent(noteBackedWorkbenchPaperId)}`,
    async (route) => {
      if (route.request().url().includes(`/papers/${encodeURIComponent(noteBackedWorkbenchPaperId)}/pdf`)) {
        await route.fallback();
        return;
      }
      canonicalPaperDetailRequestCount += 1;
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not found" }),
      });
    },
  );

  page.on("request", (request) => {
    const url = request.url();
    if (
      url.includes("/api/paper-notes/resolve-by-paper-id") &&
      url.includes(`paper_id=${encodeURIComponent(noteBackedWorkbenchPaperId)}`)
    ) {
      canonicalStructuredLookupRequestCount += 1;
    }
    if (url.includes(`/api/paper-notes/${encodeURIComponent(noteBackedWorkbenchSlug)}`)) {
      slugNoteDetailRequestCount += 1;
    }
  });

  await gotoUntilLive(page, `/workbench/${encodeURIComponent(noteBackedWorkbenchSlug)}`, async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
  });

  await expect(page).toHaveURL(new RegExp(`/workbench/${noteBackedWorkbenchPaperId}$`));
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
  expect(slugStructuredLookupRequestCount).toBe(1);
  expect(canonicalStructuredLookupRequestCount).toBeGreaterThanOrEqual(1);
  expect(canonicalPaperDetailRequestCount).toBe(0);
  expect(slugNoteDetailRequestCount).toBe(0);
});

test("backend workbench deep read run resolves parser fallback in the browser flow", async ({ page, request }) => {
  test.skip(!runParserWorkerLane, "requires dedicated parser worker lane");

  await openWorkbenchLive(page, "/workbench/paper-e2e-001?parser_backend=docling");

  await page.getByRole("button", { name: /Run deep read/i }).first().click();

  await expect
    .poll(async () => {
      const response = await request.get(`${backendBaseUrl}/jobs?paper_id=paper-e2e-001`);
      if (!response.ok()) {
        return "request_failed";
      }
      const payload = (await response.json()) as unknown;
      const jobs =
        Array.isArray(payload)
          ? payload
          : payload && typeof payload === "object" && Array.isArray((payload as { jobs?: unknown[] }).jobs)
            ? (payload as { jobs: unknown[] }).jobs
            : [];
      return jobs.some((job) => {
        if (!job || typeof job !== "object") {
          return false;
        }
        const row = job as { requested_parser_backend?: unknown; parser_backend?: unknown; status?: unknown };
        return (
          row.requested_parser_backend === "docling" &&
          row.parser_backend === "fitz_pdfplumber" &&
          row.status === "completed"
        );
      })
        ? "completed"
        : "pending";
    }, { timeout: 15_000 })
    .toBe("completed");

  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  if (!(await terminalDrawer.getByText("Terminal Logs", { exact: true }).isVisible().catch(() => false))) {
    await page.getByRole("button", { name: /^Terminal logs$/ }).first().click({ force: true });
  }
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();
  await expect
    .poll(async () => (await terminalDrawer.locator("pre").textContent()) ?? "", { timeout: 15_000 })
    .toMatch(/deepread enqueued|User queued deep read/);
  await expect
    .poll(async () => (await terminalDrawer.locator("pre").textContent()) ?? "", { timeout: 15_000 })
    .toMatch(/resolved parser backend: fitz_pdfplumber|\[INFO\] completed/);
  const sessionControls = page.getByTestId("workbench-session-controls");
  await expect(sessionControls).toBeVisible();
  await sessionControls.locator("summary").click();
  await expect(page.getByTestId("workbench-parser-selection").first()).toContainText(
    "Document reader PDF text (requested Docling)",
    { timeout: 15_000 },
  );
});

test("backend parser completion does not overwrite the next selected paper", async ({ page, request }) => {
  test.skip(!runParserWorkerLane, "requires dedicated parser worker lane");

  await openWorkbenchLive(page, "/workbench/paper-e2e-001?parser_backend=docling");

  await page.getByRole("button", { name: /Run deep read/i }).first().click();
  await page.getByRole("button", { name: /E2E Note-backed BBox Fixture/i }).click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-note-backed-bbox-001\?parser_backend=docling$/);
  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();

  await expect
    .poll(async () => {
      const response = await request.get(`${backendBaseUrl}/jobs?paper_id=paper-e2e-001`);
      if (!response.ok()) {
        return "request_failed";
      }
      const payload = (await response.json()) as unknown;
      const jobs =
        Array.isArray(payload)
          ? payload
          : payload && typeof payload === "object" && Array.isArray((payload as { jobs?: unknown[] }).jobs)
            ? (payload as { jobs: unknown[] }).jobs
            : [];
      return jobs.some((job) => {
        if (!job || typeof job !== "object") {
          return false;
        }
        const row = job as { requested_parser_backend?: unknown; parser_backend?: unknown; status?: unknown };
        return (
          row.requested_parser_backend === "docling" &&
          row.parser_backend === "fitz_pdfplumber" &&
          row.status === "completed"
        );
      })
        ? "completed"
        : "pending";
    }, { timeout: 15_000 })
    .toBe("completed");

  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  const noteBackedClaimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(
    noteBackedClaimsPanel.getByRole("button", {
      name: /The intervention shows an initial improvement window during early follow-up\./,
    }),
  ).toBeVisible();
  await expect(page.getByTestId("workbench-parser-selection").first()).toContainText("Requested document reader Docling");
});

test("backend workbench preserves content review context when opened in issue focus mode", async ({ page }) => {
  await gotoUntilLive(page, "/workbench/paper-e2e-list-missing-stats-001?focus=issues", async () => {
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.getByTestId("content-review-notice")).toContainText("Risk focus is on, but no claim review flags are recorded.", {
      timeout: 15_000,
    });
  });

  const workspaceContext = page.getByTestId("workbench-workspace-context");
  await expect(workspaceContext).toContainText("Workspace context");
  await expect(workspaceContext).toContainText("Access");
  await expect(workspaceContext).toContainText(
    "Keep access, saved checks, and claim review status aligned while you validate evidence.",
  );
  await expect(workspaceContext).toContainText("Saved review state");
  await expect(workspaceContext).toContainText("Claim review");
  await expect(page.getByTestId("workbench-header-ops-badge")).toBeVisible();
  await expect(page.getByTestId("workbench-header-review-badge")).toBeVisible();
  await expect(page.getByTestId("workbench-header-review-hint")).toContainText(/claim review/i);
  await expect(page.getByTestId("content-review-notice")).toContainText("Risk focus is on, but no claim review flags are recorded.");
  await expect(page.getByTestId("content-review-notice")).toContainText("Saved checks stay separate. Risk focus only changes which claims are surfaced first.");
  await expect(page.getByTestId("workbench-content-review-summary")).toBeVisible();
  await expect(page.getByTestId("workbench-content-review-badge")).toContainText("Clear");
  await expect(page.getByTestId("workbench-content-review-hint")).toContainText("No claim review flags in the current paper summary.");
  await expect(page.getByTestId("workbench-content-review-detail")).toContainText("Risk focus is on");
});

test.describe("mobile backend UX", () => {
  test.use({ viewport: { width: 390, height: 844 } });

test("mobile workbench renders collapsed controls without mock fallback", async ({ page }) => {
    await gotoUntilLive(page, "/workbench/paper-e2e-001", async () => {
      await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText("Mock mode")).toHaveCount(0);
      await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible({ timeout: 15_000 });
    });

    const workbenchControls = page.locator("details").filter({ hasText: "Review controls" }).first();
    await expect(workbenchControls).toBeVisible();
    await workbenchControls.locator("summary").first().click();
    await expect(workbenchControls.getByTestId("workbench-review-actions-mobile")).toContainText("Review actions");
    await expect(workbenchControls.getByTestId("workbench-session-setup-mobile")).toContainText("Session setup");

    const controlsSummary = workbenchControls.getByTestId("stats-advanced-controls").locator("summary").first();
    await expect(controlsSummary).toBeVisible();
    await controlsSummary.click();

    await expect(workbenchControls.getByRole("button", { name: /Run deep read/i })).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
  });

  test("mobile paper notes detail opens side panel sheet", async ({ page }) => {
    await gotoUntilLive(page, `/papers/${noteSlug}`, async () => {
      await expect(
        page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
      ).toBeVisible({ timeout: 15_000 });
    });

    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await expect(sidePanelButton).toContainText("Note panels");
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Note panels" })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Properties", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Outline", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Section navigator", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Related Papers", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "References", exact: true })).toBeVisible();
  });

  test("mobile paper notes detail auto-opens side panel for deep-link focus", async ({ page }) => {
    await gotoUntilLive(page, `/papers/${noteSlug}?focus=evidence:${evidenceId}`, async () => {
      await expect(
        page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
      ).toBeVisible({ timeout: 15_000 });
    });
    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();

    const evidenceCard = sheet.locator(focusDomId("evidence", evidenceId));
    await expect(evidenceCard).toBeVisible();
    await expect(evidenceCard).toHaveClass(/ring-2/);
    await expect(evidenceCard).toContainText("chunk-e2e-001");
  });

  test("mobile paper notes sheet includes structured actions and structured claims cards", async ({ page }) => {
    await gotoUntilLive(page, `/papers/${structuredNoteSlug}`, async () => {
      await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible({
        timeout: 15_000,
      });
    });
    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading").nth(2)).toHaveText("Saved claims");
    await expectHeadingOrder(
      sheet,
      ["Saved note state", "Saved claims", "My note", "Related Papers", "References", "Guarded actions", "Run history", "Properties"],
      "mobile read paper note panel order",
    );
    await expect(sheet.getByRole("heading", { name: "Guarded actions", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Run history", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Saved claims", exact: true })).toBeVisible();
    await expect(sheet).toContainText("Strong: 2 claims, avg confidence 0.81, 0 inconsistent checks.");
    await expect(sheet).toContainText("CSF biomarker evidence aligns with early detection criteria.");
  });

  test("mobile paper notes detail keeps builder debug mode in the sheet ordering", async ({ page }) => {
    await gotoUntilLive(page, `/papers/${structuredNoteSlug}?view=builder_debug`, async () => {
      await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible({
        timeout: 15_000,
      });
    });
    await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText(PAPER_NOTE_REVIEW_MODE_SUMMARY);
    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading").nth(1)).toHaveText("Saved note state");
    await expect(sheet.getByRole("heading").nth(2)).toHaveText("Saved claims");
    await expectHeadingOrder(
      sheet,
      ["Saved note state", "Saved claims", "My note", "Related Papers", "References", "Guarded actions", "Appraisal", "Run history", "Properties"],
      "mobile builder debug paper note panel order",
    );
    await expect(sheet.getByRole("heading", { name: "Guarded actions", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Appraisal", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Properties", exact: true })).toBeVisible();
  });

  test("mobile imported paper note keeps sticky actions aligned with the import bridge", async ({ page }) => {
    await page.goto("/papers");

    await expect(page.getByRole("heading", { name: "Paper Notes", exact: true })).toBeVisible();
    await page.locator('[data-testid="paper-notes-import-input"]').setInputFiles(samplePdfPath);
    await expect(page).toHaveURL(/\/papers\/sample(?:-[a-f0-9]{8})?$/, { timeout: 15_000 });

    const importGuidance = page.getByTestId("paper-note-import-guidance");
    await expect(importGuidance).toContainText("This note is already saved in Lattice.");
    await expect(importGuidance.getByTestId("paper-note-import-guidance-paper-id")).toContainText(/userpdf-[a-f0-9]+/);
    await expect(importGuidance.getByTestId("paper-note-import-guidance-copy-paper-id")).toHaveText("Copy ID");
    await expect(importGuidance.getByTestId("paper-note-import-guidance-open-review")).toBeVisible();
    await expect(importGuidance.getByTestId("paper-note-import-guidance-queue-deepread")).toHaveText("Queue deep read");
    await expect(importGuidance.getByTestId("paper-note-import-guidance-open-pdf")).toBeVisible();

    const stickyActions = page.getByTestId("paper-note-mobile-sticky-actions");
    await expect(stickyActions).toBeVisible();
    await expect(stickyActions.getByTestId("paper-note-mobile-sticky-open-pdf")).toHaveAttribute(
      "href",
      /\/api\/papers\/userpdf-[a-f0-9]+\/pdf$/,
    );
    await expect(stickyActions.getByTestId("paper-note-mobile-sticky-open-review")).toHaveAttribute(
      "href",
      /\/workbench\/userpdf-[a-f0-9]+$/,
    );
    await expect(stickyActions.getByTestId("paper-note-mobile-sticky-save-protocol")).toHaveCount(0);
  });
});

test("paper notes detail renders properties, markdown, related papers, and references", async ({ page }) => {
  await gotoUntilLive(page, `/papers/${noteSlug}`, async () => {
    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible({ timeout: 15_000 });
  });
  const propertiesPanel = page.locator("aside").filter({ hasText: "Properties" }).first();
  await expect(propertiesPanel.getByRole("heading", { name: "Properties" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Outline" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Section navigator" })).toBeVisible();
  await expect(page.getByTestId("paper-note-import-guidance")).toHaveCount(0);
  await expect(propertiesPanel.getByText("INDEXED", { exact: true })).toBeVisible();
  await expect(propertiesPanel.locator("dd").getByText("Medicine/Neurology", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "One-Line Summary" })).toBeVisible();

  const relatedHeading = page.getByRole("heading", { name: "Related Papers" }).first();
  await expect(relatedHeading).toBeVisible();
  const relatedSection = relatedHeading.locator("xpath=ancestor::section[1]");
  const firstRelatedItem = relatedSection.locator("li").first();
  await expect(firstRelatedItem).toBeVisible();
  await expect(firstRelatedItem).toContainText(/shared tags:/i);
  const relatedLink = firstRelatedItem.getByRole("link").first();
  await expect(relatedLink).toBeVisible();
  await expect(relatedLink).toHaveAttribute("href", /\/papers\//);

  const referencesHeading = page.getByRole("heading", { name: "References" }).first();
  await expect(referencesHeading).toBeVisible();
  const referencesSection = referencesHeading.locator("xpath=ancestor::section[1]");
  await expect(referencesSection.getByTestId("paper-note-reference-policy")).toContainText("Access Policy");
  await expect(referencesSection.getByTestId("paper-note-reference-policy")).toContainText("Preferred:");
  await expect(referencesSection.getByRole("link", { name: /Open PDF/i })).toHaveCount(0);
  await expect(referencesSection.getByRole("link", { name: "DOI" })).toBeVisible();
  await expect(referencesSection.getByRole("link", { name: "Zotero" })).toBeVisible();
  await expect(referencesSection.getByTestId("paper-note-reference-policy")).toContainText(
    "avoiding direct PDF exposure",
  );

  const workbenchLink = page.getByRole("link", { name: "Open review" }).first();
  await expect(workbenchLink).toBeVisible();
  await expect(workbenchLink).toHaveAttribute("href", /\/workbench\/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024$/);

  await relatedLink.click();
  await expect(page).toHaveURL(/\/papers\/.+$/);
  await expect(page.getByRole("banner").getByRole("heading")).toBeVisible();
});

test("paper notes detail supports learner and builder debug view modes", async ({ page }) => {
  await gotoUntilLive(page, `/papers/${structuredNoteSlug}?view=builder_debug`, async () => {
    await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible({
      timeout: 15_000,
    });
  });
  await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText(PAPER_NOTE_REVIEW_MODE_SUMMARY);
  const rightAside = page.locator("main > aside").nth(1);
  await expect(rightAside.getByRole("heading").first()).toHaveText("Saved note state");
  await expect(rightAside.getByRole("heading").nth(1)).toHaveText("Saved claims");
  await expectHeadingOrder(
    rightAside,
    ["Saved note state", "Saved claims", "My note", "Related Papers", "References", "Guarded actions", "Appraisal", "Run history", "Properties"],
    "desktop builder debug paper note rail order",
  );
  await expect(rightAside.getByRole("heading", { name: "Guarded actions", exact: true })).toBeVisible();
  await expect(rightAside.getByRole("heading", { name: "Appraisal", exact: true })).toBeVisible();
  const appraisalPanel = page.getByTestId("paper-note-appraisal-panel");
  await expect(appraisalPanel).toContainText("Optional reviewer lane");
  await expect(appraisalPanel.getByTestId("paper-note-appraisal-summary")).toContainText(
    "saved claims, evidence anchors, and recorded checks look internally consistent",
  );
  await expect(appraisalPanel.getByTestId("paper-note-appraisal-sources")).toContainText("claimset.resolved.json");
  await expect(appraisalPanel.getByTestId("paper-note-appraisal-checks")).toContainText("Saved claimset");
  await expect(appraisalPanel.getByTestId("paper-note-appraisal-checks")).toContainText("Review-ready gate");
  await expect(appraisalPanel.getByTestId("paper-note-appraisal-concerns")).toContainText(
    "No evidence-bounded concerns were recorded for this appraisal.",
  );
  await expect(appraisalPanel.getByTestId("paper-note-appraisal-questions")).toContainText(
    "No follow-up questions were generated from this appraisal.",
  );

  await page.getByRole("button", { name: "Read" }).click();
  await expect(page).toHaveURL(new RegExp(`/papers/${structuredNoteSlug}$`));
  await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText(PAPER_NOTE_READ_MODE_SUMMARY);
  await expect(rightAside.getByRole("heading").first()).toHaveText("Saved note state");
  await expect(rightAside.getByRole("heading").nth(1)).toHaveText("Saved claims");
  await expectHeadingOrder(
    rightAside,
    ["Saved note state", "Saved claims", "My note", "Related Papers", "References", "Guarded actions", "Run history", "Properties"],
    "desktop read paper note rail order",
  );
  await expect(rightAside.getByRole("heading", { name: "Properties", exact: true })).toBeVisible();
});

test("paper notes detail renders structured actions, run history, and structured claims cards", async ({ page }) => {
  await gotoUntilLive(page, `/papers/${structuredNoteSlug}`, async () => {
    await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible({
      timeout: 15_000,
    });
  });

  const workspaceContext = page.getByTestId("paper-note-workspace-context");
  await expect(workspaceContext).toContainText("Workspace context");
  await expect(workspaceContext).toContainText("Saved note");
  await expect(workspaceContext).toContainText("Structured state");
  await expect(workspaceContext).toContainText("Workspace mode");
  const reviewSnapshot = page.getByTestId("paper-note-review-snapshot");
  await expect(reviewSnapshot).toContainText("Review snapshot");
  await expect(reviewSnapshot).toContainText("Saved state loaded");
  await expect(reviewSnapshot).toContainText("claims 2");
  await expect(reviewSnapshot).toContainText("evidence 3");
  await expect(reviewSnapshot.getByTestId("paper-note-review-summary")).toContainText("All recorded evidence is currently grounded.");
  await expect(reviewSnapshot.getByTestId("paper-note-review-next-step")).toContainText("open Workbench");
  const reviewBridge = page.getByTestId("paper-note-review-bridge");
  await expect(reviewBridge).toContainText("Review focus");
  await expect(reviewBridge).toContainText("Saved state loaded");
  await expect(reviewBridge.getByTestId("paper-note-review-bridge-status")).toContainText("Trust state");
  await expect(reviewBridge.getByTestId("paper-note-review-bridge-status")).toContainText("Saved claims are available, but evidence depth is still thin.");
  await expect(reviewBridge.getByTestId("paper-note-review-focus-location")).toContainText("Source anchor");
  await expect(reviewBridge.getByTestId("paper-note-review-focus-hint")).toBeVisible();
  const anchorBox = await reviewBridge.getByTestId("paper-note-review-focus-location").boundingBox();
  const claimBox = await reviewBridge.getByTestId("paper-note-review-focus-claim").boundingBox();
  expect(anchorBox).not.toBeNull();
  expect(claimBox).not.toBeNull();
  expect((anchorBox?.y ?? 0) + (anchorBox?.height ?? 0)).toBeLessThan(claimBox?.y ?? Number.POSITIVE_INFINITY);
  await expect(reviewBridge.getByRole("link", { name: "Open review" })).toBeVisible();
  const savedStatePanel = page.getByTestId("paper-note-saved-state-panel");
  await expect(savedStatePanel.getByTestId("paper-note-saved-state-status")).toContainText("Loaded");
  await expect(savedStatePanel).toContainText(`.pp/${structuredNoteSlug}/state.json`);
  await expect(savedStatePanel.getByTestId("paper-note-context-trace-summary")).toContainText("source paths");

  const firstClaimEvidenceMeter = page.getByTestId("paper-note-claim-evidence-meter-claim_structured_001");
  await expect(firstClaimEvidenceMeter).toContainText("Evidence anchors");
  await expect(firstClaimEvidenceMeter).toContainText("2 evidence anchors");
  await expect(firstClaimEvidenceMeter).toContainText("2 not recorded");

  const sectionNavigator = page.getByTestId("paper-note-section-navigator");
  await expect(sectionNavigator).toContainText("Section navigator");
  await expect(sectionNavigator).toContainText("Open saved evidence");
  await expect(sectionNavigator).toContainText("state-only section");

  const propertiesPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Properties", exact: true }) }).first();
  await expect(propertiesPanel).toContainText("4");
  await expect(propertiesPanel).toContainText("yes");
  await expect(propertiesPanel).toContainText("Strong");
  await expect(propertiesPanel.getByTestId("paper-note-section-navigation-signal")).toContainText("Saved signal ready");

  const actionsPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Guarded actions", exact: true }) }).first();
  await expect(actionsPanel.getByRole("button", { name: "Extract Markdown" })).toBeVisible();
  await expect(actionsPanel.getByRole("button", { name: "Validate Citations" })).toBeVisible();
  await expect(actionsPanel.getByRole("button", { name: "Critical Appraisal" })).toBeVisible();
  await expect(actionsPanel.getByRole("button", { name: "Critical Appraisal" })).toBeDisabled();
  await expect(actionsPanel).toContainText("markitdown");
  await expect(actionsPanel).toContainText("citation-management");
  await expect(actionsPanel).toContainText("peer-review");
  await expect(actionsPanel).toContainText("secret E2E_REVIEW_SECRET");
  await expect(actionsPanel.getByTestId("paper-note-action-disabled-reason-critical_appraisal")).toContainText(
    "Blocked: missing required secret E2E_REVIEW_SECRET.",
  );

  const automationPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Run history", exact: true }) }).first();
  await expect(automationPanel).toContainText("critical_appraisal");
  await expect(automationPanel).toContainText("validate_citations");
  await expect(automationPanel).toContainText("Strong: 2 claims, avg confidence 0.81, 0 inconsistent checks.");
  await expect(automationPanel).toContainText("Checked 4 references: 1 verified, 2 local, 1 need review.");
  await expect(automationPanel.getByTestId("paper-note-run-write-scope")).toHaveCount(0);

  const claimsetPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Saved claims", exact: true }) }).first();
  await expect(claimsetPanel).toContainText("CSF biomarker evidence aligns with early detection criteria.");
  await expect(claimsetPanel).toContainText("CSF amyloid and tau shifts separate early-stage cases from controls.");
  await expect(claimsetPanel).toContainText("0.86");
  await expect(claimsetPanel).toContainText("biomarker");
  await expect(claimsetPanel).toContainText("memory");

  const relatedSection = page.locator("section").filter({ has: page.getByRole("heading", { name: "Related Papers", exact: true }) }).first();
  const structuredSignalsPeer = relatedSection.locator("li").filter({ hasText: "Structured Signals Peer Fixture" }).first();
  await expect(structuredSignalsPeer).toBeVisible();
  await expect(structuredSignalsPeer).toContainText("structured signals: Amyloid, biomarker, memory, Neurology");
});

test("paper notes detail evidence meter separates grounded, review-needed, unresolved, and unrecorded anchors", async ({ page }) => {
  await page.route(`**/paper-notes/${encodeURIComponent(structuredNoteSlug)}*`, async (route) => {
    const response = await route.fetch();
    const detail = await response.json();
    const claims = detail.structured_state?.claimset ?? [];
    if (claims[0]?.evidence?.[0]) {
      claims[0].evidence[0].grounded = true;
      claims[0].evidence[0].resolution = "NORMALIZED_MATCH";
    }
    if (claims[0]?.evidence?.[1]) {
      claims[0].evidence[1].grounded = false;
      claims[0].evidence[1].resolution = "AMBIGUOUS_MATCH";
    }
    if (claims[1]?.evidence?.[0]) {
      claims[1].evidence[0].grounded = false;
      claims[1].evidence[0].resolution = "FAILED_MATCH";
    }
    await route.fulfill({
      response,
      json: detail,
    });
  });

  await gotoUntilLive(page, `/papers/${structuredNoteSlug}`, async () => {
    await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible({
      timeout: 15_000,
    });
  });

  await expect(page.getByTestId("paper-note-review-summary")).toContainText(
    "2 saved claims and 3 evidence excerpts are available. 1 grounded, 1 need review, and 1 remain unresolved.",
  );
  await expect(page.getByTestId("paper-note-review-bridge-status")).toContainText(
    "Unresolved evidence is still blocking downstream trust.",
  );

  const firstClaimEvidenceMeter = page.getByTestId("paper-note-claim-evidence-meter-claim_structured_001");
  await expect(firstClaimEvidenceMeter).toContainText("2 evidence anchors");
  await expect(firstClaimEvidenceMeter).toContainText("1 grounded · 1 need review");

  const secondClaimEvidenceMeter = page.getByTestId("paper-note-claim-evidence-meter-claim_structured_002");
  await expect(secondClaimEvidenceMeter).toContainText("1 evidence anchor");
  await expect(secondClaimEvidenceMeter).toContainText("1 unresolved");
});

test("paper notes detail surfaces missing canonical sidecar state separately from loaded-empty state", async ({ page }) => {
  await page.goto(`/papers/${missingStateNoteSlug}`);

  await expect(page.getByRole("banner").getByRole("heading", { name: "Amnestic MCI or prodromal Alzheimer's disease?" })).toBeVisible();

  const savedStatePanel = page.getByTestId("paper-note-saved-state-panel");
  await expect(savedStatePanel.getByTestId("paper-note-saved-state-status")).toContainText("Missing");
  await expect(savedStatePanel).toContainText(`.pp/${missingStateNoteSlug}/state.json`);
  await expect(savedStatePanel).toContainText("No canonical structured sidecar state was available for this note.");

  const automationPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Run history", exact: true }) }).first();
  await expect(automationPanel).toContainText("No saved note state was loaded for this note.");
  await expect(automationPanel).toContainText("Run history only appears after saved note state is available.");

  const claimsetPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Saved claims", exact: true }) }).first();
  await expect(claimsetPanel).toContainText("No saved note state was loaded for this note.");
  await expect(claimsetPanel).toContainText("Saved claims only appear after saved note state is available.");
});

test("paper notes detail deep links focus run, claim, and evidence cards", async ({ page }) => {
  await gotoUntilLive(page, `/papers/${noteSlug}`, async () => {
    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible({ timeout: 15_000 });
  });

  const runCard = page.locator(focusDomId("run", runId));
  const claimCard = page.locator(focusDomId("claim", claimId));
  const evidenceCard = page.locator(focusDomId("evidence", evidenceId));

  await expect(runCard).toBeVisible();
  await expect(claimCard).toBeVisible();
  await expect(evidenceCard).toBeVisible();

  await runCard.locator(`a[href*="focus=${encodedFocus("run", runId)}"]`).click();
  await expect(page).toHaveURL(new RegExp(`\\/papers\\/${noteSlug}\\?focus=${encodedFocus("run", runId)}$`));
  await expect(runCard).toHaveClass(/ring-2/);

  await claimCard.locator(`a[href*="focus=${encodedFocus("claim", claimId)}"]`).click();
  await expect(page).toHaveURL(new RegExp(`\\/papers\\/${noteSlug}\\?focus=${encodedFocus("claim", claimId)}$`));
  await expect(claimCard).toHaveClass(/ring-2/);

  await evidenceCard.locator(`a[href*="focus=${encodedFocus("evidence", evidenceId)}"]`).click();
  await expect(page).toHaveURL(new RegExp(`\\/papers\\/${noteSlug}\\?focus=${encodedFocus("evidence", evidenceId)}$`));
  await expect(evidenceCard).toHaveClass(/ring-2/);
  await expect(evidenceCard).toContainText("page 1");
});

test("structured paper note deep links focus run, claim, and evidence cards", async ({ page }) => {
  await page.goto(`/papers/${structuredNoteSlug}`);

  await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible();

  const runCard = page.locator(focusDomId("run", structuredRunId));
  const claimCard = page.locator(focusDomId("claim", structuredClaimId));
  const evidenceCard = page.locator(focusDomId("evidence", structuredEvidenceId));

  await expect(runCard).toBeVisible();
  await expect(claimCard).toBeVisible();
  await expect(evidenceCard).toBeVisible();

  await runCard.locator(`a[href*="focus=${encodedFocus("run", structuredRunId)}"]`).click();
  await expect(page).toHaveURL(new RegExp(`\\/papers\\/${structuredNoteSlug}\\?focus=${encodedFocus("run", structuredRunId)}$`));
  await expect(runCard).toHaveClass(/ring-2/);

  await claimCard.locator(`a[href*="focus=${encodedFocus("claim", structuredClaimId)}"]`).click();
  await expect(page).toHaveURL(new RegExp(`\\/papers\\/${structuredNoteSlug}\\?focus=${encodedFocus("claim", structuredClaimId)}$`));
  await expect(claimCard).toHaveClass(/ring-2/);

  await evidenceCard.locator(`a[href*="focus=${encodedFocus("evidence", structuredEvidenceId)}"]`).click();
  await expect(page).toHaveURL(new RegExp(`\\/papers\\/${structuredNoteSlug}\\?focus=${encodedFocus("evidence", structuredEvidenceId)}$`));
  await expect(evidenceCard).toHaveClass(/ring-2/);
  await expect(evidenceCard).toContainText("page 3");
});

test("paper notes detail can run validate citations and persist a structured result", async ({ page }) => {
  await gotoUntilLive(page, `/papers/${actionNoteSlug}`, async () => {
  await expect(page.getByRole("banner").getByRole("heading", { name: "Live Validate Citations Fixture" })).toBeVisible({
      timeout: 15_000,
    });
  });

  const automationPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Run history", exact: true }) }).first();
  const runsContainer = automationPanel.locator("article");
  const initialRunCount = await runsContainer.count();

  const runResponse = page.waitForResponse((response) => response.url().includes("/skills/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Validate Citations" }).click();
  const response = await runResponse;
  expect(response.ok()).toBeTruthy();
  const responseJson = (await response.json()) as {
    structured_path: string;
    run: { id: string; action: string; status: string; summary: string };
  };

  await expect(automationPanel.getByText(/^Checked \d+ references:/).first()).toBeVisible();
  await expect(runsContainer).toHaveCount(initialRunCount + 1);
  await expect(automationPanel).toContainText("validate_citations");
  await expect(automationPanel).toContainText("succeeded");
  await expect(automationPanel.getByText("state updated").first()).toBeVisible();
  await expect(automationPanel.getByText("frontmatter updated").first()).toBeVisible();
  await expect(automationPanel.getByText("body summary").first()).toBeVisible();
  const signalDiff = page.getByTestId("paper-note-signal-diff");
  await expect(signalDiff).toContainText("Signal updates");
  await expect(signalDiff).toContainText(/(?:runs:\s*\d+\s*->\s*\d+|new runs:\s*\d+)/);

  const notePath = notePathFor(actionNoteSlug);
  const statePath = statePathFor(actionNoteSlug);
  const runsDir = runsDirFor(actionNoteSlug);
  await expect
    .poll(async () => {
      const noteText = await fs.readFile(notePath, "utf-8");
      return [
        noteText.includes("structured_path: .pp/zoteroliveValidateCitations2026/state.json"),
        noteText.includes("- validate_citations"),
        /citation_count:\s*\d+/.test(noteText),
        noteText.includes("## 🔧 Automation Results (short)"),
      ];
    })
    .toEqual([true, true, true, true]);

  await expect
    .poll(async () => {
      const state = JSON.parse(await fs.readFile(statePath, "utf-8")) as {
        paper_slug: string;
        runs: Array<{ id: string; action: string; status: string }>;
        signals: Record<string, unknown>;
      };
      return {
        paper_slug: state.paper_slug,
        top_run_id: state.runs[0]?.id ?? null,
        top_run_action: state.runs[0]?.action ?? null,
        top_run_status: state.runs[0]?.status ?? null,
        citation_count: state.signals.citation_count ?? null,
      };
    })
    .toEqual({
      paper_slug: actionNoteSlug,
      top_run_id: responseJson.run.id,
      top_run_action: "validate_citations",
      top_run_status: "succeeded",
      citation_count: expect.any(Number),
    });

  await expect
    .poll(async () => {
      const entries = await fs.readdir(runsDir);
      return entries.filter((entry) => entry.endsWith("_validate_citations.json")).length;
    })
    .toBeGreaterThan(0);

  const runArtifacts = JSON.parse(
    await fs.readFile(path.join(runsDir, (await fs.readdir(runsDir)).sort().at(-1) ?? ""), "utf-8"),
  ) as {
    run?: { id?: string; action?: string; status?: string };
    policy?: { network?: string };
  };
  expect(runArtifacts.run?.id).toBe(responseJson.run.id);
  expect(runArtifacts.run?.action).toBe("validate_citations");
  expect(runArtifacts.run?.status).toBe("succeeded");
  expect(runArtifacts.policy?.network).toBe("allowlist");

  await page.reload();
  await expect(page.getByRole("banner").getByRole("heading", { name: "Live Validate Citations Fixture" })).toBeVisible();
  await expect(automationPanel.locator("article")).toHaveCount(initialRunCount + 1);
  await expect(automationPanel).toContainText("validate_citations");
  await expect(page.getByTestId("paper-note-signal-diff")).toHaveCount(0);
});

test("paper notes detail can run validate citations without appending a markdown summary", async ({ page }) => {
  await page.goto(`/papers/${quietActionNoteSlug}`);

  await expect(page.getByRole("banner").getByRole("heading", { name: "Quiet Validate Citations Fixture" })).toBeVisible();
  await expect(page.getByLabel("Add short note summary")).toBeChecked();

  await page.getByLabel("Add short note summary").uncheck();
  await expect(page.getByLabel("Add short note summary")).not.toBeChecked();

  const automationPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Run history", exact: true }) }).first();
  const runsContainer = automationPanel.locator("article");
  const initialRunCount = await runsContainer.count();
  const runResponse = page.waitForResponse((response) => response.url().includes("/skills/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Validate Citations" }).click();
  const response = await runResponse;
  expect(response.ok()).toBeTruthy();
  const responseJson = (await response.json()) as {
    run: { id: string; action: string; status: string; summary: string };
  };

  await expect(automationPanel.getByText(/^Checked \d+ references:/).first()).toBeVisible();
  await expect(page.getByText("Structured state updated without markdown summary.")).toBeVisible();
  await expect(runsContainer).toHaveCount(initialRunCount + 1);
  await expect(automationPanel.getByText("state updated").first()).toBeVisible();
  await expect(automationPanel.getByText("frontmatter updated").first()).toBeVisible();
  await expect(automationPanel.getByText("body skipped").first()).toBeVisible();
  await expect(page.getByTestId("paper-note-signal-diff")).toContainText(/(?:runs:\s*\d+\s*->\s*\d+|new runs:\s*\d+)/);

  const notePath = notePathFor(quietActionNoteSlug);
  const statePath = statePathFor(quietActionNoteSlug);
  const runsDir = runsDirFor(quietActionNoteSlug);
  await expect
    .poll(async () => {
      const noteText = await fs.readFile(notePath, "utf-8");
      return [
        noteText.includes("structured_path: .pp/zoteroquietValidateCitations2026/state.json"),
        noteText.includes("- validate_citations"),
        /citation_count:\s*\d+/.test(noteText),
        noteText.includes("## 🔧 Automation Results (short)"),
      ];
    })
    .toEqual([true, true, true, false]);

  await expect
    .poll(async () => {
      const state = JSON.parse(await fs.readFile(statePath, "utf-8")) as {
        paper_slug: string;
        runs: Array<{ id: string; action: string; status: string }>;
        signals: Record<string, unknown>;
      };
      return {
        paper_slug: state.paper_slug,
        top_run_id: state.runs[0]?.id ?? null,
        top_run_action: state.runs[0]?.action ?? null,
        top_run_status: state.runs[0]?.status ?? null,
        citation_count: state.signals.citation_count ?? null,
      };
    })
    .toEqual({
      paper_slug: quietActionNoteSlug,
      top_run_id: responseJson.run.id,
      top_run_action: "validate_citations",
      top_run_status: "succeeded",
      citation_count: expect.any(Number),
    });

  await expect
    .poll(async () => {
      const entries = await fs.readdir(runsDir);
      return entries.filter((entry) => entry.endsWith("_validate_citations.json")).length;
    })
    .toBeGreaterThan(0);
});

test("paper notes detail resets quiet-run controls when navigating to another note", async ({ page }) => {
  await page.goto(`/papers/${quietActionNoteSlug}`);

  await expect(page.getByRole("banner").getByRole("heading", { name: "Quiet Validate Citations Fixture" })).toBeVisible();
  await page.getByLabel("Add short note summary").uncheck();
  await expect(page.getByLabel("Add short note summary")).not.toBeChecked();

  const runResponse = page.waitForResponse((response) => response.url().includes("/skills/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Validate Citations" }).click();
  const response = await runResponse;
  expect(response.ok()).toBeTruthy();

  const relatedPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Related Papers", exact: true }) }).first();
  await relatedPanel.getByRole("link", { name: "Live Validate Citations Fixture" }).click();

  await expect(page).toHaveURL(new RegExp(`\\/papers\\/${actionNoteSlug}$`));
  await expect(page.getByRole("banner").getByRole("heading", { name: "Live Validate Citations Fixture" })).toBeVisible();
  await expect(page.getByLabel("Add short note summary")).toBeChecked();
  await expect(page.getByText("Structured state updated without markdown summary.")).toHaveCount(0);
  await expect(page.getByTestId("paper-note-signal-diff")).toHaveCount(0);
});

test("paper notes list supports command-style tag selection", async ({ page }) => {
  await page.goto("/papers");

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  const tagCommand = page.getByTestId("paper-notes-tag-command");
  const tagInput = page.getByTestId("paper-notes-tag-input");
  await expect(tagCommand).toBeVisible();
  await tagInput.fill("Medicine");

  const option = page.getByTestId("paper-notes-tag-option").filter({ hasText: "Medicine/Neurology" }).first();
  await expect(option).toBeVisible();
  await option.click();

  await expect(page.getByTestId("paper-notes-selected-tag").filter({ hasText: "Medicine/Neurology" })).toBeVisible();
  await expect(page).toHaveURL(/tags=Medicine%2FNeurology/);
  await expect(page.getByText("No notes matched the current filters.")).toHaveCount(0);
});

test("paper notes list supports structured-only quick toggle", async ({ page }) => {
  await gotoUntilLive(page, "/papers", async () => {
    await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Loading notes...")).toHaveCount(0);
    await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Live Validate Citations Fixture" })).toHaveCount(1);
  });
  const toggle = page.getByTestId("paper-notes-structured-toggle");
  await expect(toggle).toBeVisible();
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Live Validate Citations Fixture" })).toHaveCount(1);

  await toggle.click();

  await expect(page).toHaveURL(/structured=1/);
  await expect(page.getByTestId("paper-notes-active-structured-filter")).toContainText("structured notes only");
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first()).toBeVisible();
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Live Validate Citations Fixture" })).toHaveCount(0);

  await toggle.click();

  await expect(page).not.toHaveURL(/structured=1/);
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Live Validate Citations Fixture" })).toHaveCount(1);
});

test("paper notes list active filters keep removal and recovery controls in keyboard order", async ({ page }) => {
  await gotoUntilLive(page, "/papers?tags=Medicine%2FNeurology&structured=1", async () => {
    await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible({ timeout: 15_000 });
  });
  await expect(page.getByTestId("paper-notes-selected-tag").filter({ hasText: "Medicine/Neurology" })).toBeVisible();
  await expect(page.getByTestId("paper-notes-active-structured-filter")).toContainText("structured notes only");

  const localeAssistToggles = await page
    .locator('[data-testid="paper-notes-reading-assist-toggle"], [data-testid^="paper-notes-reading-assist-toggle-"]')
    .evaluateAll((elements) =>
      elements.map((element) => ({
        testid: element.getAttribute("data-testid") ?? "",
        text: (element.textContent ?? "").replace(/\s+/g, " ").trim(),
      })),
    );

  const filterToggles = await page
    .locator(
      '[data-testid="paper-notes-starred-toggle"], [data-testid^="paper-notes-triage-toggle-"], [data-testid="paper-notes-structured-toggle"]',
    )
    .evaluateAll((elements) =>
      elements.map((element) => ({
        testid: element.getAttribute("data-testid") ?? "",
        text: (element.textContent ?? "").replace(/\s+/g, " ").trim(),
      })),
    );

  const stops = await captureTabOrder(page, 20);
  expect(stops[0]).toMatchObject({ tag: "BUTTON", text: "Import PDF", testid: "paper-notes-import-button" });
  expect(stops[1]).toMatchObject({ tag: "A", text: "Check automatic pickup setup" });
  expect(stops[2]).toMatchObject({ tag: "INPUT", name: "Search papers" });
  expect(stops[3]).toMatchObject({ tag: "INPUT", name: "Search tags" });

  const selectedTagIndex = requireFocusIndex(
    stops,
    (entry) => entry.tag === "BUTTON" && entry.testid === "paper-notes-selected-tag" && entry.name === "Remove tag Medicine/Neurology",
    "selected tag removal should stay in the primary filter cluster",
  );
  const clearSelectedTagsIndex = requireFocusIndex(
    stops,
    (entry) => entry.tag === "BUTTON" && entry.name === "Clear selected tags",
    "clear selected tags should remain adjacent to the selected tag chip",
  );
  const statusIndex = requireFocusIndex(stops, (entry) => entry.tag === "SELECT" && entry.name === "Status", "status filter should stay keyboard-reachable");
  const sortIndex = requireFocusIndex(stops, (entry) => entry.tag === "SELECT" && entry.name === "Sort", "sort filter should stay keyboard-reachable");
  const sortOrderIndex = requireFocusIndex(stops, (entry) => entry.tag === "BUTTON" && entry.name === "Toggle sort order", "sort direction should stay keyboard-reachable");
  const pageSizeIndex = requireFocusIndex(stops, (entry) => entry.tag === "SELECT" && entry.name === "Page size", "page size should stay keyboard-reachable");
  expect(selectedTagIndex).toBeGreaterThan(3);
  expect(clearSelectedTagsIndex).toBeGreaterThan(selectedTagIndex);
  expect(statusIndex).toBeGreaterThan(clearSelectedTagsIndex);
  expect(sortIndex).toBeGreaterThan(statusIndex);
  expect(sortOrderIndex).toBeGreaterThan(sortIndex);
  expect(pageSizeIndex).toBeGreaterThan(sortOrderIndex);

  let previousIndex = pageSizeIndex;
  for (const { testid, text } of filterToggles) {
    const index = requireFocusIndex(
      stops,
      (entry) => entry.tag === "BUTTON" && entry.testid === testid && entry.text === text,
      `${testid} should remain in the active-filter control cluster`,
    );
    expect(index).toBeGreaterThan(previousIndex);
    previousIndex = index;
  }

  const readingAssistIndex = requireFocusIndex(
    stops,
    (entry) =>
      entry.tag === "BUTTON" &&
      entry.testid === "paper-notes-reading-assist-available-toggle" &&
      entry.text === "Reading assist available",
    "reading-assist availability toggle should remain in the active-filter control cluster",
  );
  expect(readingAssistIndex).toBeGreaterThan(previousIndex);
  previousIndex = readingAssistIndex;

  for (const { testid, text } of localeAssistToggles) {
    const index = requireFocusIndex(
      stops,
      (entry) => entry.tag === "BUTTON" && entry.testid === testid && entry.text === text,
      `${testid} should remain in the locale assist control cluster`,
    );
    expect(index).toBeGreaterThan(previousIndex);
    previousIndex = index;
  }

  const clearAllFiltersIndex = requireFocusIndex(
    stops,
    (entry) => entry.tag === "BUTTON" && entry.name === "Clear all filters",
    "clear filters should remain reachable after the active filter toggles",
  );
  expect(clearAllFiltersIndex).toBeGreaterThan(previousIndex);
});

test("paper notes list surfaces action-needed state using workbench vocabulary", async ({ page }) => {
  await gotoUntilLive(page, "/papers?q=List%20Missing", async () => {
    await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("paper-notes-visible-summary")).toContainText("Visible now");
    await expect(page.getByTestId("paper-notes-visible-summary")).toContainText("Needs review");
    await expect(page.getByTestId("paper-notes-visible-summary")).toContainText("Repair first");
    await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "E2E List Missing Stats Note" }).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  const row = page.getByTestId("paper-note-list-row").filter({ hasText: "E2E List Missing Stats Note" }).first();
  await expect(row).toBeVisible();
  await expect(row.getByTestId("paper-note-ops-badge")).toContainText("Action needed");
  await expect(row).toContainText("Saved note checks are missing or empty.");
  await expect(row).toContainText("Open the workbench to refresh the saved note checks.");
  const nextAction = row.getByTestId("paper-note-next-action");
  await expect(nextAction).toContainText("Next action");
  await expect(nextAction).toContainText("Refresh checks in Workbench");
  await expect(nextAction.getByTestId("paper-note-next-action-review")).toHaveAttribute("href", /\/workbench\//);
  await expect(nextAction.getByTestId("paper-note-next-action-note")).toHaveAttribute("href", /\/papers\//);
});

test("paper notes list finds structured-signal matches and surfaces structured affordances", async ({ page }) => {
  await gotoUntilLive(page, "/papers?q=Amyloid%20Neurology", async () => {
    await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Loading notes...")).toHaveCount(0);
    await expect(page.getByText("relevance first")).toBeVisible();
    await expect(page.getByTestId("paper-notes-visible-summary")).toContainText("Structured");
    await expect(
      page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first(),
    ).toBeVisible();
  });

  const row = page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first();
  await expect(row).toBeVisible();
  await expect(row).toContainText("Saved note");
  await expect(row).toContainText("Structured tags");
  await expect(row).toContainText("Claims saved");
  await expect(row).toContainText("4 cites");
  await expect(row).toContainText("Appraisal: Strong");
  await expect(row).toContainText("Claim topics biomarker");
  const signals = row.getByTestId("paper-note-list-signals");
  await expect(signals).toContainText("Structured tags");
  await expect(signals.getByTestId("paper-note-list-signal-chip").first()).toContainText("Amyloid");
  await expect(signals.getByTestId("paper-note-list-signal-chip").nth(1)).toContainText("Neurology");
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="true"]')).toHaveCount(2);
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="true"]').first()).toContainText("Amyloid");
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="true"]').nth(1)).toContainText("Neurology");
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="false"]').first()).toContainText(/Tau|memory|biomarker/);
  await expect(row).toContainText("Medicine/Neurology");
  const nextAction = row.getByTestId("paper-note-next-action");
  await expect(nextAction).toContainText("Saved note context is ready for grounded evidence review.");
  await expect(nextAction.getByTestId("paper-note-next-action-review")).toContainText("Resume review");
  await expect(nextAction.getByTestId("paper-note-next-action-note")).toContainText("Open note");
  await expect(page.getByText("No notes matched the current filters.")).toHaveCount(0);
});

test("paper notes list surfaces missing saved-state truth before detail entry", async ({ page }) => {
  await page.goto("/papers?q=prodromal", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  const row = page.getByTestId("paper-note-list-row").filter({ hasText: "Amnestic MCI or prodromal Alzheimer's disease?" }).first();
  await expect(row).toBeVisible();
  await expect(row).toContainText("Needs saved note");
});

test("paper notes list supports quoted exact-phrase search", async ({ page }) => {
  await page.goto('/papers?q=%22Clinical-Biological%20Construct%22', { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  await expect(page.getByText("relevance first")).toBeVisible();
  await expect(
    page.getByTestId("paper-note-list-row").filter({ hasText: "Alzheimer Disease as a Clinical-Biological Construct" }).first(),
  ).toBeVisible();
});

test("paper notes list empty state explains structured-only misses", async ({ page }) => {
  await page.goto("/papers?q=List%20Missing&structured=1", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  const emptyState = page.getByTestId("paper-notes-empty-state");
  await expect(emptyState).toContainText("No structured notes matched this search.");
  await expect(emptyState).toContainText("Try turning off the structured-notes filter or broadening the search terms.");
  await expect(emptyState.getByTestId("paper-notes-empty-clear-structured")).toBeVisible();

  await emptyState.getByTestId("paper-notes-empty-clear-structured").click();

  await expect(page).not.toHaveURL(/structured=1/);
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "E2E List Missing Stats Note" })).toHaveCount(1);
});

test("paper notes first empty state offers starter actions when no notes are indexed", async ({ page }) => {
  await page.route("**/paper-notes*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        generated_at: "2026-04-17T00:00:00Z",
        index_path: "/tmp/paper-notes-empty.json",
        total: 0,
        page: 1,
        page_size: 24,
        total_pages: 1,
        available_tags: [],
        available_statuses: [],
        available_reading_assist_note_count: 0,
        available_reading_assist_locales: [],
        items: [],
      }),
    });
  });

  await page.goto("/papers", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Home" })).toHaveCount(0);
  await expect(page.getByText("Start here", { exact: true })).toBeVisible();
  await expect(page.getByText("Import your first PDF", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "If automatic pickup is not ready on this machine, import one PDF here. Lattice opens the saved note immediately so you can keep going from the paper detail.",
      { exact: true },
    ),
  ).toBeVisible();

  const emptyState = page.getByTestId("paper-notes-empty-state");
  await expect(emptyState).toContainText("No notes are indexed yet.");
  await expect(
    emptyState.getByText(
      "Start with one PDF on this machine. If automatic pickup is not ready yet, import it here and Lattice will open the saved note right away.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(emptyState.getByTestId("paper-notes-empty-import")).toBeVisible();
  await expect(emptyState.getByTestId("paper-notes-empty-runtime")).toHaveAttribute("href", "/ready");
  await expect(emptyState).toContainText("Import one paper, then continue from the saved note detail.");
});

test("paper notes list empty state can remove quotes from an exact-phrase miss", async ({ page }) => {
  await page.goto('/papers?q=%22Amyloid%20Neurology%22', { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  const emptyState = page.getByTestId("paper-notes-empty-state");
  await expect(emptyState).toContainText("No notes matched this exact phrase.");
  await expect(emptyState).toContainText("Try removing quotes to search by individual terms instead of an exact phrase.");
  await expect(emptyState.getByTestId("paper-notes-empty-remove-quotes")).toBeVisible();

  await emptyState.getByTestId("paper-notes-empty-remove-quotes").click();

  await expect(page).not.toHaveURL(/%22/);
  await expect(page.getByText("relevance first")).toBeVisible();
  await expect(
    page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first(),
  ).toBeVisible();
});

test("paper notes list empty state suggests token-based recovery searches", async ({ page }) => {
  await page.goto("/papers?q=Amyloid%20placebo", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  const emptyState = page.getByTestId("paper-notes-empty-state");
  await expect(emptyState).toContainText("No notes matched the current filters.");
  await expect(emptyState.getByTestId("paper-notes-empty-search-term").filter({ hasText: "Search Amyloid" })).toBeVisible();
  await expect(emptyState.getByTestId("paper-notes-empty-search-term").filter({ hasText: "Search placebo" })).toBeVisible();

  await emptyState.getByTestId("paper-notes-empty-search-term").filter({ hasText: "Search Amyloid" }).click();

  await expect(page).toHaveURL(/q=amyloid$/);
  await expect(page.getByText("relevance first")).toBeVisible();
  await expect(
    page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first(),
  ).toBeVisible();
});

test("soft-gate canary: intentional backend e2e failure drill", async () => {
  test.skip(!runSoftGateCanary, "Set PAPERPIPE_E2E_CANARY=1 to run intentional failure drill.");
  expect(1).toBe(2);
});

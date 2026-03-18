import { expect, test, type APIRequestContext, type Locator } from "@playwright/test";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const runSoftGateCanary = process.env.PAPERPIPE_E2E_CANARY === "1";
const runRealSmoke = process.env.PAPERPIPE_REAL_SMOKE === "1";
const requireRealSmokeCandidates = process.env.PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES === "1";
const backendPort = process.env.E2E_BACKEND_PORT ?? "18080";
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const noteSlug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024";
const noteBackedWorkbenchPaperId = "paper-e2e-note-backed-bbox-001";
const methodComparisonAlphaPaperId = "paper-e2e-methodcmp-alpha-001";
const methodComparisonBetaPaperId = "paper-e2e-methodcmp-beta-001";
const structuredNoteSlug = "zoterostructuredSkillsClaimset2026";
const actionNoteSlug = "zoteroliveValidateCitations2026";
const quietActionNoteSlug = "zoteroquietValidateCitations2026";
const runId = "skill-20260226T130003000000+0000-critical_appraisal";
const claimId = "claim_c0ffee000001";
const evidenceId = "evidence_deadbeef0001";
const structuredRunId = "skill-20260309T090000Z-critical_appraisal";
const structuredClaimId = "claim_structured_001";
const structuredEvidenceId = "evidence_structured_001";
const e2eSpecDir = path.dirname(fileURLToPath(import.meta.url));
const e2eVaultPath = path.resolve(e2eSpecDir, "..", ".e2e-backend-runtime", "obsidian");
const e2eMethodComparisonsRoot = path.resolve(
  e2eSpecDir,
  "..",
  ".e2e-backend-runtime",
  "storage",
  "method_comparisons",
);

function focusDomId(kind: "run" | "claim" | "evidence", id: string): string {
  return `#pp-focus-${kind}-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function encodedFocus(kind: "run" | "claim" | "evidence", id: string): string {
  return `${kind}%3A${encodeURIComponent(id)}`;
}

function notePathFor(slug: string): string {
  return path.join(e2eVaultPath, "Inbox", "PaperPipe", `${slug}.md`);
}

function statePathFor(slug: string): string {
  return path.join(e2eVaultPath, ".pp", slug, "state.json");
}

function runsDirFor(slug: string): string {
  return path.join(e2eVaultPath, ".pp", slug, "runs");
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
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator("tr").filter({ hasText: "E2E List Missing Stats Paper" }).first()).toBeVisible();

  // backend-seeded paper should be visible and navigable
  const seededPaper = page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" }).first();
  await expect(seededPaper).toBeVisible();
  await seededPaper.click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001/);
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByLabel("Reasoning").first()).toBeVisible();
  await expect(page.getByLabel("Profile").first()).toBeVisible();
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.getByText("Obsidian sync payload preview")).toBeVisible();
  await expect(page.getByText("Claim text missing")).toHaveCount(0);
  await expect(page.locator("aside").getByRole("button").filter({ hasText: "E2E List Missing Stats Paper" }).first()).toBeVisible();
});

test("backend triage separates content review cues from operational state", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Content Review" })).toBeVisible();

  const row = page.locator("tbody tr").filter({ hasText: "E2E List Missing Stats Paper" }).first();
  await expect(row.getByTestId("triage-ops-badge")).toContainText("Action needed");
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review clear");
  await expect(row.getByTestId("triage-review-hint")).toContainText("No content flags");
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

  await expect(page.getByRole("heading", { name: "E2E Multi-paper Method Comparison" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
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

test("backend triage content review action carries flagged context into workbench", async ({ page }) => {
  await page.goto("/");

  const row = page.locator("tbody tr").filter({ hasText: "E2E Content Review Paper" }).first();
  await expect(row.getByTestId("triage-ops-badge")).toContainText("Healthy");
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review 2 issues");
  await expect(row.getByTestId("triage-review-detail")).toContainText("2 mapping ambiguities");
  await row.getByTestId("triage-content-review-button").click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-content-review-001\?focus=issues/);
  await expect(page.getByTestId("content-review-notice")).toContainText("2 content review flags available.");
  await expect(page.getByTestId("content-review-notice-detail")).toContainText("2 mapping ambiguities");
  await expect(page.getByTestId("content-review-notice")).toContainText("Issue focus is enabled.");
  await expect(
    page.locator("aside").getByRole("button").filter({ hasText: "E2E Content Review Paper" }).getByTestId("rail-review-detail"),
  ).toContainText("2 mapping ambiguities");
  await expect(page.getByTestId("workbench-content-review-badge")).toContainText("2 flagged");
  await expect(page.getByTestId("workbench-content-review-hint")).toContainText("Content QA flags are separate from artifact health.");
  await expect(page.getByTestId("workbench-content-review-detail")).toContainText("2 mapping ambiguities");
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Healthy");
});

test("backend keeps unavailable content review distinct from clear state", async ({ page }) => {
  await page.goto("/");

  const row = page.locator("tbody tr").filter({ hasText: "E2E Content Review Unavailable Paper" }).first();
  await expect(row.getByTestId("triage-ops-badge")).toContainText("Healthy");
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review unavailable");
  await expect(row.getByTestId("triage-content-review-button")).toBeDisabled();
  await expect(row.getByTestId("triage-review-badge")).toContainText("Unavailable");
  await expect(row.getByTestId("triage-review-hint")).toContainText("Content review has not been generated");
  await expect(row.getByTestId("triage-review-detail")).toContainText("Not analyzed");
  await row.click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-content-review-unavailable-001$/);
  await expect(page.getByTestId("content-review-notice")).toContainText("Content review is not available yet.");
  await expect(page.getByTestId("content-review-notice-detail")).toContainText("Not analyzed");
  await expect(page.getByTestId("workbench-content-review-badge")).toContainText("Unavailable");
  await expect(page.getByTestId("workbench-content-review-hint")).toContainText("Content review has not been generated");
  await expect(page.getByTestId("workbench-content-review-detail")).toContainText("Not analyzed");
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Healthy");
  await expect(
    page.locator("aside").getByRole("button").filter({ hasText: "E2E Content Review Unavailable Paper" }).getByTestId("rail-review-unavailable-badge"),
  ).toContainText("QA unavailable");
  await expect(
    page.locator("aside").getByRole("button").filter({ hasText: "E2E Content Review Unavailable Paper" }).getByTestId("rail-review-detail"),
  ).toContainText("Not analyzed");
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
    await page.goto(`/workbench/${encodeURIComponent(paperId)}`);
    await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
    await expect(page.getByText("Mock mode")).toHaveCount(0);

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
    await expect(highlightLike).toBeVisible({ timeout: 10_000 });
    const firstBadgeText = (await linkBadge.textContent()) ?? "";

    await claimButtons.nth(secondClaimIndex).click();
    await expect(linkBadge).toBeVisible({ timeout: 10_000 });
    await expect(highlightLike).toBeVisible({ timeout: 10_000 });
    const secondBadgeText = (await linkBadge.textContent()) ?? "";
    expect(secondBadgeText).toMatch(/p\.\d+/);
    if (secondBadgeText.trim() === firstBadgeText.trim()) {
      expect(secondBadgeText).toContain("Text Match");
    }

    validated += 1;
  }

  expect(validated).toBeGreaterThan(0);
});

test("backend evidence linking keeps single highlight and updates bbox on claim change", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

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
  await page.goto(`/workbench/${encodeURIComponent(noteBackedWorkbenchPaperId)}`);

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button", { name: /The intervention shows an initial improvement window during early follow-up\./ })).toBeVisible();
  await expect(claimsPanel.getByText("Stale artifact claim should be replaced by canonical sidecar state.")).toHaveCount(0);

  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();
  await expect(pdfPanel.getByText("Text Match")).toHaveCount(0);

  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(highlight).toBeVisible();
  await expect(page.locator('[data-testid="claim-search-highlight"]')).toHaveCount(0);

  const highlightBox = await highlight.boundingBox();
  expect(highlightBox).not.toBeNull();
  if (highlightBox) {
    expect(highlightBox.width).toBeGreaterThan(24);
    expect(highlightBox.height).toBeGreaterThan(24);
  }
});

test("backend stats snapshot disambiguates claim target by text signal", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(mirrorPanel).toBeVisible();

  const targetCheck = mirrorPanel.getByRole("button").filter({ hasText: "effect-size-disambiguation" }).first();
  await expect(targetCheck).toBeVisible();
  await targetCheck.click();

  await expect(page.getByText("Claim Link · p.2")).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
});

test("backend evidence review gestures append user actions", async ({ page, request }) => {
  await page.goto("/workbench/paper-e2e-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(claimsPanel).toBeVisible();
  await expect(mirrorPanel).toBeVisible();

  await claimsPanel.getByRole("button").nth(1).click();
  await mirrorPanel.locator("details").filter({ hasText: "Claims Snapshot" }).first().getByRole("button").first().click();
  await mirrorPanel.getByRole("button").filter({ hasText: "effect-size-disambiguation" }).first().click();

  await expect.poll(async () => {
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
  }).toEqual({
    selectClaim: true,
    mirrorJump: true,
    statsJump: true,
  });
});

test("backend cross-page claim change keeps viewer mounted and re-targets highlight", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

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
  await page.goto("/workbench/paper-e2e-repair-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  const timelinePanel = page.locator("section").filter({ hasText: "Timeline" }).first();
  await expect(timelinePanel).toBeVisible();
  await expect(timelinePanel.getByText("No events in this filter yet.")).toHaveCount(0);
  await expect(timelinePanel.getByText("Repair fixture loaded")).toBeVisible();
});

test("backend timeline surfaces user-triggered actions distinctly", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  const timelinePanel = page.locator("section").filter({ hasText: "Timeline" }).first();
  await expect(timelinePanel).toBeVisible();
  await expect(timelinePanel.getByTestId("timeline-pinned-user-action")).toContainText("User");
  await expect(timelinePanel.getByTestId("timeline-source-user-action").first()).toContainText("USER");
  await expect(timelinePanel.getByText("User queued deep read")).toBeVisible();
});

test("backend repair stats action appears only when stats artifact is missing and hides after repair", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-repair-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  const repairButton = page.getByRole("button", { name: "Repair Stats", exact: true });
  const statsSnapshotSummary = page.locator("summary").filter({ hasText: "Stats Snapshot" });
  await expect(page.getByText("Obsidian sync payload preview")).toBeVisible();
  await expect(page.getByTestId("repair-stats-warning")).toContainText("Stats report is missing or empty.", { timeout: 15_000 });
  await expect(repairButton).toBeVisible();
  await expect(statsSnapshotSummary).toHaveCount(0);

  await page.getByRole("button", { name: "Show Terminal Logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await repairButton.click();

  await expect(terminalDrawer.locator("pre")).toContainText("repair-stats summary", { timeout: 15_000 });
  await expect(repairButton).toHaveCount(0);
  await expect(page.getByTestId("repair-stats-success")).toContainText("Stats repair completed.");
  await expect(page.getByText("Stats report contains 1 checks.")).toBeVisible();
  await expect(statsSnapshotSummary).toBeVisible();
});

test("backend rebuild stats action stays under advanced controls and overwrites the current snapshot", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-rebuild-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Repair Stats", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("repair-stats-warning")).toHaveCount(0);
  const statsSnapshotSummary = page.locator("summary").filter({ hasText: "Stats Snapshot" }).first();
  const statsSnapshotSection = statsSnapshotSummary.locator("xpath=ancestor::details[1]");
  await expect(statsSnapshotSection).toContainText("LEGACY_STATS_FIXTURE");

  const advancedActions = page.locator('[data-testid="stats-advanced-controls"]').filter({ hasText: "Advanced actions" }).first();
  await expect(advancedActions).toBeVisible();
  await advancedActions.locator("summary").click();

  const rebuildButton = advancedActions.getByRole("button", { name: "Rebuild Stats", exact: true });
  await expect(rebuildButton).toBeVisible();
  await expect(advancedActions).toContainText("Rebuild overwrites the current Stats Snapshot");

  await page.getByRole("button", { name: "Show Terminal Logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await rebuildButton.click();

  await expect(page.getByTestId("rebuild-stats-warning")).toContainText("Rebuilding stats snapshot...");
  await expect(terminalDrawer.locator("pre")).toContainText("repair-stats summary: mode=rebuild", { timeout: 15_000 });
  await expect(page.getByTestId("rebuild-stats-success")).toContainText("Stats rebuild completed.");
  await expect(statsSnapshotSection).toContainText("AUTO_GENERATED_FROM_CLAIMSET");
  await expect(statsSnapshotSection).not.toContainText("LEGACY_STATS_FIXTURE");
});

test("backend sync to obsidian uses the same inline feedback pattern as other workbench actions", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.getByText("Obsidian sync payload preview")).toBeVisible();

  const syncButton = page.getByRole("button", { name: "Sync to Obsidian", exact: true });
  await expect(syncButton).toBeVisible();
  await syncButton.click();

  await page.getByRole("button", { name: "Show Terminal Logs" }).click({ force: true });
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();
  await expect(terminalDrawer.locator("pre")).toContainText("obsidian-sync summary", { timeout: 15_000 });
  await expect(page.getByTestId("sync-obsidian-success")).toContainText("Obsidian sync completed.");
});

test("backend workbench reuses the same operational state summary language as list and rail", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-list-missing-stats-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  const selectedRailPaper = page.locator("aside").getByRole("button").filter({ hasText: "E2E List Missing Stats Paper" }).first();
  await expect(selectedRailPaper.getByTestId("rail-ops-badge")).toContainText("Action needed");
  await expect(selectedRailPaper.getByTestId("rail-ops-reason")).toContainText("Stats report is missing or empty.");
  await expect(page.getByTestId("workbench-ops-summary")).toBeVisible();
  await expect(page.getByTestId("workbench-ops-badge")).toContainText("Action needed");
  await expect(page.getByTestId("workbench-ops-reason")).toContainText("Open in Workbench to repair the Stats Snapshot.");
});

test("backend workbench preserves content review context when opened in issue focus mode", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-list-missing-stats-001?focus=issues");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByTestId("content-review-notice")).toContainText("No content flags recorded.");
  await expect(page.getByTestId("content-review-notice")).toContainText("Issue focus is enabled.");
  await expect(page.getByTestId("workbench-content-review-summary")).toBeVisible();
  await expect(page.getByTestId("workbench-content-review-badge")).toContainText("Clear");
  await expect(page.getByTestId("workbench-content-review-hint")).toContainText("No content flags in the current paper summary.");
  await expect(page.getByTestId("workbench-content-review-detail")).toContainText("Issue focus is enabled");
});

test.describe("mobile backend UX", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("mobile workbench renders collapsed controls without mock fallback", async ({ page }) => {
    await page.goto("/workbench/paper-e2e-001");

    await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

    const controlsSummary = page.locator('summary:has-text("Run & View Controls")').first();
    await expect(controlsSummary).toBeVisible();
    await controlsSummary.click();

    await expect(page.getByRole("button", { name: /Deep Read(?: Run)?/ }).first()).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
  });

  test("mobile paper notes detail opens side panel sheet", async ({ page }) => {
    await page.goto(`/papers/${noteSlug}`);

    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible();
    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Properties & Links" })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Properties", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Outline", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Related Papers", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "References", exact: true })).toBeVisible();
  });

  test("mobile paper notes detail auto-opens side panel for deep-link focus", async ({ page }) => {
    await page.goto(`/papers/${noteSlug}?focus=evidence:${evidenceId}`);

    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible();
    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();

    const evidenceCard = sheet.locator(focusDomId("evidence", evidenceId));
    await expect(evidenceCard).toBeVisible();
    await expect(evidenceCard).toHaveClass(/ring-2/);
    await expect(evidenceCard).toContainText("chunk-e2e-001");
  });

  test("mobile paper notes sheet includes structured actions and claimset cards", async ({ page }) => {
    await page.goto(`/papers/${structuredNoteSlug}`);

    await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible();
    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Actions", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Automation Results", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "ClaimSet", exact: true })).toBeVisible();
    await expect(sheet).toContainText("Strong: 2 claims, avg confidence 0.81, 0 inconsistent checks.");
    await expect(sheet).toContainText("CSF biomarker evidence aligns with early detection criteria.");
  });

  test("mobile paper notes detail keeps builder debug mode in the sheet ordering", async ({ page }) => {
    await page.goto(`/papers/${structuredNoteSlug}?view=builder_debug`);

    await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible();
    await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText("Builder / Debug mode lifts");
    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading").nth(1)).toHaveText("Actions");
    await expect(sheet.getByRole("heading", { name: "Properties", exact: true })).toBeVisible();
  });
});

test("paper notes detail renders properties, markdown, related papers, and references", async ({ page }) => {
  await page.goto(`/papers/${noteSlug}`);

  await expect(
    page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
  ).toBeVisible();
  const propertiesPanel = page.locator("aside").filter({ hasText: "Properties" }).first();
  await expect(propertiesPanel.getByRole("heading", { name: "Properties" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Outline" })).toBeVisible();
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
  const openPdfLink = referencesSection.getByRole("link", { name: /Open PDF/i }).first();
  await expect(openPdfLink).toBeVisible();
  await expect(openPdfLink).toHaveAttribute("href", /^(file:|https?:\/\/)/);

  const workbenchLink = page.getByRole("link", { name: "Open in Workbench" }).first();
  await expect(workbenchLink).toBeVisible();
  await expect(workbenchLink).toHaveAttribute("href", /\/workbench\/zotero%3AduboisAlzheimerDiseaseClinicalBiological2024$/);

  await relatedLink.click();
  await expect(page).toHaveURL(/\/papers\/.+$/);
  await expect(page.getByRole("banner").getByRole("heading")).toBeVisible();
});

test("paper notes detail supports learner and builder debug view modes", async ({ page }) => {
  await page.goto(`/papers/${structuredNoteSlug}?view=builder_debug`);

  await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible();
  await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText("Builder / Debug mode lifts");
  const rightAside = page.locator("main > aside").nth(1);
  await expect(rightAside.getByRole("heading").first()).toHaveText("Actions");

  await page.getByRole("button", { name: "Learner" }).click();
  await expect(page).toHaveURL(new RegExp(`/papers/${structuredNoteSlug}$`));
  await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText("Learner mode keeps related papers");
  await expect(rightAside.getByRole("heading").first()).toHaveText("Properties");
});

test("paper notes detail renders structured actions, automation results, and claimset cards", async ({ page }) => {
  await page.goto(`/papers/${structuredNoteSlug}`);

  await expect(page.getByRole("banner").getByRole("heading", { name: "Structured Skills ClaimSet Fixture" })).toBeVisible();

  const propertiesPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Properties", exact: true }) }).first();
  await expect(propertiesPanel).toContainText("4");
  await expect(propertiesPanel).toContainText("yes");
  await expect(propertiesPanel).toContainText("Strong");

  const actionsPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Actions", exact: true }) }).first();
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

  const automationPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Automation Results", exact: true }) }).first();
  await expect(automationPanel).toContainText("critical_appraisal");
  await expect(automationPanel).toContainText("validate_citations");
  await expect(automationPanel).toContainText("Strong: 2 claims, avg confidence 0.81, 0 inconsistent checks.");
  await expect(automationPanel).toContainText("Checked 4 references: 1 verified, 2 local, 1 need review.");
  await expect(automationPanel.getByTestId("paper-note-run-write-scope")).toHaveCount(0);

  const claimsetPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "ClaimSet", exact: true }) }).first();
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

test("paper notes detail deep links focus run, claim, and evidence cards", async ({ page }) => {
  await page.goto(`/papers/${noteSlug}`);

  await expect(
    page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
  ).toBeVisible();

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
  await page.goto(`/papers/${actionNoteSlug}`);

  await expect(page.getByRole("banner").getByRole("heading", { name: "Live Validate Citations Fixture" })).toBeVisible();

  const automationPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Automation Results", exact: true }) }).first();
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
  await expect(signalDiff).toContainText("citations: 3 -> 4");
  await expect(signalDiff).toContainText("new runs: 1");
  await expect(signalDiff).toContainText("new last action: validate_citations");
  await expect(signalDiff).toContainText("new last status: succeeded");

  const notePath = notePathFor(actionNoteSlug);
  const statePath = statePathFor(actionNoteSlug);
  const runsDir = runsDirFor(actionNoteSlug);
  await expect
    .poll(async () => {
      const noteText = await fs.readFile(notePath, "utf-8");
      return [
        noteText.includes("structured_path: .pp/zoteroliveValidateCitations2026/state.json"),
        noteText.includes("- validate_citations"),
        noteText.includes("citation_count: 4"),
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
      citation_count: 4,
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

  const automationPanel = page.locator("section").filter({ has: page.getByRole("heading", { name: "Automation Results", exact: true }) }).first();
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
  await expect(automationPanel.getByText("state updated")).toBeVisible();
  await expect(automationPanel.getByText("frontmatter updated")).toBeVisible();
  await expect(automationPanel.getByText("body skipped")).toBeVisible();
  await expect(page.getByTestId("paper-note-signal-diff")).toContainText("citations: 3 -> 4");

  const notePath = notePathFor(quietActionNoteSlug);
  const statePath = statePathFor(quietActionNoteSlug);
  const runsDir = runsDirFor(quietActionNoteSlug);
  await expect
    .poll(async () => {
      const noteText = await fs.readFile(notePath, "utf-8");
      return [
        noteText.includes("structured_path: .pp/zoteroquietValidateCitations2026/state.json"),
        noteText.includes("- validate_citations"),
        noteText.includes("citation_count: 4"),
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
      citation_count: 4,
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

  await expect(page.getByText("Structured state updated without markdown summary.")).toBeVisible();

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
  await page.goto("/papers");

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  const toggle = page.getByTestId("paper-notes-structured-toggle");
  await expect(toggle).toBeVisible();
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Live Validate Citations Fixture" })).toHaveCount(1);

  await toggle.click();

  await expect(page).toHaveURL(/structured=1/);
  await expect(page.getByTestId("paper-notes-active-structured-filter")).toContainText("structured only");
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first()).toBeVisible();
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Live Validate Citations Fixture" })).toHaveCount(0);

  await toggle.click();

  await expect(page).not.toHaveURL(/structured=1/);
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "Live Validate Citations Fixture" })).toHaveCount(1);
});

test("paper notes list surfaces action-needed state using workbench vocabulary", async ({ page }) => {
  await page.goto("/papers?q=List%20Missing", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  const row = page.getByTestId("paper-note-list-row").filter({ hasText: "E2E List Missing Stats Note" }).first();
  await expect(row).toBeVisible();
  await expect(row.getByTestId("paper-note-ops-badge")).toContainText("Action needed");
  await expect(row).toContainText("Stats report is missing or empty.");
  await expect(row).toContainText("Open in Workbench to repair the Stats Snapshot.");
});

test("paper notes list finds structured-signal matches and surfaces structured affordances", async ({ page }) => {
  await page.goto("/papers?q=Amyloid%20Neurology", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  await expect(page.getByText("relevance first")).toBeVisible();
  const row = page.getByTestId("paper-note-list-row").filter({ hasText: "Structured Skills ClaimSet Fixture" }).first();
  await expect(row).toBeVisible();
  await expect(row).toContainText("Structured");
  await expect(row).toContainText("ClaimSet ready");
  await expect(row).toContainText("4 cites");
  await expect(row).toContainText("Appraisal: Strong");
  await expect(row).toContainText("Claim tags biomarker");
  const signals = row.getByTestId("paper-note-list-signals");
  await expect(signals).toContainText("Structured signals");
  await expect(signals.getByTestId("paper-note-list-signal-chip").first()).toContainText("Amyloid");
  await expect(signals.getByTestId("paper-note-list-signal-chip").nth(1)).toContainText("Neurology");
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="true"]')).toHaveCount(2);
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="true"]').first()).toContainText("Amyloid");
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="true"]').nth(1)).toContainText("Neurology");
  await expect(signals.locator('[data-testid="paper-note-list-signal-chip"][data-highlighted="false"]').first()).toContainText(/Tau|memory|biomarker/);
  await expect(row).toContainText("Medicine/Neurology");
  await expect(page.getByText("No notes matched the current filters.")).toHaveCount(0);
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
  await expect(emptyState).toContainText("Try turning off Structured only or broadening the search terms.");
  await expect(emptyState.getByTestId("paper-notes-empty-clear-structured")).toBeVisible();

  await emptyState.getByTestId("paper-notes-empty-clear-structured").click();

  await expect(page).not.toHaveURL(/structured=1/);
  await expect(page.getByTestId("paper-note-list-row").filter({ hasText: "E2E List Missing Stats Note" })).toHaveCount(1);
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

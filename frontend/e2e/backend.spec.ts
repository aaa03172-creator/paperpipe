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

test("backend mode stays out of mock fallback", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator("tr").filter({ hasText: "E2E List Missing Stats Paper" }).first()).toBeVisible();

  // backend-seeded paper should be visible and navigable
  const seededPaper = page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" }).first();
  await expect(seededPaper).toBeVisible();
  await seededPaper.locator("td").first().click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001/);
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
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

test("backend evidence_spans fixture keeps zero-based normalized anchors stable", async ({ page }) => {
  await page.goto("/workbench/paper-e2e-spans-001");

  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.getByText("Claim Link · p.1")).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  const claimButtons = claimsPanel.getByRole("button");
  await expect(claimButtons).toHaveCount(2);

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(highlight).toBeVisible();

  const viewerBox = await viewer.boundingBox();
  const firstBox = await highlight.boundingBox();
  expect(viewerBox).not.toBeNull();
  expect(firstBox).not.toBeNull();
  if (viewerBox && firstBox) {
    expect(firstBox.width).toBeGreaterThan(viewerBox.width * 0.15);
    expect(firstBox.height).toBeGreaterThan(viewerBox.height * 0.08);
    expect(firstBox.x + firstBox.width).toBeLessThanOrEqual(viewerBox.x + viewerBox.width + 2);
    expect(firstBox.y + firstBox.height).toBeLessThanOrEqual(viewerBox.y + viewerBox.height + 2);
  }

  await claimButtons.nth(1).click();
  await expect(page.getByText("Claim Link · p.2")).toBeVisible();
  await expect(highlight).toBeVisible();

  const secondBox = await highlight.boundingBox();
  expect(secondBox).not.toBeNull();
  if (firstBox && secondBox) {
    const movedDelta =
      Math.abs(firstBox.x - secondBox.x) +
      Math.abs(firstBox.y - secondBox.y) +
      Math.abs(firstBox.width - secondBox.width) +
      Math.abs(firstBox.height - secondBox.height);
    expect(movedDelta).toBeGreaterThan(8);
  }
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
});

test("paper notes detail renders properties, markdown, related papers, and references", async ({ page }) => {
  await page.goto(`/papers/${noteSlug}`);

  await expect(
    page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
  ).toBeVisible();
  const propertiesPanel = page.locator("aside").filter({ hasText: "Properties" }).first();
  await expect(propertiesPanel.getByRole("heading", { name: "Properties" })).toBeVisible();
  await expect(propertiesPanel.getByText("INDEXED", { exact: true })).toBeVisible();
  await expect(propertiesPanel.getByText("Medicine/Neurology", { exact: true })).toBeVisible();
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

test("soft-gate canary: intentional backend e2e failure drill", async () => {
  test.skip(!runSoftGateCanary, "Set PAPERPIPE_E2E_CANARY=1 to run intentional failure drill.");
  expect(1).toBe(2);
});

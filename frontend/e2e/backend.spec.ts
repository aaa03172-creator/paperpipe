import { randomUUID } from "node:crypto";

import { expect, test, type APIRequestContext, type Locator } from "@playwright/test";

const runSoftGateCanary = process.env.PAPERPIPE_E2E_CANARY === "1";
const runRealSmoke = process.env.PAPERPIPE_REAL_SMOKE === "1";
const requireRealSmokeCandidates = process.env.PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES === "1";
const backendPort = process.env.E2E_BACKEND_PORT ?? "18080";
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;

interface BackendPaperSummary {
  paper_id?: string;
  pdf_exists?: boolean;
}

interface BackendArtifactEntry {
  data?: unknown;
}

interface BackendArtifactBundle {
  files?: Record<string, BackendArtifactEntry>;
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

const noteSlug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024";

test("backend mode stays out of mock fallback", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Triage Dashboard" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  // backend-seeded paper should be visible and navigable
  const seededPaper = page.locator("tbody tr").filter({ hasText: "E2E Seed Paper" }).first();
  await expect(seededPaper).toBeVisible();
  await seededPaper.locator("td").first().click();

  await expect(page).toHaveURL(/\/workbench\/paper-e2e-001/);
  await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);

  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.getByText("Claim text missing")).toHaveCount(0);
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
  if (beforeBox && afterBox) {
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

test.describe("mobile backend UX", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("mobile workbench renders collapsed controls without mock fallback", async ({ page }) => {
    await page.goto("/workbench/paper-e2e-001");

    await expect(page.getByRole("heading", { name: "Analysis Workbench" })).toBeVisible();
    await expect(page.getByText("Mock mode")).toHaveCount(0);
    await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();

    const controlsSummary = page.locator('summary:has-text("Workbench controls")').first();
    await expect(controlsSummary).toBeVisible();
    await controlsSummary.click();

    await expect(page.getByRole("button", { name: /Deep Read(?: Run)?/ }).first()).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
  });

  test("mobile paper notes detail opens review details sheet", async ({ page }) => {
    await page.goto(`/papers/${noteSlug}`);

    await expect(
      page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
    ).toBeVisible();
    const sidePanelButton = page.getByTestId("paper-note-open-side-panel");
    await expect(sidePanelButton).toBeVisible();
    await sidePanelButton.click();

    const sheet = page.getByTestId("paper-note-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Review details" })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Properties", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Outline", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "Related Papers", exact: true })).toBeVisible();
    await expect(sheet.getByRole("heading", { name: "References", exact: true })).toBeVisible();
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
  const structuredStateNotice = page.getByTestId("paper-note-structured-state-notice");
  await expect(structuredStateNotice).toContainText("Structured state is not loaded");
  await expect(structuredStateNotice).toContainText("missing canonical sidecar");
  await expect(page.getByTestId("paper-note-structured-state-path")).toContainText(
    ".pp/zoteroduboisAlzheimerDiseaseClinicalBiological2024/state.json",
  );
  await expect(page.getByTestId("paper-note-context-trace-summary")).toContainText("trace 5");

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
  await expect(row).toContainText("Saved note checks are missing or empty.");
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

test("paper notes detail supports learner and inspect view modes", async ({ page }) => {
  await page.goto(`/papers/${noteSlug}?view=builder_debug`);

  await expect(
    page.getByRole("banner").getByRole("heading", { name: /Alzheimer Disease as a Clinical-Biological Construct/i }),
  ).toBeVisible();
  await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText("Inspect mode lifts");
  await expect(page.getByTestId("paper-note-structured-state-notice")).toContainText("Structured state is not loaded");
  const rightAside = page.locator("main > aside").nth(1);
  await expect(rightAside.getByRole("heading").first()).toHaveText("Actions");

  await page.getByRole("button", { name: "Learner" }).click();
  await expect(page).toHaveURL(new RegExp(`/papers/${noteSlug}$`));
  await expect(page.getByTestId("paper-note-view-mode-summary")).toContainText("Learner mode keeps related papers");
  await expect(rightAside.getByRole("heading").first()).toHaveText("Properties");
});

test("backend image evidence viewer loads a registered external bundle on the real route", async ({ page, request }) => {
  const imageEvidenceId = `imageev_backend_external_${randomUUID().slice(0, 8)}`;
  const response = await request.post(`${backendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "E2E OMERO clean bundle",
      paper_slug: noteSlug,
      source_ref: {
        source_kind: "external_image_ref",
        external_ref: `omero://dataset/42/image/${imageEvidenceId}`,
        source_label: "OMERO image 7",
      },
      content_format: "image/png",
      metadata: {
        width_px: 1024,
        height_px: 768,
        modality: "brightfield",
        acquisition_note: "Representative backend image-evidence bundle.",
      },
      view_state: {
        active_channels: ["GFP", "DAPI"],
        zoom_level: 2.0,
        visible_overlays: ["roi_outline"],
      },
      derived_outputs: [
        {
          derived_output_id: "thumb_clean",
          kind: "thumbnail",
          source_image_evidence_id: imageEvidenceId,
          created_by: "e2e-fixture",
          created_at: "2026-03-24T12:00:00+00:00",
          tool_name: "napari",
          external_ref: `omero://dataset/42/image/${imageEvidenceId}/thumbnail`,
          note: "Representative thumbnail only.",
        },
      ],
      handoff_targets: [
        {
          target: "omero",
          openable_ref: `omero://dataset/42/image/${imageEvidenceId}`,
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
      paper_slug?: string | null;
      warnings?: Array<{ code?: string }>;
    };
    view_state?: { active_channels?: string[] } | null;
    handoff_targets?: Array<{ target?: string; openable_ref?: string }>;
  };
  expect(payload.image_evidence?.image_evidence_id).toBe(imageEvidenceId);
  expect(payload.image_evidence?.title).toBe("E2E OMERO clean bundle");
  expect(payload.image_evidence?.paper_slug).toBe(noteSlug);
  expect(payload.image_evidence?.warnings ?? []).toEqual([]);
  expect(payload.view_state?.active_channels).toEqual(["GFP", "DAPI"]);
  expect(payload.handoff_targets?.[0]?.target).toBe("omero");

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
    title: "E2E OMERO clean bundle",
    warning_count: 0,
    has_view_state: true,
    has_handoff: true,
  });

  await page.goto("/image-evidence");

  await expect(page.getByRole("heading", { name: "Image Evidence", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or image evidence id"]').fill(imageEvidenceId);
  const targetCard = page.locator("article").filter({ hasText: "E2E OMERO clean bundle" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("Clean bundle", { exact: true })).toBeVisible();
  await targetCard.getByRole("button", { name: "Open bundle" }).click();

  await expect(page).toHaveURL(new RegExp(`/image-evidence/${imageEvidenceId}$`));
  await expect(page.getByRole("heading", { name: "E2E OMERO clean bundle", exact: true })).toBeVisible();
  await expect(page.getByText("No bundle warnings saved.")).toBeVisible();
  await expect(page.getByText("Representative backend image-evidence bundle.")).toBeVisible();
  await expect(page.getByText("Thumbnail", { exact: true })).toBeVisible();
  await expect(page.getByText("Representative thumbnail only.")).toBeVisible();
  await expect(page.getByText("GFP")).toBeVisible();
  await expect(page.getByText("Open in external viewer.")).toBeVisible();

  await page.getByRole("link", { name: "Open note" }).click();
  await expect(page).toHaveURL(new RegExp(`/papers/${noteSlug}$`));
  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: /Alzheimer Disease as a Clinical-Biological Construct/i,
    }),
  ).toBeVisible();
});

test("backend image evidence viewer surfaces missing-local-file warnings on the real route", async ({ page, request }) => {
  const imageEvidenceId = `imageev_backend_missing_${randomUUID().slice(0, 8)}`;
  const missingLocalPath = `/tmp/${imageEvidenceId}.tif`;
  const response = await request.post(`${backendBaseUrl}/image-evidence/register`, {
    data: {
      image_evidence_id: imageEvidenceId,
      title: "E2E missing local image bundle",
      source_ref: {
        source_kind: "local_file",
        local_path: missingLocalPath,
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
  expect(payload.image_evidence?.warnings?.[0]?.message).toContain(missingLocalPath);
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

  await page.goto("/image-evidence");

  await expect(page.getByRole("heading", { name: "Image Evidence", exact: true })).toBeVisible();
  await expect(page.getByText("Mock mode")).toHaveCount(0);
  await page.locator('input[placeholder="Search title or image evidence id"]').fill(imageEvidenceId);
  const targetCard = page.locator("article").filter({ hasText: "E2E missing local image bundle" }).first();
  await expect(targetCard).toBeVisible();
  await expect(targetCard.getByText("1 warning", { exact: true })).toBeVisible();
  await targetCard.getByRole("button", { name: "Open bundle" }).click();

  await expect(page).toHaveURL(new RegExp(`/image-evidence/${imageEvidenceId}$`));
  await expect(page.getByRole("heading", { name: "E2E missing local image bundle", exact: true })).toBeVisible();
  await expect(page.getByText("LOCAL_SOURCE_MISSING")).toBeVisible();
  await expect(page.getByText(`Local source file does not exist: ${missingLocalPath}`)).toBeVisible();
  await expect(page.getByText("No derived outputs registered.")).toBeVisible();
  await expect(page.getByText("No view state saved for this bundle.")).toBeVisible();
  await expect(page.getByText("No handoff targets saved for this bundle.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open note" })).toHaveCount(0);
});

test("soft-gate canary: intentional backend e2e failure drill", async () => {
  test.skip(!runSoftGateCanary, "Set PAPERPIPE_E2E_CANARY=1 to run intentional failure drill.");
  expect(1).toBe(2);
});

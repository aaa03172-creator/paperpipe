import { expect, test } from "@playwright/test";

const REVIEW_WORKBENCH_SUBTITLE =
  "Review evidence, saved checks, and claim flags before regenerating or exporting downstream artifacts.";

test("mock mode fallback renders full phase3 flow", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/^Mock mode$/)).toBeVisible({ timeout: 15_000 });

  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/workbench\//);

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  const sessionControls = page.getByTestId("workbench-session-controls");
  await expect(sessionControls).toBeVisible();
  await sessionControls.getByText("Session controls", { exact: true }).click();
  await expect(sessionControls.getByLabel("Reading style")).toBeVisible();
  await expect(sessionControls.getByLabel("Context profile")).toBeVisible();

  await expect(page.locator('[data-testid="pdf-viewer"]')).toBeVisible();
  await expect(page.getByText("Cell 1 Claim")).toBeVisible();

  await page.getByRole("button", { name: "Terminal logs" }).click();
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Run deep read" }).click();
  await expect(terminalDrawer.locator("pre")).toContainText("deepread enqueued", { timeout: 15_000 });
});

test("home workspace context surfaces paper-level marker aggregation", async ({ page }) => {
  await page.goto("/");

  const markerSummary = page.getByTestId("home-workspace-marker-summary");
  await expect(markerSummary).toContainText("Paper markers");
  await expect(markerSummary.getByTestId("home-workspace-marker-detail")).toContainText(
    "2 papers already carry paper-level judgment. 2 include a private note.",
  );

  await expect(markerSummary.getByTestId("home-workspace-marker-starred")).toContainText("Starred");
  await expect(markerSummary.getByTestId("home-workspace-marker-starred")).toContainText("1");
  await expect(markerSummary.getByTestId("home-workspace-marker-starred")).toHaveAttribute("href", "/papers?starred=1");

  await expect(markerSummary.getByTestId("home-workspace-marker-revisit")).toContainText("Revisit");
  await expect(markerSummary.getByTestId("home-workspace-marker-revisit")).toContainText("1");
  await expect(markerSummary.getByTestId("home-workspace-marker-revisit")).toHaveAttribute(
    "href",
    "/papers?triage_label=revisit",
  );

  await expect(markerSummary.getByTestId("home-workspace-marker-needs-verification")).toContainText("Needs verification");
  await expect(markerSummary.getByTestId("home-workspace-marker-needs-verification")).toContainText("1");
  await expect(markerSummary.getByTestId("home-workspace-marker-experiment-relevant")).toContainText("Experiment relevant");
  await expect(markerSummary.getByTestId("home-workspace-marker-experiment-relevant")).toContainText("1");
});

test("workbench can cancel an in-flight deep read in mock mode", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Runtime checks", exact: true })).toBeVisible();
  await expect(page.getByTestId("workbench-runtime-guidance")).toContainText("If you expected live runs here");

  await page.getByRole("button", { name: "Terminal logs" }).click();
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Run deep read" }).click();
  await expect(page.getByRole("button", { name: "Cancel run" })).toBeVisible();

  await page.getByRole("button", { name: "Cancel run" }).click();
  await expect(page.getByTestId("cancel-run-success")).toContainText("Deep read cancelled.");
  await expect(page.getByRole("button", { name: "Run deep read" })).toBeVisible();
  await expect(terminalDrawer.locator("pre")).toContainText("deepread cancelled", { timeout: 15_000 });
});

test("workbench query param scopes parser pilot override into the enqueue path", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging?parser_backend=docling");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await page.getByRole("button", { name: "Terminal logs" }).click();
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Run deep read" }).click();
  await expect(page.getByTestId("workbench-parser-selection").first()).toContainText("Requested document reader Docling");
  await expect(terminalDrawer.locator("pre")).toContainText("requested_parser=docling", { timeout: 15_000 });
});

test("runtime readiness page explains forced-mock diagnostics without dead-ending", async ({ page }) => {
  await page.goto("/ready");

  await expect(page.getByRole("heading", { name: "Check whether this workspace is ready for real runs" })).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-product-loop")).toContainText("Current product loop");
  await expect(page.getByTestId("runtime-readiness-fallback")).toContainText(
    "Runtime checks are unavailable while mock mode is forced.",
  );
  await expect(page.getByTestId("runtime-readiness-overall")).toContainText("Blocked");
  await expect(page.getByTestId("runtime-readiness-check-runtime_readiness")).toContainText(
    "Disable mock mode to inspect the live backend runtime.",
  );
  await expect(page.getByTestId("runtime-readiness-open-papers")).toContainText("Open Paper Notes");
  await expect(page.getByTestId("runtime-readiness-open-papers")).toHaveAttribute("href", "/papers");
  await expect(page.getByTestId("runtime-readiness-suggested-fixes")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-fix-live-backend")).toContainText("Restore the live backend signal");
});

test("settings API key field supports clipboard paste in mock mode", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "LLM provider" })).toBeVisible();
  await page.evaluate(() => navigator.clipboard.writeText("sk-lattice-test-paste-key"));
  await page.getByRole("button", { name: "Paste key" }).click();

  await expect(page.getByLabel("API key")).toHaveValue("sk-lattice-test-paste-key");
  await expect(page.getByText("API key pasted. Save settings when ready.")).toBeVisible();
});

test("paper note detail fallback points back to runtime checks in mock mode", async ({ page }) => {
  await page.goto("/papers/ketogenicInterventionGlucoseVariability2024");

  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: /ketogenic intervention and glucose variability/i,
    }),
  ).toBeVisible();
  await expect(page.getByTestId("paper-note-runtime-guidance")).toContainText("If you expected live note data here");
  await expect(page.getByRole("link", { name: "Runtime checks", exact: true }).first()).toBeVisible();
  await expect(page.getByTestId("paper-note-section-navigator")).toContainText("Structured signals");
});

test("cloud paper opens in the existing detail viewer shell in mock mode", async ({ page }) => {
  await page.goto("/papers/paper_mock_ready?source=cloud");

  await expect(page.getByTestId("cloud-paper-detail-viewer")).toBeVisible();
  await expect(page.getByRole("banner").getByRole("heading", { name: "paper_mock_ready" })).toBeVisible();
  await expect(page.getByTestId("cloud-paper-workspace-context")).toContainText("Cloud source");
  await expect(page.getByTestId("cloud-paper-workspace-context")).toContainText("Page artifact");
  await expect(page.getByTestId("cloud-paper-workspace-context")).toContainText("Derived artifacts");
  await expect(page.getByTestId("cloud-paper-workspace-context")).toContainText("ocr 1");
  await expect(page.getByTestId("cloud-paper-workspace-context")).toContainText("tables 1");
  await expect(page.getByTestId("cloud-paper-workspace-context")).toContainText("figures 1");
  await expect(page.getByTestId("cloud-paper-workspace-context")).toContainText("Local hydration");
  await expect(page.getByTestId("cloud-paper-page-blocks")).toContainText(
    "Mock processed page text for cloud paper API contract verification.",
  );
  const derivedArtifacts = page.getByTestId("cloud-paper-derived-artifacts");
  await expect(derivedArtifacts).toContainText("Derived artifacts");
  await expect(derivedArtifacts).toContainText("Mock OCR text recovered from a rendered cloud PDF page.");
  await expect(derivedArtifacts).toContainText("Mock reconstructed table from cloud PDF layout.");
  await expect(derivedArtifacts).toContainText("Mock figure crop from rendered cloud PDF page.");
  await expect(derivedArtifacts).toContainText("Mock figure analysis placeholder derived from a server-side figure crop.");
  const downstreamHandoff = page.getByTestId("cloud-paper-downstream-handoff");
  await expect(downstreamHandoff).toContainText("Downstream handoff");
  await expect(downstreamHandoff).toContainText("Meeting Pack");
  await expect(downstreamHandoff).toContainText("background_only");
  await expect(downstreamHandoff).toContainText("Chart Pack");
  await expect(downstreamHandoff).toContainText("cloud_derived_table");
  await expect(downstreamHandoff).toContainText("Selected table table_001");
  await expect(downstreamHandoff).toContainText("Image Evidence");
  await expect(downstreamHandoff).toContainText("external_image_ref");
  await expect(downstreamHandoff).toContainText("Selected figure figure_001");
  await expect(downstreamHandoff).toContainText("Method Comparison");
  await expect(downstreamHandoff).toContainText("missing");
  await expect(downstreamHandoff).toContainText("Obsidian");
  await expect(downstreamHandoff).toContainText("derived_noncanonical");
  const downstreamActions = page.getByTestId("cloud-paper-downstream-actions");
  await expect(downstreamActions).toContainText("Export actions");
  await expect(downstreamActions).toContainText("permission_required");
  await expect(downstreamActions).toContainText("export permission required");
  await expect(downstreamActions.getByRole("button", { name: "Prepare Obsidian" })).toBeDisabled();
  await expect(downstreamActions.getByRole("button", { name: "Register artifacts" })).toBeDisabled();
  await expect(page.getByText("Trust order")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Provenance" })).toBeVisible();
});

test("cloud paper downstream handoff shows empty states when table and figure candidates are unavailable", async ({ page }) => {
  await page.goto("/papers/paper_mock_no_downstream_candidates?source=cloud");

  await expect(page.getByTestId("cloud-paper-detail-viewer")).toBeVisible();
  const downstreamHandoff = page.getByTestId("cloud-paper-downstream-handoff");
  await expect(downstreamHandoff).toContainText("Downstream handoff");
  await expect(downstreamHandoff).toContainText("Chart Pack");
  await expect(downstreamHandoff).toContainText("unavailable");
  await expect(downstreamHandoff).toContainText("No table candidate is ready for Chart Pack.");
  await expect(downstreamHandoff).toContainText("Image Evidence");
  await expect(downstreamHandoff).toContainText("No figure candidate is ready for Image Evidence.");
  await expect(downstreamHandoff).not.toContainText("Selected table");
  await expect(downstreamHandoff).not.toContainText("Selected figure");
});

test("cloud paper downstream registry readback shows reviewed artifact status", async ({ page }) => {
  await page.goto("/papers/paper_mock_reviewed?source=cloud");

  await expect(page.getByTestId("cloud-paper-detail-viewer")).toBeVisible();
  const downstreamActions = page.getByTestId("cloud-paper-downstream-actions");
  await expect(downstreamActions).toContainText("1 registration read back / review_pending");
  const registryArtifacts = page.getByTestId("cloud-paper-downstream-registry-artifacts");
  await expect(registryArtifacts).toContainText("review_approved");
  await expect(registryArtifacts).toContainText("maintainer review event");
  await expect(registryArtifacts).toContainText("note recorded");
  await expect(downstreamActions).toContainText("Promotion readiness");
  await expect(downstreamActions).toContainText("blocked / 1/5 approved");
  await expect(downstreamActions).toContainText("blocker review_pending");
  await expect(downstreamActions).toContainText("Promotion plan");
  await expect(downstreamActions).toContainText("blocked dry-run / 0 items");
  await expect(downstreamActions).toContainText("no canonical mutation");
  await expect(downstreamActions).toContainText("plan blocker review_pending");
});

test("cloud paper downstream promotion readiness becomes eligible after all artifacts are approved", async ({ page }) => {
  await page.goto("/papers/paper_mock_promotion_ready?source=cloud");

  await expect(page.getByTestId("cloud-paper-detail-viewer")).toBeVisible();
  const downstreamActions = page.getByTestId("cloud-paper-downstream-actions");
  await expect(downstreamActions).toContainText("Promotion readiness");
  await expect(downstreamActions).toContainText("eligible / 5/5 approved");
  await expect(downstreamActions).toContainText("Promotion plan");
  await expect(downstreamActions).toContainText("ready dry-run / 5 items");
  await expect(downstreamActions).toContainText("no canonical mutation");
  await expect(downstreamActions).not.toContainText("blocker");
});

test("paper notes search surfaces readable cloud page matches in mock mode", async ({ page }) => {
  await page.goto("/papers?q=processed");

  const cloudSearch = page.getByTestId("cloud-paper-search-results");
  await expect(cloudSearch).toBeVisible();
  await expect(cloudSearch).toContainText('1 cloud match for "processed"');
  const result = cloudSearch.getByTestId("cloud-paper-search-result-row").first();
  await expect(result).toContainText("paper_mock_ready");
  await expect(result).toContainText("Mock processed page text");
  await expect(result).toHaveAttribute("href", "/papers/paper_mock_ready?source=cloud");
});

test("paper notes cloud auth preflight guides live GCP setup from mock mode", async ({ page }) => {
  await page.goto("/papers");

  const authPanel = page.getByTestId("cloud-auth-preflight");
  await expect(authPanel).toBeVisible();
  await expect(authPanel).toContainText("Mock mode");
  await expect(authPanel).toContainText("Use a live runtime to check Google Cloud authentication.");
  await expect(authPanel).toContainText("Cloud adapter");
  await expect(authPanel).toContainText("Check again");
});

test("structured paper note detail keeps review focus close to reading", async ({ page }) => {
  await page.goto("/papers");

  const assistAvailableToggle = page.getByTestId("paper-notes-reading-assist-available-toggle");
  const assistToggle = page.getByTestId("paper-notes-reading-assist-toggle");
  await assistAvailableToggle.click();
  await expect(page).toHaveURL(/has_reading_assist=1/);
  await expect(page.getByTestId("paper-notes-active-reading-assist-filter")).toContainText("Reading assist available");
  await expect(page.getByTestId("paper-note-list-row")).toHaveCount(1);

  await assistToggle.click();
  await expect(page).toHaveURL(/has_reading_assist=1/);
  await expect(page).toHaveURL(/reading_assist_locale=ko/);
  await expect(page.getByTestId("paper-notes-active-reading-assist-filter")).toContainText("Korean assist only");
  await expect(page.getByTestId("paper-note-list-row")).toHaveCount(1);

  const listRow = page
    .getByTestId("paper-note-list-row")
    .filter({ hasText: "Adaptive Intervention Signals with Ambiguous Evidence Anchors" })
    .first();
  await expect(listRow).toContainText("2 reading assists");
  await listRow.getByRole("link", { name: /Adaptive Intervention Signals with Ambiguous Evidence Anchors/i }).click();
  await expect(page).toHaveURL(/reading_assist_locale=ko/);

  await expect(
    page.getByRole("banner").getByRole("heading", {
      name: /adaptive intervention signals with ambiguous evidence anchors/i,
    }),
  ).toBeVisible();
  const workspaceContext = page.getByTestId("paper-note-workspace-context");
  await expect(workspaceContext).toContainText("Workspace context");
  await expect(workspaceContext).toContainText("Workspace mode");

  const bridge = page.getByTestId("paper-note-review-bridge");
  await expect(bridge).toBeVisible();
  await expect(bridge).toContainText("Review focus");
  await expect(bridge).toContainText("Saved state loaded");
  await expect(bridge.getByTestId("paper-note-review-bridge-status")).toContainText("Trust state");
  await expect(bridge.getByTestId("paper-note-review-bridge-ops-badge")).toContainText("Action needed");
  await expect(bridge.getByRole("link", { name: "Open saved evidence" })).toBeVisible();
  await expect(bridge.getByTestId("paper-note-review-focus-location")).toContainText("Source anchor:");
  await expect(bridge.getByTestId("paper-note-review-focus-hint")).toBeVisible();
  const anchorBox = await bridge.getByTestId("paper-note-review-focus-location").boundingBox();
  const claimBox = await bridge.getByTestId("paper-note-review-focus-claim").boundingBox();
  expect(anchorBox).not.toBeNull();
  expect(claimBox).not.toBeNull();
  expect((anchorBox?.y ?? 0) + (anchorBox?.height ?? 0)).toBeLessThan(claimBox?.y ?? Number.POSITIVE_INFINITY);
  await expect(bridge.getByRole("link", { name: "Open review" })).toBeVisible();

  const readingAssist = page.getByTestId("paper-note-reading-assist");
  await expect(readingAssist).toContainText("Korean reading assist");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toHaveCount(0);
  await expect(readingAssist.getByTestId("paper-note-reading-assist-locale-switcher")).toContainText("Auto");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-locale-switcher")).toContainText("Korean");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-locale-switcher")).toContainText("Japanese");

  const propertiesPanel = page.locator("aside").filter({ hasText: "Properties" }).first();
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-availability")).toContainText("Korean available");
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-availability")).toContainText("Japanese available");
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-current-view")).toContainText("Korean viewing");
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-current-view")).toContainText("Manual selection");
  await expect(propertiesPanel.getByTestId("paper-note-section-navigation-signal")).toContainText("Saved signal thin");
  await expect(propertiesPanel.getByTestId("paper-note-section-navigation-signal-detail")).toContainText(
    "viewer-side fallback grouping",
  );

  await readingAssist.getByTestId("paper-note-reading-assist-toggle").click();
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Machine translated from English");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText(
    "English/original text remains canonical",
  );
  await expect(readingAssist).toContainText("Canonical EN");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("One-Line Summary");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Translator mock-fallback");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Model mock-translation-v1");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Version 2026-04-04");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText(
    "Adaptive intervention signals look promising",
  );
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText(
    "적응형 중재 신호는 유망하지만",
  );

  await readingAssist.getByTestId("paper-note-reading-assist-locale-ja").click();
  await expect(page).toHaveURL(/reading_assist_locale=ja/);
  await expect(readingAssist).toContainText("Japanese reading assist");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Translator mock-fallback-ja");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Model mock-translation-v2");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Version 2026-04-08");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText(
    "適応的介入シグナルは有望だが",
  );
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-current-view")).toContainText("Japanese viewing");
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-current-view")).toContainText("Manual selection");

  await readingAssist.getByTestId("paper-note-reading-assist-locale-auto").click();
  await expect(page).not.toHaveURL(/reading_assist_locale=/);
  await expect(readingAssist).toContainText("Korean reading assist");
  await expect(readingAssist.getByTestId("paper-note-reading-assist-body")).toContainText("Translator mock-fallback");
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-current-view")).toContainText("Korean viewing");
  await expect(propertiesPanel.getByTestId("paper-note-reading-assist-current-view")).toContainText("Auto default");
});

test("workbench rail keeps parser pilot query when selecting another paper", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging?parser_backend=docling");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByTestId("workbench-workspace-context")).toContainText("Workspace context");
  await page.getByRole("button", { name: /Ketogenic Intervention and Glucose Variability/i }).click();
  await expect(page).toHaveURL(/\/workbench\/paper-2024-glucose\?parser_backend=docling$/);

  await page.getByRole("button", { name: "Terminal logs" }).click();
  const terminalDrawer = page.locator('aside[aria-hidden="false"]').first();
  await expect(terminalDrawer.getByText("Terminal Logs", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Run deep read" }).click();
  await expect(page.getByTestId("workbench-parser-selection").first()).toContainText("Requested document reader Docling");
  await expect(terminalDrawer.locator("pre")).toContainText("requested_parser=docling", { timeout: 15_000 });
});

test("workbench surfaces paper-level markers as read-only carryover", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  const workspaceContext = page.getByTestId("workbench-workspace-context");
  await expect(workspaceContext).toContainText("Saved review state");
  await expect(page.getByTestId("workbench-section-navigation-signal")).toContainText("Saved signal thin");
  await expect(page.getByTestId("workbench-section-navigation-signal-detail")).toContainText(
    "section reopen quality may vary",
  );
  const paperOperatorSummary = page.getByTestId("workbench-paper-operator-summary");
  await expect(paperOperatorSummary).toContainText("Paper note");
  await expect(paperOperatorSummary).toContainText("My note");
  await expect(paperOperatorSummary).toContainText("Needs verification");
  await expect(paperOperatorSummary).toContainText("Revisit");
  await expect(paperOperatorSummary).toContainText("Needs manual evidence review before I trust or reuse the saved anchors.");
  await expect(paperOperatorSummary.getByRole("link", { name: "Continue in note" })).toHaveAttribute(
    "href",
    /\/papers\/adaptiveInterventionSignalsAmbiguous2026$/,
  );
});

test("workbench surfaces inference summary in mock mode", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  const inferenceCard = page.getByTestId("workbench-inference-summary");
  await expect(inferenceCard).toBeVisible();
  await expect(inferenceCard.getByTestId("workbench-inference-backend")).toContainText("backend: local");
  await expect(inferenceCard.getByTestId("workbench-inference-payload")).toContainText("payload: local only");
  await expect(inferenceCard.getByTestId("workbench-inference-redaction")).toContainText("no redaction");
  await expect(inferenceCard.getByTestId("workbench-inference-lane-reader")).toContainText("reader");
  await expect(inferenceCard.getByTestId("workbench-inference-lane-reader")).toContainText("llama3:8b");
});

test("workbench surfaces evidence grounding scorecard in mock mode", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging");

  const scorecard = page.getByTestId("workbench-evidence-grounding-scorecard");
  await expect(scorecard).toBeVisible();
  await expect(scorecard).toContainText("Evidence grounding");
  await expect(scorecard.getByTestId("workbench-evidence-grounding-readiness")).toContainText("warn");
  await expect(scorecard.getByTestId("workbench-evidence-grounding-canonical")).toContainText(
    "Non-canonical review gate",
  );
  await expect(scorecard.getByTestId("workbench-evidence-grounding-reasons")).toContainText(
    "missing_p0_gold_metrics",
  );
  await expect(scorecard.getByTestId("workbench-evidence-grounding-reasons")).toContainText(
    "accepted_corrections_not_replayable",
  );
});

test("encoded paper id route does not crash in workbench", async ({ page }) => {
  await page.goto("/workbench/paper%25id");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();
  await expect(page.getByText("Invalid paper id.")).toHaveCount(0);
});

test("paper notes query state syncs with URL params", async ({ page }) => {
  await page.goto("/papers?q=alzheimer&sort=confidence&order=asc&page=3");

  await expect(page.locator('input[placeholder="Title, alias, or slug"]')).toHaveValue("alzheimer");
  await expect(page.locator("select").nth(1)).toHaveValue("confidence");
  await expect(page).toHaveURL(/\/papers\?q=alzheimer&sort=confidence&order=asc$/);

  await page.locator('input[placeholder="Title, alias, or slug"]').fill("biomarker");
  await expect(page).toHaveURL(/\/papers\?q=biomarker&sort=confidence&order=asc$/);

  await page.getByRole("button", { name: "Toggle sort order" }).click();
  await expect(page).toHaveURL(/\/papers\?q=biomarker&sort=confidence$/);
});

test("paper note operator markers surface in mock list filters and detail panels", async ({ page }) => {
  await page.goto("/papers");

  const starredToggle = page.getByTestId("paper-notes-starred-toggle");
  await starredToggle.click();
  await expect(page).toHaveURL(/starred=1/);
  await expect(page.getByTestId("paper-notes-active-starred-filter")).toContainText("starred only");
  await expect(page.getByTestId("paper-note-list-row")).toHaveCount(1);

  const starredRow = page
    .getByTestId("paper-note-list-row")
    .filter({ hasText: "Ketogenic Intervention and Glucose Variability: Randomized Trial" })
    .first();
  await expect(starredRow.getByTestId("paper-note-list-operator-badges")).toContainText("Starred");
  await expect(starredRow.getByTestId("paper-note-list-operator-badges")).toContainText("My note");
  await expect(starredRow.getByTestId("paper-note-list-operator-badges")).toContainText("Experiment relevant");

  await starredToggle.click();
  const triageToggle = page.getByTestId("paper-notes-triage-toggle-needs_verification");
  await triageToggle.click();
  await expect(page).toHaveURL(/triage_label=needs_verification/);
  await expect(page.getByTestId("paper-notes-active-triage-filter")).toContainText("Needs verification");
  await expect(page.getByTestId("paper-note-list-row")).toHaveCount(1);

  const verificationRow = page
    .getByTestId("paper-note-list-row")
    .filter({ hasText: "Adaptive Intervention Signals with Ambiguous Evidence Anchors" })
    .first();
  await verificationRow.getByRole("link", { name: /Adaptive Intervention Signals with Ambiguous Evidence Anchors/i }).click();

  const operatorPanel = page.getByTestId("paper-note-operator-panel");
  await expect(operatorPanel).toContainText("Keep paper-level judgment separate");
  await expect(operatorPanel.getByTestId("paper-note-operator-scope-note")).toContainText(
    "They do not change saved claims, evidence, or review state.",
  );
  await expect(operatorPanel.getByTestId("paper-note-operator-badge-note")).toContainText("My note");
  await expect(operatorPanel.getByTestId("paper-note-operator-badge-needs_verification")).toContainText(
    "Needs verification",
  );
  await expect(operatorPanel.getByTestId("paper-note-operator-textarea")).toHaveValue(
    "Needs manual evidence review before I trust or reuse the saved anchors.",
  );
});

test("paper notes fallback points back to runtime checks in mock mode", async ({ page }) => {
  await page.goto("/papers");

  await expect(page.getByRole("heading", { name: "Paper Notes" })).toBeVisible();
  await expect(page.getByTestId("paper-notes-runtime-guidance")).toContainText(
    "If you expected the live notes index here",
  );
  await expect(page.getByRole("link", { name: "open Runtime checks" })).toBeVisible();
});

test("issue button routes with focus=issues and selects risk claim", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible();
  await page.locator("tbody tr").first().locator("td").nth(2).getByRole("button").click();

  const viewer = page.locator('[data-testid="pdf-viewer"]').first();
  const highlight = page.locator('[data-testid="claim-highlight"]').first();
  await expect(page).toHaveURL(/focus=issues/);
  await expect(page.getByTestId("content-review-notice")).toContainText("3 flagged review issues remain in focus.");
  await expect(page.getByTestId("content-review-notice")).toContainText("Risk focus is on. Saved checks stay separate");
  await expect(page.getByText("Claim Link · p.1")).toBeVisible();
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

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await claimsPanel.getByRole("button").first().click();

  await expect(page.getByText("Claim Link · p.1")).toBeVisible();
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

test("not analyzed papers do not masquerade as clear content review", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  const row = page.locator("tbody tr").filter({ hasText: "Systems Omics Review for Metabolic Resilience" }).first();
  await expect(row.getByTestId("triage-content-review-button")).toContainText("Review unavailable");
  await expect(row.getByTestId("triage-review-badge")).toContainText("Unavailable");
  await expect(row.getByTestId("triage-review-hint")).toContainText("Claim review has not been generated");
  await expect(row.getByTestId("triage-review-detail")).toContainText("Not analyzed");
});

test("runtime guard shows fallback and missing-text notices when claim evidence is incomplete", async ({ page }) => {
  await page.goto("/workbench/paper-2025-nutrition");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  await expect(page.getByTestId("claim-guard-fallback")).toBeVisible();
  await expect(page.getByTestId("claim-guard-text-missing")).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByText("Missing evidence")).toBeVisible();
  await expect(claimsPanel.getByText("Text missing", { exact: true })).toBeVisible();
});

test("obsidian stats snapshot click jumps to mapped claim highlight", async ({ page }) => {
  await page.goto("/workbench/paper-2023-imaging");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText("Claim Link · p.1")).toBeVisible();

  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(mirrorPanel).toBeVisible();

  const targetCheck = mirrorPanel.getByRole("button").filter({ hasText: "effect-size" }).first();
  await expect(targetCheck).toBeVisible();
  await targetCheck.click();

  await expect(page.getByText("Claim Link · p.1")).toBeVisible();
  await expect(page.locator('[data-testid="claim-highlight"]').first()).toBeVisible();
  await page.screenshot({ path: "../tmp_verify_obsidian_stats_jump.png", fullPage: true });
});

test("duplicate claim highlights keep PDF focus on the bbox-backed page while claim review stays conservative", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel).toBeVisible();

  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();
  await expect(pdfPanel.getByText("Text Match · p.4")).toHaveCount(0);
  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button").first()).toContainText("Text fallback · p.1");
});

test("stats snapshot disambiguates target claim by text signal without losing the selected page cue", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();

  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  const targetCheck = mirrorPanel.getByRole("button").filter({ hasText: "effect-size-disambiguation" }).first();
  await expect(targetCheck).toBeVisible();
  await targetCheck.click();

  await expect(pdfPanel.getByText("Claim Link · p.2")).toBeVisible();
  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button").nth(1)).toContainText("Text fallback · p.2");
});

test("mirror grounding badges surface resolved and review-needed evidence states", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  const mirrorPanel = page.locator("article").filter({ hasText: "Obsidian Mirror" }).first();
  await expect(mirrorPanel).toBeVisible();

  await expect(mirrorPanel.getByTestId("workbench-mirror-claim-grounding-claim-1")).toContainText("Grounded");
  await expect(mirrorPanel.getByTestId("workbench-mirror-claim-grounding-claim-2")).toContainText("Not recorded");
  await expect(mirrorPanel.getByTestId("workbench-mirror-stat-grounding-mock-check-2")).toContainText("Needs review");
});

test("timeline surfaces user-triggered actions distinctly", async ({ page }) => {
  await page.goto("/workbench/paper-2026-ambiguous");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  const timelinePanel = page.locator("section").filter({ hasText: "Timeline" }).first();
  await expect(timelinePanel).toBeVisible();

  await expect(timelinePanel.getByTestId("timeline-pinned-user-action")).toContainText("User queued deep read");
  await expect(timelinePanel.getByTestId("timeline-source-user-action").first()).toContainText("USER");
  await expect(timelinePanel.getByTestId("timeline-row-user-action").first()).toContainText("User queued deep read");
});

test("notebook artifact normalization supports zero-based pages and mixed bbox units", async ({ page }) => {
  await page.goto("/workbench/paper-2026-notebook-normalized");

  await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();
  await expect(page.getByText(/^Mock mode$/)).toBeVisible();

  const pdfPanel = page.locator("section").filter({ hasText: "PDF Renderer" }).first();
  await expect(pdfPanel.getByText("Claim Link · p.1")).toBeVisible();

  const claimsPanel = page.locator("article").filter({ hasText: "Cell 1 Claim" }).first();
  await expect(claimsPanel.getByRole("button").first()).toContainText("Mapped · p.1");
  await claimsPanel.getByRole("button").nth(1).click();
  await expect(pdfPanel.getByText("Claim Link · p.2")).toBeVisible();
  await expect(claimsPanel.getByRole("button").nth(1)).toContainText("Mapped · p.2");
  await expect(pdfPanel.getByText("Text Match")).toHaveCount(0);
});

test.describe("mobile UX scenarios", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("mobile triage cards and workbench collapsed controls work", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Paper-first workspace", { exact: true })).toBeVisible();
    await expect(page.getByText(/^Mock mode$/)).toBeVisible();

    const firstMobileCard = page.locator("article").filter({ hasText: "Open Workbench" }).first();
    await expect(firstMobileCard).toBeVisible();
    await firstMobileCard.getByRole("button", { name: "Open Workbench" }).click();

    await expect(page).toHaveURL(/\/workbench\//);
    await expect(page.getByText(REVIEW_WORKBENCH_SUBTITLE)).toBeVisible();

    const controlsSummary = page.locator('summary:has-text("Review controls")').first();
    await expect(controlsSummary).toBeVisible();
    await controlsSummary.click();

    const runViewControls = controlsSummary.locator("xpath=..");
    await expect(runViewControls.getByLabel("Reading style")).toBeVisible();
    await expect(runViewControls.getByLabel("Context profile")).toBeVisible();
    await expect(runViewControls.locator('summary:has-text("Review maintenance")').first()).toBeVisible();
    await expect(page.getByRole("button", { name: /Run deep read|Cancel run/ }).first()).toBeVisible();
    await expect(page.getByText("Errors / Done")).toBeVisible();
    await expect(page.getByText("Pinned Events")).toBeVisible();

    const railSummary = page.getByRole("button", { name: /Papers ·/ }).first();
    await expect(railSummary).toBeVisible();
  });
});

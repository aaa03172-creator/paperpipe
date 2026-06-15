Status: Active
Date: 2026-05-22
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `AnalysisWorkbench` artifact panel grounding scorecard summary (`/workbench/:paperId`)
- Goal action: Let a research operator quickly inspect evidence-grounding health for a saved deep-read run without opening raw artifact JSON.
- Primary persona: Research operator deciding whether saved claims and evidence links are ready for reuse, comparison, export, or presentation.
- Current friction: The backend can write `evidence_grounding_scorecard.json`, but the workbench only exposes it through raw artifact data. Users must parse schema-shaped JSON to see whether claims are grounded, unsupported, or awaiting gold-set scoring.
- Success metric: The workbench shows a compact, honest scorecard card with readiness, non-canonical status, core grounding metrics, failure codes, and recommended next action.
- Constraints:
  - Preserve the existing `ArtifactPanel` layout and dark-first `--pp-*` token system.
  - Treat the scorecard as an additive review-gate artifact, not canonical structured state.
  - Do not infer gold-set accuracy when gold metrics are unavailable.
  - Keep raw JSON available for audit.

## Quick Review (5 min)
- The trust question is real: "Can I reuse these claims with confidence?"
- The answer should be visible near saved checks, inference boundary, and compiled knowledge.
- The card must distinguish runtime proxy metrics from gold-scored metrics.
- Missing scorecard data should say "not available" instead of inventing certainty.
- The UI should point to the next review action, not create a new workflow.

## Full Review
### P0
- If grounding status remains raw-JSON-only, operators can accidentally trust polished downstream artifacts while evidence linkage quality is weak.
- The UI must label the scorecard as `non_canonical` so it supports review without becoming another truth store.
- Gold-set metrics must appear only when available; otherwise the user should see that runtime proxies are being shown.

### P1
- Readiness, grounded evidence ratio, unsupported proxy rate, and locator/page coverage are the first scan targets.
- Failure codes should be visible as review triage cues, not hidden behind a debug drawer.
- Recommended next action should be shown in plain operator language.

### P2
- Future gold-set comparison and model benchmark summaries can extend this card without moving it.
- Stage-level failure ownership can remain summarized until operators need deeper debugging.

### Full Review Coverage
- 6P storyboard context:
  - Problem: the user wants to reuse paper claims but cannot quickly see whether evidence grounding is strong.
  - Emotion: concern that a good-looking summary might be unsupported or overstated.
  - Action: open the workbench for the saved run.
  - Struggle: scorecard data exists but is buried in raw artifact JSON.
  - Attempt: user expands raw JSON or relies on claim cards alone.
  - Happy Ending: user scans one card, sees grounding health and next action, then decides whether to review, fix, or reuse.
- BMAP:
  - Motivation is high when the user is about to export, compare, or present findings.
  - Ability improves when metrics are grouped and labeled in operator terms.
  - Prompt belongs near artifact trust surfaces, not in a separate settings page.
- B.I.A.S:
  - Block: raw scorecard JSON is high-effort and likely ignored.
  - Interpret: `runtime proxy` versus `gold scored` prevents false certainty.
  - Act: recommended next action gives a concrete review direction.
  - Store: repeated transparent scorecards build a habit of checking grounding before reuse.
- Peak-End:
  - Peak is answering "is this evidence-grounded enough?" without leaving the workbench.
  - Pit is trusting a downstream artifact because the raw scorecard was too hidden.
  - Transition is from claim reading into evidence-quality review.
  - End is a clear next step: review failures, add gold data, or reuse cautiously.
- Ethics:
  - Regret: pass if the card avoids overstating runtime proxy metrics as truth.
  - Black Mirror: pass if low-confidence/unsupported claims stay visible.
  - In Real-Life: the product should behave like a careful research assistant naming uncertainty.

## BMAP diagnosis
- Motivation: High for operators deciding reuse or export readiness.
- Ability: Currently limited by JSON-only access; improved by a compact card.
- Prompt: Strong when placed inside the artifact panel alongside saved checks and compiled knowledge.

## B.I.A.S diagnosis
- Block: The raw scorecard shape creates too much scanning effort.
- Interpret: Operators need metric labels that clarify proxy versus gold scoring.
- Act: The UI should make the next review action obvious without adding another command.
- Store: A consistent trust card makes evidence grounding feel inspectable and repeatable.

## Peak-End design notes
- Peak: readiness plus key grounding numbers should be understood in one glance.
- Pit: hiding grounding status behind raw JSON can lead to overtrust.
- Transition: place the card after saved checks and before inference/compiled outputs.
- End: keep the raw JSON drawer available for audit while the summary handles routine review.

## Concrete changes
- Add a read-only Evidence grounding scorecard card to `ArtifactPanel`.
- Pull scorecard data from `artifactBundle.files.evidence_grounding_scorecard.data`.
- Show readiness, layer/canonical status, runtime proxy metrics, available gold metrics, failure code counts, and recommended next action.
- Use existing badge, border, and dark-first token patterns.
- Keep scorecard absence quiet with a short "not generated yet" message only when the artifact entry is missing or absent.
- Current implementation surfaces `missing_p0_gold_metrics` and `accepted_corrections_not_replayable` as visible review-gate reason codes.

## Ethics check results
- Regret: Low. The design exposes uncertainty and missing gold-set evaluation instead of hiding it.
- Black Mirror: Low. It does not rank papers or users; it surfaces review quality signals.
- In Real-Life: Pass. A careful colleague would tell you which claims still need evidence review before reuse.

## Next PR-sized actions
- Add a direct correction-log affordance from high-risk failure codes once the correction API has a stable frontend flow.
- Add a benchmark comparison view after multiple scorecards can be selected.
- Add route-level browser coverage for the scorecard card once the workbench fixture includes scorecard data.

## Verification
- `cd frontend && npm run build` passes.
- `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "workbench surfaces evidence grounding scorecard in mock mode"` passes.
- `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "workbench surfaces evidence grounding scorecard|workbench grounding scorecard surfaces failure codes"` passes.
- The mock E2E path covers both a warning scorecard with unavailable gold metrics and a failing scorecard with visible failure codes.
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend seeded fixture bootstrap meta matches available artifacts|backend workbench shows evidence grounding scorecard from live artifact bundle"` passes.
- `.venv/bin/python -m pytest tests/test_artifacts_runs_api.py::test_artifacts_latest_and_run_bundle tests/test_jobs_api_smoke.py::test_jobs_bootstrap_meta_endpoint_returns_file_content` passes.
- The live backend E2E path seeds `evidence_grounding_scorecard.json`, exposes the scorecard through the artifact bundle, and confirms Workbench renders the non-canonical review-gate summary from the live API path.

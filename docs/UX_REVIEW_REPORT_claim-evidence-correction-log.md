Status: Active
Date: 2026-05-22
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `AnalysisWorkbench` artifact panel correction log handoff (`/workbench/:paperId`)
- Goal action: Let a research operator save a claim/evidence correction case from a grounding scorecard failure without rewriting canonical claim state.
- Primary persona: Research operator reviewing unsupported, overstated, or wrongly linked claims before reuse.
- Current friction: The correction API can persist append-only improvement data, but accepted eval-candidate rows now require replay lineage that older scorecards do not expose.
- Success metric: The operator can select a claim, open the scorecard correction section, choose a failure reason, edit corrected claim text, save a non-canonical correction case, and only opt into eval reuse when parser/model/prompt/profile lineage is available.
- Constraints:
  - Correction records are improvement/eval data, not canonical claim truth.
  - Keep the form small and tied to the selected claim.
  - Preserve scorecard runtime/gold metric boundaries.
  - Avoid collecting unnecessary personal data; default reviewer is a simple local operator label.

## Quick Review (5 min)
- The correction action belongs next to failure codes, not in raw JSON.
- The form should be collapsed by default so it does not interrupt normal review.
- The copy must say it does not rewrite the saved claimset.
- Reason codes should come from scorecard failures when available.
- Saving should produce clear feedback and leave the user's current review context intact.

## Full Review
### P0
- Do not let a correction form imply that the canonical claimset was changed.
- Do not create a second truth store; the saved record is append-only review/eval data.
- Keep evidence locator capture bounded to the current selected claim anchor.
- Do not submit `accepted_for_eval=true` unless replay lineage is available.

### P1
- Default reason codes should reflect scorecard failures.
- The operator should see why eval reuse is unavailable when lineage is missing.
- Submission feedback should confirm persistence and review-feedback linkage without promising downstream adoption.

### P2
- Recent corrections should remain visible for the selected claim.
- Future work can expand exact locator editing for figure/table/table-cell corrections.

### Full Review Coverage
- 6P storyboard context:
  - Problem: an operator spots a weak or wrong claim/evidence link during review.
  - Emotion: concern that the issue will be forgotten after leaving the Workbench.
  - Action: open the scorecard correction section for the selected claim.
  - Struggle: correction data needs structured reason/evidence lineage, not a vague note.
  - Attempt: operator edits the claim text and saves a reason-coded correction.
  - Happy Ending: the correction is stored for review/prompt/model improvement, becomes eval-reusable only when replay lineage exists, and does not mutate canonical state.
- BMAP:
  - Motivation is high when the operator is already looking at a failure code.
  - Ability improves through defaults: selected claim, scorecard reason, current evidence anchor, reviewer label.
  - Prompt is the scorecard failure code itself.
- B.I.A.S:
  - Block: the form is collapsed and appears only inside the scorecard context.
  - Interpret: wording explains correction logs are non-canonical.
  - Act: one save button records the structured case.
  - Store: a clear saved/export-status message reinforces what the correction can and cannot be reused for.
- Peak-End:
  - Peak is turning a discovered grounding defect into a saved structured correction.
  - Pit is losing the defect as an informal note or raw memory.
  - Transition is failure-code review -> correction capture -> continue reading.
  - End is confirmation that the case was saved without changing claim truth.
- Ethics:
  - Regret: pass if the UI remains clear that this does not rewrite the saved claim.
  - Black Mirror: pass if reviewer data stays minimal and local.
  - In Real-Life: a careful collaborator records the correction and says what it did not change.

## BMAP diagnosis
- Motivation: High at the moment a failure code is visible.
- Ability: Medium-high with selected-claim defaults; deeper evidence editing can come later.
- Prompt: Strong when placed under the grounding scorecard's failure summary.

## B.I.A.S diagnosis
- Block: Collapsed details avoid adding clutter to routine scorecard scans.
- Interpret: Non-canonical copy prevents overtrust.
- Act: Required fields are few: reason, reviewer, corrected text.
- Store: Save/export-status feedback gives closure and keeps replayable eval reuse distinct from ordinary correction memory.

## Peak-End design notes
- Peak: "I found a grounding issue and captured it before I forgot."
- Pit: "I know this is wrong but have nowhere structured to put it."
- Transition: failure code -> selected claim -> correction record.
- End: saved correction case remains separate from claim truth while showing whether it was exported or kept as correction memory only.

## Concrete changes
- Add a collapsed `Log correction case` section to the Workbench scorecard card.
- Default reason codes from scorecard failure codes when available.
- Submit append-only correction records through `/claim-evidence-corrections`.
- Include selected claim text, current evidence anchor, reason code, reviewer label, eval-candidate flag, and scorecard metadata.
- Disable eval acceptance when the scorecard lacks complete parser/model/prompt/profile lineage, with inline copy explaining the missing prerequisite.
- Read typed scorecard `candidate_config` lineage when it is present, so replayable scorecard artifacts can enable eval acceptance without inventing lineage in the UI.
- Support run-local `candidate_config.json` sidecars in scorecard rebuilds, giving operators an artifact-backed way to make Workbench eval acceptance available for replayable runs.
- Show recent correction cases for the selected claim after save, keeping them separate from canonical claim state.
- When an eval-candidate correction has replay lineage and no existing `related_feedback_id`, the backend creates a linked `artifact_review_feedback` row with artifact type `evidence_grounding_scorecard`; the UI reports `feedback linked`.
- Expose backend filters for accepted eval candidates and feedback export status so a later review queue can reuse the same correction store instead of introducing a parallel one.

## Ethics check results
- Regret: Low. The UI explicitly says it does not rewrite the saved claimset and blocks eval acceptance without replay lineage.
- Black Mirror: Low. It captures minimal reviewer identity and no hidden tracking.
- In Real-Life: Pass. The flow behaves like a research teammate preserving a correction for later review.

## Next PR-sized actions
- Expand locator editing for figure/table/table-cell corrections.
- Add a focused review queue surface for accepted eval-candidate corrections using the existing correction list filters.
- Generate or backfill replayable scorecards with complete candidate lineage for runs that should support Workbench eval acceptance.

## Verification
- `.venv/bin/python -m pytest tests/test_claim_evidence_corrections_api.py -q` passes: `18 passed, 5 warnings`.
- `.venv/bin/python -m pytest tests/test_paper_understanding_gold.py tests/test_claim_evidence_corrections_api.py tests/test_evidence_grounding_scorecard.py tests/test_evidence_grounding_benchmark.py -q` passes: `437 passed, 5 warnings`.
- `cd frontend && npm run build` passes.
- `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "workbench can log a non-canonical correction case|workbench surfaces evidence grounding scorecard|workbench grounding scorecard surfaces failure codes"` passes: `3 passed`.
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench shows evidence grounding scorecard from live artifact bundle|backend workbench saves and reloads claim evidence correction cases"` passes: `2 passed`.
- Mock and backend E2E verify that current scorecards disable eval acceptance without lineage and still save ordinary non-canonical correction cases.
- Scorecard schema/service tests verify that `candidate_config` lineage can be carried through the non-canonical scorecard artifact.

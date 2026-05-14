# UX Review Report: Paper Detail Right Rail

Status: Implemented route-specific UX report with follow-up evidence-meter guard
Date: 2026-05-14
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Screen/Flow: `/papers/:slug` Paper Detail right rail and mobile sheet
Goal action: make source state, saved evidence state, personal markers, and safe next action legible before guarded actions
Primary persona: biomedical researcher reading a saved paper note and deciding whether to continue reading, inspect evidence, or open Workbench
Current friction: `PaperNoteDetailPage.tsx` contains the right panels, but the rail/sheet order and header actions do not yet fully follow the shared source -> evidence -> personal memory -> downstream -> guarded action grammar
Success metric: users can identify saved state, claim/evidence availability, personal markers, and the primary `Open review` handoff before encountering lower-priority actions or debug/properties panels
Constraints: route-only micro-spike, no backend/schema/dependency changes, no chat/runtime/provider settings, no full redesign, preserve existing panels and markdown rendering

Related docs:
- `docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`
- `docs/PaperPipe_UI_GRAMMAR.md`
- `docs/PaperPipe_Page_Architecture.md`
- `docs/PaperPipe_Extracted_Data_Workflow_Map.md`
- `docs/API_CHAT_CONTRACT.md`

## 1. Executive Summary

The first UI implementation should be a Paper Detail micro-spike focused on rail and mobile sheet ordering.

The current route already has the right building blocks:
- `SavedStatePanel`
- `ClaimSetPanel`
- `OperatorStatePanel`
- `ActionsPanel`
- `AutomationResultsPanel`
- `PropertiesPanel`
- `RelatedPapersPanel`
- `ReferencesPanel`
- `ReviewSnapshotPanel`
- `ReviewBridgePanel`
- `ReadingAssistPanel`
- `OutlinePanel`
- `SectionNavigatorPanel`
- `AppraisalPanel`

The safest change is to reuse these panels and change only:
- ordering
- grouping
- section copy
- action hierarchy
- mobile sheet order
- optional tiny helper arrays for panel composition

Do not rewrite `PaperNoteDetailPage.tsx`. It is large, but it already contains evidence-aware and provenance-aware pieces. The first patch should make the product grammar more obvious without changing what data is loaded or how actions execute.

## 2. Quick Review (5 min)

- Choice count: too many actions appear near the top of the route before the trust hierarchy settles.
- Benefit: existing saved state, claim/evidence, personal marker, and action panels can be reordered into a clearer research sequence.
- Next action: make `Open review` the main evidence handoff, with protocol/action panels visibly downstream or guarded.
- Feedback: preserve existing save, deep-read, action, and focus feedback.
- Ethics: avoid making reading assist, generated summaries, or action output look stronger than saved evidence state.

## 3. Full Review

### P0

- Do not change backend APIs, schemas, persistence, artifact shapes, markdown rendering, claim extraction, or action execution.
- Do not add `approved`, `verified`, `final`, `canonical approval`, graph truth, or assistant states.
- Do not add CopilotKit, Lazyweb runtime, graph visualization, animation libraries, provider settings, or live chat.
- Do not introduce `used by` or `stale impact` panels unless existing route data supports them.
- Do not store provider secrets, MCP tokens, or assistant config in the browser.

### P1

- Reorder desktop right rail and mobile sheet around the shared grammar:
  1. saved/source state
  2. claim/evidence availability
  3. personal markers
  4. related source context
  5. references
  6. guarded actions
  7. run history / automation / appraisal
  8. properties/debug
- Keep `ActionsPanel` but relabel its role as guarded/maintenance actions.
- Keep `ClaimSetPanel` near the top because it is the evidence bridge to Workbench.
- Keep `OperatorStatePanel` below evidence state because personal memory is important but not evidence truth.
- Move lower-value metadata/properties lower than related papers and references.

### P2

- Defer broad coverage gauges until a precise metric is available.
- Allow a narrow per-claim evidence meter when it only summarizes already-loaded claim evidence anchors and grounding metadata, without creating a new readiness score or truth state.
- Defer relationship summaries until route data can identify reuse/stale impact without inventing relationships.
- Defer header action simplification if it risks changing tested flows; rail/sheet order can land first.

## 4. Full Review Coverage

6P storyboard context:
- Problem: the researcher lands on a paper note and must decide whether to read, inspect evidence, save personal markers, or run a guarded action.
- Emotion: they want confidence that they are not acting on generated or incomplete state.
- Action: they scan the right rail or mobile sheet, then open Workbench or continue reading.
- Struggle: current panels are all useful, but the order can mix source/evidence, personal memory, actions, properties, and automation.
- Attempt: reorder panels without changing runtime contracts.
- Happy Ending: the user sees saved state and evidence availability first, then personal memory and related context, then guarded actions.

BMAP:
- Motivation: high because the route is the bridge from reading to evidence review.
- Ability: high if the rail order matches a stable pattern and avoids extra choices.
- Prompt: `Open review` should appear as the obvious evidence handoff after state context.

B.I.A.S:
- Block: reduce cognitive load by grouping panels into trust sequence rather than feature type.
- Interpret: titles/descriptions should clarify whether a panel is source state, evidence state, personal memory, downstream action, or debug.
- Act: put guarded actions after source/evidence/personal marker context.
- Store: repeat the same rail order on mobile sheet so users learn one mental model.

Peak-End:
- Peak: user opens Workbench from Paper Detail knowing saved state and claim/evidence availability.
- Pit: user sees actions or generated/downstream options before understanding source state.
- Transition: Paper Library -> Paper Detail -> Workbench should preserve paper identity and evidence status.
- End: if the user does not open Workbench, they still leave with personal markers saved and source context intact.

Ethics:
- Regret: reduced by showing evidence availability before action.
- Black Mirror: risk appears if generated action output or reading assist becomes visually stronger than evidence state.
- In Real-Life: PaperPipe should say "here is what is saved, here is what is evidence-linked, here is what you can safely do next."

## 5. Current Code Reality

Main route:
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`

Relevant panel functions:
- `ReadingAssistPanel` at `PaperNoteDetailPage.tsx`
- `PropertiesPanel` at `PaperNoteDetailPage.tsx`
- `AppraisalPanel` at `PaperNoteDetailPage.tsx`
- `ReviewSnapshotPanel` at `PaperNoteDetailPage.tsx`
- `ReviewBridgePanel` at `PaperNoteDetailPage.tsx`
- `SavedStatePanel` at `PaperNoteDetailPage.tsx`
- `OutlinePanel` at `PaperNoteDetailPage.tsx`
- `SectionNavigatorPanel` at `PaperNoteDetailPage.tsx`
- `RelatedPapersPanel` at `PaperNoteDetailPage.tsx`
- `ReferencesPanel` at `PaperNoteDetailPage.tsx`
- `ActionsPanel` at `PaperNoteDetailPage.tsx`
- `AutomationResultsPanel` at `PaperNoteDetailPage.tsx`
- `ClaimSetPanel` at `PaperNoteDetailPage.tsx`
- `OperatorStatePanel` at `PaperNoteDetailPage.tsx`

Existing desktop rail order in read mode:
1. `SavedStatePanel`
2. `ClaimSetPanel`
3. `OperatorStatePanel`
4. `PropertiesPanel`
5. `RelatedPapersPanel`
6. `ReferencesPanel`
7. `ActionsPanel`
8. `AutomationResultsPanel`

Existing desktop rail order in review mode:
1. `SavedStatePanel`
2. `ClaimSetPanel`
3. `OperatorStatePanel`
4. `ActionsPanel`
5. `AppraisalPanel`
6. `AutomationResultsPanel`
7. `PropertiesPanel`
8. `RelatedPapersPanel`
9. `ReferencesPanel`

Existing mobile sheet largely mirrors the two mode-specific orders and also includes outline/navigation panels.

## 6. Recommended Desktop Rail Order

Use the same order in read and review modes for the core trust sequence. Review mode can add `AppraisalPanel`, but should not move guarded actions above source/evidence/personal marker context.

Recommended core order:

1. `SavedStatePanel`
   - role: saved/source state
   - copy tweak: clarify that loaded state is available, not scientific validation

2. `ClaimSetPanel`
   - role: claim/evidence availability
   - copy tweak: describe claims as saved state for review, not truth
   - optional label: `Evidence availability`

3. `OperatorStatePanel`
   - role: personal memory
   - keep existing boundary copy

4. `RelatedPapersPanel`
   - role: related source context
   - keep before actions because it helps reading context

5. `ReferencesPanel`
   - role: source/reference context

6. `ActionsPanel`
   - role: guarded/maintenance actions
   - copy tweak: title should become `Guarded actions` or description should say actions can update generated state or markdown summary but do not change source truth

7. `AppraisalPanel`
   - role: review artifact, only when present
   - place after guarded actions or before run history depending on whether it is more relevant to review mode; do not put it above saved/claim/personal state

8. `AutomationResultsPanel`
   - role: run history and debug/lineage support

9. `PropertiesPanel`
   - role: metadata/debug support
   - keep lower than related/reference context

Read mode should omit `AppraisalPanel` when unavailable but keep the same surrounding order.

Review mode should not move `ActionsPanel` above `RelatedPapersPanel` and `ReferencesPanel` unless the action is the only viable recovery path for missing state.

## 7. Recommended Mobile Sheet Order

Mobile sheet should prioritize trust sequence, then navigation:

1. `SavedStatePanel`
2. `ClaimSetPanel`
3. `OperatorStatePanel`
4. `RelatedPapersPanel`
5. `ReferencesPanel`
6. `ActionsPanel`
7. `AppraisalPanel` when present
8. `AutomationResultsPanel`
9. `PropertiesPanel`
10. `OutlinePanel`
11. `SectionNavigatorPanel`

Rationale:
- Mobile users opening `Note panels` usually need state/action context, not just navigation.
- Outline and section navigation are still useful, but they duplicate reading navigation rather than owning trust state.
- If focus deep link opens the sheet, `SavedStatePanel` and `ClaimSetPanel` should still appear first so focused claims are interpreted in context.

## 8. Header Action Guidance

Do not overhaul header actions in the first patch.

Allowed tiny copy/order adjustments:
- keep `Open review` as the dominant evidence handoff
- keep `Runtime checks` as support/recovery
- keep protocol actions visually secondary
- do not add assistant or provider actions
- do not move protocol generation above saved/evidence state in the rail

Defer:
- full header action redesign
- import/deep-read card redesign
- protocol attachment flow redesign

## 9. Relationship And Reuse Decision

Do not add `Used by` or `Stale impact` UI in the first patch unless existing `PaperNoteDetailResponse` data already exposes it directly.

For the first patch:
- acceptable: add a short absence note in the UX report that relationship data is not yet route-owned
- unacceptable: create a fake relation panel, fake graph, or static placeholder that implies data exists

Future route-specific data review should inspect:
- `PaperNoteDetailResponse`
- structured state `claimset`
- context trace summary
- artifact references
- paper synthesis lineage
- downstream artifact indexes

## 10. Concrete Implementation Changes

First code patch should be limited to:
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`

Preferred implementation shape:
- create small local render helpers or arrays for desktop rail sections and mobile sheet sections
- use those helpers to remove duplicated mode-specific ordering
- keep existing panel props unchanged
- update `ActionsPanel` title/description copy only if low-risk
- avoid changing component internals unless copy needs clarification

Do not touch:
- `frontend/src/app/lib/api.ts`
- `frontend/src/app/lib/types.ts`
- backend routes
- schemas
- tests snapshots unless visual verification requires updates
- package dependencies

Suggested route-level grouping:

```text
trustSequence:
  SavedStatePanel
  ClaimSetPanel
  OperatorStatePanel

contextSequence:
  RelatedPapersPanel
  ReferencesPanel

guardedSequence:
  ActionsPanel
  AppraisalPanel when present
  AutomationResultsPanel

supportSequence:
  PropertiesPanel
  OutlinePanel / SectionNavigatorPanel on mobile
```

## 11. Acceptance Criteria

The micro-spike is acceptable when:
- desktop read and review modes share the same core trust order
- mobile sheet order matches the trust order
- `ActionsPanel` is not presented as a primary evidence action
- personal markers remain separate from claim/evidence state
- per-claim visual evidence signals only summarize `claim.evidence[*].grounded` / `resolution` and missing metadata as `not recorded`
- no fake `used by` or `stale impact` data is introduced
- no dependency, schema, API, provider, chat, or runtime behavior changes
- `/api/chat` remains stub-only
- no new public token/config paths are added

## 11.1 Follow-Up Evidence Meter

The follow-up implementation may add a compact meter inside each saved claim card:
- label: `Evidence anchors`
- count: number of saved evidence anchors attached to the claim
- segments: grounded, needs review, unresolved, and not recorded
- color source: existing `--pp-*` status tokens only
- boundary: this is a display summary of saved structured state, not a new score, approval, or product requirement

This keeps the visual language useful without making the page feel like a colorful dashboard. It also avoids overstating biomedical certainty when older fixtures or saved states do not preserve grounding metadata; those cases should say `not recorded`.

## 12. Verification Plan

Required after implementation:
- `cd frontend && npm run build`

Targeted checks to inspect before choosing tests:
- `frontend/e2e/backend.spec.ts` for Paper Notes / Paper Detail coverage
- `frontend/e2e/visual-backend.backend.spec.ts` for existing visual snapshots touching Paper Detail

Run Playwright only if:
- existing tests cover Paper Detail right rail or mobile sheet
- route layout changes are large enough to require visual comparison

Document-only checks for this report:
- `python3 scripts/lint_docs.py docs/UX_REVIEW_REPORT_paper-detail-right-rail.md`
- `git diff --check -- docs/UX_REVIEW_REPORT_paper-detail-right-rail.md`
- `python3 scripts/check_no_live_secrets.py --root .`

## 13. Next PR-Sized Actions

1. Implement the Paper Detail rail/sheet micro-spike.
   - Keep the patch route-local and order/copy-only.

2. Build and verify.
   - Run frontend build.
   - Run targeted tests only if existing coverage maps to the changed surface.

3. Re-audit after screenshot/build.
   - Decide whether Workbench or Paper Library should receive the next grammar pass.

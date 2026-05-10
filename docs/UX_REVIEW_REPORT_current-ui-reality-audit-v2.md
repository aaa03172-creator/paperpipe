# UX Review Report: Current UI Reality Audit v2

Status: Proposed audit
Date: 2026-05-10
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Screen/Flow: Current core UI routes
Goal action: choose the safest first reference-driven UI spike
Primary persona: biomedical researcher reading papers, checking evidence, and reusing downstream artifacts
Current friction: strong evidence-aware features exist across routes, but scan hierarchy, relationship visibility, and action order are not yet governed by one shared UI grammar
Success metric: first route spike can improve source/evidence/state/reuse/action clarity without changing runtime contracts or adding dependencies
Constraints: Vite + React Router, TailwindCSS, existing `--pp-*` tokens, local-first, `/api/chat` stub-only, no new runtime dependency without approval

Related docs:
- `docs/PaperPipe_Design_Identity.md`
- `docs/PaperPipe_Page_Architecture.md`
- `docs/PaperPipe_Extracted_Data_Workflow_Map.md`
- `docs/PaperPipe_UI_GRAMMAR.md`
- `docs/Reference_Driven_Redesign_Plan_2026-05-10.md`
- `docs/API_CHAT_CONTRACT.md`

## 1. Executive Summary

The current UI is not a blank slate and should not be redesigned wholesale.

The existing frontend already has many correct ingredients:
- React Router route family around Home, Paper Notes, Paper Detail, Workbench, artifact viewers, and Runtime readiness
- dark-first `--pp-*` visual tokens
- local `StatusBadge`, `StatusChip`, `Stepper`, `Rail`, `WorkspaceContextStrip`, `ArtifactHeaderContext`, `ArtifactPanel`, and shadcn-style primitives
- lucide icons in meaningful controls
- route-level warnings, fallback states, runtime guidance, and downstream artifact disclaimers

The main gap is not lack of visual polish. The main gap is that the product grammar is not applied evenly:
- Paper Detail has the right information but too much of it competes in the header and rail.
- Paper Library has useful next-action cards but still reads partly like a rich index rather than a source/evidence handoff surface.
- Workbench is already the strongest evidence-first surface but could tighten source coverage, warning density, and repair action grouping.
- Artifact detail pages are improving, especially Meeting Pack, but still need a reusable artifact review grammar across Meeting Pack, Chart Pack, Method Comparison, Image Evidence, and Protocol Card.
- Runtime Readiness is useful and product-aware, but should remain support/recovery, not a workspace homepage.

Recommendation:
- first implementation spike should be a bounded Paper Detail right-rail and mobile-sheet grammar pass, not a full Paper Detail redesign
- if implementation risk is considered too high because `PaperNoteDetailPage.tsx` is large, the fallback first spike should be Paper Notes List row state/action grammar

## 2. Quick Review (5 min)

- Choice count: Home, Paper Notes, and Workbench generally expose a clear next action; Paper Detail exposes too many high-value actions in the first viewport.
- Benefit: current UI already cares about source, review, runtime, and downstream artifact boundaries.
- Next action: use the completed Paper Detail right-rail UX report to implement the bounded route-local micro-spike.
- Feedback: save, import/deep-read, sync, regenerate, rerender, and runtime fallbacks already have feedback patterns that should be reused.
- Ethics: most screens warn that generated/downstream artifacts are not source truth, but success/readiness badges need stricter wording in future route work.

## 3. Full Review

### P0

- Do not add CopilotKit, Lazyweb, graph visualization, motion libraries, or assistant runtime work during the first UI spike.
- Do not change `/api/chat` from stub-only.
- Do not introduce browser-owned provider secrets or settings-held API keys.
- Do not add `approved`, `verified`, `final`, or `canonical approval` states.
- Do not change schemas, artifact shapes, or persistence to support visual redesign.

### P1

- Start with Paper Detail right rail ordering because it is the core reading-to-evidence bridge.
- Keep the first Paper Detail spike to layout/order/copy/state grouping only.
- Preserve existing `SavedStatePanel`, `ClaimSetPanel`, `OperatorStatePanel`, `ActionsPanel`, `AutomationResultsPanel`, `PropertiesPanel`, `RelatedPapersPanel`, and `ReferencesPanel`; reorder and relabel before rewriting.
- Make mobile sheet order match `docs/PaperPipe_UI_GRAMMAR.md`.
- Add route-level `used by` / `stale impact` placeholders only if data already exists; otherwise document as missing rather than inventing relation state.

### P2

- Later apply the same grammar to Workbench and artifact detail family.
- Later add visual state refinements such as coverage bars, warning density, or progress gauges only after each metric is precisely labeled.
- Later create assistant-boundary UX report, but not before chat/runtime contract changes.

## 4. Full Review Coverage

6P storyboard context:
- Problem: the UI now covers reading, claim review, figure/table evidence, artifacts, notes, runtime readiness, and future assistant support.
- Emotion: the researcher wants confidence and recoverability, not a busier interface.
- Action: the user opens Home, chooses a paper, reads detail, jumps to Workbench, and reviews an artifact.
- Struggle: route-level state is useful but sometimes scattered, so users must infer which panel owns source, evidence, personal memory, artifact reuse, or next action.
- Attempt: audit current routes against the new UI grammar before implementation.
- Happy Ending: a user can identify source state, evidence state, personal markers, downstream reuse, and the next safe action in one scan.

BMAP:
- Motivation: high because users need to trust evidence and downstream reuse.
- Ability: medium; current UI already contains the data, but panel order and state grouping require route-specific cleanup.
- Prompt: Paper Detail should prompt `Open review` only after source/saved-state/evidence context is visible.

B.I.A.S:
- Block: reduce first-scan overload by moving maintenance/debug/actions below source and review state.
- Interpret: rename and group current panels around source, evidence, review, personal memory, downstream, and guarded actions.
- Act: preserve one primary action per route; keep guarded actions behind warnings/provenance.
- Store: repeat the same rail/sheet order across Paper Detail, Workbench, and artifact detail.

Peak-End:
- Peak: a user moves from paper text or a claim panel into Workbench with evidence context intact.
- Pit: a user sees many badges/actions but cannot tell which are source truth, personal markers, or downstream artifacts.
- Transition: Paper Library -> Paper Detail -> Workbench already exists and should be clarified rather than replaced.
- End: artifact handoff should end with provenance, warnings, and draft/reuse state.

Ethics:
- Regret: reduced by preventing visual polish from overstating evidence confidence.
- Black Mirror: risk appears if repeated downstream artifact badges look like independent confirmation.
- In Real-Life: the product should act like a careful lab colleague who points back to source before proposing action.

## 5. Current Route Inventory

The frontend route table is defined in `frontend/src/App.tsx`:

| Route | Page file | Current family | Audit priority |
| --- | --- | --- | --- |
| `/` | `frontend/src/app/pages/TriageDashboard.tsx` | Home / Recovery | P1 |
| `/papers` | `frontend/src/app/pages/PaperNotesListPage.tsx` | Paper Library | P1 |
| `/papers/:slug` | `frontend/src/app/pages/PaperNoteDetailPage.tsx` | Paper Detail | P0 first spike candidate |
| `/workbench/:paperId` | `frontend/src/app/pages/AnalysisWorkbench.tsx` + `WorkbenchLayout.tsx` | Evidence Workbench | P1 second spike candidate |
| `/meeting-packs`, `/meeting-packs/:packId` | `frontend/src/app/pages/MeetingPackPage.tsx` | Artifact Detail | P1 |
| `/method-comparisons`, `/method-comparisons/:comparisonId` | `frontend/src/app/pages/MethodComparisonPage.tsx` | Artifact Detail | P2 |
| `/chart-packs`, `/chart-packs/:chartPackId` | `frontend/src/app/pages/ChartPackPage.tsx` | Artifact Detail | P2 |
| `/image-evidence`, `/image-evidence/:imageEvidenceId` | `frontend/src/app/pages/ImageEvidencePage.tsx` | Figure / Table Evidence | P1 |
| `/protocol-cards`, `/protocol-cards/:protocolId` | `frontend/src/app/pages/ProtocolCardPage.tsx` | Artifact Detail | P2 |
| `/ready` | `frontend/src/app/pages/RuntimeReadinessPage.tsx` | Runtime / Diagnostics | P2 |

## 6. Route Scores

Scale:
- 1 = weak
- 2 = present but scattered
- 3 = usable
- 4 = strong
- 5 = route already matches the new grammar

| Route family | First-scan question | State/provenance clarity | Action hierarchy | Evidence/reuse visibility | Visual grammar readiness | Risk |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Home / Recovery | What should I continue now? | 4 | 4 | 2 | 4 | medium |
| Paper Library | Which paper should I open, repair, or review? | 3 | 4 | 2 | 3 | low |
| Paper Detail | What am I reading, what state exists, and what evidence should I inspect next? | 3 | 2 | 3 | 3 | high |
| Evidence Workbench | Which claim needs attention and what supports it? | 4 | 4 | 4 | 4 | medium |
| Meeting Pack Detail | What upstream evidence does this draft use, and is it safe to reuse? | 4 | 4 | 3 | 4 | medium |
| Other artifact detail | What source and review state backs this artifact? | 3 | 3 | 3 | 3 | medium |
| Runtime / Diagnostics | Is this local machine ready or blocked? | 4 | 4 | n/a | 4 | low |

## 7. Findings By Route

### 7.1 Home / Recovery

Current strengths:
- `TriageDashboard.tsx` already models resume priority, blocker/review/reading states, workspace summary, and marker summaries.
- It uses `Rail`, `StatusBadge`, `StatusChip`, `ContentReviewSummary`, and `OperationalStateSummary`.
- It asks the right question: continue reading, review, or fix blocker.

Gaps:
- Relationship visibility is still shallow: users see queues and markers, but not `used by` or stale downstream impact.
- Queue/counter language must stay grounded in actual state and avoid becoming a fake project dashboard.

PR-sized action:
- defer implementation until Paper Detail spike proves the grammar.

### 7.2 Paper Library

Current strengths:
- `PaperNotesListPage.tsx` has structured filters, row-level state badges, operator markers, checks, source type, and next-action cards.
- The row-level next action already chooses between note, review, and repair.
- Search, tag filtering, reading-assist filtering, and import state are mature enough to preserve.

Gaps:
- Some badges use success/accent language for `Saved note`, `Claims saved`, and structured tags; future copy should clarify these are availability/state, not scientific validation.
- Source state is present but low-detail: DOI/Zotero/Vault are visible, but local PDF/open-access/institution/missing distinctions are stronger elsewhere.
- Reuse/stale impact is not visible at the list level.

Fallback first spike if Paper Detail is too risky:
- tighten row state vocabulary and icon/label hierarchy without changing data contracts.

### 7.3 Paper Detail

Current strengths:
- `PaperNoteDetailPage.tsx` is already close to the desired route shape: header context, center reading body, left outline/context, right panels, mobile sheet, sticky mobile action.
- It separates saved state, claims, operator markers, properties, related papers, references, actions, and automation results.
- It supports focus deep links for claim/evidence/run.
- It has import/deep-read progress feedback and runtime fallback guidance.

Gaps:
- The first viewport has too many actions: Runtime checks, Save protocol card, Attach protocol file, Note panels, Open review, plus import/deep-read actions in some states.
- Right rail order is close but not identical to the new grammar. Current order generally starts with saved state and claimset, but relationship/reuse and stale-impact summaries are not explicit.
- `ActionsPanel` can appear before lower-value context depending on mode, and its role as guarded/maintenance action is not always clear.
- Mobile sheet repeats many panels but should explicitly follow the grammar order: saved/source state, warnings, provenance, coverage, used-by/stale impact, personal markers, primary action, secondary actions, guarded actions, debug.
- Reading Assist is useful but should stay visually weaker than source/evidence.

Recommended first spike:
- Paper Detail right rail + mobile sheet ordering only.
- Do not rewrite markdown rendering, claim extraction, operator state, action execution, or backend APIs.

### 7.4 Evidence Workbench

Current strengths:
- `AnalysisWorkbench.tsx` plus `WorkbenchLayout.tsx` already implements a strong evidence workbench: left paper rail, center PDF panel, right artifact panel/timeline.
- Header uses `WorkspaceContextStrip` for access, saved review state, paper note markers, and claim review.
- `Stepper` shows pipeline stage and job status.
- Warnings and repair notices are visible before action feedback.
- `ArtifactPanel` connects claims, highlights, inference summary, obsidian mirror, paper synthesis, and review state.

Gaps:
- This route is dense and should not be the first redesign target unless Paper Detail is blocked.
- Warning density and source coverage could become better gauges later, but only if labels are precise.
- Terminal logs and maintenance controls are present; keep them folded and secondary.

Second spike candidate:
- after Paper Detail, tighten Workbench source coverage/warning density/action grouping.

### 7.5 Meeting Pack / Artifact Detail

Current strengths:
- `MeetingPackPage.tsx` already says meeting packs are downstream briefing artifacts.
- Detail view separates draft summary, source items, slide outline, review state, continue-from-draft, validation, maintenance, and retrieval trace.
- Regenerate/rerender are inside `Draft maintenance`, which matches guarded-action grammar.
- It explicitly states readiness is a reuse gate, not proof that claims are reviewed.

Gaps:
- Artifact detail grammar should be extracted into a shared pattern for Meeting Pack, Chart Pack, Method Comparison, Image Evidence, and Protocol Card.
- `readiness` and `Can regenerate` success styling should remain carefully labeled as process/reuse state, not correctness.
- Source refs are visible at the pack level; future work should attach refs closer to individual reusable units where existing data supports it.

PR-sized action:
- defer until after Paper Detail and Workbench route grammar.

### 7.6 Figure / Table Evidence

Current strengths:
- `ImageEvidencePage.tsx` exists as its own route family and uses source/review/route icons.
- It is structurally aligned with future Figure / Table Evidence work.

Gaps:
- Needs dedicated audit before implementation because figure/table evidence can easily look canonical through styling.
- Must preserve the rule that visual evidence ledgers are review artifacts, not truth owners.

PR-sized action:
- create route-specific UX report before any visual/viewport change.

### 7.7 Runtime / Diagnostics

Current strengths:
- `RuntimeReadinessPage.tsx` is clearly a recovery/support page.
- It uses status badges, warning/failure states, suggested fixes, and product-loop guidance.
- It links users back to Paper Notes or Meeting Packs rather than trying to become the main workspace.

Gaps:
- Summary cards are useful but should not grow into a KPI dashboard.
- Animated refresh spinner is acceptable but should remain reduced-motion compatible where feasible.

PR-sized action:
- no immediate redesign needed.

## 8. Visual State Opportunities

Accept for first spike:
- right-rail section icons with labels for source, evidence, marker, action, and related context
- subtle saved-state feedback already present
- stable badge vocabulary for saved state, missing state, unresolved, stale, and blocked
- mobile sheet ordering based on UI grammar

Revise before use:
- coverage bars or gauges: use only with exact labels such as `source coverage`, `evidence refs`, or `review progress`
- success badges: use for saved/completed/local-ready process state only
- warning density: useful in Workbench, but not as a truth or quality score

Defer:
- graph visualization
- animated artifact flow diagrams
- assistant panel
- CopilotKit runtime
- motion libraries
- 3D/canvas visualization

Reject:
- color per artifact family
- graph edge colors as truth indicators
- assistant answer cards that look more authoritative than evidence
- broad `approved` or `verified` states

## 9. Design Debt Table

| Area | Severity | Evidence | Smallest fix |
| --- | --- | --- | --- |
| Paper Detail action overload | P1 | header and import states expose many actions before rail trust hierarchy settles | route-specific action hierarchy pass |
| Paper Detail mobile sheet order | P1 | sheet repeats panels but is not explicitly tied to source/evidence/reuse/action grammar | reorder sheet sections and update copy |
| Relationship visibility | P1 | `used by` / `stale impact` appears in docs but not consistently in routes | add placeholders only where data exists; otherwise document missing data |
| Artifact family consistency | P1 | Meeting Pack is strong but other artifact pages may diverge | later shared artifact-detail grammar pass |
| Success color semantics | P2 | saved/current/readiness states use success styling in multiple routes | keep labels process-specific; avoid correctness wording |
| Assistant boundary | P2 | docs reserve future assistant, runtime is stub-only | no UI implementation until contract changes |

## 10. Concrete Implementation Changes

First route-specific UX report should target:
- `docs/UX_REVIEW_REPORT_paper-detail-right-rail.md`

First implementation spike should touch only:
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- possibly local copy/section helper functions inside the same file

Do not touch in first spike:
- backend APIs
- schemas
- artifact stores
- markdown parsing/rendering
- Workbench
- artifact pages
- dependencies
- chat/runtime/provider settings

Candidate Paper Detail changes:
- make the right rail order match UI grammar:
  1. saved/source state
  2. evidence/claim coverage
  3. provenance/source chain
  4. personal markers
  5. related/reuse or missing-reuse placeholder
  6. next safe action
  7. guarded/maintenance actions
  8. properties/debug
- update mobile `Sheet` order to the same trust order
- make `ActionsPanel` visibly guarded/maintenance when it can mutate generated state or markdown
- keep `Open review` as the dominant action, but avoid placing downstream artifact actions above source/evidence state
- add labels that clarify `coverage, not truth` where claim count or coverage-like badges appear

## 11. Ethics Check Results

Regret:
- Current UI generally tries to prevent over-trust. The first spike should reduce regret by making source/review state easier to see before downstream actions.

Black Mirror:
- Highest risk is not visual beauty; it is generated/downstream content accumulating native-looking confidence across routes.

In Real-Life:
- The product mostly behaves like a careful research collaborator already. The next improvement is to become more orderly before becoming more visually expressive.

## 12. Next PR-Sized Actions

1. Use `docs/UX_REVIEW_REPORT_paper-detail-right-rail.md`.
   - Keep the implementation scoped to Paper Detail right rail, mobile sheet order, action hierarchy, and visual-state labels.

2. Implement the Paper Detail micro-spike.
   - Keep it to one route and avoid backend/schema/dependency changes.

3. Verify.
   - Run `cd frontend && npm run build`.
   - Run relevant Paper Notes/Paper Detail Playwright coverage if available.
   - Add screenshot or visual comparison only if the route already has visual coverage or the PR changes layout enough to justify it.

## 13. Verification

This audit is documentation-only.

Checks to run for this document:
- `python3 scripts/lint_docs.py docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`
- `git diff --check -- docs/UX_REVIEW_REPORT_current-ui-reality-audit-v2.md`
- `python3 scripts/check_no_live_secrets.py --root .`

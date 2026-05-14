# Frontend / Viewer / Runtime-Readiness Lane Scoping

Status: scoped execution note
Date: 2026-03-29
Lane: `frontend/viewer/runtime-readiness`
Parent triage: [Current_Worktree_Lane_Triage_2026-03-29.md](/Users/jangseongjin/paperpipe/docs/reports/Current_Worktree_Lane_Triage_2026-03-29.md)

## Purpose

Turn the broad viewer-facing dirty surface into one bounded execution lane with:

- concrete owner files
- clear exclusions
- one recommended PR-sized next slice
- one exact verification set

This note does not reopen extraction/runtime-specialty work, and it does not claim every viewer-related dirty path should ship together.

## Current Judgment

This is still the best next active non-extraction lane in the repository, but it is too large to treat as one patch.

The safe interpretation is:

- keep the lane centered on operational viewer continuity
- keep `/ready` as the canonical runtime diagnosis surface
- treat adjacent workbench/paper-note entry clarity as part of the same user-facing lane
- keep artifact-viewer expansion and broader copy sweeps out of the first pass

## Existing Anchors

Primary UX/report anchors already in the tree:

- [UX_REVIEW_REPORT_runtime-readiness.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_runtime-readiness.md)
- [UX_REVIEW_REPORT_runtime-entry-fallback.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_runtime-entry-fallback.md)
- [UX_REVIEW_REPORT_workbench-run-cancel.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_workbench-run-cancel.md)
- [UX_REVIEW_REPORT_workbench-persona-profile-split.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md)

These already imply the right boundary:

- operational continuity and honest fallback disclosure belong together
- runtime readiness is not a standalone backend-only tool
- the workbench is part of the same operational trust surface, but not every workbench/theme cleanup belongs in the first slice

## Owner Map

### 1. Route and app-shell owners

These files own whether the lane is reachable at all:

- [App.tsx](/Users/jangseongjin/paperpipe/frontend/src/App.tsx)
- [main.tsx](/Users/jangseongjin/paperpipe/frontend/src/main.tsx)
- [index.css](/Users/jangseongjin/paperpipe/frontend/src/index.css)
- [WorkbenchLayout.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/layouts/WorkbenchLayout.tsx)

Responsibilities:

- route registration for `/ready`, `/papers`, `/papers/:slug`, `/workbench/:paperId`
- SPA shell continuity under the existing backend-served runtime entry
- preserving the current `--pp-*` visual contract

### 2. Runtime-readiness contract owners

These files own the canonical readiness diagnosis surface:

- [backend/main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [RuntimeReadinessPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/RuntimeReadinessPage.tsx)
- [api.ts](/Users/jangseongjin/paperpipe/frontend/src/app/lib/api.ts)
- [types.ts](/Users/jangseongjin/paperpipe/frontend/src/app/lib/types.ts)
- [test_runtime_readiness_api.py](/Users/jangseongjin/paperpipe/tests/test_runtime_readiness_api.py)
- [test_runtime_readiness_backend_entrypoint.py](/Users/jangseongjin/paperpipe/tests/test_runtime_readiness_backend_entrypoint.py)
- [test_runtime_readiness_external_roots.py](/Users/jangseongjin/paperpipe/tests/test_runtime_readiness_external_roots.py)

Responsibilities:

- `/health/ready` FastAPI contract
- `/api/health/ready` browser bridge behavior
- fallback honesty when backend checks are unavailable
- masked-path behavior
- backend entrypoint and external-root diagnostics

### 3. Operational entry owners

These files decide whether a user can actually discover and use the readiness surface from normal product flow:

- [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx)
- [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)
- [PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)
- [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx)
- [Rail.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/Rail.tsx)
- [ArtifactPanel.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/ArtifactPanel.tsx)
- [PdfPanel.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/components/PdfPanel.tsx)
- [accessSummary.ts](/Users/jangseongjin/paperpipe/frontend/src/app/lib/accessSummary.ts)
- [contentReview.ts](/Users/jangseongjin/paperpipe/frontend/src/app/lib/contentReview.ts)

Responsibilities:

- triage-to-readiness discoverability
- paper-notes import fallback guidance
- workbench/operator trust language when runtime or artifact state is ambiguous
- keeping operational language consistent across list/detail/workbench surfaces

### 4. Backend/API surfaces touched by operational viewer flow

These are supporting owners, not the primary lane center:

- [backend/routers/paper_notes.py](/Users/jangseongjin/paperpipe/backend/routers/paper_notes.py)
- [backend/routers/obsidian.py](/Users/jangseongjin/paperpipe/backend/routers/obsidian.py)
- [test_paper_notes_api.py](/Users/jangseongjin/paperpipe/tests/test_paper_notes_api.py)
- [test_obsidian_artifacts_api.py](/Users/jangseongjin/paperpipe/tests/test_obsidian_artifacts_api.py)
- [test_obsidian_institutional_block.py](/Users/jangseongjin/paperpipe/tests/test_obsidian_institutional_block.py)
- [test_obsidian_save.py](/Users/jangseongjin/paperpipe/tests/test_obsidian_save.py)
- [test_jobs_api_smoke.py](/Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py)

Responsibilities:

- support the viewer/workbench contract without turning this lane into a backend rewrite
- keep note/artifact surfaces reachable and honest

### 5. Browser verification owners

These files already provide concentrated end-to-end coverage:

- [frontend/e2e/mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/mock.spec.ts)
- [frontend/e2e/backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)
- [frontend/playwright.mock.config.ts](/Users/jangseongjin/paperpipe/frontend/playwright.mock.config.ts)
- [frontend/playwright.backend.config.ts](/Users/jangseongjin/paperpipe/frontend/playwright.backend.config.ts)
- [tests/test_frontend_real_smoke_backend_launcher.py](/Users/jangseongjin/paperpipe/tests/test_frontend_real_smoke_backend_launcher.py)

Already-covered key signals:

- `/ready` forced-mock fallback browser path
- `/ready` live backend browser path
- `/papers` import card exposes `Check automatic pickup setup`
- backend launcher/runtime-readiness preflight

## Explicitly Out Of Scope For The First Pass

Do not mix these into the first PR-sized slice:

- [ChartPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ChartPackPage.tsx)
- [ImageEvidencePage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ImageEvidencePage.tsx)
- [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx)
- [MethodComparisonPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MethodComparisonPage.tsx)
- [ProtocolCardPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/ProtocolCardPage.tsx)
- their corresponding feature-specific mock/browser specs
- parser-worker specific workbench controls unless a change directly touches parser status presentation
- personal runtime / packaging work
- meeting-pack / handoff feature work

Reason:

- these are viewer-adjacent, but not necessary to close the runtime-readiness lane safely
- pulling them in would turn one coherent operational lane into another broad mixed patch

## Recommended PR-Sized Next Action

### Slice: Runtime-readiness operational entry alignment

Goal:

- keep `/ready` as the canonical diagnosis page
- tighten how normal user flows point to it
- avoid reopening unrelated viewer/copy sweeps

Include:

- route and runtime-readiness contract owners
- triage entry clarity
- paper-notes import/setup fallback clarity
- only the minimum workbench or detail-surface wording needed to keep operational messaging coherent

Do not include:

- artifact viewer feature expansion
- broad workbench copy rewrite
- runtime backend/service redesign
- packaging/runtime delivery work

Expected result:

- a user can discover readiness from triage and paper-notes flow
- the readiness page remains the single trusted place for machine-level diagnosis
- fallback/import language stays consistent with that diagnosis path

## Smallest Relevant Verification Set

If the next patch touches the runtime-readiness contract or page:

- `python3 -m pytest /Users/jangseongjin/paperpipe/tests/test_runtime_readiness_api.py /Users/jangseongjin/paperpipe/tests/test_runtime_readiness_backend_entrypoint.py /Users/jangseongjin/paperpipe/tests/test_runtime_readiness_external_roots.py -q`
- `cd /Users/jangseongjin/paperpipe/frontend && npm run build`
- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "runtime readiness page explains forced-mock diagnostics without dead-ending"`
- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend runtime readiness page surfaces live runtime checks in the browser"`

If the patch also touches the paper-notes import/setup entry:

- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend paper notes index can import a local PDF from the browser"`

If the patch touches backend-served runtime startup/preflight:

- `python3 -m pytest /Users/jangseongjin/paperpipe/tests/test_frontend_real_smoke_backend_launcher.py -q`

Broader signoff rule:

- only escalate to `cd frontend && npm run verify:frontend` if the touched surfaces already cross multiple viewer/browser routes

## Why This Slice First

This is the best next step because it is:

- already grounded in existing UX review artifacts
- small enough to verify without reopening the whole viewer stack
- user-facing in a clear way
- connected to existing browser and backend readiness tests

Compared with the rest of the dirty tree, this slice has the best ratio of:

- coherent ownership
- user-visible value
- already-existing verification

## Short Version

Treat `frontend/viewer/runtime-readiness` as one bounded operational lane, not as “all open frontend work.”

The next safe implementation slice is:

1. `/ready` contract and page
2. triage and paper-notes entry clarity
3. only minimal adjacent operational wording needed for consistency

Leave artifact-viewer expansion, packaging, meeting-pack, and broad runtime work out of that first pass.

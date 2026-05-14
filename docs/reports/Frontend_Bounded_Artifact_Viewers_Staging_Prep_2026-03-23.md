# Frontend Bounded Artifact Viewers Staging Prep

Status: staging-prep manifest  
Date: 2026-03-23  
Lane: `frontend-bounded-artifact-viewers`

## Purpose

Define the commit-safe frontend closure that promotes the existing viewer shell into a bounded multi-viewer surface for:

- Paper Notes
- Meeting Packs
- Method Comparisons
- Chart Packs
- Image Evidence

This lane also carries the viewer-facing API/mock/type extensions, targeted Playwright coverage, and the backend E2E bootstrap fixes needed to run the viewer stack from a clean checkout.

## Why This Is A Shared Lane

`/Users/jangseongjin/paperpipe/frontend/src/App.tsx` now routes the bounded artifact families through the same viewer shell. The safe unit is not a single page.

The effective closure is:

- router shell
- bounded viewer pages
- shared viewer-facing API/types/mock data
- targeted E2E + visual coverage
- backend E2E bootstrap script

## In Scope

### Frontend runtime
- `/Users/jangseongjin/paperpipe/frontend/src/App.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/PdfPanel.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/layouts/WorkbenchLayout.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/api.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/types.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/ChartPackPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/ImageEvidencePage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/MethodComparisonPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/command.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/input.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/index.css`

### Playwright and visual baselines
- `/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/chart-pack.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/image-evidence.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/method-comparison.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts-snapshots/*`
- `/Users/jangseongjin/paperpipe/frontend/e2e/visual-mock.mock.spec.ts-snapshots/mock-mobile-claim-highlight-darwin.png`
- `/Users/jangseongjin/paperpipe/frontend/playwright.backend.config.ts`
- `/Users/jangseongjin/paperpipe/frontend/playwright.mock.config.ts`
- `/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh`

### UX artifact touched in this lane
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_image-evidence-viewer.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Frontend_Bounded_Artifact_Viewers_Staging_Prep_2026-03-23.md`

## Out Of Scope

Keep these out of this commit:

- `/Users/jangseongjin/paperpipe/docs/CHART_PACK.md`
- `/Users/jangseongjin/paperpipe/docs/METHOD_COMPARISON.md`
- `/Users/jangseongjin/paperpipe/docs/README.md`
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/pyproject.toml`
- `/Users/jangseongjin/paperpipe/scripts/bootstrap.py`
- `/Users/jangseongjin/paperpipe/src/obsidian.py`
- `/Users/jangseongjin/paperpipe/tests/*`
- storage/runtime artifacts under `/Users/jangseongjin/paperpipe/storage/`
- local tooling folders such as `/Users/jangseongjin/paperpipe/.omx/` and `/Users/jangseongjin/paperpipe/.serena/`

## Hidden Dependencies Closed In This Lane

Clean-checkout backend E2E bootstrap was not self-contained until the following were fixed inside `/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh`:

- create `jobs` before cleanup
- create `execution_runs` before backend listing paths touch event-log helpers
- create `job_events` so additive event-log code can operate against a clean runtime DB

Without those fixes, temp-worktree backend Playwright failed before viewer routes loaded.

## Verification

### Current worktree
- `cd /Users/jangseongjin/paperpipe/frontend && npm run build`
- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts e2e/image-evidence.mock.spec.ts e2e/meeting-pack.mock.spec.ts e2e/method-comparison.mock.spec.ts`
- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.mock.config.ts e2e/visual-mock.mock.spec.ts`
- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend method comparison viewer|backend chart pack viewer|backend image evidence viewer|paper notes list supports command-style tag selection|paper notes list supports structured-only quick toggle|paper notes list surfaces action-needed state using workbench vocabulary|paper notes list finds structured-signal matches and surfaces structured affordances|paper notes list supports quoted exact-phrase search|paper notes list empty state explains structured-only misses|paper notes list empty state can remove quotes from an exact-phrase miss|paper notes list empty state suggests token-based recovery searches"`
- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench rail layout|claim highlight|paper notes list layout|paper note detail layout|structured paper note detail layout|image evidence detail layout|image evidence index layout"`

Observed:
- build passed
- mock viewer specs passed (`6`)
- mock visual claim-highlight specs passed (`2`)
- backend viewer + paper-notes specs passed (`13`)
- backend visual subset passed (`13`)

### Temp worktree closure
Temp worktree: `/tmp/paperpipe-frontend-viewer-shell-verify-20260323`

Applied only the in-scope files above onto clean `HEAD` and verified:
- `npm run build` passed
- mock viewer + mock visual subset passed (`8`)
- backend viewer + paper-notes functional subset passed (`13`)

Note:
- backend visual subset still showed snapshot drift for `workbench rail layout` and `mobile claim highlight` in the temp worktree, while the same visual subset passed in the current worktree.
- That drift appears tied to clean-runtime bootstrap/path-sensitive rendering rather than missing code closure, because the functional backend subset and the current-worktree visual subset both pass.

## Safe Next Git Step

Stage only the files in scope above, then commit as the bounded frontend viewer shell lane.

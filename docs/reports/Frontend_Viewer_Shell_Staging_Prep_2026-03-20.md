# Frontend Viewer Shell Staging Prep

Status: staging-prep manifest  
Date: 2026-03-20  
Lane: `frontend-viewer-shell`

## Purpose

Define the shared frontend viewer shell subset that introduces the `/papers`, `/meeting-packs`, and `/method-comparisons` routes together with their viewer pages and mock coverage.

## Why This Is A Shared Lane

`/Users/jangseongjin/paperpipe/frontend/src/App.tsx` does not expose the Method Comparison page in isolation.
It introduces lazy routes for:

- `PaperNotesListPage`
- `MeetingPackPage`
- `MethodComparisonPage`

So the commit-safe unit is the shared viewer shell, not `method-comparison viewer` alone.

## In Scope

- `/Users/jangseongjin/paperpipe/frontend/src/App.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/MethodComparisonPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/command.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/input.tsx`
- `/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/method-comparison.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-mode-family.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_method-comparison-viewer.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Frontend_Viewer_Shell_Staging_Prep_2026-03-20.md`

## Out Of Scope

Keep these out of this commit:

- `/Users/jangseongjin/paperpipe/frontend/src/index.css`
- `/Users/jangseongjin/paperpipe/frontend/playwright.mock.config.ts`
- chart-pack viewer files
- `/Users/jangseongjin/paperpipe/storage/method_comparisons/`
- broader frontend visual snapshot churn

## Verification Strategy

Current worktree `npm run build` is not a valid verdict for this lane because it fails on unrelated dirty work (`ChartPackPage`).

Use temp worktree closure verification instead:

1. stage only the files in scope
2. apply staged patch to a clean temp worktree at current `HEAD`
3. reuse local `node_modules` only for verification
4. run:
   - `npm run build`
   - `npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts e2e/meeting-pack.mock.spec.ts e2e/method-comparison.mock.spec.ts`

## Verification Already Observed In Current Worktree

- `npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts e2e/meeting-pack.mock.spec.ts e2e/method-comparison.mock.spec.ts`
  - passed in the current worktree
- current worktree build failure is attributable to unrelated dirty file `ChartPackPage.tsx`, not this lane

## Safe Next Git Step

Stage only the files listed in scope above, then verify in a temp worktree before commit.

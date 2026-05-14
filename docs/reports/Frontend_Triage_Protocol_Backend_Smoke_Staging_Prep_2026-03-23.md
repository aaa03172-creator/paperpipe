# Frontend Triage + Protocol Backend Smoke Staging Prep (2026-03-23)

## Scope
Bounded frontend lane for:
- triage summary strip + primary next action UI
- backend smoke coverage for triage summary counts
- real-route protocol card inspector smoke
- backend E2E runtime seed support for protocol cards

## Included Files
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx`
- `/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_triage-dashboard.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Frontend_Triage_Protocol_Backend_Smoke_Staging_Prep_2026-03-23.md`

## Excluded On Purpose
- `frontend/e2e/visual-backend.backend.spec.ts`
- `frontend/e2e/visual-backend.backend.spec.ts-snapshots/*`
- `docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
- `docs/UX_REVIEW_REPORT_meeting-pack-viewer.md`
- `docs/reports/Frontend_Backend_Visual_Coverage_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `cd /Users/jangseongjin/paperpipe/frontend && npm run build`
- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c /Users/jangseongjin/paperpipe/frontend/playwright.backend.config.ts /Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts -g "backend triage summarizes repair, review, and ready buckets|backend protocol knowledge inspector loads a saved protocol card and keeps note handoff on the real route"`

Clean temp worktree closure:
- `cd /tmp/paperpipe-frontend-backend-visual-verify-20260323/frontend && npm run build`
- `cd /tmp/paperpipe-frontend-backend-visual-verify-20260323/frontend && npx playwright test -c /tmp/paperpipe-frontend-backend-visual-verify-20260323/frontend/playwright.backend.config.ts /tmp/paperpipe-frontend-backend-visual-verify-20260323/frontend/e2e/backend.spec.ts -g "backend triage summarizes repair, review, and ready buckets|backend protocol knowledge inspector loads a saved protocol card and keeps note handoff on the real route"`
- `cd /tmp/paperpipe-frontend-backend-visual-verify-20260323 && python3 scripts/lint_docs.py`

## Notes
- This lane intentionally excludes the broader backend visual snapshot set. The visual lane still needs separate closure because desktop triage snapshot parity does not hold in a clean temp worktree yet.

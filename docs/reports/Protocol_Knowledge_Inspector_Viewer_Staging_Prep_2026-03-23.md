# Protocol Knowledge Inspector Viewer Staging Prep (2026-03-23)

## Scope
Frontend read-only viewer lane for protocol cards.

## Included files
- `/Users/jangseongjin/paperpipe/frontend/src/App.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/api.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/mock.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/lib/types.ts`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/ProtocolCardPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx`
- `/Users/jangseongjin/paperpipe/frontend/e2e/protocol-card.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`
- `/Users/jangseongjin/paperpipe/docs/README.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Protocol_Knowledge_Inspector_Viewer_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `cd frontend && npm run build`
- `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/protocol-card.mock.spec.ts`

Temp closure:
- `cd frontend && npm run build`
- `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/protocol-card.mock.spec.ts`
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`

## Notes
- This is a read-only v0 lane. It does not add editing or activation controls.
- The mock spec scrolls to the cautions section before asserting long-form caution copy because that content is below the initial viewport.

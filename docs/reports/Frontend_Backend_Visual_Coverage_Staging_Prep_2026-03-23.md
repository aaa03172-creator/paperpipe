# Frontend Backend Visual Coverage Staging Prep (2026-03-23)

## Scope
Bounded frontend/viewer verification lane for backend-driven visual coverage across:
- triage
- paper notes list/detail
- workbench shell/rail/highlight
- chart-pack
- meeting-pack
- protocol knowledge

## Included files
- `/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts`
- `/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_e2e.sh`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Frontend_Backend_Stale_Baseline_Audit_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/frontend/e2e/visual-backend.backend.spec.ts-snapshots/*`
- `/Users/jangseongjin/paperpipe/docs/reports/Frontend_Backend_Visual_Coverage_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts`
- `python3 scripts/lint_docs.py`

Temp closure:
- same as above
- visual lane closure is valid only when the full backend visual spec is green after any baseline refresh

## Notes
- This lane does not widen route semantics; it only refreshes and packages backend-driven viewer verification.
- Snapshot files are part of the lane because route-level screenshot coverage is not complete without them.
- Recent baseline refreshes were required after triage summary and deep-read note-state promotion changed the visible shells for `/`, `/papers`, and `/workbench`.

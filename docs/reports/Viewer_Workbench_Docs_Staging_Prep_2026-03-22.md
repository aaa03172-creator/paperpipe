# Viewer and Workbench Docs Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the viewer/workbench documentation set that already matches committed runtime behavior and product framing.

## Included scope

- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`
- `docs/Product_Positioning_Principles.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/PERSONA_MODE_ROADMAP_2026-03-17.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/Korean_Reading_Assist_Policy.md`
- `docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `docs/UX_REVIEW_REPORT_skills-actions.md`
- `docs/UX_REVIEW_REPORT_triage-dashboard.md`
- `docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md`
- `docs/UX_REVIEW_REPORT_korean-reading-assist.md`
- `docs/reports/Viewer_Workbench_Docs_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- `docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
- `docs/UX_REVIEW_REPORT_method-comparison-viewer.md`
- `docs/UX_REVIEW_REPORT_meeting-pack-trace.md`
- `docs/UX_REVIEW_REPORT_meeting-pack-mode-family.md`
- tracked legacy docs such as `docs/ux-review.md` and `docs/ux-review-report.md`
- frontend implementation files

## Verification

1. `python3 scripts/lint_docs.py`
2. staged diff stays docs-only

## Commit target

`docs(viewer): add paper-notes and workbench product docs`

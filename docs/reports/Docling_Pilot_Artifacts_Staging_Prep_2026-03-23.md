# Docling Pilot Artifacts Staging Prep (2026-03-23)

## Scope
Docs/data lane for bounded `docling` pilot evidence and intake decision artifacts.

## Included files
- `/Users/jangseongjin/paperpipe/docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Docling_Pilot_Artifacts_Staging_Prep_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_20260323/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_20260323_r2/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r3/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r4/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r5/`

## Verification
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`

## Notes
- `docling_pilot_manifest_20260323_r6/` is intentionally excluded because it is an empty work directory, not a stable artifact set.
- This lane does not change runtime behavior; it packages evidence, manifests, and the bounded intake decision.

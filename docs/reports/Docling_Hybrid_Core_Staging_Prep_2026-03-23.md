# Docling Hybrid Core Staging Prep (2026-03-23)

## Scope
Core parser/eval lane for the bounded hybrid `docling` backend work.

## Included files
- `/Users/jangseongjin/paperpipe/src/ingest/parser_backends.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_parser_backend.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Docling_Hybrid_Core_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `pytest -q tests/test_ingest_parser_backend.py tests/test_ingest_backend_eval.py`
- `python3 scripts/eval/compare_ingest_backends.py --help`

Temp closure:
- `python3 scripts/eval/compare_ingest_backends.py --help`
- `pytest -q tests/test_ingest_parser_backend.py tests/test_ingest_backend_eval.py`

## Notes
- This lane promotes the parser path from pure structured-table preference to a bounded hybrid fallback model.
- Pilot manifests, snapshots, and decision docs are intentionally excluded and should land as a separate evidence lane.

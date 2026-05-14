# Docling Parser Eval Core Staging Prep (2026-03-23)

## Scope
Self-contained parser/eval lane for bounded `docling` comparison work.

## Included files
- `/Users/jangseongjin/paperpipe/pyproject.toml`
- `/Users/jangseongjin/paperpipe/src/ingest/parser_backends.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_parser_backend.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Docling_Parser_Eval_Core_Staging_Prep_2026-03-23.md`

## Verification
Current worktree:
- `pytest -q tests/test_ingest_parser_backend.py tests/test_ingest_backend_eval.py`
- `python3 scripts/eval/compare_ingest_backends.py --help`

Temp closure:
- `PAPERPIPE_CONFIG_PATH=config.example.yaml python3 -c "from src.ingest.parser_backends import DoclingParserBackend; print('parser import ok')"`
- `python3 scripts/eval/compare_ingest_backends.py --help`
- `pytest -q tests/test_ingest_parser_backend.py tests/test_ingest_backend_eval.py`

## Notes
- `docling` remains optional runtime infrastructure; this lane only hardens bounded parser evaluation and structured table extraction.
- Pilot reports and manifest snapshots are intentionally excluded and should land as a separate docs/data lane.

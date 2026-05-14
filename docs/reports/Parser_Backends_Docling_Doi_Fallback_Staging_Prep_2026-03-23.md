# Parser Backends Docling DOI Fallback Staging Prep (2026-03-23)

## Goal
Split a narrow parser-backend lane that teaches the docling backend to recover DOI metadata from the fitz fallback path when conversion text misses it.

## Included
- `/Users/jangseongjin/paperpipe/src/ingest/parser_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_parser_backend.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Parser_Backends_Docling_Doi_Fallback_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- The runtime change is limited to DOI fallback inside `DoclingParserBackend.extract_text_and_meta(...)`.
- The test addition covers the exact fallback behavior and lives in the existing parser backend suite.
- No config, CLI workflow, or frontend changes are required.

## Verification Plan
- `pytest -q tests/test_ingest_parser_backend.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
Docling extraction retains DOI recovery even when the converted document text loses the front-matter DOI string.

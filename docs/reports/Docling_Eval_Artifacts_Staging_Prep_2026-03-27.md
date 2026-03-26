# Docling Eval Artifacts Staging Prep (2026-03-27)

## Goal
- Close the remaining parser-eval evidence lane after runtime shell separation.

## Include
- `/Users/jangseongjin/paperpipe/docs/reports/Docling_Eval_Lane_Packaging_2026-03-24.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Docling_Tool_Intake_Decision_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`
- `/Users/jangseongjin/paperpipe/scripts/eval/audit_section_quality.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/audit_table_merge_semantics.py`
- `/Users/jangseongjin/paperpipe/tests/test_section_quality_audit.py`
- `/Users/jangseongjin/paperpipe/tests/test_table_merge_audit.py`
- `/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_expanded_broad_20260324.json`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r11/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260324_r16/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/`
- `/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/`

## Exclude
- `/Users/jangseongjin/paperpipe/scripts/bootstrap.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_extraction_outputs.py`
- `/Users/jangseongjin/paperpipe/tests/test_extraction_regression_eval.py`
- `/Users/jangseongjin/paperpipe/tests/test_ollama_provider_timeout.py`
- teacher-review spot-check docs and artifacts
- `/Users/jangseongjin/paperpipe/storage/*`

## Verification
- `pytest -q /Users/jangseongjin/paperpipe/tests/test_section_quality_audit.py /Users/jangseongjin/paperpipe/tests/test_table_merge_audit.py /Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`
- `python3 /Users/jangseongjin/paperpipe/scripts/eval/audit_section_quality.py --help`
- `python3 /Users/jangseongjin/paperpipe/scripts/eval/audit_table_merge_semantics.py --help`
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`
- clean temp worktree closure:
  - same pytest set
  - same help checks
  - docs lint

## Notes
- This lane is parser-eval evidence only. It does not reopen runtime adoption or broad extraction-regression work.
- `compare_extraction_outputs.py` remains a separate eval lane because it targets `TrialExtraction` goldset comparison rather than docling parser comparison.

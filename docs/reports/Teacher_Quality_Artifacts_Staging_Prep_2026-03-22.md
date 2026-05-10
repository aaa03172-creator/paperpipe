# Teacher Quality Artifacts Staging Prep (2026-03-22)

## Scope
Self-contained teacher-quality lane for local teacher review helpers, quarantine review tooling, claimset evidence policy tests, and teacher evaluation artifacts under goldset/baselines/snapshots.

## Included files
- `/Users/jangseongjin/paperpipe/src/quality/__init__.py`
- `/Users/jangseongjin/paperpipe/scripts/generate_teacher_outputs.py`
- `/Users/jangseongjin/paperpipe/scripts/review_teacher_quarantine.py`
- `/Users/jangseongjin/paperpipe/tests/test_claimset_policy.py`
- `/Users/jangseongjin/paperpipe/tests/test_teacher_review.py`
- `/Users/jangseongjin/paperpipe/tests/test_teacher_quarantine_review.py`
- `/Users/jangseongjin/paperpipe/goldset/accepted/`
- `/Users/jangseongjin/paperpipe/goldset/manifest.json`
- `/Users/jangseongjin/paperpipe/goldset/queries.jsonl`
- `/Users/jangseongjin/paperpipe/goldset/pdfs/.gitkeep`
- `/Users/jangseongjin/paperpipe/goldset/splits/v20260309_teacher_probe/`
- `/Users/jangseongjin/paperpipe/goldset/splits/v20260310_teacher_compare/`
- `/Users/jangseongjin/paperpipe/baselines/quality_eval_teacher_compare_20260310/`
- `/Users/jangseongjin/paperpipe/baselines/quality_eval_teacher_probe_20260309.metrics.json`
- `/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch01.json`
- `/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch01.txt`
- `/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch02.json`
- `/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_batch_20260313_batch02.txt`
- `/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_compare_20260310.json`
- `/Users/jangseongjin/paperpipe/snapshots/compare/quality_eval_teacher_compare_20260310.txt`
- `/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_probe_20260309/`
- `/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_compare_20260310/`
- `/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch01/`
- `/Users/jangseongjin/paperpipe/snapshots/quality_eval_teacher_batch_20260313_batch02/`
- `/Users/jangseongjin/paperpipe/docs/reports/Teacher_Quality_Artifacts_Staging_Prep_2026-03-22.md`

## Explicitly excluded
- `/Users/jangseongjin/paperpipe/scripts/evaluate_search.py` and `/Users/jangseongjin/paperpipe/tests/test_evaluate_search.py` because they belong to search-eval / research-dna follow-up.
- `/Users/jangseongjin/paperpipe/scripts/seed_stats_report_from_claimset.py` because it belongs to stats repair/runtime flow.
- `/Users/jangseongjin/paperpipe/baselines/search_eval/` because it belongs to search evaluation, not teacher quality.

## Verification target
- `python3 scripts/generate_teacher_outputs.py --help`
- `python3 scripts/review_teacher_quarantine.py --help`
- `pytest -q tests/test_claimset_policy.py tests/test_teacher_review.py tests/test_teacher_quarantine_review.py`
- `python3 scripts/lint_docs.py`

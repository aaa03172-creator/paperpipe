# Search Eval Staging Prep (2026-03-23)

## Scope
Self-contained search evaluation lane for post-run metric recomputation, baseline promotion history, and sample baseline artifacts.

## Included files
- `/Users/jangseongjin/paperpipe/scripts/evaluate_search.py`
- `/Users/jangseongjin/paperpipe/tests/test_evaluate_search.py`
- `/Users/jangseongjin/paperpipe/baselines/search_eval/`
- `/Users/jangseongjin/paperpipe/docs/reports/Search_Eval_Staging_Prep_2026-03-23.md`

## Explicitly excluded
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`
- `/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py`
- `/Users/jangseongjin/paperpipe/src/config.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`

## Verification target
- `python3 scripts/evaluate_search.py --help`
- `pytest -q tests/test_evaluate_search.py`

## Notes
- `python3 scripts/lint_docs.py` currently fails on an existing retired-stub reference in `/Users/jangseongjin/paperpipe/frontend/PHASE3_CONTROL_UI_IMPLEMENTATION_PLAN.md`, outside this lane.

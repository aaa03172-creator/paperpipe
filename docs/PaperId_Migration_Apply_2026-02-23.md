# Paper ID Migration Apply Report (2026-02-23)

## Execution
- Backup:
  - `storage/state.db.bak.20260223_124000`
- Apply command:
  - `python3 scripts/apply_paper_id_migration.py --db storage/state.db --plan storage/paper_id_migration_plan.json --apply --backup storage/state.db.bak.20260223_124000`

## Apply Output
- mappings: `52`
- impacts:
  - papers: `52`
  - review_queue: `54`
  - jobs: `0`
  - runs: `0`
  - user_actions: `0`

## Post-Apply Verification
- `python3 scripts/audit_paper_id_policy.py --db storage/state.db --sample-limit 3`
  - papers_total: `56`
  - canonical_count: `52`
  - canonical_ratio: `0.9286`
- `python3 scripts/plan_paper_id_migration.py --db storage/state.db --out storage/paper_id_migration_plan_post.json`
  - total_candidates: `0`
- SQL checks:
  - paper_key_missing: `0`
  - orphan_review_queue: `0`
  - orphan_jobs: `50` (same as backup)
  - orphan_runs: `27` (same as backup)
  - orphan_user_actions: `0`

## Runtime Regression
- `python3 -m pytest -q -k "not docker_sandbox"`: `283 passed, 1 skipped, 4 deselected`
- `python3 scripts/test_phase3_integration.py`: PASS

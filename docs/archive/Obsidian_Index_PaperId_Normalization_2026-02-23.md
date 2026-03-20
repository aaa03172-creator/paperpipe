# Obsidian Index Paper_ID Normalization (2026-02-23)

Status: Historical implementation note  
Date: 2026-02-23  
Owner: Runtime/data maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Why
- DB `papers.paper_id` canonical migration is complete.
- Remaining gap was legacy `Paper_ID` values in Obsidian CSV (`plain DOI/link` 형태).

## Added Tooling
- `scripts/audit_obsidian_index_ids.py`
  - CSV `Paper_ID` canonical ratio/category audit
  - migratable candidate count (`doi` / `obsidian_path`)
- `scripts/normalize_obsidian_index_ids.py`
  - default dry-run planner
  - `--apply` with backup + deterministic rewrite

## Safety Rules
- Canonical `Paper_ID` values are untouched.
- Non-canonical rows are changed only when:
  - DOI exists -> `doi:{normalized_doi}`, or
  - DOI missing and DB `papers.obsidian_path` maps 1:1 to canonical `paper_id`.
- Otherwise no change (skip).

## Execution (Current Vault)
- Audit (before):
  - `rows_total=1`
  - `canonical_count=0`
  - `migratable_candidates=1` (`10.1234/test -> doi:10.1234/test`)
- Apply:
  - Backup: `obsidian/00_Index/paper_collection.csv.bak.20260223_040722`
  - CSV updated.
- Audit (after):
  - `rows_total=1`
  - `canonical_count=1`
  - `migratable_candidates=0`

## Release Checkpoint Recheck (2026-02-23)
- Command:
  - `python3 scripts/audit_obsidian_index_ids.py --index obsidian/00_Index/paper_collection.csv --db storage/state.db --sample-limit 10`
  - `python3 scripts/normalize_obsidian_index_ids.py --index obsidian/00_Index/paper_collection.csv --db storage/state.db --print-sample 10`
- Result:
  - audit: `canonical_ratio=1.0`, `migratable_candidates=0`
  - normalize dry-run: `candidates=0`
- Decision:
  - 운영 vault CSV에 대한 추가 `--apply`는 불필요(no-op)로 확정.

## Regression
- `pytest -q tests/test_obsidian_index_id_normalization.py tests/test_obsidian_index_ids.py tests/test_core_ids.py tests/test_paper_id_migration_plan.py tests/test_paper_id_migration_apply.py`
  - `18 passed`
- `pytest -q -k "not docker_sandbox"`
  - `291 passed, 1 skipped, 4 deselected`

# Paper ID Migration Audit (2026-02-23)

## Commands
- `python3 scripts/audit_paper_id_policy.py --db storage/state.db --sample-limit 2`
- `python3 scripts/plan_paper_id_migration.py --db storage/state.db --out storage/paper_id_migration_plan.json --print-sample 5`

## Snapshot
- papers_total: `56`
- canonical_count: `0`
- canonical_ratio: `0.0`
- migration_candidates (dry-run): `52`
- canonical_targets (dry-run proposed): `52`

## Notes
- Current production rows are mostly legacy IDs (`legacy:other`), plus a small local legacy bucket.
- Dry-run planner proposes canonical targets using DOI/PDF hash when available.
- Planner is non-destructive: it only writes JSON output (`storage/paper_id_migration_plan.json`).

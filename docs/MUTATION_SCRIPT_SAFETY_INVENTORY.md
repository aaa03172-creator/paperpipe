# Mutation Script Safety Inventory

Status: Active
Date: 2026-04-26
Owner: Operations maintainers
Canonical runbook: `docs/MUTATION_SCRIPT_SAFETY_INVENTORY.md`
Canonical parent: `docs/OPERATIONS_RUNBOOK.md`

## Purpose

Use this inventory before running local scripts that mutate runtime DB rows, vault files, storage bundles, branches, or generated artifacts.

This document records what the current scripts appear to provide today:

- dry-run default
- explicit `--apply`
- backup-before-apply
- transaction or rollback-aware mutation
- operator-readable summary output

It is not a replacement for reading the target script before use.

## Safety Classes

- `green`: dry-run by default, explicit apply, and backup/transaction or bounded rollback story fits the mutation.
- `yellow`: dry-run/apply exists, but backup or rollback expectations are partial or delegated to the owning store/service.
- `red`: mutates by default or lacks an obvious dry-run/apply/backup boundary. Treat as maintenance debt before normal operator use.
- `n/a`: not a destructive mutation script in the current sense, but relevant as an adjacent generator or check.

## Inventory

| Script | Mutates | Dry-run default | Apply flag | Backup before apply | Transaction / rollback | Summary output | Safety | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `scripts/archive_fixture_no_feedback_papers.py` | SQLite `papers` rows into archive table plus delete | yes | yes | yes | yes | yes | green | Uses SQLite backup, `BEGIN IMMEDIATE`, commit/rollback, and prints backup path. |
| `scripts/archive_legacy_failed_jobs.py` | SQLite `jobs` rows into failure archive plus delete | yes | yes | yes | yes | yes | green | Uses SQLite backup, `BEGIN IMMEDIATE`, commit/rollback, and prints backup path. |
| `scripts/normalize_summaries.py` | SQLite `papers.summary` / related fields | yes | yes | yes | yes | yes | green | Uses SQLite backup, bounded update transaction, dry-run preview, and backup path. |
| `scripts/replay_processor_gate_intake_logs.py` | SQLite `papers.feedback_json` replay fields | yes | yes | yes | yes | yes | green | Uses SQLite backup, `BEGIN IMMEDIATE`, commit/rollback, and prints backup path. |
| `scripts/backfill_analysis.py` | SQLite `papers.feedback_json`, `confidence`, `summary` | yes | yes | yes | yes | yes | green | Dry-run summarizes candidates without LLM calls. `--apply` requires a DB path, creates a SQLite backup, and applies updates in one transaction. |
| `scripts/migrate_legacy.py` | legacy `feedback.jsonl` rows into SQLite `papers` | yes | yes | yes | yes | yes | green | Legacy-only importer. Dry-run by default; `--apply` creates a SQLite backup and inserts candidates in one transaction. |
| `scripts/cleanup_backup_branches.py` | local git backup branches | yes | yes | n/a | n/a | yes | green | Branch backups are intentionally disposable after retention window; dry-run default is the key guard. |
| `scripts/archive_meeting_pack_noise.py` | Meeting Pack directories moved to archive root | yes | yes | partial | delegated | yes | yellow | Uses dry-run/apply and archive move. No separate backup manifest; archive directory is the recovery surface. |
| `scripts/backfill_deepread_handoff_artifacts.py` | derived files in deep-read run dirs | yes | yes | yes | partial | yes | green | Writes derived artifacts only under `--apply` and backs up original derived files under an artifact-backup directory first. Treat generated artifacts as rerenderable/support material. |
| `scripts/backfill_highlight_source.py` | claimset artifact JSON files | yes | yes | yes | partial | yes | green | File rewrite only under `--apply`; backs up original claimset JSON files under an artifact-backup directory first. Use only when regenerated/highlight fields are easy to validate. |
| `scripts/backfill_operational_outputs.py` | Obsidian exports and/or job enqueue side effects | yes | yes | no | delegated | yes | yellow | Applies only with selected action flags. Exporter uses `overwrite=False`; enqueue is API/queue side effect, not file rollback. |
| `scripts/backfill_meeting_pack_titles.py` | Meeting Pack JSON/Markdown/handoff files through service | yes | yes | no | delegated | yes | yellow | Service uses `apply=False` by default, returns `dry_run`, and CLI help now explicitly says default is dry-run. |
| `scripts/backfill_meeting_pack_handoff_artifacts.py` | Meeting Pack handoff artifacts through service | yes | yes | no | delegated | yes | yellow | Service uses `apply=False` by default, returns `dry_run`, and CLI help now explicitly says default is dry-run. No independent backup is made. |
| `scripts/migrate_legacy_trial_extraction_alias.py` | YAML config keys in-place | yes | yes | no | no | yes | yellow | Dry-run returns `2` when rewrites are needed. No backup; run in git-controlled trees or make a branch/copy first. |
| `scripts/sweep_legacy_trial_extraction_aliases.py` | sibling repo YAML rewrites via migration script | yes | yes | no | no | yes | yellow | Applies to multiple sibling roots when `--apply` is set. Use after per-root audit; prefer branch backups first. |
| `scripts/migrate_obsidian_note_filenames.py` | Obsidian note files, vault links, index CSVs, DB `obsidian_path` | yes | yes | partial | partial | yes | yellow | `--apply` now requires `--confirm-vault-backup` and creates a SQLite DB backup first. Vault backup remains operator-owned because note/link/index rewrites span the configured vault. |

## Adjacent Generators And Checks

These scripts write reports, generated predictions, bundles, release artifacts, or smoke outputs. They are not routine state-repair mutation scripts, but operators should still understand their output roots before use:

- `scripts/bootstrap_verification_env.py`
- `scripts/build_personal_runtime_bundle.py`
- `scripts/build_personal_runtime_user_kits.py`
- `scripts/release_macos_personal_runtime.py`
- `scripts/capture_stale_incident_snapshots.py`
- `scripts/check_stale_reclaim_readiness.py`
- `scripts/check_sqlite_restore_drill.py`
- `scripts/run_ops_readiness_monitor.py`
- `scripts/downloader_ops_dashboard.py`
- `scripts/eval/*` audit/generation/materialization scripts

Most of these produce additive artifacts under `snapshots/`, `storage/reports/`, packaging output, or bounded support roots. Treat their outputs according to `docs/RESTORE_READINESS_MATRIX.md`.

## Minimum Bar For New Mutation Scripts

New operator-facing mutation scripts should include:

1. dry-run by default
2. explicit `--apply`
3. clear target path/DB arguments
4. backup-before-apply for SQLite or canonical structured state mutation
5. transaction or rollback-aware mutation when multiple writes must stay consistent
6. summary output that can be pasted into a runbook or incident note
7. non-zero exit code for unsafe preconditions or failed mutation

For file-backed generated artifacts, a separate backup may be unnecessary when the artifact is truly rerenderable. The script should still say that explicitly and print what it would write.

## Immediate Follow-Ups

1. Keep this inventory updated when a script moves from one safety class to another.

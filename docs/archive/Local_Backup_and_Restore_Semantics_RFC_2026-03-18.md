# Local Backup and Restore Semantics RFC

Status: Historical proposal  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related:
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/archive/Proposal_to_Lattice_Mapping_2026-03-18.md`
- `docs/Local_Backup_Branch_Retention_2026-02-24.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md`

## Purpose

External proposal docs repeatedly pushed for local-first backup, restore, and versioning discipline.

That idea is valid, but it does not fit the current repo as a new top-level `/projects/{id}/backup` platform API.

This RFC defines the smallest future backup/restore semantics that fit current PaperPipe/Lattice reality:
- file-backed local artifacts
- single-user workflow
- bounded asset roots
- dry-run and rollback-first operational style

## Current fit

Current repo already has partial backup and rollback discipline:
- backup-before-apply scripts for DB mutation lanes
- append-only or snapshot-style artifacts in several bounded systems
- local backup branch retention policy
- versioned or snapshot-backed reproducibility in `Research DNA`, evaluation, and artifact metadata

Current repo does not have:
- a unified runtime-wide backup manifest
- a first-class restore runbook for all bounded asset families
- an approved `projects` workspace backup API

So the correct move is:
- define backup/restore semantics as a bounded future operations layer
- not as a stealth product-model rewrite

## Non-goals

- not cloud sync
- not multi-user disaster recovery
- not a reason to introduce `/projects/{project_id}/backup`
- not a replacement for git or local filesystem ownership
- not a justification for broad DB normalization

## Boundary rules

### What this layer may do

- define when backup is required before a destructive or overwrite-prone operation
- define restore expectations for file-backed bounded assets
- preserve enough manifest metadata to explain what was backed up and why
- keep local-first recovery paths human-checkable

### What this layer must not do

- pretend every current artifact family already supports automatic restore
- hide partial restore risk behind a generic “backup successful” label
- require a new app-wide workspace model before adding value
- collapse git branch backup, DB snapshot backup, and artifact rerenderability into one vague mechanism

## Current partial coverage

### Local branch safety

Current doc:
- `docs/Local_Backup_Branch_Retention_2026-02-24.md`

What exists:
- local backup branches
- retention window
- dry-run default
- opt-in deletion

What it does not cover:
- runtime artifact restore
- DB snapshot restore
- bounded asset restore guarantees

### Scripted DB mutation safety

Current repo already has apply lanes that create backups before mutation, for example:
- summary normalization
- failed-job archive
- paper-id migration

Common existing pattern:
- dry-run default
- explicit `--apply`
- backup file created first
- transaction or rollback-aware mutation

This is good local discipline, but it is still scattered rather than expressed as one bounded rule set.

### Bounded asset snapshots

Current bounded systems already preserve partial restore-friendly state:
- deepread artifact snapshots such as `bootstrap_meta.json` and `run_meta.json`
- `Meeting Pack` saved `generation_request` plus rerender path
- `Research DNA` query-version snapshots and compare provenance snapshots

These are useful, but they are subsystem-specific rather than a unified backup/restore policy.

## Proposed phase-0 model

### `BackupScope`

Suggested scope families:
- `db_snapshot`
- `artifact_bundle`
- `meeting_pack_bundle`
- `research_dna_bundle`
- `profile_snapshot`
- `local_branch_backup`

### `BackupManifest`

Suggested fields:
- `backup_id`
- `scope_type`
- `created_at`
- `trigger`
  - `manual`
  - `pre_apply`
  - `pre_cleanup`
  - `pre_migration`
- `source_paths[]`
- `backup_paths[]`
- `operator`
- `restore_instructions`
- `integrity_note`
- `status`
  - `created`
  - `verified`
  - `restore_tested`
  - `expired`

### `RestoreReadiness`

Suggested values:
- `direct_restore`
- `rerenderable`
- `manual_only`
- `not_supported`

Why this split matters:
- some assets can be byte-restored
- some are best recovered by deterministic rerender from saved request state
- some currently remain manual recovery only

## Storage proposal

Do not add a global backup database first.

Prefer explicit file-backed manifests:

```text
storage/backups/
  manifests/
    <backup_id>.json
  db/
    <timestamp>_state.db
  bundles/
    <backup_id>/
```

This fits the current repo because:
- local-first paths remain inspectable
- restore artifacts can live beside current storage roots
- bounded systems can adopt manifests gradually instead of waiting for a platform migration

## API proposal

Not approved for immediate implementation.

If a future bounded ops surface is needed, keep it narrow:
- `POST /ops/backups/create`
- `GET /ops/backups`
- `GET /ops/backups/{backup_id}`
- `POST /ops/backups/{backup_id}/restore-check`

Do not introduce:
- product-facing `/projects/{id}/backup`
- restore promises that current subsystems cannot actually keep

## Integration rules

### Deepread artifacts

- artifact backup should preserve run-scoped bundle identity
- restore may be direct file restore or rerun from preserved inputs, but the chosen lane must be explicit

### Meeting Pack

- pack bundles already support rerender-oriented recovery from saved request state
- rerenderability is useful, but it is not the same thing as a full backup guarantee

### Research DNA

- query-version snapshots and compare provenance are already meaningful backup-like assets
- future restore semantics must preserve append-only history and approval audit rather than flattening state into one mutable file

### Git branch backups

- local branch retention remains an adjacent safety lane, not the runtime backup system
- do not conflate developer branch retention with user/runtime data restore

## Suggested PR sequence

1. `PR-DOC-BackupRestore-RFC`
- fix the vocabulary and restore-readiness model first

2. `PR-OPS-BackupManifest-v0`
- add manifest shape and helper utilities only

3. `PR-OPS-Bounded-Restore-Checks-v0`
- add restore-check or rerenderability validation for selected bounded asset families

4. `PR-OPS-Restore-Runbook-v0`
- add operator-facing runbook after the guarantees are real

## Adoption gate

Implement only if:
- the repo needs a clearer shared rule for backup-before-apply and restore-readiness
- the semantics can stay honest about which assets are directly restorable versus merely rerenderable
- the work remains additive to the current paper/job/artifact architecture

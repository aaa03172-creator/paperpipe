# Restore Readiness Matrix

Status: Active
Date: 2026-04-26
Owner: Operations maintainers
Canonical runbook: `docs/RESTORE_READINESS_MATRIX.md`
Canonical parent: `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`

## Purpose

Use this matrix to answer a narrow operations question:

> If a local PaperPipe runtime asset is missing, corrupt, or partially written, what recovery expectation is honest today?

This document is intentionally documentation-only. It does not open a unified backup API, shared backup manifest runtime, or automatic restore path.

## Readiness Vocabulary

- `direct_restore`: a byte-level file or directory restore is the primary recovery move when the operator already has a trusted copy.
- `rerenderable`: the asset is usually best recreated from saved structured/request state, but that is not the same as a complete backup guarantee.
- `backup_before_apply`: recovery depends on a script-created pre-apply backup or transaction-aware maintenance flow.
- `manual_only`: current recovery requires operator inspection, rerun, rebuild, or domain-specific cleanup. Do not promise automatic restore.
- `not_supported`: no current restore expectation is documented beyond preserving local source files and inspecting logs.

## Boundary Rules

- Do not edit `storage/state.db` directly to repair queue, job, paper, or run state.
- Do not treat logs, support artifacts, reports, or generated dashboards as canonical state.
- Do not claim every asset under `storage/` has direct restore support.
- Do not collapse DB snapshot restore, bundle rerenderability, local branch backups, and artifact rollback into one generic backup claim.
- Before any destructive or overwrite-prone operation, prefer dry-run output, explicit `--apply`, a printed backup path, and a transaction or rollback-aware write.

## Matrix

| Asset family | Typical path | Layer | Current readiness | Honest recovery move | Notes |
| --- | --- | --- | --- | --- | --- |
| Runtime SQLite state | `storage/state.db` | canonical structured state | `backup_before_apply` | Restore from a known-good SQLite backup created before a bounded mutation, then re-run readiness checks. | No app-wide backup API exists. Queue/job repair should use FastAPI ops endpoints, not manual row edits. |
| Script-created DB backups | `storage/backups/*.db` | review/gate artifact | `direct_restore` | Copy back only after operator confirms the backup matches the intended pre-apply point. | Backup files are local safety artifacts, not an automatic restore registry. Use `scripts/check_sqlite_restore_drill.py` to validate a backup copy before relying on it. |
| Deep-read run artifacts | `storage/artifacts/<paper>/<run>/` | user-facing artifact/export plus review artifacts | `manual_only` | Inspect run metadata, logs, and canonical DB state; rerun through the job API when needed. | Run directories are useful evidence, but restore may require a new run rather than byte replacement. Preserve run identity when copying for forensic review. |
| Job progress logs | `logs/jobs/{job_id}.jsonl` | raw memory | `manual_only` | Use for diagnosis and timeline reconstruction; do not restore as state. | Worker progress logs are not canonical job state. |
| Runtime logs | `logs/` | raw memory | `manual_only` | Preserve for incident review; rotate or delete only after the incident is closed. | Logs may contain local operational context even with sanitizer boundaries. |
| Stale-running incident snapshots | `storage/stale_running_incidents/` | review/gate artifact | `manual_only` | Use as bounded support evidence before/after reclaim; do not restore into runtime state. | Snapshot files are for false-positive and incident review. |
| Downloader dashboard reports | `storage/reports/downloader_ops_dashboard.md` | review/gate artifact | `rerenderable` | Regenerate with `scripts/downloader_ops_dashboard.py`. | The report summarizes DB state and thresholds; it is not source state. |
| General reports | `storage/reports/` | review/gate artifact | `manual_only` | Regenerate when the owning script supports it; otherwise preserve as local evidence. | Report semantics vary by lane. |
| Zotero export cache | `storage/zotero_export.json` | raw source cache / compiled support | `rerenderable` | Re-export or resync from Zotero when source access is available. | Treat Zotero and local PDFs as upstream source owners, not this cache alone. |
| Imported PDF storage | `storage/pdfs/` | raw source | `direct_restore` | Restore original PDFs from local source/backup; then rerun import or readiness checks if metadata drifted. | Raw PDFs should be preserved as originals. Do not rely on derived artifacts as replacements. |
| Obsidian notes/vault state | configured vault and `.pp/` state | user-facing artifact/export plus structured sidecars | `manual_only` | Restore the vault from the operator's vault backup or regenerate notes from canonical state where supported. | Note generation must remain idempotent; `.pp/` structured state should not be overwritten blindly. |
| Meeting Pack bundles | `storage/meeting_packs/` | user-facing artifact/export | `rerenderable` | Prefer regenerate/rerender from saved request and source state when available; byte-restore a bundle only from a trusted local copy. | Store code has rollback-aware writes, but that is write safety, not a universal restore guarantee. |
| Chart Pack bundles | `storage/chart_packs/` | user-facing artifact/export | `rerenderable` | Regenerate from saved structured inputs/specs when available; inspect data/spec/render consistency before reuse. | Bundle writes are rollback-aware for managed files. |
| Method Comparison bundles | `storage/method_comparisons/` | user-facing artifact/export | `rerenderable` | Regenerate from saved comparison inputs when possible; byte-restore only a complete bundle. | JSON/CSV/Markdown bundle files should stay consistent. |
| Paper Synthesis bundles | `storage/paper_syntheses/` | compiled knowledge / user-facing artifact | `rerenderable` | Regenerate from canonical paper/run state where supported; do not treat synthesis as source truth. | Compiled knowledge must trace back upstream. |
| Protocol Cards | `storage/protocol_cards/` | compiled knowledge / user-facing artifact | `rerenderable` | Restore a complete bundle or regenerate from source protocol material and saved versions. | Version files are part of the bundle contract. |
| Protocol Attachments | `storage/protocol_attachments/` | raw source / user-facing support | `direct_restore` | Restore original attachment bytes from trusted local copies. | Attachments may be source-like; avoid lossy regeneration claims. |
| Image Evidence bundles | `storage/image_evidence/` | compiled knowledge / user-facing artifact | `rerenderable` | Regenerate derived evidence when source images and structured context are available; byte-restore complete bundles only. | Store code has rollback-aware writes, but source images should be preserved separately. |
| Talk Pack bundles | `storage/talk_packs/` | user-facing artifact/export | `rerenderable` | Rebuild/rerender from saved talk-pack JSON and source artifacts where available. | Rendered files are outputs; restore should preserve the owning JSON contract. |
| Project Memory | `storage/project_memory/` | raw memory / compiled support | `manual_only` | Preserve and inspect files; do not promote local memory files into canonical truth during recovery. | Project memory is support/retrieval material unless a canonical doc adopts it. |
| Feedback logs | `storage/feedback.jsonl`, `storage/artifact_review_feedback.jsonl` | raw memory / review artifact | `direct_restore` | Restore append-only logs from trusted local backup; validate downstream indexes after replacement. | Indexes can usually be rebuilt; logs themselves are the important local record. |
| Artifact generation outcomes | `storage/artifact_generation_outcomes.jsonl` | review/gate artifact | `direct_restore` | Restore the append-only log from trusted local backup or accept loss as local ops-history loss. | Not a replacement for canonical artifact state. |
| Project context links | `storage/project_context_links.jsonl` | raw memory / compiled support | `direct_restore` | Restore append-only log from trusted backup; verify UI/API readers still parse it. | Treat as support context, not source paper evidence. |
| RAG and feedback indexes | `storage/rag/`, `storage/feedback_index/` | cache | `rerenderable` | Rebuild from canonical/source state and feedback logs. | Indexes are caches and should not be the only copy of source evidence. |
| Cache roots | `storage/cache/` or install-layout cache | cache | `rerenderable` | Clear and rebuild. | Cache loss should not be data loss. |
| Research DNA state | `research_dna/` or configured root | canonical structured state / compiled support | `manual_only` | Restore from trusted local copy only after preserving append-only history and approval/provenance context. | Query-version snapshots are backup-like, but there is no generic restore API. |
| Config files | `config.yaml`, `config/`, `profiles.yaml` | canonical structured state / config | `direct_restore` | Restore from versioned/local backup and run `lattice self-test --json`. | Watch for secret values and machine-specific paths. |
| Local branch backups | local git branches | developer safety artifact | `direct_restore` | Use git branch operations according to the retention policy. | Adjacent to runtime recovery; not a user-data backup system. |

## Operator Decision Flow

1. Classify the asset layer: raw source, raw memory, compiled knowledge, canonical structured state, review/gate artifact, or user-facing artifact/export.
2. Check this matrix for the readiness class.
3. If the asset is canonical structured state, prefer documented APIs or a script-created backup over manual edits.
4. If the asset is user-facing/exported, decide whether a complete byte restore or a rerender from saved state is safer.
5. If the asset is raw source, restore the original bytes and then regenerate downstream derived state.
6. If the asset is raw memory, logs, reports, or support evidence, preserve it for review rather than promoting it into canonical state.

## Reopen Conditions

Revisit runtime implementation only if one of these becomes true:

- multiple asset families need a shared restore-readiness contract enforced in code
- operators need one command to list local assets by restore class
- an incident proves that doc-only guidance is insufficient for confident recovery
- a future backup manifest PR is explicitly reopened from `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`

Until then, this matrix is the honest operating map, not a product promise.

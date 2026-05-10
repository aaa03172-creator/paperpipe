# Runbook and Queue Docs Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the remaining repo/runbook metadata updates and queue refresh docs without touching runtime code.

## Included scope

- `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md`
- `docs/Local_Backup_Branch_Retention_2026-02-24.md`
- `docs/Pending_PR_Queue.md`
- `docs/Prompt_Antigravity_Phase31_Parallel.txt`
- `docs/README.md`
- `docs/archive/README.md`
- `docs/deprecation_src_db.md`
- `docs/development_rules.md`
- `docs/institutional_access.md`
- `docs/ocr_fallback.md`
- `docs/operations_checklist_watcher_review_queue.md`
- `docs/runtime_security_env.md`
- `docs/ux-review.md`
- `docs/ux-review-report.md`
- `docs/reports/Runbook_Queue_Docs_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- `AGENTS.md`
- frontend or backend code
- active UX report artifacts already committed

## Verification

1. `python3 scripts/lint_docs.py`
2. staged diff stays docs-only

## Commit target

`docs(runbooks): refresh queue and operational references`

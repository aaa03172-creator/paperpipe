# Runtime Readiness Lane Stage Set

Status: exact stage boundary
Date: 2026-04-08
Lane: `runtime-readiness/installability`
Parent notes:
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`
- `docs/reports/Installability_Audit_2026-03-27.md`
- `docs/reports/Personal_Runtime_MVP_Checklist_2026-03-28.md`

## Purpose

Freeze the smallest practical git-stage boundary for the clean runtime-readiness split assembled from merged base.

This note does not stage or commit anything.
It answers one narrower question:

- from the clean split branch, which files are now whole-file safe to stage together, and which paths should still stay out?

## Diff Re-check Summary

The clean split branch was re-checked directly after the backend/browser-safe readiness port and frontend build verification.

Current judgment:

- the previously mixed owners from the dirty tree were brought over narrowly enough that this clean branch can now be staged as a whole-file lane
- `workspace-summary`, `HomeWorkspaceSummary`, institutional-access, and broader workspace-shell additions are not present in the runtime-readiness owner files on this branch
- the runtime-readiness page, `/health/ready`, browser beta gate hardening, launcher wiring, and request-audit/storage helpers still form one bounded story
- generated outputs from local verification remain out-of-scope even though they may exist locally

## Whole-File Safe For This Clean Lane

These files are safe to stage as whole files from the clean split branch:

- `backend/main.py`
- `docs/reports/Installability_Audit_2026-03-27.md`
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`
- `docs/reports/Personal_Runtime_MVP_Checklist_2026-03-28.md`
- `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`
- `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`
- `docs/reports/Runtime_Readiness_Lane_Stage_Set_2026-04-08.md`
- `frontend/README.md`
- `frontend/e2e/backend.gated.spec.ts`
- `frontend/package.json`
- `frontend/playwright.backend.gated.config.ts`
- `frontend/playwright.backend.real.config.ts`
- `frontend/scripts/run_backend_for_e2e.sh`
- `frontend/scripts/run_backend_for_real_smoke.sh`
- `frontend/src/App.tsx`
- `frontend/src/app/lib/api.ts`
- `frontend/src/app/lib/types.ts`
- `frontend/src/app/pages/RuntimeReadinessPage.tsx`
- `scripts/run_backend_for_real_smoke.py`
- `src/cli.py`
- `src/db_utils.py`
- `src/schemas/ops.py`
- `src/services/event_log.py`
- `src/services/path_masking.py`
- `src/services/runtime_paths.py`
- `src/services/runtime_readiness.py`
- `tests/test_beta_gate_api.py`
- `tests/test_browser_request_audit_api.py`
- `tests/test_browser_security_headers_api.py`
- `tests/test_frontend_real_smoke_backend_launcher.py`
- `tests/test_frontend_real_smoke_preflight.py`
- `tests/test_runtime_readiness_api.py`
- `tests/test_runtime_readiness_backend_entrypoint.py`
- `tests/test_runtime_readiness_external_roots.py`

Why these are safe together:

- they all support the same operator story:
  - packaged launcher readiness
  - `/health/ready`
  - browser-safe beta access
  - request-audit and security-header hardening for close-person browser use
  - real-smoke preflight and launch support
- the clean split explicitly excludes the mixed workspace and institutional-access additions that made patch staging necessary in the dirty tree
- this lane still does not introduce a storage migration beyond additive request-audit tables and indexes already covered by targeted tests

## Keep-Out Paths

Do not include these in the same stage set:

- `frontend/dist/`
- `frontend/node_modules/`
- `docs/reports/Institutional_Access_Fit_Review_2026-03-28.md`
- `docs/reports/Institutional_Access_Status_Semantics_RFC_2026-03-28.md`
- `frontend/src/app/lib/accessSummary.ts`
- `frontend/playwright.backend.parser.config.ts`
- `frontend/scripts/run_fake_worker_for_e2e.py`
- `frontend/e2e/backend.spec.ts`
- research-workspace or home-context docs/components/files
- parser-worker and specialty-runtime eval files
- generated outputs under `storage/`, `snapshots/`, `output/`, `packaging/`, or `.codex/work/`

Why they stay out:

- they belong to different lanes than runtime-readiness/installability
- they were not needed to verify the bounded readiness story
- `dist/` and `node_modules/` are local verification byproducts, not source changes

## Manual Stage Recipe

If this clean split is staged next, the safe sequence is:

```bash
git add \
  backend/main.py \
  docs/reports/Installability_Audit_2026-03-27.md \
  docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md \
  docs/reports/Personal_Runtime_MVP_Checklist_2026-03-28.md \
  docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md \
  docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md \
  docs/reports/Runtime_Readiness_Lane_Stage_Set_2026-04-08.md \
  frontend/README.md \
  frontend/e2e/backend.gated.spec.ts \
  frontend/package.json \
  frontend/playwright.backend.gated.config.ts \
  frontend/playwright.backend.real.config.ts \
  frontend/scripts/run_backend_for_e2e.sh \
  frontend/scripts/run_backend_for_real_smoke.sh \
  frontend/src/App.tsx \
  frontend/src/app/lib/api.ts \
  frontend/src/app/lib/types.ts \
  frontend/src/app/pages/RuntimeReadinessPage.tsx \
  scripts/run_backend_for_real_smoke.py \
  src/cli.py \
  src/db_utils.py \
  src/schemas/ops.py \
  src/services/event_log.py \
  src/services/path_masking.py \
  src/services/runtime_paths.py \
  src/services/runtime_readiness.py \
  tests/test_beta_gate_api.py \
  tests/test_browser_request_audit_api.py \
  tests/test_browser_security_headers_api.py \
  tests/test_frontend_real_smoke_backend_launcher.py \
  tests/test_frontend_real_smoke_preflight.py \
  tests/test_runtime_readiness_api.py \
  tests/test_runtime_readiness_backend_entrypoint.py \
  tests/test_runtime_readiness_external_roots.py
```

No patch staging should be necessary on this clean branch if the working tree remains limited to the files above.

## Smallest Relevant Verification Before Staging

Run:

```bash
python3 scripts/lint_docs.py
python3 -m compileall backend/main.py src/cli.py src/schemas/ops.py src/services/runtime_readiness.py src/services/runtime_paths.py src/services/event_log.py src/db_utils.py scripts/run_backend_for_real_smoke.py
/Users/jangseongjin/paperpipe/.venv/bin/pytest -q tests/test_runtime_readiness_api.py tests/test_runtime_readiness_backend_entrypoint.py tests/test_runtime_readiness_external_roots.py tests/test_beta_gate_api.py tests/test_browser_request_audit_api.py tests/test_browser_security_headers_api.py tests/test_frontend_real_smoke_preflight.py tests/test_frontend_real_smoke_backend_launcher.py
cd frontend && npm run build
```

Current result at re-check time:

- docs lint passed
- targeted compileall passed
- targeted pytest bundle passed: `23 passed`
- frontend production build passed

## Short Version

The dirty-tree runtime-readiness lane required patch staging.

The clean split branch no longer does.

The safe boundary is now:

- whole-file stage the runtime-readiness source, docs, frontend page/launcher files, and targeted tests
- keep generated frontend build outputs and unrelated institutional-access, workspace, and parser/eval files out

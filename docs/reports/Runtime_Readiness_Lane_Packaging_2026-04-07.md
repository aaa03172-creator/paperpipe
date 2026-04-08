# Runtime Readiness Lane Packaging (2026-04-07)

Status: Active packaging note
Date: 2026-04-07
Owner: Lattice runtime maintainers
Canonical: `docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md`

## Purpose

Define the next safe bounded lane inside the current mixed dirty worktree.

This note is not a new roadmap.
It is a separation note for the `runtime-readiness / installability` slice only.

## Current judgment

The next bounded lane worth separating from the mixed dirty tree is:

- runtime-readiness and installability hardening
- launcher/preflight support for real smoke verification
- browser-safe readiness and close-person beta gate hardening
- personal-runtime documentation that matches the current local-first, single-operator deployment shape

This note does **not** reopen:

- extraction / specialty-runtime evaluation
- research-workspace or broader home/workspace surfaces
- institutional-access cleanup as a separate product lane

## Important boundary

The current dirty-tree [`docs/Pending_PR_Queue.md`](/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md) still points to the older `2026-03-28` release-refresh proof.

Merged base has already advanced beyond that.

So for this dirty tree:

- do not treat the queue posture here as the latest merged-base release posture
- use this note only to separate the runtime-readiness lane from the rest of the mixed tree
- perform any real split on top of a clean branch/worktree from the merged base

## What belongs in this lane

This lane is about making the current launcher-first local runtime easier to verify, package, and diagnose without changing the product unit.

That includes:

- readiness checks surfaced through backend and launcher
- browser-safe readiness behavior for close-person beta surfaces
- real-smoke launcher/preflight support
- the dedicated runtime-readiness page
- personal-runtime deployment/installability docs

It does **not** include:

- generalized workspace-summary or home-surface additions
- access-summary or institutional-access labeling
- parser-worker or specialty-runtime behavior

## Whole-file safe candidates

These files look coherent enough to review as one runtime-readiness lane without hunk-splitting:

- `docs/reports/Installability_Audit_2026-03-27.md`
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`
- `docs/reports/Personal_Runtime_MVP_Checklist_2026-03-28.md`
- `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`
- `src/services/runtime_readiness.py`
- `scripts/run_backend_for_real_smoke.py`
- `frontend/src/app/pages/RuntimeReadinessPage.tsx`
- `frontend/e2e/backend.gated.spec.ts`
- `frontend/playwright.backend.gated.config.ts`
- `frontend/playwright.backend.real.config.ts`
- `frontend/scripts/run_backend_for_real_smoke.sh`
- `frontend/README.md`
- `frontend/package.json`
- `tests/test_runtime_readiness_api.py`
- `tests/test_runtime_readiness_backend_entrypoint.py`
- `tests/test_runtime_readiness_external_roots.py`
- `tests/test_frontend_real_smoke_preflight.py`
- `tests/test_frontend_real_smoke_backend_launcher.py`
- `tests/test_beta_gate_api.py`
- `tests/test_browser_request_audit_api.py`
- `tests/test_browser_security_headers_api.py`

Why these are safe together:

- they all point back to the same operator story: `self-test`, `/health/ready`, real-smoke launch, or personal-runtime packaging/installability
- they do not require reopening research-workspace semantics
- they are mostly dedicated files rather than mixed neighborhood edits

## Patch-stage only

These files are part of the lane, but they are mixed with unrelated or later-lane work and should **not** be staged wholesale:

- `backend/main.py`
- `src/cli.py`
- `src/schemas/ops.py`
- `frontend/src/App.tsx`
- `frontend/src/app/lib/api.ts`
- `frontend/src/app/lib/types.ts`
- `frontend/playwright.backend.config.ts`
- `frontend/scripts/run_backend_for_e2e.sh`

Stage only the hunks that are clearly about:

- `RuntimeReadinessCheck` / `RuntimeReadinessResponse`
- `/health/ready`
- browser-safe readiness behavior for beta-gated browser surfaces
- request-audit / security-header / browser-write hardening tied to close-person browser access
- `lattice self-test` and real-smoke launcher wiring
- the `/ready` route and `getRuntimeReadiness()` frontend path
- `specialty_trial_extraction` key normalization only where needed for the runtime-readiness real-smoke path

Do **not** stage from these files in this lane when the hunks are about:

- `HomeWorkspaceSummaryResponse`
- `/workspace-summary`
- broader home/workspace shell behavior
- unrelated job, artifact, parser, or workbench behavior

## Keep out of this lane

These files are visible nearby but should stay out of the runtime-readiness lane:

- `docs/reports/Institutional_Access_Fit_Review_2026-03-28.md`
- `docs/reports/Institutional_Access_Status_Semantics_RFC_2026-03-28.md`
- `frontend/src/app/lib/accessSummary.ts`
- `frontend/playwright.backend.parser.config.ts`
- `frontend/scripts/run_fake_worker_for_e2e.py`
- `frontend/e2e/backend.spec.ts`
- extraction/specialty-runtime files under `goldset/`, `scripts/eval/`, or sidecar services
- research-workspace/home-context files and docs
- generated/runtime outputs under `storage/`, `snapshots/`, `output/`, `dist/`, or `packaging/`

Why:

- institutional-access cleanup is a different additive API/UI lane
- parser-worker coverage is a different execution/eval lane
- `frontend/e2e/backend.spec.ts` is too broad and mixes multiple surfaces
- generated artifacts are not the same thing as runtime-readiness source changes

## Safest next split move

Do not stage this lane directly from the current dirty main worktree.

Instead:

1. create a clean branch/worktree from the latest merged base
2. bring over the `whole-file safe` files first
3. patch-stage the mixed owner files one by one
4. keep `HomeWorkspaceSummary` and other workspace-lane hunks out

Recommended first verification on the clean split:

- `python3 scripts/lint_docs.py`
- `pytest -q tests/test_runtime_readiness_api.py tests/test_runtime_readiness_backend_entrypoint.py tests/test_runtime_readiness_external_roots.py`
- `pytest -q tests/test_frontend_real_smoke_preflight.py tests/test_frontend_real_smoke_backend_launcher.py`
- `pytest -q tests/test_beta_gate_api.py tests/test_browser_request_audit_api.py tests/test_browser_security_headers_api.py`

Optional follow-up verification once the clean split is assembled:

- `cd frontend && npm run e2e:backend:gated`

## Explicit non-recommendations

Do not do these as part of this lane:

- do not bundle institutional-access status work into runtime-readiness
- do not bring in parser-worker or specialty-runtime coverage just because some launcher files touch both
- do not treat `workspace-summary` additions as installability work
- do not update the dirty-tree queue posture first and then infer staging scope from it
- do not stage the current dirty tree as one package because several readiness files are adjacent

## References

- `docs/reports/Current_State_Packaging_2026-03-24.md`
- `docs/reports/Current_State_Staging_Guide_2026-03-24.md`
- `docs/reports/Installability_Audit_2026-03-27.md`
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`
- `docs/reports/Personal_Runtime_MVP_Checklist_2026-03-28.md`
- `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`

## Conclusion

The next bounded split is not a new feature lane.

It is a packaging lane:

- readiness
- installability
- personal-runtime deployment honesty
- browser-safe beta hardening

Keep that lane narrow, and keep workspace, institutional-access, and parser/eval work out of it.

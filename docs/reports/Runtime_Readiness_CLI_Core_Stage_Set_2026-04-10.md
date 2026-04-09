# Runtime Readiness CLI Core Stage Set

Status: exact stage boundary
Date: 2026-04-10
Lane: `runtime/runtime-readiness-cli-core`
Parent notes:
- [Runtime_Readiness_Lane_Packaging_2026-04-07.md](/Users/jangseongjin/paperpipe/docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md)
- [Runtime_Paths_Install_Layout_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Runtime_Paths_Install_Layout_Stage_Set_2026-04-10.md)
- [Current_Worktree_Lane_Triage_2026-04-07.md](/Users/jangseongjin/paperpipe/docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md)

## Purpose

Freeze the next smallest safe lane after install-layout runtime paths.

This lane is the runtime-readiness core needed by the launcher and packaged entrypoint:

- schema-backed runtime-readiness checks
- a dedicated readiness collector service
- `lattice self-test`
- packaged backend launch helpers for `lattice start`

This lane is intentionally smaller than the broader runtime-readiness packaging note.

## Current Judgment

The currently coherent bounded split is:

- [runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)
- the `RuntimeReadinessCheck` / `RuntimeReadinessResponse` schema surface in [ops.py](/Users/jangseongjin/paperpipe/src/schemas/ops.py)
- the CLI hunks in [cli.py](/Users/jangseongjin/paperpipe/src/cli.py) for:
  - `self-test`
  - backend preflight in `start`
  - `_build_backend_launch_command`
  - `_argv_with_frozen_app_default_command`
  - hidden `serve-backend`
  - packaged-app default-command entrypoint behavior
- focused tests that lock those owners

This lane should not absorb:

- backend `/health/ready`
- browser beta gate or request-audit hardening
- the frontend runtime-readiness page
- real-smoke launcher scripts
- packaged release docs or user-kit builders

## Whole-File Safe Files

These files are dedicated enough to stage whole:

- [runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)
- [test_cli_self_test_command.py](/Users/jangseongjin/paperpipe/tests/test_cli_self_test_command.py)
- [test_cli_start_command.py](/Users/jangseongjin/paperpipe/tests/test_cli_start_command.py)
- [test_runtime_readiness_backend_entrypoint.py](/Users/jangseongjin/paperpipe/tests/test_runtime_readiness_backend_entrypoint.py)
- [test_runtime_readiness_external_roots.py](/Users/jangseongjin/paperpipe/tests/test_runtime_readiness_external_roots.py)
- [test_runtime_paths_bundle_assets.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_bundle_assets.py)
- [Runtime_Readiness_CLI_Core_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Runtime_Readiness_CLI_Core_Stage_Set_2026-04-10.md)

Why they are safe together:

- they all prove the same operator story: installability self-test, runtime root visibility, and packaged launcher entry behavior
- they do not require FastAPI route or frontend route changes

## Patch-Stage Only

These files are mixed-owner and must not be staged wholesale:

- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [ops.py](/Users/jangseongjin/paperpipe/src/schemas/ops.py)

Stage only these hunks from [cli.py](/Users/jangseongjin/paperpipe/src/cli.py):

- import of `collect_runtime_readiness`
- helper definitions:
  - `_build_backend_launch_command`
  - `_argv_with_frozen_app_default_command`
- `self-test` command
- `start` preflight use of `collect_runtime_readiness()` and the switch to `_build_backend_launch_command(...)`
- hidden `serve-backend` command
- `entrypoint()` wrapper that prefixes `start` for packaged macOS app launches

Leave out from [cli.py](/Users/jangseongjin/paperpipe/src/cli.py):

- watchdog dependency helper and watch-command gating
- `doctor()` watch/log presentation changes
- `clear_logs()` / `reset()` log-root changes
- unrelated clinical-result formatting changes
- repair-stats wording tweaks
- all research-DNA screening command additions

Stage only these hunks from [ops.py](/Users/jangseongjin/paperpipe/src/schemas/ops.py):

- `RuntimeReadinessCheck`
- `RuntimeReadinessResponse`

Leave out from [ops.py](/Users/jangseongjin/paperpipe/src/schemas/ops.py):

- `HomeWorkspaceSummaryResponse`

## Keep Out Of This Lane

Do not stage these nearby files in this split:

- [main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [test_runtime_readiness_api.py](/Users/jangseongjin/paperpipe/tests/test_runtime_readiness_api.py)
- [RuntimeReadinessPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/RuntimeReadinessPage.tsx)
- [backend.gated.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.gated.spec.ts)
- [playwright.backend.gated.config.ts](/Users/jangseongjin/paperpipe/frontend/playwright.backend.gated.config.ts)
- [run_backend_for_real_smoke.py](/Users/jangseongjin/paperpipe/scripts/run_backend_for_real_smoke.py)
- [run_backend_for_real_smoke.sh](/Users/jangseongjin/paperpipe/frontend/scripts/run_backend_for_real_smoke.sh)
- [test_frontend_real_smoke_backend_launcher.py](/Users/jangseongjin/paperpipe/tests/test_frontend_real_smoke_backend_launcher.py)
- [test_beta_gate_api.py](/Users/jangseongjin/paperpipe/tests/test_beta_gate_api.py)
- [test_browser_request_audit_api.py](/Users/jangseongjin/paperpipe/tests/test_browser_request_audit_api.py)
- [test_browser_security_headers_api.py](/Users/jangseongjin/paperpipe/tests/test_browser_security_headers_api.py)

Why they stay out:

- they reopen a broader backend/browser contract lane
- they depend on route wiring, auth posture, or hosted-beta behavior that is larger than this CLI-core patch

## Verification

Use only the narrow core checks for this lane:

```bash
cd /Users/jangseongjin/paperpipe && python3 -m py_compile \
  src/services/runtime_readiness.py \
  src/schemas/ops.py \
  src/cli.py \
  tests/test_cli_self_test_command.py \
  tests/test_cli_start_command.py \
  tests/test_runtime_readiness_backend_entrypoint.py \
  tests/test_runtime_readiness_external_roots.py \
  tests/test_runtime_paths_bundle_assets.py
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_cli_self_test_command.py \
  tests/test_cli_start_command.py \
  tests/test_runtime_readiness_backend_entrypoint.py \
  tests/test_runtime_readiness_external_roots.py \
  tests/test_runtime_paths_bundle_assets.py
cd /Users/jangseongjin/paperpipe && git diff --check \
  src/services/runtime_readiness.py \
  src/schemas/ops.py \
  src/cli.py \
  tests/test_cli_self_test_command.py \
  tests/test_cli_start_command.py \
  tests/test_runtime_readiness_backend_entrypoint.py \
  tests/test_runtime_readiness_external_roots.py \
  tests/test_runtime_paths_bundle_assets.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Short Version

This lane is the CLI-facing runtime-readiness core only:

- add schema-backed readiness checks
- expose a dedicated readiness collector
- surface it through `lattice self-test`
- make packaged `start` use the same preflight and backend-launch contract

Do not widen it yet into backend/browser readiness routes or release packaging docs.

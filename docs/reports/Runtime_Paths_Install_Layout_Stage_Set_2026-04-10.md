# Runtime Paths Install Layout Stage Set

Status: exact stage boundary
Date: 2026-04-10
Lane: `runtime/runtime-paths-install-layout`
Parent notes:
- [Runtime_Readiness_Lane_Packaging_2026-04-07.md](/Users/jangseongjin/paperpipe/docs/reports/Runtime_Readiness_Lane_Packaging_2026-04-07.md)
- [Current_Worktree_Lane_Triage_2026-04-07.md](/Users/jangseongjin/paperpipe/docs/reports/Current_Worktree_Lane_Triage_2026-04-07.md)
- [Optional_Verifier_Import_And_Handoff_Assertions_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Optional_Verifier_Import_And_Handoff_Assertions_Stage_Set_2026-04-10.md)

## Purpose

Freeze the smallest safe follow-up lane after the clinical extraction and optional verifier splits.

This lane is not the whole personal-runtime packaging story.
It is the path-contract prerequisite that lets later packaging and runtime-readiness work resolve user-scoped install-layout paths without reopening broader backend or UI surfaces.

## Current Judgment

The currently coherent next lane is:

- install-layout-aware runtime root expansion in [runtime_paths.py](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)
- focused runtime-path tests for macOS and Windows user-scoped roots
- a dedicated stage note that records the exact boundary

This lane should not also absorb:

- CLI self-test or packaged launcher wiring
- backend `/health/ready` or browser runtime-readiness API work
- personal-runtime release scripts and handoff docs
- broader workspace or research-surface changes

## Files In Scope

These files belong to this lane:

- [runtime_paths.py](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)
- [test_runtime_paths_research_dna.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_research_dna.py)
- [test_runtime_paths_cache.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_cache.py)
- [test_runtime_paths_config.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_config.py)
- [test_runtime_paths_logs.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_logs.py)
- [test_runtime_paths_paper_syntheses.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_paper_syntheses.py)
- [test_runtime_paths_windows.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_windows.py)
- [Runtime_Paths_Install_Layout_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Runtime_Paths_Install_Layout_Stage_Set_2026-04-10.md)

## What This Lane Adds

The runtime-path change in [runtime_paths.py](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py) is limited to:

- bundle-aware source root resolution:
  - `bundle_root()`
  - `app_source_root()`
  - `frontend_runtime_dir()`
- install-layout-aware roots for:
  - `storage_root()`
  - `logs_root()`
  - `cache_root()`
- new user-scoped helper roots for:
  - `exports_root()`
  - `library_root()`
  - `pdf_storage_root()`
  - `managed_watch_folder_root()`
  - `paper_syntheses_root()`
- keeping existing `PAPERPIPE_HOME` and explicit env override precedence intact

Why this split is safe:

- it stays inside the canonical runtime-path owner
- it does not change job, paper, or artifact schemas
- it gives later packaging and runtime-readiness lanes a stable path contract instead of duplicating OS-specific rules elsewhere

## Keep Out Of This Lane

Do not stage these nearby files as part of this split:

- [runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)
- [cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [ops.py](/Users/jangseongjin/paperpipe/src/schemas/ops.py)
- [build_personal_runtime_bundle.py](/Users/jangseongjin/paperpipe/scripts/build_personal_runtime_bundle.py)
- [build_personal_runtime_user_kits.py](/Users/jangseongjin/paperpipe/scripts/build_personal_runtime_user_kits.py)
- [release_macos_personal_runtime.py](/Users/jangseongjin/paperpipe/scripts/release_macos_personal_runtime.py)
- [check_windows_personal_runtime_smoke.py](/Users/jangseongjin/paperpipe/scripts/check_windows_personal_runtime_smoke.py)
- [PERSONAL_RUNTIME_INSTALL.md](/Users/jangseongjin/paperpipe/docs/PERSONAL_RUNTIME_INSTALL.md)
- [MACOS_PERSONAL_RUNTIME_RELEASE.md](/Users/jangseongjin/paperpipe/docs/MACOS_PERSONAL_RUNTIME_RELEASE.md)
- [WINDOWS_PERSONAL_RUNTIME_ALPHA.md](/Users/jangseongjin/paperpipe/docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md)
- [test_runtime_paths_bundle_assets.py](/Users/jangseongjin/paperpipe/tests/test_runtime_paths_bundle_assets.py)

Why they stay out:

- they depend on later readiness or packaging behavior that is not yet part of this smallest safe path-owner split
- bundling them now would turn a path-contract patch into a broader installability lane

## Verification

Run only the path-owner checks for this lane:

```bash
cd /Users/jangseongjin/paperpipe && python3 -m py_compile \
  src/services/runtime_paths.py \
  tests/test_runtime_paths_research_dna.py \
  tests/test_runtime_paths_cache.py \
  tests/test_runtime_paths_config.py \
  tests/test_runtime_paths_logs.py \
  tests/test_runtime_paths_paper_syntheses.py \
  tests/test_runtime_paths_windows.py
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_runtime_paths_research_dna.py \
  tests/test_runtime_paths_cache.py \
  tests/test_runtime_paths_config.py \
  tests/test_runtime_paths_logs.py \
  tests/test_runtime_paths_paper_syntheses.py \
  tests/test_runtime_paths_windows.py
cd /Users/jangseongjin/paperpipe && git diff --check \
  src/services/runtime_paths.py \
  tests/test_runtime_paths_research_dna.py \
  tests/test_runtime_paths_cache.py \
  tests/test_runtime_paths_config.py \
  tests/test_runtime_paths_logs.py \
  tests/test_runtime_paths_paper_syntheses.py \
  tests/test_runtime_paths_windows.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
```

## Short Version

This lane is the runtime-path contract only:

- make install-layout roots explicit
- keep env override precedence honest
- add focused path tests on macOS and Windows

Do not widen it yet into CLI, backend readiness, or packaged release docs.

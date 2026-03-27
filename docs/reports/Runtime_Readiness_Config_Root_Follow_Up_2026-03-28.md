# Runtime Readiness Config-Root Follow-Up

Status: bounded follow-up note  
Date: 2026-03-28  
Owner: Runtime/installability maintainers

## Purpose

Record the smallest follow-up needed after the first `runtime readiness` slice already landed on `master`.

This follow-up is intentionally narrow:
- keep `/health/ready`
- keep `lattice self-test`
- add a first-class `config_root()` policy
- expose config-root writability separately from config-file loadability

It does not:
- add a desktop shell
- reopen packaging or installer scope
- change the current launcher-first product boundary

## Why This Follow-Up Exists

The current runtime already has:
- `/health/ready`
- `lattice self-test`
- built-frontend serving under `/ui`

But the remaining gap was that config diagnostics still centered on a single file path.

For installability and launcher-first operator use, that was too thin:
- `config file readable` and
- `config root writable`

are not the same thing.

This follow-up separates those two concerns.

## What Changed

### 1. Runtime path layer

`src/services/runtime_paths.py` now adds:
- `config_root()`
- `install_layout_enabled()`
- `user_config_base_dir()`

and extends `config_file_path()` so it can resolve config more honestly under:
- `PAPERPIPE_CONFIG_DIR`
- `PAPERPIPE_HOME`
- `PAPERPIPE_INSTALL_LAYOUT=1`

It also aligns `profiles_config_path()` with the same config-root policy.

### 2. Runtime readiness surface

`src/services/runtime_readiness.py` now emits a separate `config_root` check:
- `ok` when writable
- `warn` when not writable

This keeps the readiness surface additive.
It does not change the existing `config_file` load check.

### 3. Test coverage

Added/updated targeted tests for:
- config-root resolution under `PAPERPIPE_HOME`
- config-file preference under `<home>/config/config.yaml`
- legacy fallback to `<home>/config.yaml`
- install-layout resolution on macOS
- `/health/ready` carrying the new `config_root` check

## Verification

```bash
pytest -q tests/test_runtime_readiness_api.py tests/test_cli_self_test_command.py tests/test_runtime_paths_config.py
```

Result:
- `9 passed`

## Current Boundary

This follow-up supports a more installable launcher-first local runtime.

It is not evidence for:
- packaged-app readiness
- installer readiness
- desktop wrapper adoption
- broader runtime/platform redesign

## Decision

Keep this as a bounded runtime-readiness/installability slice only.

If installability work continues later, it should continue from this posture:
- launcher first
- path normalization second
- packaging much later

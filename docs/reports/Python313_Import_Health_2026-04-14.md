# Python 3.13 Import Health

Status: bounded runtime diagnostic
Date: 2026-04-14
Lane: `smallest-safe-patch`

## Why This Exists

During the artifact-history follow-up, direct verification started failing in a way that did not
look like a normal PaperPipe regression.

The observed symptom was simple:

- `.venv/bin/python -c 'import pytest'` stalled
- `.venv/bin/python -c 'import backend.main'` stalled
- `.venv/bin/python -c 'import src.cli'` stalled

This note records what was re-checked, what was actually repo-local, and what appears to be an
interpreter-level problem outside the repo.

## Repo-Local Fixes Landed

Two repo-local module-load paths were still pulling `subprocess` at import time:

- [src/cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [src/ingest/ocr_fallback.py](/Users/jangseongjin/paperpipe/src/ingest/ocr_fallback.py)

Those imports are now lazy via a small module-local proxy so the repo no longer widens the
`subprocess -> selectors -> select` path earlier than necessary.

That is still a correct change even though it does not fully solve the environment problem below.

## What Was Reproduced

Using a healthy runner interpreter to probe the target Python binary, the low-level failure is
reproducible even outside PaperPipe:

- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -S -c 'import select'`
  stalls
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -S -c 'import subprocess'`
  stalls

That means the current framework Python 3.13 runtime is unhealthy before any PaperPipe module is
imported.

## Current Interpretation

This is not one clean repo bug.
It is a layered issue:

1. PaperPipe had a small avoidable widening of the bad path.
2. The current Python 3.13 framework build itself still hangs on core imports such as `select`.
3. Third-party imports built on top of that path, including `typer`, `anyio`, and `fastapi`,
   remain vulnerable until the interpreter/runtime itself is replaced or rebuilt.

## Durable Diagnostic Surface

The repo now includes:

- [check_python_import_health.py](/Users/jangseongjin/paperpipe/scripts/check_python_import_health.py)
- [bootstrap_verification_env.py](/Users/jangseongjin/paperpipe/scripts/bootstrap_verification_env.py)
- [resolve_verification_python.py](/Users/jangseongjin/paperpipe/scripts/resolve_verification_python.py)

Generated snapshots from this pass:

- [summary.json](/Users/jangseongjin/paperpipe/snapshots/python_import_health/python313_framework_core_doublecheck_20260414/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/python_import_health/python313_venv_import_health_20260414b/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/python_import_health/python_import_health_custom_verify_20260414/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/python_import_health/python314_homebrew_import_health_20260414/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/python_import_health/python314_venv_import_health_20260414/summary.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/verification_env_bootstrap/verification_env_bootstrap_20260414b/summary.json)

This script is intentionally runner-driven:

- run it with a healthy Python
- point `--python-bin` at the interpreter you want to probe
- inspect the generated snapshot under `snapshots/python_import_health/`

It exists so future import stalls can be classified quickly as:

- repo-local import widening
- dependency import widening
- interpreter-level import failure

## Recommended Next Action

Do not treat the current `.venv` / framework Python 3.13 import stalls as solved by repo code
alone.

The safe next move is:

- keep the lazy-import repo patch
- use the import-health probe to capture the failing interpreter state
- use a healthy verification environment for repo checks until the broken runtime is replaced

## Healthy Verification Path

This pass also confirmed a working bounded verification environment:

- interpreter: `/opt/homebrew/bin/python3.14`
- venv: `/Users/jangseongjin/paperpipe/.venv314`

Observed results:

- `.venv314` import-health snapshot is fully green:
  - [summary.json](/Users/jangseongjin/paperpipe/snapshots/python_import_health/python314_venv_import_health_20260414/summary.json)
- direct import smoke succeeds:
  - `import src.cli`
  - `import backend.main`
  - `import pytest`
- targeted regressions succeed under `.venv314`:
  - `tests/test_python_import_health.py`
  - `tests/test_cli_start_command.py`
  - `tests/test_ocr_fallback.py`

Current recommendation:

- keep the old `.venv` as evidence of the failing Python 3.13 path
- use `.venv314` for bounded local verification until the Python 3.13 runtime is rebuilt or removed
- use `scripts/bootstrap_verification_env.py` to recreate that path instead of relying on one-off shell history
- let repo verify wrappers resolve `PAPERPIPE_VERIFICATION_PYTHON`, then `.venv314`, before falling back to weaker local defaults

## Verification Wrapper Recovery

The repo's main local verification wrappers no longer call bare `pytest` directly:

- [run_agents_smoke.sh](/Users/jangseongjin/paperpipe/scripts/run_agents_smoke.sh)
- [run_backend_api_smoke.sh](/Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh)
- [run_escalation_judge_verify.sh](/Users/jangseongjin/paperpipe/scripts/run_escalation_judge_verify.sh)
- [run_meeting_pack_verify.sh](/Users/jangseongjin/paperpipe/scripts/run_meeting_pack_verify.sh)

They now resolve a healthy interpreter through
[resolve_verification_python.py](/Users/jangseongjin/paperpipe/scripts/resolve_verification_python.py)
and run `python -m pytest` from that interpreter instead of trusting whichever `pytest` binary happens
to be first in `PATH`.

Observed bounded verification after that change:

- resolver path selection succeeds:
  - `python3 scripts/resolve_verification_python.py --require-module pytest`
- targeted helper tests succeed under `.venv314`:
  - `tests/test_resolve_verification_python.py`
  - `tests/test_bootstrap_verification_env.py`
  - `tests/test_python_import_health.py`
- one wrapper lane was re-run end to end:
  - `./scripts/run_escalation_judge_verify.sh`

Follow-up double-check:

- `./scripts/run_agents_smoke.sh` initially still failed under `.venv314` because the bootstrap helper only installed `requirements.txt + pytest`, while the agent smoke lane also imports `langgraph` through
  [stats_agent.py](/Users/jangseongjin/paperpipe/src/agents/stats_agent.py#L5).
- The bounded fix is:
  - `bootstrap_verification_env.py` now includes `langgraph` in its default extra packages
  - `run_agents_smoke.sh` now requires both `pytest` and `langgraph` when resolving a verification interpreter
- Reproducibility was re-confirmed by rerunning:
  - `python3 scripts/bootstrap_verification_env.py --python-bin /opt/homebrew/bin/python3.14 --venv-dir .venv314 --run-id verification_env_bootstrap_langgraph_20260414`
  - `./scripts/run_agents_smoke.sh`
- One more recovery hardening landed after that:
  - the bootstrap helper now uses a more realistic default import-health timeout (`10` seconds)
  - and exits non-zero when the rebuilt venv fails the full import-health probe, instead of printing a false-success summary
- The README-style recovery path was re-run directly:
  - `python3 scripts/bootstrap_verification_env.py --run-id local_verification_bootstrap_20260415b`
  - `./scripts/run_agents_smoke.sh`
  - result: healthy `.venv314` rebuild plus `18 passed`
- After that same rebuild, the other main wrapper lanes were also re-run and exited cleanly:
  - `./scripts/run_backend_api_smoke.sh`
  - `./scripts/run_meeting_pack_verify.sh`
  - `./scripts/run_escalation_judge_verify.sh`
- The runtime-readiness/self-test surface now points back to the same recovery path on backend import failure:
  - [runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)
  - missing `backend_entrypoint` dependencies still say to install requirements first
  - and now also point maintainers at `python3 scripts/bootstrap_verification_env.py --run-id local_verification_bootstrap` when local repo verification is failing before tests truly start

## Short Version

PaperPipe had a small real import-time problem and that patch is now landed.

The larger blocker is upstream of the repo: the current Python 3.13 runtime itself stalls on core
imports such as `select` and `subprocess`, so remaining `typer` / `fastapi` / backend import
stalls should be treated as interpreter health failures until that runtime is replaced.

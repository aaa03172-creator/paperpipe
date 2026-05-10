# Config Local-First Core Staging Prep (2026-03-23)

## Goal
Split a narrow config-runtime lane that promotes local-first defaults and formalizes ingest config loading without dragging profile snapshots or CLI workflow changes into the same commit.

## Included
- `/Users/jangseongjin/paperpipe/src/config.py`
- `/Users/jangseongjin/paperpipe/config.example.yaml`
- `/Users/jangseongjin/paperpipe/docs/reports/Config_Local_First_Core_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- `src/config.py` adds `IngestConfig`, uses `config_file_path(...)`, and flips the runtime default to local-first.
- `config.example.yaml` is the matching operator-facing template for that runtime shape.
- `config/profiles.yaml` is intentionally excluded because it is a data snapshot lane, not runtime config logic.
- `src/services/cli_workflows.py` is also excluded because it mixes timeout-policy adoption with ingest wiring.

## Verification Plan
In a temp worktree containing only this patch:
- `PAPERPIPE_CONFIG_PATH=.../config.example.yaml pytest -q tests/test_config_env_override.py tests/test_runtime_paths_research_dna.py tests/test_frontend_real_smoke_preflight.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
The default runtime config becomes local-first, ingest settings have an explicit typed config block, and config resolution follows the runtime path helper consistently.

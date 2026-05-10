# Provider Defaults Staging Prep

Date: 2026-03-27
Status: Ready for isolated packaging
Owner: Runtime maintainers

## Goal

Close the bounded provider/defaults lane that:
- adds explicit cloud embedding-model config support
- aligns the local default judge model with the current Ollama baseline
- locks both behaviors with config/provider tests

## Include

- `config.example.yaml`
- `src/config.py`
- `src/llm_provider.py`
- `tests/test_config_env_override.py`
- `tests/test_frontend_real_smoke_preflight.py`
- `tests/test_ollama_provider_timeout.py`
- `tests/test_openai_provider_embeddings.py`
- `docs/reports/Provider_Defaults_Staging_Prep_2026-03-27.md`

## Exclude

- `frontend/README.md`
- `docs/CLI_WORKFLOW_REFERENCE.md`
- `src/cli.py`
- profile/deep-read follow-up files

## Verification

Current worktree:
- `pytest -q tests/test_config_env_override.py tests/test_frontend_real_smoke_preflight.py tests/test_ollama_provider_timeout.py tests/test_openai_provider_embeddings.py`
- `python3 scripts/lint_docs.py`

Clean temp closure:
- apply staged bundle on top of `HEAD`
- run the same pytest set
- run `python3 scripts/lint_docs.py`

## Commit Message

`feat(config): close provider defaults lane`

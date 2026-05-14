# Provider Defaults Follow-up Staging Prep

Date: 2026-03-27
Status: Ready for isolated follow-up
Owner: Runtime maintainers

## Goal

Close the missed residual hunk from the provider-defaults lane: align the local default `judge` model with the committed Ollama fallback baseline.

## Include

- `src/config.py`
- `docs/reports/Provider_Defaults_Followup_Staging_Prep_2026-03-27.md`

## Verification

- `pytest -q tests/test_config_env_override.py tests/test_frontend_real_smoke_preflight.py tests/test_ollama_provider_timeout.py tests/test_openai_provider_embeddings.py`
- `python3 scripts/lint_docs.py`

## Commit Message

`fix(config): align local judge default`

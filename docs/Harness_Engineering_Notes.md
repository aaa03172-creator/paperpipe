# Harness Engineering Notes

Last checked: 2026-05-31

This note captures the development-side harness contract used by local Codex/CI work. It is additive guidance, not a runtime source of truth. The shared eval run metadata shape lives in `src/schemas/eval_harness.py`.

## Pytest markers

Pytest runs with `--strict-markers` so new marker names must be registered in `pyproject.toml`.

- `smoke`: fast local smoke coverage for changed developer workflow surfaces.
- `real_smoke`: opt-in checks that exercise real local services, files, or browser flows.
- `network`: opt-in checks that may touch external network services.
- `external_inference`: opt-in checks that may call external model providers.
- `slow`: longer-running checks that are normally excluded from tight edit loops.
- `goldset`: evaluation or regression checks backed by curated goldset fixtures.

## Eval run metadata

Eval harness run summaries should expose a small common `metadata` object so runs remain traceable across local smoke checks and CI artifacts:

- `schema_version`
- `harness`
- `run_id`
- `mode`
- `generated_at_utc`
- `payload_class`
- `provider`
- `model`
- `eval_id`
- `case_ids`
- `subset`

For deterministic local harnesses, `provider` should stay `deterministic`, `model` should stay `null`, and `payload_class` should stay `local_only`. Model-judged or external-inference evals must keep those fields explicit instead of relying on surrounding logs.

## Goldset manifest identity

Tracked JSON manifests under `goldset/manifests/` should expose identity fields directly:

- top-level `eval_id`, matching the manifest filename stem
- top-level `subset`, such as `pilot`, `candidate`, `regression`, `eval`, or `oracle`
- per-row `case_id` on each `documents[]`, `runs[]`, or `items[]` entry

Prefer stable existing identifiers for `case_id`: `run_key`, then `document_id`, then `paper_id`. Do not use generated timestamps for case IDs.

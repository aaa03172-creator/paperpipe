# Docling Tool Intake Decision

Status: bounded fit decision  
Date: 2026-03-23  
Lane: `tool-intake-review`

## Current Bottleneck

PaperPipe needs a safer way to evaluate alternate PDF parsing paths for ingestion without replacing the current runtime parser stack.

The concrete bottleneck is not “we have no parser”.
It is:
- we need bounded evidence for whether an alternate parser improves text and table extraction on real local PDFs
- we must avoid parser replacement as a first move

Current owner path:
- ingest runtime: [ingest_agent.py](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py)
- parser backends: [parser_backends.py](/Users/jangseongjin/paperpipe/src/ingest/parser_backends.py)
- bounded eval harness: [compare_ingest_backends.py](/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py)
- bounded fixture manifest: [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)

## Classification

`defer`

Interpretation:
- not ready for runtime adoption
- acceptable only as a bounded sidecar pilot and reference path for parser evaluation

Why not `direct candidate`:
- one meaningful table loss remains on the bounded fixture set
- the remaining loss appears tied to docling representation, not just a local regex quirk
- current evidence is too small and too mixed for promotion

Why not `reference only`:
- docling is not merely a source of ideas now; it is installed, importable, and evaluated in this environment
- there is enough concrete runtime-fit evidence to keep it as a live pilot candidate, but not enough to promote it

## Safest Insertion Point

Keep docling only in these insertion points for now:
- sidecar evaluation via [compare_ingest_backends.py](/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py)
- optional parser backend path in [parser_backends.py](/Users/jangseongjin/paperpipe/src/ingest/parser_backends.py)
- local optional dependency under `pyproject.toml` extra `parser-eval`

Do not make it:
- default ingest backend
- hidden fallback that changes runtime behavior automatically
- a reason to rewrite table extraction ownership

## Do Not Rewrite These Parts

- [ingest_agent.py](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py)
- [parser_backends.py](/Users/jangseongjin/paperpipe/src/ingest/parser_backends.py)
- [db_utils.py](/Users/jangseongjin/paperpipe/src/db_utils.py)
- current FastAPI API surface
- current Pydantic artifact contracts under [src/schemas](/Users/jangseongjin/paperpipe/src/schemas)
- note/export paths and idempotent write behavior

## Main Risks

- meaningful table loss still exists on `Hansson 2023`
- even after switching the optional docling backend to structured `TableItem` extraction, `Hansson 2023` still exposes only pages 2 and 8 as tables
- docling export appears to flatten at least one figure-like clinical decision table into narrative text, making local table recovery harder
- installing docling changed active environment packages such as `transformers` and `huggingface_hub`, so dependency drift needs attention
- raw table count alone is too noisy; promotion depends on richer table-fidelity criteria

## Evidence Summary

Bounded manifest-backed runs:
- readiness failure: [docling_pilot_manifest_20260323/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323/metrics.json)
- real compare after install: [docling_pilot_manifest_20260323_r3/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r3/metrics.json)
- DOI parity restored: [docling_pilot_manifest_20260323_r4/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r4/metrics.json)
- meaningful-table metric verdict: [docling_pilot_manifest_20260323_r5/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r5/metrics.json)
- structured-table backend rerun: [docling_pilot_manifest_20260323_r6/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r6/metrics.json)

Current bounded result:
- baseline success: `6 / 6`
- candidate success: `6 / 6`
- DOI parity: restored to `6 / 6`
- raw table loss docs: `2`
- meaningful table loss docs: `1`

Remaining blocker:
- `Hansson 2023` page-4 clinical-stage decision table
- `r6` confirms this is still missing even when docling structured tables are consumed directly rather than via markdown parsing

## Smallest Pilot

Allowed next pilot:
1. keep using [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)
2. investigate only the `Hansson 2023` missing table case
3. if a bounded local recovery heuristic exists, test it only behind the harness
4. rerun the same manifest and compare `meaningful_table_loss_docs`

Stop conditions:
- if `Hansson 2023` meaningful loss remains, do not promote docling into runtime default or implicit fallback
- if fixing that case requires broad parser replacement or contract drift, stop and keep docling as deferred pilot only

## Decision

As of 2026-03-23:
- Docling is a bounded parser pilot candidate
- Docling is deferred for runtime adoption
- PaperPipe should keep the current parser stack as the runtime owner

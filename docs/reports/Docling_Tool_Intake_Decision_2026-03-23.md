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

`direct candidate`

Interpretation:
- direct candidate for a behind-flag optional parser pilot
- not ready for default runtime adoption

Why `direct candidate` now:
- the bounded manifest passes with the current optional backend path
- the remaining Hansson blocker was removed by a page-aware meaningful-table rescue, not a broad parser rewrite
- the insertion point stays narrow: optional backend plus sidecar evaluation only

Why not `reference only`:
- docling is not merely a source of ideas now; it is installed, importable, evaluated, and partially integrated into the optional backend path
- the current fit is operational, not just conceptual

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

- pure docling still misses the `Hansson 2023` page-4 decision table; the current pass depends on a page-aware fallback merge from `fitz/pdfplumber`
- fallback frequency could grow on a larger fixture set, so current evidence is still narrow
- installing docling changed active environment packages such as `transformers` and `huggingface_hub`, so dependency drift needs attention
- raw table count alone is too noisy; promotion depends on richer table-fidelity criteria

## Evidence Summary

Durable manifest-backed runs:
- page-aware fallback merge pass: [docling_pilot_manifest_20260323_r8/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/metrics.json)
- section-aware rerun after docling text fix: [docling_pilot_manifest_20260323_r9/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/metrics.json)

Interpretation:
- `r8` is the first durable pass with meaningful fallback metadata recorded
- `r9` keeps that pass while restoring page-aware text sections
- older local reruns informed the investigation but are not required to understand the current bounded decision

Current bounded result:
- baseline success: `6 / 6`
- candidate success: `6 / 6`
- DOI parity: restored to `6 / 6`
- raw table loss docs: `1`
- meaningful table loss docs: `0`

Remaining caveat:
- `Hansson 2023` page-4 clinical-stage decision table is still absent from pure docling output
- `r8` passes because the optional backend explicitly merges that page from `fitz/pdfplumber`, and the eval row now records `table_fallback_used=true` and `table_fallback_pages=[4]`
- `r9` keeps that pass while also restoring page-aware text sections, so the current behind-flag pilot no longer collapses documents to a single section

## Smallest Pilot

Allowed next pilot:
1. keep using [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)
2. keep docling behind a flag as an optional hybrid backend only
3. expand the fixture set and watch how often `table_fallback_used` fires
4. rerun the same manifest plus any new fixtures and compare both `meaningful_table_loss_docs` and fallback frequency

Stop conditions:
- if fallback pages start appearing frequently or on safety-critical table documents, do not promote docling into runtime default or implicit fallback
- if keeping the pass rate requires broad parser replacement or contract drift, stop and keep docling behind the flag only

## Decision

As of 2026-03-23:
- Docling is a direct candidate for a behind-flag optional parser pilot
- Docling is not ready for default runtime adoption
- PaperPipe should keep the current parser stack as the runtime owner

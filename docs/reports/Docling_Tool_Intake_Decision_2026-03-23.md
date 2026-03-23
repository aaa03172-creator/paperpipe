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
- expanded fixture manifest: [ingest_backend_pilot_expanded_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_expanded_20260323.json)

## Classification

`direct candidate`

Interpretation:
- direct candidate for a behind-flag optional parser pilot
- not ready for default runtime adoption

Why `direct candidate` now:
- the bounded manifest passes with the current optional backend path
- the remaining Hansson blocker was removed by a page-aware meaningful-table rescue, not a broad parser rewrite
- the insertion point stays narrow: optional backend plus sidecar evaluation only
- expanded follow-up shows low fallback frequency (`1 / 18`) and no meaningful page-level table loss

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
- same-page multi-table merge cases (`Benedict 2020`, `Dubois 2021`) still fail the current count-based meaningful-table gate on the expanded fixture set
- installing docling changed active environment packages such as `transformers` and `huggingface_hub`, so dependency drift needs attention
- raw table count alone is too noisy; promotion depends on richer table-fidelity criteria

## Evidence Summary

Bounded manifest-backed runs:
- readiness failure: [docling_pilot_manifest_20260323/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323/metrics.json)
- real compare after install: [docling_pilot_manifest_20260323_r3/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r3/metrics.json)
- DOI parity restored: [docling_pilot_manifest_20260323_r4/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r4/metrics.json)
- meaningful-table metric verdict: [docling_pilot_manifest_20260323_r5/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r5/metrics.json)
- structured-table backend rerun: [docling_pilot_manifest_20260323_r6/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r6/metrics.json)
- page-aware fallback merge pass: [docling_pilot_manifest_20260323_r8/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r8/metrics.json)
- section-aware rerun after docling text fix: [docling_pilot_manifest_20260323_r9/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/metrics.json)
- expanded fixture follow-up: [docling_pilot_manifest_expanded_20260323_r10/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r10/metrics.json)

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

Expanded follow-up result:
- candidate success: `18 / 18`
- docs with table fallback: `1 / 18`
- meaningful table loss docs: `2`
- meaningful page-loss docs: `0`
- the two expanded blockers (`Benedict 2020`, `Dubois 2021`) look like same-page merged-table cases rather than missing-page failures

## Smallest Pilot

Allowed next pilot:
1. keep using [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)
2. keep docling behind a flag as an optional hybrid backend only
3. use the expanded fixture set to watch how often `table_fallback_used` fires and where same-page merged tables appear
4. rerun the same manifests plus any new fixtures and compare `meaningful_table_loss_docs`, fallback frequency, and page-level table coverage

Stop conditions:
- if fallback pages start appearing frequently or on safety-critical table documents, do not promote docling into runtime default or implicit fallback
- if keeping the pass rate requires broad parser replacement or contract drift, stop and keep docling behind the flag only
- if same-page merged tables prove semantically lossy after content-level inspection, do not promote beyond bounded optional pilot

## Decision

As of 2026-03-23:
- Docling is a direct candidate for a behind-flag optional parser pilot
- Docling is not ready for default runtime adoption
- PaperPipe should keep the current parser stack as the runtime owner

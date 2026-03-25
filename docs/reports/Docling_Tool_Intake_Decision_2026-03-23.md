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
- broad second expanded fixture manifest: [ingest_backend_pilot_expanded_broad_20260324.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_expanded_broad_20260324.json)

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
- optional per-job FastAPI/job override via [main.py](/Users/jangseongjin/paperpipe/backend/main.py), [queue.py](/Users/jangseongjin/paperpipe/src/jobs/queue.py), and [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- local optional dependency under `pyproject.toml` extra `parser-eval`

Guardrail:
- per-job `parser_backend="docling"` is still gated by `config.ingest.enable_docling`; when the flag is off, the effective runtime backend remains `fitz_pdfplumber`
- the current caller-side pilot entry point is intentionally narrow: [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx) honors `?parser_backend=docling` on the workbench route instead of exposing a general-purpose selector
- operator-facing status now separates `requested_parser_backend` from effective `parser_backend`; this avoids reading a requested pilot backend as if it had definitely executed

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
- fallback frequency could still grow on a larger fixture set beyond the current broad rerun, so current evidence is stronger but still bounded
- section-quality audit on the expanded set surfaces three low page-text-ratio review docs, and the clarified rerun splits doc-vs-page counts while classifying them as layout-heavy (`table_heavy_page`, `table_and_figure_heavy_page`, `figure_heavy_page`) with no unclassified text-loss bucket
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
- expanded fixture rerun with same-page merge classification: [docling_pilot_manifest_expanded_20260323_r11/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260323_r11/metrics.json)
- same-page merge semantic audit: [docling_same_page_merge_audit_20260323_r12/summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_20260323_r12/summary.json)
- section-quality audit: [docling_section_quality_audit_20260324_r15/summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_20260324_r15/summary.json)
- broad second expanded compare: [docling_pilot_manifest_expanded_broad_20260324_r16/metrics.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260324_r16/metrics.json)
- broad second expanded merge audit: [docling_same_page_merge_audit_broad_20260324_r17/summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_broad_20260324_r17/summary.json)
- broad second expanded section audit: [docling_section_quality_audit_broad_20260324_r18/summary.json](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_broad_20260324_r18/summary.json)

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
- meaningful table loss docs: `0`
- meaningful page-loss docs: `0`
- same-page merge docs: `2`
- section audit missing substantive page docs: `0`
- section audit low page-text-ratio docs: `3`
- section audit low page-text-ratio doc bucket counts: `table_heavy_page=1`, `table_and_figure_heavy_page=1`, `figure_heavy_page=1`
- section audit low page-text-ratio page bucket counts: `table_heavy_page=1`, `table_and_figure_heavy_page=1`, `figure_heavy_page=4`
- section audit low page-text-ratio unclassified docs: `0`
- section audit section collapse docs: `0`
- the two expanded blockers (`Benedict 2020`, `Dubois 2021`) now live in `same_page_merge_docs` rather than `meaningful_table_loss_docs`
- follow-up merge audit shows `semantic_merge_preserved_count = 2 / 2` and `content_gap_count = 0`
- section-quality audit shows the remaining text-side review bucket is confined to layout-heavy pages, not broad page loss or one-section collapse

Broad second expanded result:
- candidate success: `12 / 12`
- docs with table fallback: `0`
- meaningful table loss docs: `0`
- same-page merge docs: `0`
- low text ratio docs: `0`
- section audit page coverage preserved count: `12 / 12`
- section audit low page-text-ratio docs: `0`
- section audit unclassified docs: `0`
- the second broad rerun adds no new review bucket and no new fallback dependency on this disjoint sample

## Smallest Pilot

Allowed next pilot:
1. keep using [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)
2. keep docling behind a flag as an optional hybrid backend only
3. if a bounded runtime pilot is needed, request it per job through `POST /jobs/deepread` with `parser_backend`
4. use the expanded fixture set to watch how often `table_fallback_used` fires and where same-page merged tables appear
5. rerun the same manifests plus any new fixtures and compare `meaningful_table_loss_docs`, `same_page_merge_docs`, fallback frequency, and section-quality audit review buckets
6. if `low_page_text_ratio_unclassified_docs_count` becomes non-zero, treat that as a stop signal until the affected pages are inspected
7. if broader reruns keep passing without new fallback or unclassified review buckets, keep docling in the behind-flag hybrid lane but do not promote it to default without an explicit architecture decision

Stop conditions:
- if fallback pages start appearing frequently or on safety-critical table documents, do not promote docling into runtime default or implicit fallback
- if keeping the pass rate requires broad parser replacement or contract drift, stop and keep docling behind the flag only
- if same-page merged tables prove semantically lossy after content-level inspection, do not promote beyond bounded optional pilot

## Decision

As of 2026-03-23:
- Docling is a direct candidate for a behind-flag optional parser pilot
- Docling is not ready for default runtime adoption
- PaperPipe should keep the current parser stack as the runtime owner

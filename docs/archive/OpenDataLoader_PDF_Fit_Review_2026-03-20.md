# OpenDataLoader PDF Fit Review

Status: Historical fit review  
Date: 2026-03-20  
Owner: Repository maintainers  
Canonical parent: `docs/reports/Current_Baseline_Recheck_2026-03-18.md`

## 1. Executive Summary

`OpenDataLoader PDF` fits PaperPipe only as a bounded `parser candidate` / `layout-aware fallback candidate`.

It does **not** fit as:

- a new core engine
- a replacement for the current ingest pipeline
- a retrieval / ranking / memory / judge / RAG primitive

Current-system-safe conclusion:

- keep the current `fitz_pdfplumber` baseline parser
- keep the current OCR fallback path
- if reopened, evaluate `OpenDataLoader PDF` only on hard-document subsets
- store outputs as sidecar artifacts, not as a replacement canonical runtime schema

Recommendation:

- `limited pilot only`
- `deterministic local mode first`
- `hybrid mode later, only if the hard-document subset justifies it`

## 2. Why This Is A Parser Candidate, Not A Core Engine

PaperPipe already has a bounded parser slot and parser/runtime guardrails:

- `src/config.py` exposes `ingest.parser_backend` and OCR/table fallback options
- `src/agents/ingest_agent.py` wires parser choice and fallback behavior into ingest
- `src/ingest/parser_backends.py` defines the `ParserBackend` abstraction
- `backend/services/job_runner.py` records parser backend and ingest options into bootstrap/run metadata

This means the right interpretation is:

- parser candidate
- parser-adjacent hard-document helper
- optional layout-aware preprocessor

It is not:

- a new runtime center
- a replacement artifact model
- a reason to recenter the system around parser-centric architecture

## 3. Best-Fit Use Cases In PaperPipe

Highest-value document types:

- multi-column biomedical papers
- table-heavy PDFs
- formula-heavy scientific PDFs
- scanned or image-based PDFs
- text-poor / layout-broken PDFs
- tagged PDFs where structure-tree extraction may outperform heuristic reading order

Why the output is potentially useful:

- Markdown can help bounded chunking and human inspection.
- JSON with semantic element types and bounding boxes can help page-block provenance.
- Table/caption/formula/image structure can support later extractor or grounding improvements without changing the current default reader path.
- Annotated or inspectable outputs are useful for HITL debugging.

## 4. What It Should NOT Replace

Do not use it to replace:

- the current default parser baseline
- the current `ocrmypdf + tesseract` fallback lane
- `DocumentArtifactV2` as the current parser-facing canonical contract
- reader/extraction/grounding logic
- RAG/chat/note/memory architecture

Reason:

- OpenDataLoader PDF improves document parsing, not biomedical reasoning.
- Better parser output does not automatically solve screening, extraction quality, evidence adjudication, or answer quality.
- The current runtime still depends on the existing ingest contract and bridge path; replacing that surface would widen scope far beyond a parser pilot.

## 5. Operational Complexity And Constraints

Confirmed upstream operational facts:

- Java `11+` and Python `3.10+` are required.
- The official Python path warns that each `convert()` spawns a JVM process.
- Upstream explicitly recommends batching multiple files in one call because repeated single-document calls are slow.
- Base local mode runs without GPU or cloud services.
- Hybrid mode is optional and defaults to `off`.
- Hybrid mode needs extra dependencies and a backend server, with added RAM/disk/runtime cost.

Practical interpretation for PaperPipe:

- deterministic local mode is realistic for a bounded pilot
- hybrid mode is **not** a default candidate
- batch-first orchestration is required if this is evaluated seriously
- single-file on-demand invocation inside the hot ingest path is likely the wrong shape

## 6. Safest Integration Architecture

Use this exact strategy if the parser lane is reopened:

1. keep the current parser baseline
2. add or reuse a quality gate for hard-document detection
3. run OpenDataLoader PDF only for those selected documents
4. persist `markdown/json` as sidecar artifacts
5. keep downstream extractor / reader / RAG structure unchanged by default

Best insertion point:

- `document ingestion`
- after baseline parse and quality assessment
- before any optional bounded normalization into downstream helper formats

Good roles:

- `parser candidate`
- `layout-aware fallback`
- `table-heavy PDF specialist`
- `hard-document evaluation backend`

Bad roles:

- canonical storage replacement
- runtime-wide schema replacement
- memory or RAG system center

## 7. Sidecar Schema Suggestion

Prefer raw sidecars plus optional normalized summaries.

Recommended raw sidecar fields:

- `parser_name`
- `parser_mode`
- `source_pdf_path`
- `markdown`
- `layout_json`
- `raw_text`
- `page_blocks`
- `semantic_type`
- `element_id`
- `page_index`
- `bbox`
- `quality_flags`
- `fallback_reason`
- `provenance`

Recommended normalized helper view:

- `page_blocks[].text`
- `page_blocks[].semantic_type`
- `page_blocks[].page_index`
- `page_blocks[].bbox_pdf_raw`
- `page_blocks[].source_element_id`

Important constraint:

- keep upstream raw bbox values separate from any canonical bbox normalization
- do not replace `DocumentArtifactV2` directly with upstream JSON
- if normalization is attempted later, validate bbox coordinate semantics first

## 8. Low-Risk Pilot Plan

Pilot corpus:

- 20–30 hard-case PDFs only
- scanned / image-based
- table-heavy
- formula-heavy
- low-text-confidence
- current `NO_TABLE_FOUND` / `OCR_LOW_CONF` / `text-poor` style failures

Compare:

- current parser text coverage
- usable table recovery
- heading/section recovery
- provenance usefulness for later grounding
- batch runtime cost
- operator inspectability

Success criteria:

- repeatable quality gain on the hard-document subset
- no default-path regression
- rollback remains trivial because outputs are sidecars only
- no downstream contract rewrite is needed

Rollback shape:

- feature-flagged
- batch-only
- sidecar-only
- fail-safe back to current parser

## 9. Recommendation

Current recommendation: `limited pilot only`.

Safe order:

1. deterministic local mode only
2. hard-document subset only
3. sidecar artifact only
4. hybrid mode only if the local pilot shows a clear hard-case gap that justifies more operational complexity

This keeps the tool in the right place: an optional parser-side capability, not a new system center.

For the bounded experiment shape, use:

- `docs/archive/OpenDataLoader_PDF_Hard_Doc_Pilot_Spec_2026-03-20.md`

## 10. Do Not Rewrite These Parts

- `src/ingest/parser_backends.py` default parser contract
- `src/agents/ingest_agent.py` default ingest flow
- `docs/ocr_fallback.md` OCR fallback semantics
- `src/contracts/document_artifact_v2.py` canonical parser-facing contract
- `backend/services/job_runner.py` ingest/index/read/verify orchestration
- existing reader / extraction / grounding / RAG / note layers

## 11. Safest Next 3 Experiments

1. Build a hard-document subset manifest and compare `fitz_pdfplumber` against OpenDataLoader local deterministic output in batch mode only.
2. Save OpenDataLoader outputs as `markdown + layout_json` sidecars and judge whether they improve human inspection and provenance usefulness before touching any downstream consumer.
3. Keep hybrid mode in a separate experiment and enable it only for complex-table or OCR-heavy subsets if the local deterministic pilot leaves a measurable gap.

## Sources

- [OpenDataLoader PDF GitHub](https://github.com/opendataloader-project/opendataloader-pdf)
- [FAQ](https://opendataloader.org/docs/faq)
- [Quick Start with Python](https://www.opendataloader.org/docs/quick-start-python)
- [JSON Schema](https://www.opendataloader.org/docs/json-schema)
- [CLI Options Reference](https://opendataloader.org/docs/cli-options-reference)
- [Hybrid Mode](https://opendataloader.org/docs/hybrid-mode)

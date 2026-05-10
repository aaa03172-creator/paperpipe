## Extractor/parser component: Import PDF metadata sniffing

Purpose:
Derive title and DOI during manual import.
Input:
Stored PDF path.
Output:
Imported note title and optional DOI.
Callers:
`import_pdf_payload`.
Downstream consumers:
Paper note, `papers` row, PDF URL.
Expected behavior:
Reasonable title/DOI where available; safe fallback otherwise.
Actual behavior:
Reads PDF metadata title and scans first pages for DOI; falls back to filename.
Important edge cases:
Malformed PDF after `%PDF-` header, poor embedded title, DOI absent after first 16 pages.
Known limitations:
No deep parse validation at import.
Failure handling:
Exceptions are swallowed; fallback values used.
Tests found:
`tests/test_paper_notes_api.py`.
Gaps or risks:
Minimal `%PDF-` files can pass import validation.
Conclusion: Probably working
Evidence:
`backend/routers/paper_notes.py:757`, `backend/routers/paper_notes.py:808`, `backend/routers/paper_notes.py:939`.

## Extractor/parser component: Fitz/pdfplumber backend

Purpose:
Default PDF parser for text, metadata, page blocks, and tables.
Input:
PDF path.
Output:
`PaperMetadata`, page-level sections, tables, `DocumentArtifactV2`.
Callers:
`IngestAgent`.
Downstream consumers:
Indexer, Reader, grounding, sidecars.
Expected behavior:
Extract realistic academic paper text, semantic sections, metadata, tables, provenance.
Actual behavior:
Uses PDF metadata for title/authors/year/journal, emits one section per page, extracts text via PyMuPDF, tables via pdfplumber with generic captions.
Important edge cases:
Multi-column reading order, missing metadata, scanned papers, malformed PDFs, table captions/provenance, references.
Known limitations:
No semantic section segmentation; no citation/reference model; table captions are synthetic.
Failure handling:
Exceptions return `None` at IngestAgent level.
Tests found:
`tests/test_ingest_parser_backend.py`.
Gaps or risks:
Reader priority section logic expects semantic names that this backend does not provide.
Conclusion: Partially working
Evidence:
`src/ingest/parser_backends.py:210`, `src/ingest/parser_backends.py:228`, `src/ingest/parser_backends.py:260`, `src/ingest/parser_backends.py:284`.

## Extractor/parser component: Docling backend

Purpose:
Optional parser backend with Docling-derived text/tables.
Input:
PDF path.
Output:
Same artifact contract as default parser.
Callers:
`create_parser_backend`; enabled by config/override and `enable_docling`.
Downstream consumers:
Same as default parser.
Expected behavior:
Improve layout/table extraction and preserve provenance when available.
Actual behavior:
Uses Docling when import succeeds; fallback behavior exists.
Important edge cases:
Docling unavailable, missing page text, markdown-table fallback provenance.
Known limitations:
Markdown-table fallback assigns tables to page 1 when structured provenance is unavailable.
Failure handling:
Unknown/import failure falls back to fitz/pdfplumber.
Tests found:
`tests/test_ingest_parser_backend.py`, `tests/test_job_runner_ingest_backend.py`.
Gaps or risks:
Runtime Docling quality not verified against real hard PDFs in this pass.
Conclusion: Probably working
Evidence:
`src/ingest/parser_backends.py:417`, `src/ingest/parser_backends.py:981`, `src/ingest/parser_backends.py:1044`, `src/ingest/parser_backends.py:1064`.

## Extractor/parser component: OCR fallback

Purpose:
Recover text for scanned/image-only PDFs when enabled.
Input:
PDF path and OCR settings.
Output:
OCR PDF path and OCR metadata.
Callers:
`IngestAgent.process`.
Downstream consumers:
Parser backend re-runs on OCR output.
Expected behavior:
Detect low text and run OCR safely.
Actual behavior:
Detects total extracted text below threshold; calls `ocrmypdf` if installed.
Important edge cases:
OCR tool missing, non-English papers, low-confidence OCR, huge scanned PDFs.
Known limitations:
Default depends on config; real OCR coverage now exists for a generated image-only English fixture, but non-English and huge scanned PDFs remain weak.
Failure handling:
Returns metadata with `ocr_applied=False` and error.
Tests found:
`tests/test_ocr_fallback.py`.
Gaps or risks:
Tests now include real OCRmyPDF/Tesseract round trip when those tools are installed; the test skips cleanly when they are unavailable.
Conclusion: Probably working
Evidence:
`src/ingest/ocr_fallback.py:32`, `src/ingest/ocr_fallback.py:53`, `src/agents/ingest_agent.py:172`.

## Extractor/parser component: Cloud table fallback

Purpose:
Optional pass3 table recovery for selected pages.
Input:
PDF path and page budget.
Output:
`TableExtractionResult` with failure taxonomy.
Callers:
`IngestAgent._extract_tables_pass3_cloud`.
Downstream consumers:
Document artifact tables, visual evidence, reader.
Expected behavior:
Use external inference only with explicit payload governance and provenance.
Actual behavior:
Selects table-like pages and sends page text to OpenAI-compatible chat completions if enabled and client exists.
Important edge cases:
Privacy preflight disabled/unattached, no API key, bad JSON, low-quality tables.
Known limitations:
External payload is selected page text, not minimized beyond page selection.
Failure handling:
Failure taxonomy records `NO_API`, low accuracy, privacy blocked.
Tests found:
`tests/test_ingest_parser_backend.py`.
Gaps or risks:
Direct use of `CloudTableFallbackExtractor` can bypass runner-attached privacy callback.
Conclusion: Needs verification
Evidence:
`src/ingest/cloud_table_fallback.py:63`, `src/ingest/cloud_table_fallback.py:110`, `src/ingest/cloud_table_fallback.py:205`.

## Extractor/parser component: Reader claim extraction and grounding

Purpose:
Extract claims/evidence and ground evidence to chunks/pages/bboxes.
Input:
`DocumentArtifactV2`.
Output:
`ClaimSet`, `claimset.resolved.json`, evaluation/coverage/evidence sidecars.
Callers:
`run_deepread_job`.
Downstream consumers:
Paper Notes, synthesis, comparison, meeting packs.
Expected behavior:
Produce evidence-backed claims with traceable spans.
Actual behavior:
Attempts LLM JSON extraction; falls back to best/heuristic claims; grounding matches quotes/raw text against chunks and page blocks.
Important edge cases:
LLM timeout, invalid JSON, empty claims, chunk collisions, ambiguous quote matches.
Known limitations:
Quality depends on parser section names and chunk IDs.
Failure handling:
Timeout sidecar and failure metadata; empty claimsets mark not-ready and enqueue follow-up if possible.
Tests found:
`tests/test_citation_grounding.py`, `tests/test_job_runner_clinical_extraction.py`.
Gaps or risks:
Heuristic fallback may generate claims when true extraction failed; readiness flags must be honored downstream.
Conclusion: Probably working
Evidence:
`src/agents/reader_agent.py:138`, `src/agents/reader_agent.py:293`, `src/services/citation_grounding.py:30`, `backend/services/job_runner.py:1578`.

## Extractor/parser component: Figure and visual evidence sidecars

Purpose:
Extract figure captions and compile visual evidence ledger.
Input:
Document artifact and resolved claimset.
Output:
`figure_captions.json`, `visual_evidence_ledger.json`.
Callers:
`run_deepread_job`.
Downstream consumers:
Paper Notes/Deep Read markdown and review artifacts.
Expected behavior:
Trace figure/table evidence clearly.
Actual behavior:
Captions are regex/text based; figures are marked caption-only.
Important edge cases:
Multi-panel figures, image-only figures, captions split across pages, visual measurements.
Known limitations:
No image crop, no figure bbox/panel extraction.
Failure handling:
Sidecar write failure is non-fatal.
Tests found:
`tests/test_figure_caption_sidecar.py`.
Gaps or risks:
Visual evidence is not full figure extraction.
Conclusion: Partially working
Evidence:
`src/services/figure_caption_sidecar.py:12`, `src/services/figure_caption_sidecar.py:18`, `src/services/visual_evidence_ledger.py:76`.

# OCR Fallback (PR#3)

## Goal
- Handle scanned/partial-scanned PDFs by adding an OCR text layer before ingest.
- Keep fail-safe behavior: no crash, never overwrite original.

## Implementation
- Module: `src/ingest/ocr_fallback.py`
  - `detect_need_ocr(pdf_path, min_text_chars=200) -> bool`
  - `run_ocr(pdf_in, pdf_out, lang="eng", deskew=True) -> dict`
  - `build_ocr_cache_path(pdf_path, cache_dir, lang) -> Path`
- Integration:
  - `IngestAgent.process(..., enable_ocr_fallback=False, ocr_lang="eng", ocr_min_text_chars=200)`
  - If enabled and OCR needed:
    - OCR output cached at `storage/ocr_cache/<hash>.pdf`
    - Ingest runs on OCR output if available.
  - Original PDF is never overwritten.

## Metadata Recording
- Recorded on `PaperMetadata`:
  - `ocr_applied`
  - `ocr_engine`
  - `ocr_version`
  - `ocr_lang`
  - `ocr_error`
  - `ocr_output_path`

## Dependencies
- `ocrmypdf`
- `tesseract` (+ language packs)

## Behavior on Failure
- If OCR is unavailable/fails:
  - `ocr_applied = false`
  - `ocr_error` contains reason
  - ingest continues with original PDF path

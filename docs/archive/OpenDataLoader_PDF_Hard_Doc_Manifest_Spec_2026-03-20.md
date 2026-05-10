# OpenDataLoader PDF Hard-Doc Manifest Spec

Status: Historical bounded manifest spec  
Date: 2026-03-20  
Owner: Repository maintainers  
Canonical parent: `docs/archive/OpenDataLoader_PDF_Hard_Doc_Pilot_Spec_2026-03-20.md`

## 1. Purpose

Define the frozen input manifest for any future `OpenDataLoader PDF` hard-document pilot.

This spec exists to prevent pilot drift:

- no changing the corpus mid-run
- no opportunistic cherry-picking after seeing outputs
- no silent expansion from parser-side evaluation into broader product claims

## 2. Non-Goals

This manifest spec does **not**:

- approve a pilot by itself
- change the default parser path
- define output schema changes
- define downstream extraction behavior
- define success metrics beyond manifest selection hygiene

## 3. Manifest Role

The manifest is the frozen list of documents used for the bounded parser comparison.

It should be created **before** running the candidate parser and should remain unchanged for the life of that pilot batch.

Required behaviors:

- freeze once selected
- version by date or batch id
- keep paper identity and source path explicit
- record why each file belongs in the hard-doc subset

## 4. Target Corpus Size

Recommended size:

- `20–30` PDFs for the first bounded pilot

Avoid:

- fewer than `10` PDFs unless the goal is only smoke validation
- more than `30` PDFs for the first pilot, because review cost and interpretation drift rise quickly

## 5. Inclusion Criteria

Each manifest item should satisfy at least one strong hard-doc reason:

- `scanned_pdf`
- `image_based_pdf`
- `table_heavy_pdf`
- `formula_heavy_pdf`
- `text_poor_pdf`
- `layout_broken_pdf`
- `tagged_pdf_candidate`

Preferred repo-grounded signals:

- `table_failure_taxonomy` contains `NO_TABLE_FOUND`
- `table_failure_taxonomy` contains `OCR_LOW_CONF`
- OCR fallback was applied but output still looks weak
- extracted text length is abnormally low
- human review notes indicate table/layout loss

## 6. Exclusion Criteria

Do not include:

- ordinary born-digital PDFs with acceptable baseline extraction
- documents chosen only because they are famous or easy to inspect
- documents with missing or unstable source paths
- documents whose baseline outputs cannot be reproduced
- documents added after candidate outputs were already inspected

## 7. Required Fields

Each manifest row should include:

- `manifest_batch_id`
- `paper_id`
- `source_pdf_path`
- `source_pdf_sha256`
- `subset_reason`
- `baseline_parser_backend`
- `ocr_applied`
- `table_failure_taxonomy`
- `text_len_baseline`
- `page_count`
- `notes`

Recommended additional fields:

- `doi`
- `title`
- `journal`
- `year`
- `has_tables_baseline`
- `has_formula_signals`
- `has_scanned_pages_signal`
- `selected_by`
- `selected_at`

## 8. Allowed Value Shapes

Suggested normalized values:

- `subset_reason`: one of the bounded hard-doc reasons listed above
- `baseline_parser_backend`: current parser name, usually `fitz_pdfplumber`
- `ocr_applied`: `true` or `false`
- `table_failure_taxonomy`: list of known taxonomy labels already used by the current runtime

Notes:

- `subset_reason` should remain conservative and human-readable
- if multiple reasons apply, either keep a primary reason plus `notes`, or add `subset_reasons[]`
- avoid inventing fuzzy labels during the first pilot

## 9. Freeze Rules

Once the manifest is accepted for a pilot batch:

- do not add new PDFs
- do not remove PDFs because the candidate parser performed poorly
- do not relabel subset reasons mid-run
- do not swap source files without creating a new manifest version

If any of those changes are necessary, create a new batch id.

## 10. Review Rules

Before the pilot starts, check:

1. every `source_pdf_path` exists and is stable
2. every row has a justified hard-doc reason
3. baseline outputs are available for all rows
4. the batch is diverse enough to avoid overfitting to one failure mode

Recommended diversity guard:

- do not let any single subtype dominate the first batch unless that subtype is the explicit pilot goal

## 11. Storage Shape

Keep the manifest outside canonical runtime truth.

Safe locations:

- dated archive-side experiment note
- dated report attachment
- evaluation harness input file

Unsafe use:

- treating the manifest as a product runtime source of truth
- wiring it into normal ingest defaults

## 12. Example Row Shape

```json
{
  "manifest_batch_id": "opendataloader_harddoc_20260320_a",
  "paper_id": "doi:10.1016/S1474-4422(08)70259-X",
  "source_pdf_path": "storage/pdfs/lancet_review.pdf",
  "source_pdf_sha256": "abc123...",
  "subset_reason": "table_heavy_pdf",
  "baseline_parser_backend": "fitz_pdfplumber",
  "ocr_applied": false,
  "table_failure_taxonomy": ["NO_TABLE_FOUND"],
  "text_len_baseline": 4821,
  "page_count": 12,
  "notes": "Baseline text is usable but tables are missing."
}
```

## 13. Stop Conditions

Stop manifest preparation if:

- the subset cannot be defined from repo-grounded signals
- documents are being chosen by intuition alone
- source paths are unstable
- reviewers are trying to optimize the set around the candidate parser before the run

## 14. Do Not Rewrite These Parts

- current parser defaults
- current OCR fallback path
- canonical runtime artifact schema
- downstream reader / extraction / grounding / RAG behavior

## 15. Safest Next 3 Experiments

1. Draft a small candidate manifest from existing parser/OCR failure signals only, before looking at any OpenDataLoader outputs.
2. Validate that every manifest row has a reproducible baseline artifact and stable PDF path.
3. Freeze the first manifest version and use it unchanged for the bounded parser comparison batch.

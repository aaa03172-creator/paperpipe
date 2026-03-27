# OpenDataLoader Sidecar Inspection

Status: bounded inspection report  
Date: 2026-03-27  
Lane: `opendataloader-sidecar-eval`

## Purpose

Inspect the first local `OpenDataLoader PDF` sidecar run against the current tracked parser evidence on the same frozen 4-document hard-doc subset.

Scope boundary:
- use the existing tracked baseline/docling eval outputs as the comparison frame
- inspect only the first local `OpenDataLoader` `json + markdown` sidecars
- keep this as a docs-only inspection lane

Out of scope:
- runtime parser adoption
- `parser_backend` enum/config changes
- canonical schema changes
- parser replacement conclusions

## Inputs

- Frozen manifest: [opendataloader_sidecar_hard_doc_20260327.json](/Users/jangseongjin/paperpipe/goldset/manifests/opendataloader_sidecar_hard_doc_20260327.json)
- First-run execution report: [OpenDataLoader_Sidecar_First_Run_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/OpenDataLoader_Sidecar_First_Run_2026-03-27.md)
- Tracked parser comparison source:
  - `snapshots/ingest_backend_eval/docling_pilot_manifest_20260323_r9/detailed_results.jsonl`
- Local-only `OpenDataLoader` raw sidecars:
  - `snapshots/opendataloader_sidecar_eval/opendataloader_sidecar_hard_doc_20260327_r1/raw/`

## Comparison Summary

| Document | Tracked baseline signal | Tracked docling signal | OpenDataLoader first run | Inspection note |
|---|---|---|---|---|
| `Chandra 2023` | `fitz`: `0` tables, taxonomy `NO_TABLE_FOUND`, `116,953` text chars | `docling`: `2` meaningful tables, `122,581` text chars | `0` table nodes, `8` image nodes, `114,369` markdown chars | reading order looked clean, but no table recovery signal appeared |
| `Hansson 2023` | `fitz`: `3` meaningful tables, taxonomy `DEGENERATE_SHAPE`, `95,417` text chars | `docling`: `3` meaningful tables, fallback rescue on page `4`, `103,268` text chars | `2` table nodes, `1` image node, `93,336` markdown chars | table nodes existed, but cell text was empty in both tables |
| `Pichet Binette 2023` | `fitz`: `0` tables, taxonomy `NO_TABLE_FOUND`, `59,708` text chars | `docling`: `4` meaningful tables, `58,869` text chars | `0` table nodes, `4` image nodes, `59,912` markdown chars | article text came through, but no table recovery signal appeared |
| `Therriault 2022` | `fitz`: `7` raw tables, `1` meaningful table, taxonomy `DEGENERATE_SHAPE`, `78,573` text chars | `docling`: `1` meaningful table, `76,445` text chars | `9` table nodes, `55` image nodes, `84,642` markdown chars | strong layout signal, but table cells were empty and image-heavy output was noisy |

## Per-Document Notes

### Chandra 2023

- Markdown looked article-like and preserved high-level reading order:
  - review label
  - main title
  - abstract/body flow
  - `Background` heading
- That is useful for human inspection and possible layout-aware chunking experiments.
- But on the current frozen subset it did **not** recover the thing that most clearly differentiated this file in tracked parser eval:
  - `docling` surfaced `2` meaningful tables
  - `OpenDataLoader` surfaced `0` table nodes

### Hansson 2023

- `OpenDataLoader` did surface table structures on pages `3` and `4`.
- Markdown also showed some visible table framing, including a disease-stage table shell.
- But the JSON tables were not populated with usable text:
  - table count `2`
  - tables with any non-empty cell text `0`
  - total non-empty table cells `0 / 28`
- Compared with tracked `docling`, this currently looks like structure detection without clearly usable table content.

### Pichet Binette 2023

- The main article body and metadata came through in readable Markdown.
- However, this file is important because tracked parser eval showed a large spread:
  - `fitz`: `0` tables
  - `docling`: `4` meaningful tables
- In the first `OpenDataLoader` run:
  - table nodes `0`
  - image nodes `4`
  - table-like Markdown lines only came from boxed prose/citation blocks, not actual recovered tables
- So on this document the first run did not beat the tracked `docling` recovery signal.

### Therriault 2022

- `OpenDataLoader` surfaced the strongest raw layout signal in the subset:
  - `9` table nodes
  - `55` image nodes
  - `51` table-like Markdown lines
- This suggests that the parser is seeing complex layout regions.
- But the current raw tables were still not text-bearing:
  - tables with any non-empty cell text `0`
  - total non-empty table cells `0 / 102`
- The Markdown was also image-heavy and noisy, especially around extended-data figure regions.
- Net result: promising layout visibility, but not yet a clearly better structured table output for downstream use.

## What This Inspection Supports

- `OpenDataLoader PDF` is installable and runnable in a local isolated lane.
- It can produce readable Markdown with useful reading-order cues on biomedical papers.
- It can surface layout objects such as headings, images, and table shells.
- It remains a reasonable bounded sidecar candidate for:
  - hard-doc visual inspection
  - annotated/layout-aware debugging
  - future chunking/provenance experiments

## What This Inspection Does Not Support

- promotion to a default parser backend
- runtime parser routing changes
- direct canonical schema mapping
- a claim that `OpenDataLoader` already outperforms the current parser path on table-heavy hard docs

The strongest caution from this first inspection is simple:
- on `Hansson` and `Therriault`, `table` nodes existed but the current JSON tables had empty cell text
- on `Chandra` and `Pichet Binette`, no table nodes surfaced even though tracked `docling` recovery had already shown meaningful tables

## Current Recommendation

Keep `OpenDataLoader PDF` in the bounded sidecar lane only.

Recommended posture now:
1. keep current runtime parser path unchanged
2. keep `OpenDataLoader` outputs as local or optional sidecars
3. only reopen a deeper parser experiment if a later run shows one of:
   - stable non-empty table cell recovery on the hard-doc subset
   - materially better reading-order output that a downstream chunking/provenance experiment can actually consume
   - a portable snapshot contract that does not depend on local absolute paths or bulky default image trees

## Follow-Up Boundaries

Safe follow-up:
- compact comparison report like this one
- optional second bounded run with explicit image-output policy or tagged-PDF structure-tree option
- manual review of one or two annotated difficult pages

Still not approved:
- runtime adoption
- parser replacement
- hybrid mode as a default
- downstream schema redesign around raw `OpenDataLoader` JSON

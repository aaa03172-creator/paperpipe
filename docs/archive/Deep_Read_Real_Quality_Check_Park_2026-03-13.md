Status: Historical real-input quality check  
Date: 2026-03-13  
Scope: `POST /jobs/deepread` browser path and runtime output quality for `zotero:parkDiscoveryDualactionSmall2022`

# Summary

`Deep Read` was directly verified on the live local browser route and on the real runtime worker path.

The runtime path is operational:
- browser click on `/workbench/zotero%3AparkDiscoveryDualactionSmall2022` enqueued a real job
- the worker completed the run
- artifact bundle was written
- Obsidian note upsert wrote exactly one `## 🤖 Agent Deep Read` section

However, the quality review on the real output initially showed three important caveats:
- the extracted claim was directionally correct but compressed relative to the source sentence
- the generated limitation (`Small sample size`) did not appear to be grounded in the parsed source text
- stats verification completed operationally, but the result was effectively a degenerate `UNVERIFIABLE` fallback driven by poor table extraction quality

# Runtime Evidence

Browser-triggered run:
- `job_id`: `a62abafe-6911-43a9-b05e-24322d0837be`
- `run_id`: `run_20260313_103553`
- final status: `completed`

Earlier note-upsert validation run:
- `job_id`: `01728b93-ca7c-4ad1-8d2e-0fb3d98818c4`
- `run_id`: `run_20260313_103328`
- final status: `completed`

Artifacts:
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_103553`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_103328`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_104454`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_105057`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_105324`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110307`
- `/Users/jangseongjin/paperpipe/storage/artifacts/zotero:parkDiscoveryDualactionSmall2022/run_20260313_110600`

Updated note:
- `/Users/jangseongjin/Documents/Obsidian/MyVault/Inbox/PaperPipe/zoteroparkDiscoveryDualactionSmall2022.md`

Observed note state:
- `## 🤖 Agent Deep Read` section count: `1`

# Claim Quality Check

Extracted claim:
- `KARI compounds directly inhibit ASM activity.`

Resolved evidence span:
- page: `1` (rendered section label: `page_2`)
- source chunk: `p02_c05`
- grounding status: `NORMALIZED_MATCH`

Direct source text recovered from parsed page:
- `indicating that KARI compounds inhibited ASM activity without changing mRNA and protein levels.`
- `the direct inhibition effects of the KARI compounds on the secretory form of ASM ...`
- `KARI compounds, especially KARI 201 and 101, exhibited a more significant inhibition effect on secretory ASM than others.`
- `These results showed that KARI compounds directly inhibited both lysosomal and secretory ASM activity in AD patient cells.`

Assessment:
- the extracted claim is substantively supported by the source text
- but it compresses a more specific source statement into a simpler generic claim
- specifically, it drops the stronger qualifier about unchanged `mRNA` / `protein` levels and the more specific scope (`lysosomal and secretory ASM`)

Follow-up reruns after reader hardening:
- `run_20260313_104454` removed the unsupported limitation line and upgraded the claim wording to include `without changing mRNA and protein levels`
- `run_20260313_105057` improved note output further, but `quote/raw_text/source_span` were still internally inconsistent because the worker was restarted between hardening passes
- `run_20260313_105324` closed that gap on a fresh worker:
  - `limitations = []`
  - `quote ∈ raw_text`
  - `claimset.resolved.json` reports `grounded = true`, `resolution = OK`
- `run_20260313_110600` closed the remaining runtime-facing gaps:
  - note evidence display now removes wrapped-hyphen artifacts and figure-fragment prefixes
  - `claimset.resolved.json` again reports `grounded = true`, `resolution = OK`
  - `stats_report.json` now short-circuits degenerate tables before sandbox planning and records `notes = auto_fallback_degenerate_table_shape`

Current judgment:
- acceptable as a grounded source-backed claim
- still somewhat compressed relative to the most specific source wording (`direct inhibition effects`, `lysosomal and secretory ASM`)
- no longer blocked by unsupported limitation leakage

# Limitation Quality Check

Initial generated limitation:
- `Small sample size`

Observed source support:
- no direct match for `small sample size` was found in the parsed `document_artifact.json`
- no nearby explicit limitation sentence supporting that wording was identified in the checked output path

Follow-up status:
- reader-side hardening now suppresses unsupported limitations unless lexical support exists in the source chunk set
- fresh real reruns (`run_20260313_104454`, `run_20260313_105057`, `run_20260313_105324`) wrote `limitations = []`
- the Park note now has no `- **Limitations**:` line in the current `## 🤖 Agent Deep Read` section

Current judgment:
- the specific `Small sample size` leakage is closed
- the contract still uses string limitations rather than evidence-bearing limitation objects, so this is a bounded hardening step rather than the final evidence model

# Stats Verification Check

Stats report outcome:
- `checks = 1`
- verdict: `unverifiable`
- notes: `auto_fallback_no_extractable_stats`

Table extraction state:
- `table_extraction_pass = pass1`
- `table_failure_taxonomy = ["DEGENERATE_SHAPE"]`
- extracted table shape:
  - caption: `Table found on page 4`
  - columns: `["52.83"]`
  - row: `["53.08\\n52.31"]`

Observed verification behavior:
- stats runtime completed end-to-end
- but the extracted table is too degenerate to support a meaningful test
- the generated verification code therefore falls back to an `unverifiable` result

Judgment:
- operational success: yes
- statistical validation quality: weak for this paper/run

# Direct Conclusions

What is confirmed:
- `Deep Read` browser trigger works
- worker execution works
- artifact writing works
- note upsert works

What is not yet strong enough:
- fully high-fidelity claim wording preservation
- broader upstream table extraction quality beyond the explicit degenerate-table short-circuit

Follow-up applied after the initial check:
- unsupported limitations are now suppressed unless the wording is lexically supported by source chunks
- evidence span canonicalization now forces unsupported model quotes back onto source-backed chunk excerpts before the note is written
- this closes the specific `Small sample size` leakage observed in the Park 2022 run and removes the earlier `quote/raw_text/source_span` mismatch on the fresh worker rerun
- note rendering now cleans wrapped evidence quotes for display without mutating the canonical artifact quote/raw_text pair
- stats verification now short-circuits clearly degenerate tables into an explicit `auto_fallback_degenerate_table_shape` report instead of emitting meaningless generated code
- it does not yet add evidence-bearing limitation objects to the contract

# Follow-up Direction

The next useful follow-up is not more runtime wiring.

The useful lane is output-quality hardening:
1. claim fidelity / compression policy
2. broader upstream table extraction quality beyond the current degenerate-table short-circuit

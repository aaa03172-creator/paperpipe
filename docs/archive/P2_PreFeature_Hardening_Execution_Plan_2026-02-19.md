# PaperPipe P2 Pre-Feature Hardening Execution Plan (2026-02-19)

Status: Historical execution plan  
Date: 2026-02-19  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## 0) Scope Freeze
- This plan covers PR#1 ~ PR#3 only.
- No out-of-scope refactor.
- Evidence-first, fail-safe, unknown-allowed policy stays unchanged.

## 1) Repo Reality Check (Verified)
- Current ingest contract is `DocumentArtifact` v1 in `src/schemas/agent_artifacts.py`.
- Current ingest implementation is PyMuPDF + pdfplumber in `src/agents/ingest_agent.py`.
- Existing eval scripts are ad-hoc (`scripts/run_eval.sh`, `scripts/run_eval_v2.sh`, `scripts/analyze_eval.py`).
- OCR fallback pipeline (`ocrmypdf` + `tesseract`) is not implemented yet.

## 2) Adjusted Decisions Before Implementation
1. PR#2 will be additive, not replacement.
- Add `DocumentArtifactV2` as a new contract.
- Keep existing `DocumentArtifact` path alive to avoid pipeline breakage.

2. Goldset PDF handling will be local-first.
- Repo stores manifest/pointers by default.
- Missing local PDFs must fail loudly (no silent skip).

3. Determinism checks will ignore known volatile fields.
- Timestamps/runtime paths are excluded from strict equality.
- Stable IDs and stable key set are mandatory.

4. OCR fallback is opt-in by flag.
- Keep main path lean.
- On OCR failure: continue with original PDF + explicit metadata/log.

## 3) PR Plan

### PR#1 Eval Harness + Goldset Skeleton
Goal:
- Build repeatable evaluation baseline with versioned snapshots and machine-readable diffs.

Acceptance Criteria:
- AC1: Goldset structure exists (`goldset/queries.jsonl`, `goldset/manifest.json`, `goldset/pdfs/`).
- AC2: Snapshot run writes versioned outputs (`ingest/reader/index/stats/summary.json`).
- AC3: Diff tool outputs JSON and human-readable summary with added/removed/changed counts.

Regression Tests:
- T1: Determinism (stable document ID and stable output keys).
- T2: Snapshot integrity (required files exist for fixture run).
- T3: Diff sanity (counts are present and non-negative).

### PR#2 DocumentArtifact v2 Contract
Goal:
- Introduce stable IDs and bbox-ready structure for shared downstream consumption.

Acceptance Criteria:
- AC1: Stable IDs for page/block/line/span.
- AC2: BBox convention explicitly documented.
- AC3: Ingest can produce v2 artifact without breaking existing consumers.

Implementation Rules:
- If bbox unavailable, set `bbox_pdf = null` and mark reason (no fabrication).
- Serialize/deserialize must preserve IDs and bbox values.

Regression Tests:
- T1: Same PDF processed twice -> stable page/block IDs.
- T2: Produced output validates against v2 schema.
- T3: If bbox exists, it is non-negative and inside page bounds.

### PR#3 OCR Fallback (OCRmyPDF + Tesseract)
Goal:
- Recover text layer for scanned PDFs with fail-safe behavior.

Acceptance Criteria:
- AC1: Scanned fixture can produce OCR text layer.
- AC2: OCR applied/version/lang metadata is recorded.
- AC3: OCR failure does not crash pipeline; original PDF path is preserved.

Regression Tests:
- T1: OCR path increases extracted text length beyond threshold.
- T2: Simulated OCR failure returns safe fallback metadata.

## 4) Stop Conditions
- If existing schema/contract conflicts with v2 design in a way that cannot be additive, stop and report exact file/line conflict before coding further.
- If required local fixture PDFs are missing, fail explicitly and report unresolved manifest entries.

## 5) Execution Order
1. PR#1 first (evaluation guardrail).
2. PR#2 second (contract stabilization).
3. PR#3 third (OCR fallback).

## 6) Start Log
- 2026-02-19: Plan fixed and saved.
- Next action: PR#1 skeleton (`goldset/`, `scripts/eval/`, `snapshots/`) and baseline harness entrypoints.

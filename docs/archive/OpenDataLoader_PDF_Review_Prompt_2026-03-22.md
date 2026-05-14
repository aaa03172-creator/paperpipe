# OpenDataLoader PDF Review Prompt

Status: Historical review prompt  
Date: 2026-03-22  
Owner: Repository maintainers  
Canonical parent: `docs/archive/OpenDataLoader_PDF_Fit_Review_2026-03-20.md`

## Purpose

Capture a PaperPipe-grounded prompt for reviewing `OpenDataLoader PDF` without reopening parser replacement scope.

This is a reusable review prompt, not a migration plan and not a runtime spec.

## Local Architecture Anchors

Any future review using this prompt should anchor to these current local contracts first:

- `docs/Lattice_v3_Master_Spec.md`
- `docs/document_artifact_v2.md`
- `docs/ocr_fallback.md`
- `src/config.py`
- `src/ingest/parser_backends.py`
- `src/agents/ingest_agent.py`
- `backend/services/job_runner.py`

Local facts the prompt is designed to preserve:

- `ParserBackend` is the current parser slot.
- `IngestAgent.process_v2(...)` is the additive ingest path.
- `DocumentArtifactV2` is the current parser-facing canonical runtime contract.
- `ingest.parser_backend` currently exposes `fitz_pdfplumber | docling`.
- OCR and table fallback semantics already exist and should remain intact.
- `bootstrap_meta.json` and `run_meta.json` already record parser/fallback telemetry.

## Prompt

```md
Task: produce a bounded fit review of OpenDataLoader PDF for PaperPipe's current PDF ingestion layer. This is a compatibility assessment, not a redesign task.

Target:
https://github.com/opendataloader-project/opendataloader-pdf

Before answering, inspect these local sources first and treat them as canonical:
- docs/Lattice_v3_Master_Spec.md
- docs/document_artifact_v2.md
- docs/ocr_fallback.md
- src/config.py
- src/ingest/parser_backends.py
- src/agents/ingest_agent.py
- backend/services/job_runner.py

If you find related files in `docs/archive/`, use them only as historical context, not as source of truth.

Role:
You are a senior systems architect preserving and improving a local-first biomedical research agent.

Objective:
Assess whether OpenDataLoader PDF can be used safely as an additive parser-side capability in PaperPipe.
This is not a proposal to adopt it as the new default parser and not a prompt to redesign the system around parsing.

Hard constraints:
1. Do not propose replacing the current PDF pipeline.
2. Do not propose removing the current baseline parser, OCR fallback, or existing table fallback lanes.
3. Do not propose a full rewrite, parser-layer migration, storage schema replacement, or downstream architecture rewrite.
4. Treat OpenDataLoader PDF only as an optional parser candidate, layout-aware fallback, sidecar artifact producer, or hard-document batch evaluator.
5. Default stance: keep the current baseline parser and use OpenDataLoader only for bounded additive evaluation.
6. Do not expand this tool into retrieval, ranking, memory, judge, chat, RAG, or note architecture.
7. Treat `DocumentArtifactV2` as the current canonical parser-facing runtime contract.
8. Mark every non-certain claim as one of: `Confirmed from local repo`, `Confirmed from upstream`, `Inference`, or `Unknown`.
9. If something is not supported by the inspected code or upstream docs, say so explicitly.

Current local architecture facts you must anchor to:
- `ParserBackend` is the current parser slot.
- `IngestAgent.process_v2(...)` is the additive ingest path.
- `DocumentArtifactV2` is the current parser-facing canonical contract.
- `ingest.parser_backend` currently exposes only `fitz_pdfplumber | docling`; do not assume OpenDataLoader should immediately become a new default enum value.
- OCR and table fallback semantics already exist and must remain intact.
- `bootstrap_meta.json` and `run_meta.json` already record parser/fallback telemetry.
- The parser is an ingestion helper, not the system center.

Known upstream facts about OpenDataLoader PDF:
- Markdown / JSON(with bounding boxes) / HTML output
- deterministic local mode + AI hybrid mode
- emphasis on multi-column papers, scanned PDFs, tables, formulas, charts
- Python `convert()` spawns a JVM per call, so batch execution is preferred
- Java 11+ and Python 3.10+ required

Do not assume more than this without verification.

Evaluate only these questions:

A. Fit in our architecture
- What is the safest role in PaperPipe: parser candidate, layout-aware fallback, hard-document batch evaluator, table-heavy specialist, or sidecar generator?
- Is the safer first integration shape:
  1. a bounded sidecar/batch lane outside the hot ingest path, or
  2. an optional backend behind the parser abstraction?
- If you mention an optional backend, explain why sidecar-first may still be safer in the current codebase.

B. What it is good for
- Which document classes benefit most?
- How could Markdown + bbox JSON help chunking, page-block provenance, evidence grounding, citation alignment, or HITL inspection?

C. What it should NOT replace
- Be explicit about what must remain in place:
  - current baseline parser
  - OCR fallback lane
  - table fallback lane
  - `DocumentArtifactV2`
  - reader / extraction / grounding / RAG / note layers
- Explain why this tool should not be over-interpreted beyond PDF ingestion help.

D. Operational realism
- Assess Java + Python + JVM spawn overhead.
- State whether batch-first orchestration is required.
- State whether deterministic local mode is enough for phase 1.
- State whether hybrid mode should remain off by default.
- State whether no-GPU local pilot is feasible.
- State whether single-file synchronous hot-path invocation is a bad fit.

E. Safest integration strategy
Assume this default strategy unless local evidence disproves it:
1. keep current parser
2. add a quality gate or hard-document detector
3. run OpenDataLoader only for selected documents
4. save outputs as sidecar artifacts
5. keep downstream consumers unchanged by default

Also evaluate whether the safest first implementation should avoid touching `ingest.parser_backend` entirely and instead run as a separate helper lane.

F. Data schema implications
- Prefer raw sidecars plus optional normalized helper views.
- Do not replace `DocumentArtifactV2` with upstream JSON.
- Keep upstream bbox values separate from canonical `bbox_pdf` until coordinate semantics are verified.
- Prefer artifact-dir sidecars and metadata flags over DB schema changes.
- If proposing normalized fields, clearly separate:
  - raw upstream payload
  - PaperPipe helper projection
  - canonical runtime schema

G. Low-risk pilot design
- Propose only hard-case document subsets.
- Reuse current failure signals where possible, such as low-text cases or table extraction failures.
- Define comparison metrics, success criteria, rollback shape, and operator inspection value.
- Require trivial rollback and no default-path regression.

H. Risks to avoid
- starting from parser replacement
- enabling hybrid mode by default
- rewriting downstream schema because bbox/json looks attractive
- redesigning note/memory/RAG around parser outputs
- ignoring batch cost and operational complexity
- treating parser quality as a proxy for end-to-end biomedical reasoning quality

Output format:
1. Executive summary
2. Current architecture anchors
3. Why this is a parser candidate, not a core engine
4. Best-fit use cases in our system
5. What it should NOT replace
6. Operational complexity and constraints
7. Safest integration architecture
8. Sidecar schema suggestion
9. Low-risk pilot plan
10. Recommendation
11. Evidence and unknowns
12. Do not rewrite these parts
13. Safest next 3 experiments

Additional output requirements:
- Cite local files or runtime contracts where relevant.
- Distinguish local-repo-confirmed facts from upstream-confirmed facts.
- Prefer language like `optional module`, `fallback`, `sidecar artifact`, `evaluation harness`, and `bounded pilot`.
- Avoid migration language unless you are explicitly warning against it.
```

## Why This Prompt Shape Is Safer

Compared with a generic external-tool review prompt, this version adds:

- explicit local contract anchors before any judgment
- a hard boundary around `DocumentArtifactV2`
- a warning against assuming `OpenDataLoader PDF` should become a new default `parser_backend`
- operational emphasis on sidecar-first and batch-first evaluation
- a required evidence/unknown split so uncertain claims do not get presented as architecture truth

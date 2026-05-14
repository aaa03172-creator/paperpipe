# LiteParse Review Prompt

Status: Historical review prompt  
Date: 2026-03-22  
Owner: Repository maintainers  
Canonical parent: `docs/archive/External_Reference_Fit_Review_2026-03-18.md`

## Purpose

Capture a PaperPipe-grounded prompt for reviewing `LiteParse` without reopening parser replacement scope.

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

## Official Source Priority

When reusing this prompt, prefer sources in this order:

1. official LiteParse docs
2. official GitHub repo / README
3. official LlamaIndex blog
4. third-party articles only as secondary context

This matters because some third-party summaries overstate LiteParse's sweet spot or imply output modes that are not primary in the official materials.

## Official Facts Already Verified

As of 2026-03-22, the official materials support these baseline facts:

- LiteParse is a local open-source parser focused on fast, light parsing with spatial text and bounding boxes.
- It runs locally without cloud dependencies, LLMs, or API keys.
- Officially highlighted outputs are `text`, `json`, and page `screenshots`, not richer structure-heavy parser outputs.
- It supports PDFs, Office files, and images.
- OCR support exists via built-in Tesseract.js or an HTTP OCR server.
- OCR is selective by default and first use may download Tesseract model files unless they are pre-cached.
- TypeScript and CLI are the primary native surfaces.
- The Python package wraps the LiteParse CLI, so the Node CLI must be installed first.
- Batch parsing is explicitly supported and faster than repeated per-file setup.
- Official materials position dense tables, complex multi-column layouts, charts, handwritten text, and hard scanned PDFs as areas where higher-end parsing may do better.

## Prompt

```md
Task: produce a bounded fit review of LiteParse for PaperPipe's current PDF ingestion layer. This is a compatibility assessment, not a redesign task.

Targets:
- https://developers.llamaindex.ai/liteparse/
- https://github.com/run-llama/liteparse
- https://www.llamaindex.ai/blog/liteparse-local-document-parsing-for-ai-agents
- https://www.marktechpost.com/2026/03/19/llamaindex-releases-liteparse-a-cli-and-typescript-native-library-for-spatial-pdf-parsing-in-ai-agent-workflows/

Source priority:
1. official LiteParse docs
2. official GitHub repo / README
3. official LlamaIndex blog
4. third-party article only as secondary context

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
Assess whether LiteParse can be used safely as an additive parser-side capability in PaperPipe.
This is not a proposal to adopt it as the new default parser and not a prompt to redesign the system around parsing.

Hard constraints:
1. Do not propose replacing the current PDF pipeline.
2. Do not propose removing the current baseline parser, OCR fallback, or existing table fallback lanes.
3. Do not propose a full rewrite, parser-layer migration, storage schema replacement, or downstream architecture rewrite.
4. Treat LiteParse only as an optional parser candidate, fast local parser helper, bbox-aware sidecar generator, OCR helper, or hard-document batch evaluator.
5. Default stance: keep the current baseline parser and use LiteParse only for bounded additive evaluation.
6. Do not expand this tool into retrieval, ranking, memory, judge, chat, RAG, or note architecture.
7. Treat `DocumentArtifactV2` as the current canonical parser-facing runtime contract.
8. Mark every non-certain claim as one of: `Confirmed from local repo`, `Confirmed from official LiteParse sources`, `Inference`, or `Unknown`.
9. If something is not supported by the inspected code or official sources, say so explicitly.

Current local architecture facts you must anchor to:
- `ParserBackend` is the current parser slot.
- `IngestAgent.process_v2(...)` is the additive ingest path.
- `DocumentArtifactV2` is the current parser-facing canonical contract.
- `ingest.parser_backend` currently exposes only `fitz_pdfplumber | docling`; do not assume LiteParse should immediately become a new default enum value.
- OCR and table fallback semantics already exist and must remain intact.
- `bootstrap_meta.json` and `run_meta.json` already record parser/fallback telemetry.
- The parser is an ingestion helper, not the system center.

Known official LiteParse facts you may rely on unless superseded by newer official docs:
- local open-source parser
- spatial text parsing with bounding boxes
- OCR support with built-in Tesseract.js or HTTP OCR servers
- screenshots as a first-class output
- PDFs, Office docs, and images supported
- TypeScript, Python, and CLI usage exist
- Python package wraps the CLI; Node CLI installation is still required
- outputs emphasized by official materials are text, JSON, and screenshots
- OCR model files may download on first use unless pre-cached
- batch parsing is supported and preferred over repeated cold-start style calls
- official materials present dense tables, complex multi-column layouts, charts, handwritten text, and hard scanned PDFs as likely limit cases

Do not assume more than this without verification.

Evaluate only these questions:

A. Fit in our architecture
- What is the safest role in PaperPipe: parser candidate, fast local parser helper, bbox-aware preprocessor, OCR helper, screenshot sidecar generator, or hard-document batch evaluator?
- Is the safer first integration shape:
  1. a bounded sidecar/batch lane outside the hot ingest path, or
  2. an optional backend behind the parser abstraction?
- If you mention an optional backend, explain why sidecar-first may still be safer in the current codebase.

B. What it is good for
- Which document classes benefit most?
- Focus on realistic best-fit cases such as born-digital PDFs, simpler layout-preserving parse needs, bbox/provenance capture, and fast local parsing.
- How could OCR, bbox JSON, and screenshots help chunking, page-block provenance, evidence grounding, or visual re-check?

C. Known limits / overreach risks
- Be explicit about where official materials suggest LiteParse may underperform or should not be overclaimed:
  - dense tables
  - complex multi-column layouts
  - charts
  - handwritten text
  - hard scanned PDFs
- Explain the trade-off between a layout-preserving parser and a structure-heavy parser.
- Explain why LiteParse should not be over-interpreted beyond PDF ingestion help.

D. Operational realism
- Assess the practical benefits of local CPU-based execution.
- Assess the operational implications of TypeScript/CLI-native packaging.
- Assess whether Python integration is better treated as a sidecar CLI wrapper rather than a first-class native backend inside the current Python runtime.
- Assess the storage and ops cost of keeping screenshots plus bbox JSON as sidecars.
- Note any air-gapped or reproducibility caveat from first-run OCR model downloads.

E. Safest integration strategy
Assume this default strategy unless local evidence disproves it:
1. keep current parser
2. add LiteParse as a fast local parser candidate or sidecar helper
3. run LiteParse only for selected document groups
4. save text/json/screenshot results as sidecar artifacts
5. keep downstream extractor / RAG / note system unchanged by default

Also evaluate whether the safest first implementation should avoid touching `ingest.parser_backend` entirely and instead run as a separate helper lane.

F. Data schema implications
- Prefer raw sidecars plus optional normalized helper views.
- Do not replace `DocumentArtifactV2` with LiteParse output.
- Keep upstream bbox values separate from canonical `bbox_pdf` until coordinate semantics are verified.
- Prefer artifact-dir sidecars and metadata flags over DB schema changes.
- If proposing normalized fields, clearly separate:
  - raw upstream payload
  - PaperPipe helper projection
  - canonical runtime schema

Suggested candidate fields to assess:
- `raw_text`
- `layout_text`
- `bbox_json`
- `page_screenshots`
- `parser_name`
- `parser_mode`
- `ocr_used`
- `provenance`

Do not assume richer structure fields such as markdown/table schemas unless official sources or direct output inspection support them.

G. Low-risk pilot design
- Propose only bounded document subsets.
- Distinguish likely best-fit subsets from likely stress/failure subsets.
- Define comparison metrics, success criteria, rollback shape, and operator inspection value.
- Require trivial rollback and no default-path regression.

H. Risks to avoid
- starting from parser replacement
- treating LiteParse as a universal document understanding engine
- rewriting downstream schema because bbox/json/screenshots look attractive
- redesigning note/memory/RAG around parser outputs
- relying on article summaries over official docs

Output format:
1. Executive summary
2. Why this is a parser candidate, not a core engine
3. Best-fit use cases in our system
4. Known limits and overreach risks
5. Operational complexity and constraints
6. Safest integration architecture
7. Sidecar schema suggestion
8. Low-risk pilot plan
9. Recommendation
10. Evidence and unknowns
11. Do not rewrite these parts
12. Safest next 3 experiments

Additional output requirements:
- cite local files or runtime contracts where relevant
- distinguish local-repo-confirmed facts from official-source-confirmed facts
- prefer language like `optional module`, `fallback`, `sidecar artifact`, `evaluation harness`, and `bounded pilot`
- avoid migration language unless you are explicitly warning against it
```

## Why This Prompt Shape Is Safer

Compared with a generic parser review prompt, this version adds:

- explicit local contract anchors before any judgment
- a hard boundary around `DocumentArtifactV2`
- a warning against assuming LiteParse should become a new default `parser_backend`
- operational emphasis on sidecar-first, CLI-aware, and batch-aware evaluation
- a correction against overclaiming `markdown` or structure-heavy output when official materials emphasize `text`, `json`, and `screenshots`
- a required evidence/unknown split so uncertain claims do not get presented as architecture truth

## Sources

- https://developers.llamaindex.ai/liteparse/
- https://developers.llamaindex.ai/liteparse/guides/library-usage/
- https://developers.llamaindex.ai/liteparse/guides/ocr/
- https://github.com/run-llama/liteparse
- https://www.llamaindex.ai/blog/liteparse-local-document-parsing-for-ai-agents
- https://www.marktechpost.com/2026/03/19/llamaindex-releases-liteparse-a-cli-and-typescript-native-library-for-spatial-pdf-parsing-in-ai-agent-workflows/

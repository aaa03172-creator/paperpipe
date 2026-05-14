# External Reference Fit Review

Status: Historical fit review  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Scope:
- consolidate recent external reference reviews into one current-system-safe note
- preserve the current PaperPipe/Lattice architecture as the default
- record only additive, bounded, low-risk interpretations
- do not introduce a new master spec, runtime contract, or migration plan

Reviewed references:
- [GLM-OCR GitHub README](https://github.com/zai-org/GLM-OCR)
- [AI Can Learn Scientific Taste](https://tongjingqi.github.io/AI-Can-Learn-Scientific-Taste/)
- [Ars Contexta GitHub README](https://github.com/agenticnotetaking/arscontexta)
- [Ars Contexta site](https://www.arscontexta.org)
- [OpenAlex Works API docs](https://developers.openalex.org/api-reference/works)
- [Semantic Scholar API overview](https://www.semanticscholar.org/product/api)
- [PubTator 3.0 paper](https://pubmed.ncbi.nlm.nih.gov/38572754/)
- [MedCPT paper](https://pubmed.ncbi.nlm.nih.gov/41031073/)
- [MedCPT model card](https://huggingface.co/ncbi/MedCPT-Article-Encoder)
- [EBM-NLP GitHub](https://github.com/bepnye/EBM-NLP)
- [Trialstreamer paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7727361/)
- [GROBID docs](https://grobid.readthedocs.io/en/latest/)
- [PaperQA2 GitHub](https://github.com/Future-House/paper-qa)

Reference baseline:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/RESEARCH_DNA.md`
- `docs/WEB_VIEWER.md`
- `docs/Output_Contract_Audit_2026-03-13.md`
- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `docs/reports/Committed_Backend_API_Stack_Summary_2026-03-18.md`

## 0. Executive Summary

The current repo still does not justify an architecture reset.

The safest consolidated judgment from the recent reference reviews is:

- preserve the current FastAPI-first, Pydantic-first, artifact-first runtime
- treat external projects as `sidecar`, `fallback`, `benchmark`, `dataset`, or `reference` inputs only
- keep note/memory systems below the research pipeline, not above it
- keep current paper/run/artifact/state contracts as the active runtime default

The strongest repository-level conclusion is not "which external stack is best."

It is this:

- PaperPipe already has a bounded biomedical core loop worth preserving
- the current bottlenecks look like retrieval quality, extraction reliability, evidence grounding, and operator legibility
- most external references are useful only when interpreted narrowly against those bottlenecks

## 1. Current-System-Safe Baseline

Current product reality already includes three stable lanes:

1. `Research DNA`
2. `Meeting Pack`
3. `paper-notes` operational detail surface

These lanes are already documented as product-real surfaces in:

- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`

This matters because the reviewed references should not be allowed to reopen the baseline boundary by default.

In practice, that means:

- no framework migration
- no new generic memory platform
- no new top-level vault-first product model
- no replacement of current paper/run/artifact/state roots

## 2. Consolidated Classification

| Reference | Safe system slot | Current classification | Confidence | Boundary note |
| --- | --- | --- | --- | --- |
| OpenAlex | `source & enrichment layer` | supplemental candidate only | high | metadata/citation enrichment, not source of truth |
| Semantic Scholar API | `source & enrichment layer` | supplemental candidate only | high | citation/reference/anchor enrichment only |
| PubTator Central | `source & enrichment layer` | promising sidecar candidate | medium | biomedical entity/relation annotation, not screening truth |
| MedCPT | `retrieval / reranking baseline` | benchmark-first candidate | medium | compare against current retrieval before any stronger claim |
| EBM-NLP | `extraction training/eval dataset` | dataset only | high | useful for PICO-style eval/training, not runtime |
| GROBID | `parser layer` | defer | medium | bibliography/full-text structure reference, but low immediate ROI |
| Docling | `parser layer` | optional benchmark path only | high | keep feature-flagged, no default parser switch |
| Trialstreamer | `SR/RCT pipeline reference` | reference only | high | trial-specific workflow reference, not product core |
| PaperQA2 | `agentic RAG architecture reference` | reference only | high | citation-aware RAG reference, not runtime center |
| GLM-OCR | `OCR/parser fallback` | limited fallback candidate | medium | hard-doc subset only, not default parser |
| AI Can Learn Scientific Taste | `judgment-layer reference` | reference only | high | judge/thinker split is reusable, citation target is not |
| Ars Contexta | `note/ops/memory reference` | reference only | high | note hygiene ideas only, no plugin/runtime adoption |

## 3. What Conclusions Are Strong

The following conclusions are well-supported and should stay stable unless the repo itself changes materially.

### 3.1 OpenAlex and Semantic Scholar should remain supplemental

This is already aligned with current repo policy and code reality.

- OpenAlex is useful for metadata and bibliometric enrichment
- Semantic Scholar is useful for citation/reference/anchor fallback
- neither should become a new architecture center

The repo already warns against `OpenAlex-first` thinking in the search lane.

### 3.2 Docling should stay optional

This is already reflected in current code and earlier fit reviews.

- parser backend abstraction exists
- `docling` sits behind a feature flag
- fallback to `fitz/pdfplumber` already exists

The correct interpretation is:

- keep Docling as a bounded parser comparison path
- do not present it as the new parser default

### 3.3 Ars Contexta should be treated as note/ops reference only

The official sources make this explicit.

- it is a Claude Code plugin
- it generates a vault-centered knowledge system
- it assumes hooks, commands, and setup flow tied to that plugin model

The only safe borrowable ideas are:

- note/ops separation
- schema validation
- MOC-like navigation
- session capture and maintenance signals

Even those should remain subordinate to the biomedical research pipeline.

### 3.4 Scientific Taste is a reference for judgment structure, not a target architecture

The reviewed project is built around:

- citation-based community preference
- Scientific Judge
- Scientific Thinker
- reward-model-style alignment

For PaperPipe, the reusable part is the separation between:

- judgment/ranking
- generation/planning

The non-reusable part is treating citation as the target truth for biomedical relevance or quality.

## 4. What Conclusions Should Stay Softer

The following judgments still make sense, but should be stated more cautiously.

### 4.1 GLM-OCR

Current evidence supports:

- fallback role only
- subset value for scanned/image-heavy/low-text-confidence documents

Current evidence does not yet prove:

- strong overall pipeline ROI on our corpus
- that OCR is the main bottleneck across current runs

So the safest standing conclusion is:

- GLM-OCR is a constrained fallback candidate, not a current adoption mandate

### 4.2 PubTator Central

Current evidence supports:

- strong conceptual fit as a biomedical entity annotation sidecar

Current evidence does not yet prove:

- precision/recall tradeoff on our actual notes, grounding, and screening flows

So the safest standing conclusion is:

- promising sidecar candidate, not yet a proven quality multiplier

### 4.3 MedCPT

Current evidence supports:

- correct layer classification as retrieval/reranking baseline
- strong conceptual fit with biomedical search

Current evidence does not yet prove:

- clear superiority over the current retrieval/index setup for our live workflows

So the safest standing conclusion is:

- benchmark-first candidate, not yet a justified retrieval-layer change

### 4.4 Note/memory concepts

Current evidence supports:

- note validation and navigation ideas can improve inspectability

Current evidence does not yet prove:

- that a richer note/memory substrate automatically improves research quality

So the safest standing conclusion is:

- memory/note ideas are support-layer improvements only

## 5. Non-Adoption Guardrails

The following moves remain explicitly out of bounds unless the repository makes a deliberate future product decision.

- do not rebuild the system around a vault, plugin, or generic memory platform
- do not treat note-taking substrate as more important than biomedical retrieval, screening, extraction, and grounding
- do not replace current parser/index/runtime contracts because an external project looks more elegant
- do not turn supplemental sources into new source-of-truth layers
- do not smuggle external orchestration systems into the baseline under the label of “architecture inspiration”

## 6. Durable Recommendation

Use the reviewed references as:

- vocabulary for future bounded RFCs
- benchmark candidates
- sidecar candidates
- dataset candidates
- historical fit-review inputs

Do not use them as:

- replacement runtime specs
- replacement API contracts
- replacement DB/state models
- justification for widening current baseline scope

If these references are revisited later, reopen them only with new repository-grounded evidence:

- measured corpus-level OCR hard-case gains
- measured retrieval/rerank improvements on current search tasks
- measured annotation usefulness for screening/grounding
- measured note/ops improvements that help operator reliability without shifting product center

# External Reference Classification (2026-04-13)

Status: completed fit review
Date: 2026-04-13
Lane: `pp` + `tool-intake-review`

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`

Reference sources:
- [Sasoo v0.6.7](https://github.com/dosigner/sasoo/releases/tag/v0.6.7)
- Context Hub / annotation-layer thread summary provided in the review prompt
- [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)
- [llm-research-wiki](https://github.com/MetamusicX/llm-research-wiki)
- [PageIndex](https://github.com/VectifyAI/PageIndex)
- [gbrain](https://github.com/garrytan/gbrain)
- [OpenAI Codex use cases](https://developers.openai.com/codex/use-cases)
- [VibeVoice](https://github.com/microsoft/VibeVoice)
- [OpenHarness](https://github.com/HKUDS/OpenHarness)
- [supergemma4-26b-uncensored-mlx-4bit-v2](https://hf.co/Jiunsong/supergemma4-26b-uncensored-mlx-4bit-v2)
- [supergemma4-26b-uncensored-gguf-v2](https://hf.co/Jiunsong/supergemma4-26b-uncensored-gguf-v2)

## 1. Current repo reality check

### Confirmed repo state

The current repo remains:

- paper-first
- artifact-first
- local-first
- single-operator-first
- evidence-linked
- reviewable by a human operator

Confirmed current truth boundary:

- source data owner:
  - PDF / Zotero / imported source files
- canonical truth owner:
  - schema-backed structured paper state and lane-owned bounded state
- derived layers:
  - paper notes
  - compiled knowledge such as `Paper Synthesis`
  - workbench/viewer surfaces
  - downstream artifacts
- support-only raw-memory layers:
  - event logs
  - execution traces
  - backend-only `Project Memory`
  - future conversation-like memory

Confirmed from repo:

- `/api/chat` is still a stub-only compatibility surface
  - `docs/API_CHAT_CONTRACT.md`
  - `backend/main.py`
- `Research DNA` is an active bounded core lane, but not yet a first-class web viewer route
  - `docs/Product_Positioning_Principles.md`
  - `docs/RESEARCH_DNA.md`
- `Project Memory` is implemented but intentionally backend-only, `raw_memory`, and `non_canonical`
  - `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
  - `src/project_memory/store.py`
  - `src/schemas/project_memory.py`
- `Paper Synthesis` is implemented as bounded `compiled_knowledge`, not a new truth owner
  - `docs/PAPER_SYNTHESIS.md`
  - `src/paper_syntheses/service.py`
  - `src/schemas/paper_synthesis.py`
  - `backend/routers/paper_syntheses.py`
- current viewer/workbench surfaces are real and bounded
  - `docs/WEB_VIEWER.md`
  - `frontend/src/App.tsx`
  - `backend/routers/paper_notes.py`
  - `context_trace` is additive trace metadata, not a new evidence truth owner
  - current web routes still do not imply a broad `/projects` workspace surface
- current ingest still centers on `fitz + pdfplumber`, with optional OCR and table salvage paths
  - `src/ingest/parser_backends.py`
  - `src/ingest/ocr_fallback.py`
  - `src/ingest/cloud_table_fallback.py`
- runtime governance already has jobs/runs/events/audits/policy layers
  - `src/db_utils.py`
  - `src/services/event_log.py`
  - `src/jobs/queue.py`
  - `src/skills/policy.py`
  - `config/skills_policy.yaml`

### Current bottlenecks

Repo-grounded bottlenecks look like:

1. scan-heavy / table-heavy PDF salvage quality
2. evidence locator fidelity and reopen quality
3. long-document navigation quality
4. reusable annotation or caveat accumulation for operators
5. operator continuity across repeated paper/artifact work

Current bottlenecks do **not** primarily look like:

- missing generalized chat memory
- missing broad workspace platform objects
- missing generalized wiki as truth owner
- missing multi-agent harness as product core

### Structural constraints that must stay intact

- do not let wiki, notes, prompts, or memory files outrank canonical structured state
- do not let retrieval/navigation become a hidden system of record
- do not let workbench artifacts masquerade as truth owners
- do not let `Project Memory` silently backdoor a project/workspace product surface
- do not let local model enthusiasm hide current parsing/navigation/provenance bottlenecks

## 2. Category legend

Use exactly one bucket per reference:

1. 지금 바로 반영 검토 가치가 높음
2. 작은 범위 실험은 가치 있음
3. 내부 운영 자산으로만 유효
4. 장기 로드맵 참고용
5. 현재 단계에서는 과함 / 보류
6. 기준 레퍼런스로는 부적절 / 사실상 기각 권고

## 3. Reference-by-reference judgment

## Sasoo v0.6.7

- What it is:
  - PDF input to phase-based paper analysis with workbench/library/report/chat surface and optional figure/table/recipe/experiment-plan presentation.
- Which category it belongs to:
  - `2. 작은 범위 실험은 가치 있음`
  - `paper workbench / phase-analysis`
- Why it matters here:
  - The most relevant part is not the whole product shape.
  - The useful part is phase separation and operator-visible workbench staging.
- Which bottleneck it touches:
  - operator workflow clarity
  - figure/table review sequencing
  - review-first workbench surface
- Where it could fit in this repo:
  - as a surface-level workbench reference only
  - especially for phase grouping inside the existing `/workbench/:paperId` flow
- Prerequisites:
  - existing artifacts need a thin phase grouping contract
  - phase display must remain downstream of current artifact lineage
- Risks / mismatches:
  - recipe / experiment-plan objects could prematurely widen product scope
  - chat/workbench surface could be mistaken for backend contract
  - canonical structured state and provenance could be visually weakened if the surface becomes too primary
- Recommendation:
  - `small experiment`
- Smallest viable experiment:
  - add a thin phase strip or grouped artifact sections to the existing workbench using current artifacts only
- Why not now:
  - no reason to adopt Sasoo's product shape, chat posture, or experiment-planning scope as current PaperPipe core

## Context Hub / annotation-layer thread summary

- What it is:
  - an operating thesis that agents fail from missing current context and missing accumulated annotations more often than from raw model weakness
- Which category it belongs to:
  - `2. 작은 범위 실험은 가치 있음`
  - `context / annotation layer`
- Why it matters here:
  - The repo does appear light on reusable parser caveats, exclusion reasons, review notes, and repeated failure guidance.
  - That is a real operator workflow gap.
- Which bottleneck it touches:
  - context accumulation
  - annotation reuse
  - operator continuity
  - review posture consistency
- Where it could fit in this repo:
  - as a bounded annotation ledger next to canonical state, not above it
  - candidate surfaces:
    - parser caveat records
    - extraction failure notes
    - exclusion reasons
    - review/gate warnings
- Prerequisites:
  - explicit layer marking
  - source backlinks
  - clear statement that annotations are support-only
- Risks / mismatches:
  - annotation drift into truth ownership
  - using memory to patch weak evidence instead of fixing provenance and extraction quality
- Recommendation:
  - `small experiment`
- Smallest viable experiment:
  - create a bounded additive annotation ledger for parser caveats and review notes tied to paper/run/source refs
- Why not now:
  - there is still no justification for a broad memory or context-hub product surface

## andrej-karpathy-skills

- What it is:
  - a skill and operating-discipline asset for agent behavior
- Which category it belongs to:
  - `3. 내부 운영 자산으로만 유효`
  - `operator skill asset`
- Why it matters here:
  - useful as developer or agent discipline
  - not useful as product architecture
- Which bottleneck it touches:
  - developer workflow consistency
  - agent execution hygiene
- Where it could fit in this repo:
  - only in Codex/operator workflow norms
  - not in runtime truth or product surface
- Prerequisites:
  - none beyond selective internal adoption of good habits
- Risks / mismatches:
  - treating prompt or skill packs as architecture
  - importing external runtime assumptions into PaperPipe
- Recommendation:
  - `internal ops asset`
- Smallest viable experiment:
  - absorb only a few discipline principles into local working habits or future skill wording
- Why not now:
  - it does not reduce current biomedical runtime bottlenecks directly

## llm-research-wiki

- What it is:
  - a persistent wiki-style knowledge layer on top of sources
- Which category it belongs to:
  - `4. 장기 로드맵 참고용`
  - `wiki layer`
- Why it matters here:
  - useful as an explanatory-layer idea
  - not appropriate as current truth owner
- Which bottleneck it touches:
  - human-readable explanatory synthesis
  - long-term knowledge mapping
- Where it could fit in this repo:
  - only as a future bounded explanatory layer
  - likely paper-scoped before any broader scope
- Prerequisites:
  - current compiled-knowledge lane must stay stable first
  - any wiki layer must preserve clear backlinks into canonical state and source refs
- Risks / mismatches:
  - wiki becoming de facto source of truth
  - overlap or confusion with note/export surfaces
  - widening product scope toward generalized workspace memory
- Recommendation:
  - `roadmap`
- Smallest viable experiment:
  - none now beyond learning from layout and maintenance posture
- Why not now:
  - the repo already has a safer bounded compiled-knowledge lane in `Paper Synthesis`

## PageIndex

- What it is:
  - TOC / section hierarchy / node navigation oriented retrieval for long documents
- Which category it belongs to:
  - `1. 지금 바로 반영 검토 가치가 높음`
  - `retrieval / navigation layer`
- Why it matters here:
  - This is the reference that maps most directly to a real current bottleneck.
  - Long-document navigation remains underpowered relative to current evidence-linked ambitions.
- Which bottleneck it touches:
  - retrieval/navigation quality
  - long document section access
  - review article / protocol / textbook-like chapter navigation
- Where it could fit in this repo:
  - as a retrieval/navigation adjunct
  - not as a vector replacement and not as a truth owner
  - likely tied to section IDs, TOC nodes, and reopen paths
- Prerequisites:
  - preserve section hierarchy and node references in ingest artifacts where possible
  - bridge node/section identity into current evidence and deep-link surfaces
- Risks / mismatches:
  - presenting vectorless retrieval as a total replacement
  - allowing navigation summaries to stand in for evidence
- Recommendation:
  - `adopt now`, but only as a bounded pilot
- Smallest viable experiment:
  - build a tiny section/tree navigation pilot on a frozen set of long biomedical PDFs and compare reopen quality
- Why not now:
  - it still needs a bounded benchmark and should not trigger a retrieval-stack rewrite

## gbrain

- What it is:
  - a markdown-centric system that sharply separates system of record, retrieval access, and agent memory
- Which category it belongs to:
  - `3. 내부 운영 자산으로만 유효`
  - `system-of-record separation`
- Why it matters here:
  - the most valuable part is the separation principle, not the product shape
- Which bottleneck it touches:
  - conceptual hygiene around truth owners versus access layers
- Where it could fit in this repo:
  - as a sanity-check reference in docs and design decisions
- Prerequisites:
  - none
- Risks / mismatches:
  - broad personal-brain framing does not match current biomedical workspace scope
  - markdown repo as truth owner is not the current PaperPipe contract
- Recommendation:
  - `internal ops asset`
- Smallest viable experiment:
  - use it as a language check when clarifying source-of-truth versus retrieval versus memory boundaries
- Why not now:
  - its strongest value is conceptual reinforcement, not a concrete implementation path

## OpenAI Codex use cases

- What it is:
  - capability reference and usage examples for Codex
- Which category it belongs to:
  - `3. 내부 운영 자산으로만 유효`
  - `capability reference`
- Why it matters here:
  - useful as a capability vocabulary reference
  - not useful as PaperPipe architecture guidance
- Which bottleneck it touches:
  - developer/operator understanding of what a coding agent can do
- Where it could fit in this repo:
  - development workflow reference only
- Prerequisites:
  - none
- Risks / mismatches:
  - treating provider use-case docs as architecture truth
- Recommendation:
  - `internal ops asset`
- Smallest viable experiment:
  - none
- Why not now:
  - it does not resolve current ingest, evidence, retrieval, or artifact bottlenecks

## VibeVoice

- What it is:
  - a voice-focused adjacent tool
- Which category it belongs to:
  - `5. 현재 단계에서는 과함 / 보류`
  - `low-priority adjacent tool`
- Why it matters here:
  - only weakly connected to current product bottlenecks
- Which bottleneck it touches:
  - possible future voice capture or transcript ingestion
- Where it could fit in this repo:
  - only in a future voice/transcript lane if that becomes real
- Prerequisites:
  - text-first structure and promotion flows should exist first
- Risks / mismatches:
  - voice novelty could distract from core biomedical parsing and evidence work
- Recommendation:
  - `hold`
- Smallest viable experiment:
  - none now
- Why not now:
  - voice is not a primary current bottleneck

## OpenHarness

- What it is:
  - a generalized agent harness with tools, skills, memory, session resume, permissions, and multi-agent coordination
- Which category it belongs to:
  - `3. 내부 운영 자산으로만 유효`
  - `harness / runtime`
- Why it matters here:
  - some governance ideas are useful on the development side
  - the full harness shape is not a fit for the product runtime
- Which bottleneck it touches:
  - development-side permission discipline
  - session resume ergonomics
  - background task governance
- Where it could fit in this repo:
  - dev-side inspiration only
  - possibly for narrower governance or resume patterns
- Prerequisites:
  - any adoption must stay outside canonical product truth layers
- Risks / mismatches:
  - `MEMORY.md` or injected context files being mistaken for truth owners
  - subagent and hook systems widening the product toward a generic harness
- Recommendation:
  - `internal ops asset`
- Smallest viable experiment:
  - borrow narrow permission or resume ideas in development workflow only
- Why not now:
  - current runtime already has narrower job/run/event/policy layers and does not need a harness rewrite

## supergemma4-26b-uncensored-mlx-4bit-v2

- What it is:
  - a local Apple Silicon MLX model candidate
- Which category it belongs to:
  - `5. 현재 단계에서는 과함 / 보류`
  - `local model candidate`
- Why it matters here:
  - only as a provider option
  - not as a solution to current repo bottlenecks
- Which bottleneck it touches:
  - local inference optionality only
- Where it could fit in this repo:
  - optional local benchmark slot if provider experiments are reopened
- Prerequisites:
  - a real benchmark tied to PaperPipe tasks
  - explicit safety and output-quality evaluation
- Risks / mismatches:
  - `uncensored` posture is risky for biomedical defaults
  - author benchmark claims are not enough for adoption
- Recommendation:
  - `hold`
- Smallest viable experiment:
  - optional local-reader benchmark on fixed fixtures only
- Why not now:
  - provider breadth is not the current bottleneck

## supergemma4-26b-uncensored-gguf-v2

- What it is:
  - a local GGUF / `llama.cpp` model candidate
- Which category it belongs to:
  - `5. 현재 단계에서는 과함 / 보류`
  - `local model candidate`
- Why it matters here:
  - same role as the MLX variant: optional local serving candidate only
- Which bottleneck it touches:
  - local inference optionality only
- Where it could fit in this repo:
  - optional provider benchmark lane
- Prerequisites:
  - task-grounded benchmark and safety evaluation
- Risks / mismatches:
  - `uncensored` baseline risk
  - no evidence that it improves current structured-state quality or provenance discipline
- Recommendation:
  - `hold`
- Smallest viable experiment:
  - optional GGUF benchmark on a narrow fixed slice only
- Why not now:
  - current issues are not model-availability issues

## 4. Bucket summary

### 1. 지금 바로 반영 검토 가치가 높음

- `PageIndex`
  - only as a bounded navigation pilot

### 2. 작은 범위 실험은 가치 있음

- `Sasoo`
  - only for workbench phase/grouping ideas
- Context Hub / annotation-layer thesis
  - only for a bounded annotation ledger

### 3. 내부 운영 자산으로만 유효

- `andrej-karpathy-skills`
- `gbrain`
- `OpenAI Codex use cases`
- `OpenHarness`

### 4. 장기 로드맵 참고용

- `llm-research-wiki`

### 5. 현재 단계에서는 과함 / 보류

- `VibeVoice`
- `supergemma4-26b-uncensored-mlx-4bit-v2`
- `supergemma4-26b-uncensored-gguf-v2`

### 6. 기준 레퍼런스로는 부적절 / 사실상 기각 권고

- none of the reviewed items require a full rejection as raw reading material
- but several are explicitly **not** valid as core architecture replacements:
  - `Sasoo` as backend product definition
  - `llm-research-wiki` as truth owner
  - `OpenHarness` as product runtime substrate
  - local model candidates as current bottleneck solution

## 5. Cross-reference synthesis

Common direction across the useful references:

- improve navigation before widening memory
- improve salvage before widening chat
- accumulate bounded annotations before building a broad context platform
- keep operator-visible phase clarity and review surfaces
- separate system of record, access layer, and memory layer explicitly

What the repo really needs next:

1. better long-document navigation
2. better salvage on hard PDFs
3. better locator quality visibility
4. better reusable annotation/caveat handling
5. better operator continuity without promoting raw memory into truth

Where each layer should live:

- source of truth:
  - canonical structured state and explicit evidence/source lineage
- annotation:
  - support-only additive layer
- wiki:
  - explanatory layer only
- retrieval:
  - access/navigation layer only
- session memory:
  - operational layer only
- workbench artifact:
  - derived layer only

What matters more than models right now:

- locator fidelity
- section hierarchy
- provenance visibility
- additive regeneration
- reviewable artifact contracts

What must not be overvalued:

- generalized wiki
- generalized memory
- harness memory files
- vectorless-retrieval hype
- local-model benchmark marketing

## 6. Proposed layered interpretation for current repo

### 1. Source data

- Purpose:
  - preserve imported originals
- Allowed contents:
  - PDF
  - bibliographic source data
  - immutable imported raw inputs
- Forbidden contents:
  - AI-rewritten source-of-truth replacements
- Owner of truth:
  - source records themselves
- Interaction with agent:
  - read and cite, do not silently rewrite

### 2. Context / annotation layer

- Purpose:
  - keep reusable caveats, exclusions, repeated failure notes, and review hints
- Allowed contents:
  - parser caveats
  - extraction warnings
  - reviewer notes
  - exclusion reasons
- Forbidden contents:
  - canonical biomedical truth claims without upstream anchors
- Owner of truth:
  - none; support-only
- Interaction with agent:
  - use as warning and context aid only

### 3. Wiki / explanatory layer

- Purpose:
  - give humans a readable explanation layer
- Allowed contents:
  - compiled summaries
  - explanatory pages
  - concept maps
- Forbidden contents:
  - claims that bypass canonical/evidence anchors
- Owner of truth:
  - none; derived only
- Interaction with agent:
  - phrasing and navigation help only

### 4. Retrieval / navigation layer

- Purpose:
  - help the system reopen the right parts of source and state
- Allowed contents:
  - TOC
  - section hierarchy
  - node identifiers
  - related edges
  - focus locators
- Forbidden contents:
  - summary as hidden truth owner
- Owner of truth:
  - none; access-only
- Interaction with agent:
  - fetch and reopen evidence/state efficiently

### 5. Canonical structured state

- Purpose:
  - remain the current runtime truth
- Allowed contents:
  - schema-backed paper state
  - lane-owned bounded canonical state
- Forbidden contents:
  - prompt files
  - memory files
  - wiki pages as canonical substitutes
- Owner of truth:
  - PaperPipe/Lattice runtime
- Interaction with agent:
  - primary answer-generation anchor

### 6. Harness / runtime / session governance layer

- Purpose:
  - govern execution, permissions, queueing, audit, and resume
- Allowed contents:
  - jobs
  - runs
  - events
  - audits
  - policy
- Forbidden contents:
  - biomedical truth ownership
- Owner of truth:
  - runtime operations
- Interaction with agent:
  - controls side effects and execution safety

### 7. Derived artifacts / workbench / note/export layer

- Purpose:
  - review, package, and export bounded outputs
- Allowed contents:
  - notes
  - packs
  - synthesized bundles
  - workbench views
- Forbidden contents:
  - silent replacement of canonical state
- Owner of truth:
  - downstream artifact only for its own derived payload
- Interaction with agent:
  - generate, inspect, rerender, and trace back upstream

## 7. Development-side vs agent-side judgment

### Development-side

Most relevant from this review:

- section/tree navigation experiments
- parser and OCR salvage hardening
- reusable annotation ledger
- permission and audit hygiene
- evaluation harness expansion for navigation and recovery quality

Least relevant right now:

- whole harness swaps
- provider-driven architecture changes
- voice-first workflow additions

### Agent-side

Most relevant from this review:

- better context supply from current canonical state
- better reopen paths to evidence and sections
- bounded annotation reuse
- explicit uncertainty and provenance
- stronger side-effect safety through existing governance

Least relevant right now:

- generalized persistent memory
- autonomous multi-agent loops
- prompt-file truth substitution

## 8. Ranked action list

1. action:
   - run a bounded PageIndex-style section/tree navigation pilot
   - why now:
     - it addresses a confirmed retrieval bottleneck directly
   - expected upside:
     - better navigation and reopen quality on long biomedical documents
   - risk:
     - hierarchy quality may vary by parser quality
   - size:
     - `M`
   - owner type:
     - `retrieval`

2. action:
   - freeze or extend a long-document benchmark slice for section-aware navigation evaluation
   - why now:
     - navigation changes need a fixed slice
   - expected upside:
     - comparable retrieval experiments
   - risk:
     - fixture prep cost
   - size:
     - `S`
   - owner type:
     - `eval`

3. action:
   - add a bounded annotation ledger for parser caveats and review exclusions
   - why now:
     - operator continuity is underpowered
   - expected upside:
     - less repeated failure and clearer review posture
   - risk:
     - annotation may be mistaken for truth
   - size:
     - `M`
   - owner type:
     - `backend`

4. action:
   - expose richer section/location metadata from ingest artifacts where available
   - why now:
     - navigation pilots need a bridge into current evidence/deep-link flows
   - expected upside:
     - better reopen and focus quality
   - risk:
     - parser variance
   - size:
     - `M`
   - owner type:
     - `ingest`

5. action:
   - improve workbench phase clarity using current artifacts only
   - why now:
     - Sasoo's main valid lesson is surface-level workflow staging
   - expected upside:
     - clearer operator review flow
   - risk:
     - fake phase semantics if overdesigned
   - size:
     - `S`
   - owner type:
     - `frontend`

6. action:
   - keep OCR/table salvage work tied to hard-case evaluation slices
   - why now:
     - ingest quality remains a real upstream bottleneck
   - expected upside:
     - safer parser/fallback decisions
   - risk:
     - ops cost if candidate tooling is heavy
   - size:
     - `M`
   - owner type:
     - `ingest`

7. action:
   - clarify source-of-truth versus annotation versus retrieval boundaries in follow-up docs where needed
   - why now:
     - several external references create pressure toward blur
   - expected upside:
     - lower architecture drift risk
   - risk:
     - documentation sprawl
   - size:
     - `S`
   - owner type:
     - `product`

8. action:
   - keep local-model experiments optional and benchmark-gated
   - why now:
     - preserves local-first flexibility without provider-led drift
   - expected upside:
     - optional local runtime path later
   - risk:
     - wasted effort if benchmark is weak
   - size:
     - `S`
   - owner type:
     - `infra`

## 9. Explicit non-recommendations

- do not turn wiki or annotation layers into truth owners
- do not let prompt, skill, or memory files outrank canonical structured state
- do not market vectorless retrieval as a full replacement for evidence-grounded navigation
- do not treat Sasoo workbench UX as a backend contract
- do not treat OpenHarness memory/session ideas as product runtime truth
- do not treat local model benchmarks as the main answer to current runtime bottlenecks
- do not reopen broad project/workspace/platform lanes based on external references alone

## 10. What was inspected and what remains unverified

### Inspected

- canonical product/runtime docs
- implemented ingest/parsing paths
- implemented viewer/workbench routes
- current memory/chat/project boundaries
- current compiled-knowledge lane
- current runtime governance and policy surfaces
- upstream README or model metadata for each reviewed reference

### Still unverified

- exact real-world gain from PageIndex-style navigation on PaperPipe's own long-document slice
- exact storage shape for a future bounded annotation ledger
- any trustworthy benchmark proving current value from the reviewed local models

## 11. Bottom line

This review does **not** justify a broad architecture reset.

It does justify a narrow next wave of work:

- section-aware navigation
- bounded annotation reuse
- continued salvage/evidence hardening
- clearer operator workbench staging

The current source-of-truth boundary remains correct and should stay in place.

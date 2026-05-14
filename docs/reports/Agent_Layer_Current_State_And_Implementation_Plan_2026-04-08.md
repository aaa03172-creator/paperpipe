# Agent Layer Current State And Implementation Plan (2026-04-08)

Status: working design report
Date: 2026-04-08
Owner: runtime maintainers
Canonical status: not canonical; this is a dated repo-grounded planning note

Related docs:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `docs/RESEARCH_DNA.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

## Purpose

Record the current PaperPipe repository state after a repo-first read plus original-source review of the cited references, then turn that reading into a smallest-safe implementation plan.

This report is not a new runtime spec.

It exists to:
- prevent speculative agent-layer rewrites
- keep raw source, raw memory, compiled knowledge, and canonical state separate
- identify the smallest next implementation slices that fit the current repo

## 1. Current repo reading

### 1.1 Confirmed current center

Current PaperPipe/Lattice remains:
- paper-first
- job/run/artifact-first
- local-first
- single-operator-first
- evidence-linked
- human-reviewable

Current PaperPipe is not yet:
- a first-class project/workspace platform
- a broad chat or memory runtime
- a generalized entity registry for project / decision / experiment / task

### 1.2 Confirmed active runtime surfaces

The current runtime already has:
- deep-read orchestration with ingest, index, read, verify
- paper-scoped structured state promotion
- bounded derived artifact families
- event/activity logging
- runtime/provider abstraction
- evidence and uncertainty policy enforcement

The current runtime does not have:
- a live general chat memory lane
- a project-scoped canonical runtime owner
- a generalized multi-agent orchestration framework

### 1.3 Layer-by-layer assessment

| Layer | Current repo status | Notes |
| --- | --- | --- |
| Raw source layer | exists | PDFs, bibliographic inputs, notes, file imports, bounded source-side adapters already exist |
| Raw memory layer | partial | `execution_runs`, `job_events`, `user_actions`, and backend-only `project_memory` exist, but remain non-canonical and intentionally product-gated |
| Compiled knowledge layer | partial | bounded artifact families already behave like derived outputs, and the current worktree includes an untracked `paper_syntheses` slice that is directionally aligned but not yet confirmed as landed baseline |
| Canonical structured state | exists but paper-scoped | `StructuredPaperState` is real today, but current repo does not yet approve a broader canonical project/workspace model |
| Review / gate layer | partial but real | evidence policy, grounding, reader eval, teacher review, quality gates, acceptance contracts already exist in additive form |
| Runtime abstraction layer | exists | local / cloud / hybrid providers plus install-layout/runtime-path abstraction already exist |
| User-facing artifact layer | exists | note mirrors, meeting packs, protocol cards, method comparisons, image evidence, chart packs already exist as derived surfaces |

## 2. Reference fit review

### 2.1 Karpathy `llm-wiki` gist

Strong fit:
- raw source stays separate from compiled wiki
- schema-guided assets are useful
- compiled markdown can be a durable navigation layer

Safe PaperPipe interpretation:
- use this as compiled-knowledge guidance only
- do not treat compiled markdown as canonical scientific truth

Reference:
- `https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f`

### 2.2 MemPalace

Useful fit:
- verbatim raw-memory retention
- retrieval-oriented support layer
- local-first bias

Unsafe PaperPipe interpretation:
- do not let raw-memory retrieval become the primary owner of biomedical truth
- do not let conversational or free-form memory outrank canonical evidence-linked state

Reference:
- `https://github.com/milla-jovovich/mempalace`

### 2.3 claude-sisyphus-grad

Useful fit:
- explicit research logs
- reviewer/judge separation
- auditability of iterative research work

Unsafe PaperPipe interpretation:
- do not import autonomous loop posture
- do not introduce generic experiment-orchestration or code-mutation loops into the current biomedical workspace runtime

Reference:
- `https://github.com/Hwiyeon/claude-sisyphus-grad`

### 2.4 Lemonade

Useful fit:
- local runtime abstraction
- OpenAI-compatible serving posture

Safe PaperPipe interpretation:
- use as a provider/runtime-compatibility reference only
- do not let runtime product choice leak into canonical contracts

Reference:
- `https://lemonade-server.ai/`

### 2.5 Karpathy X post

The original X post URL is confirmed, but the exact post text was not reliably retrievable in this environment.

Current safe posture:
- treat the linked gist as the directly verified source
- do not attribute exact wording from the X post unless re-verified later

Reference:
- `https://x.com/karpathy/status/2039805659525644595`

## 3. Current judgment

The current repo is closer to the requested layer model than it first appears.

The main gap is not “missing architecture.”

The main gap is:
- missing explicit layer taxonomy for agents and developers
- uneven enforcement of derived-vs-canonical boundaries across newer lanes
- lack of one compact implementation plan that hardens these boundaries without reopening closed scope

## 4. Already exists / partial / missing / should not add yet

### Already exists

- paper/job/artifact-first canonical posture
- paper-scoped structured state
- evidence-first claim policy
- provenance/gate artifacts for deep-read
- bounded derived artifact lanes
- local/cloud/hybrid provider abstraction
- local-first runtime path abstraction

### Partially exists

- compiled knowledge as a dedicated layer
- raw memory as a bounded support layer
- reviewer/judge separation
- project context as a UX concept without canonical ownership
- shared gate vocabulary across derived artifact families

### Missing but needed

- a compact active rule that explicitly classifies outputs by layer
- a standard contract for compiled knowledge assets
- a rule that raw-memory retrieval can assist but cannot silently promote biomedical answers
- a reusable minimal provenance/uncertainty gate for compiled outputs

### Should not be added yet

- generalized memory/chat runtime
- first-class project/workspace canonical object model
- universal object registry for decision/task/experiment/claim/evidence
- autonomous maintenance or self-rewriting loops
- compiled wiki as a replacement for canonical state
- memory-first answer generation for biomedical truth

## 5. Smallest-safe implementation plan

### Step 1. Layer taxonomy hardening

Goal:
- make the layer boundary explicit for agents and maintainers

Why first:
- this reduces future drift without changing runtime product scope

Likely files:
- `AGENTS.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- possibly one small active note only if the existing notes become too crowded

Proposed output:
- one explicit taxonomy covering:
  - raw source
  - raw memory
  - compiled knowledge
  - canonical structured state
  - review/gate artifacts
  - user-facing exports

Guardrail:
- extend existing canonical notes if possible rather than creating a parallel master doc

Verification:
- docs-only consistency pass

### Step 2. Compiled knowledge contract hardening

Goal:
- treat `paper_syntheses` as the first formal compiled-knowledge pilot

Why second:
- this is the closest current worktree implementation to the requested Karpathy-style compiled layer

Likely files:
- `src/schemas/paper_synthesis.py`
- `src/paper_syntheses/service.py`
- `src/paper_syntheses/renderer.py`
- `tests/test_paper_synthesis_service.py`
- `tests/test_paper_synthesis_store.py`

Proposed output:
- explicit derived-layer metadata such as:
  - stronger source lineage requirements
  - explicit uncertainty and freshness preservation
  - optional layer classification field if it helps downstream consumers

Guardrail:
- do not turn paper synthesis into canonical truth or a second promoted state owner
- if this slice is still untracked at execution time, treat it as an adoption/hardening step on current worktree code rather than as a baseline-only refactor

Verification:
- targeted pytest for paper synthesis service/store

### Step 3. Raw-memory and gate boundary hardening

Goal:
- keep memory helpful but non-canonical
- reuse minimal gate semantics across derived outputs

Why third:
- this is where future drift risk is highest

Likely files:
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md` or a small follow-up report if clarification is needed
- selective gate docs or lane docs where compiled assets present biomedical content

Proposed output:
- explicit rule that raw memory cannot be sole support for biomedical answers
- explicit non-canonical raw-memory status on `Project Memory` records
- no API/viewer expansion by implication

## 6. Implementation status on 2026-04-08

The first three bounded slices were partially landed during this pass.

Implemented:
- Step 1 layer taxonomy hardening in:
  - `AGENTS.md`
  - `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
  - `docs/PaperPipe_Minimum_Operating_Principles.md`
- Step 2 minimal compiled-knowledge hardening in the current `paper_syntheses` worktree slice:
  - `src/schemas/paper_synthesis.py`
  - `src/paper_syntheses/service.py`
  - `src/paper_syntheses/renderer.py`
  - `tests/test_paper_synthesis_service.py`
  - `tests/test_paper_synthesis_store.py`
- Step 3 raw-memory boundary hardening in the tracked `Project Memory` slice:
  - `src/schemas/project_memory.py`
  - `tests/test_project_memory_schema.py`
  - `tests/test_project_memory_store.py`
  - `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

What changed in Step 2:
- `PaperSynthesis` now carries an explicit `layer="compiled_knowledge"` marker.
- The synthesis source-ref vocabulary now allows additive `quality_gate` and `acceptance_contract` entries.
- The service includes those review artifacts as optional provenance refs only when present.
- The rendered markdown now prints the layer marker and preserves the “derived, not canonical” framing.
- Warning behavior now surfaces non-pass quality-gate states as explicit review-only signals.

What changed in Step 3:
- `ProjectMemoryWorkspace` and `ProjectMemoryItem` now carry explicit `layer="raw_memory"` markers.
- The same models now carry `canonical_status="non_canonical"` so saved records do not masquerade as promoted runtime truth.
- Store/schema tests now verify those markers survive round-trip persistence.
- The active API-gate note now records those markers as part of the current backend-only contract.

Verification run:
- `python3 scripts/lint_docs.py`
- `pytest -q tests/test_paper_synthesis_service.py tests/test_paper_synthesis_store.py`
- `pytest -q tests/test_project_memory_schema.py tests/test_project_memory_store.py`

Remaining caution:
- The `paper_syntheses` slice remains current-worktree code and is not confirmed here as a landed tracked baseline.
- `Project Memory` remains backend-only; these markers clarify boundaries but do not approve an API or viewer.
- A small shared gate vocabulary for other derived outputs is still only partially reused outside the deep-read and `paper_syntheses` lanes.

Guardrail:
- do not reopen `Project Memory` API or viewer scope by “boundary clarification” work

Verification:
- docs consistency plus targeted tests for touched schema/store slices

## 7. Additional implementation status on 2026-04-08

One more bounded tracked lane was hardened after the first report pass.

Implemented:
- Step 4 minimal gate-vocabulary reuse in the tracked `method_comparison` slice:
  - `src/schemas/method_comparison.py`
  - `src/method_comparisons/service.py`
  - `src/method_comparisons/renderer.py`
  - `tests/test_method_comparison_schema.py`
  - `tests/test_method_comparison_service.py`
  - `tests/test_method_comparison_store.py`

What changed in Step 4:
- `MethodComparison` now carries `layer="user_facing_artifact"` and `canonical_status="non_canonical"`.
- The schema now exposes bounded `readiness` and `freshness` fields.
- The service now derives `readiness` from evidence-ref presence plus warning state, keeps `freshness` at `unknown` until a real freshness signal exists, and surfaces conflict cells as explicit warnings.
- The rendered markdown now prints the derived-artifact framing plus a promotion guardrail.

Verification run:
- `pytest -q tests/test_method_comparison_schema.py tests/test_method_comparison_service.py tests/test_method_comparison_store.py tests/test_method_comparisons_api.py`

Remaining caution:
- This is still a bounded gate-vocabulary reuse, not a generalized cross-lane artifact framework.

## 8. Docs-only boundary clarification on 2026-04-08

One small docs-only guardrail slice was landed after the lane hardening work.

Implemented:
- Step 5 answer-generation boundary clarification in active notes:
  - `docs/PaperPipe_Minimum_Operating_Principles.md`
  - `docs/Evidence_and_Uncertainty_Rules.md`
  - `docs/API_CHAT_CONTRACT.md`

What changed in Step 5:
- The operating note now states that promoted biomedical answers should route through canonical structured state first and upstream evidence lineage second.
- The evidence rule now makes answer-generation routing explicit and adds `canonical_status` to the recommended compact trust vocabulary for derived or memory lanes.
- The stub-only chat contract now records the same boundary for any future live `/api/chat` implementation.

Verification run:
- `python3 scripts/lint_docs.py`

Remaining caution:
- This is a guardrail clarification only; it does not create a live chat runtime or a generalized answer-orchestration layer.

## 9. Recommended stop point

Default recommendation now:
- stop structural widening unless a specific tracked lane has an immediate product need
- preserve the current lane-by-lane guardrails instead of introducing a shared artifact framework

Only reopen implementation if:
- a tracked lane now needs the same non-canonical framing for a real user-facing reason
- a lane can support the change with local tests and without broad schema/platform expansion

## 10. Additional implementation status on 2026-04-09

One more tracked user-facing lane was hardened after the previous stop point.

Implemented:
- Step 6 minimal non-canonical framing for the tracked `meeting_pack` lane:
  - `src/schemas/meeting_pack.py`
  - `src/meeting_packs/renderer.py`
  - `tests/test_meeting_pack_schema.py`
  - `tests/test_meeting_pack_store.py`
  - `tests/test_meeting_pack_service.py`
  - `tests/test_meeting_pack_api.py`

What changed in Step 6:
- `MeetingPack` now carries `layer="user_facing_artifact"` and `canonical_status="non_canonical"`.
- The rendered markdown now surfaces the same derived-artifact framing and promotion guardrail already used in other bounded user-facing lanes.
- Existing `readiness`, trace, and handoff semantics were preserved rather than replaced with a new shared framework.

Verification run:
- `pytest -q tests/test_meeting_pack_schema.py tests/test_meeting_pack_store.py tests/test_meeting_pack_service.py tests/test_meeting_pack_api.py tests/test_meeting_pack_handoff_artifacts.py`

Remaining caution:
- This keeps `Meeting Pack` aligned with the boundary work, but it still does not justify a generalized cross-lane artifact abstraction.

## 11. Consolidation checkpoint on 2026-04-09

Checkpoint result:
- the current boundary-hardening slices coexist without test regressions in the touched schema/store/service/API paths
- the safest next move is to hold the boundary here until a concrete lane-specific product need appears

Verification run:
- `pytest -q tests/test_paper_synthesis_service.py tests/test_paper_synthesis_store.py tests/test_project_memory_schema.py tests/test_project_memory_store.py tests/test_method_comparison_schema.py tests/test_method_comparison_service.py tests/test_method_comparison_store.py tests/test_method_comparisons_api.py tests/test_meeting_pack_schema.py tests/test_meeting_pack_store.py tests/test_meeting_pack_service.py tests/test_meeting_pack_api.py tests/test_meeting_pack_handoff_artifacts.py`

## 12. Decision summary

The safest current move is not to invent a new agent platform.

The safest current move is to:
- formalize the layer taxonomy
- harden the existing compiled-knowledge pilot
- keep raw memory subordinate
- reuse additive provenance/gate semantics

That fits the current PaperPipe repo better than any broad architecture rewrite.

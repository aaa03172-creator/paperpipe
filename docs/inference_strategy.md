# Inference Strategy

Status: Active operating note
Date: 2026-04-13
Owner: Runtime/product maintainers
Canonical: `docs/inference_strategy.md`

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `docs/runtime_security_env.md`

Related docs:
- `docs/inference_data_boundary.md`
- `docs/inference_routing_policy.md`
- `docs/reports/Inference_Backend_Strategy_Review_2026-04-10.md`
- `docs/reports/Personal_Runtime_Deployment_Architecture_2026-03-28.md`

## Purpose

Define the smallest durable inference strategy that fits the current PaperPipe/Lattice repo without reopening product scope.

This note is for:

- separating `local-first data ownership` from `local-only inference`
- keeping inference backend choice subordinate to the current paper/job/artifact runtime
- setting the safest near-term operating recommendation for average lab hardware

This note is not:

- a new master spec
- a promise of a broad chat runtime
- a license to centralize canonical data into a shared service

## Current Judgment

The current recommended product posture is:

- `desktop-first personal runtime`
- `local canonical data`
- `local retrieval/index/state ownership`
- `selective external inference for difficult reasoning`
- `optional local model and optional future lab server`

In short:

`local-first data, hybrid inference`

This is the safest interpretation of the current repo for average-hardware operator distribution.

## 1. What "local-first" means here

In this repo, `local-first` primarily means:

- canonical state stays operator-scoped
- source data and notes stay operator-scoped
- retrieval and indexing should not depend on a shared hosted truth store
- the product unit remains `one operator = one runtime`

It does not automatically mean:

- every operator machine must run a strong local LLM
- every reasoning task must be executed on-device
- product success should depend on per-user GPU availability

## 2. Product unit stays personal runtime

Inference strategy must preserve the current deployment shape:

- personal runtime per operator
- local install first
- managed single-tenant hosting second
- shared multi-user stateful service not recommended as the default product unit

Inference routing may become more flexible.

Canonical ownership may not.

## 3. Core strategy

### 3.1 Recommended near-term shape

For the current repo stage, prefer:

1. local personal runtime
2. local canonical data + local search/index
3. same-origin backend API
4. selective inference backend routing

Recommended routing posture:

- local model:
  - optional
  - good for lightweight or offline-tolerant tasks
- commercial inference:
  - allowed for hard reasoning, final synthesis, and evaluator/judge lanes
- lab inference server:
  - optional institution path
  - not the default product assumption

### 3.2 Recommended operator-facing default

For average-hardware distribution, the recommended product strategy is functionally equivalent to:

- `Hybrid 1`
  - data local
  - search local
  - notes local
  - hard reasoning external when needed

This note does not rewrite the current `llm.mode` config contract.

It clarifies product deployment guidance:

- `local-first` should remain the data/runtime posture
- average-hardware operator distribution should not assume local-only inference as the default success path

## 4. Why local-only is not the default product strategy

Strong local open models are now real and useful.

That still does not make `per-user local-only inference` the safest default product strategy because:

- average lab PCs are heterogeneous
- GPU availability is unreliable
- memory and VRAM requirements vary sharply by model size and quantization
- install/support burden increases materially
- runtime speed and failure modes become hardware-dependent

Local models therefore remain:

- valuable
- supported
- strategically important

but they are not the required baseline for all operator environments.

## 5. Why commercial-only is also not the product strategy

Commercial-only is too aggressive for the current repo because it risks:

- eroding local-first product identity
- widening the data boundary unnecessarily
- centralizing more runtime responsibility than the current product shape warrants
- turning a personal runtime into a thin client for a hosted system

Therefore:

- commercial inference may be important
- commercial ownership of canonical state is not

## 6. Backend roles

### 6.1 Local model role

Best current fit:

- slot classification
- tagging
- one-liners
- lightweight extraction
- embeddings when the local environment is provisioned
- fallback when external inference is unavailable

### 6.2 Commercial inference role

Best current fit:

- difficult reasoning
- final synthesis
- evaluator/judge lanes
- high-ambiguity answer composition
- difficult escalation decisions

### 6.3 Lab server role

Best current fit:

- institution-managed open-model serving
- cost-sensitive teams that still want strong centralized inference
- privacy posture stricter than public commercial API routing

Current rule:

- lab server is an optional backend slot, not the baseline product assumption

## 7. Thin relay rule

If commercial inference is used, the safest current shape is a thin relay or same-origin backend path that handles:

- vendor authentication
- request signing
- rate limiting
- budget enforcement
- audit metadata
- optional response caching

That relay must not become:

- the canonical data owner
- the note/wiki owner
- the primary runtime state owner
- a hidden shared workspace backend

## 8. Boundaries that must stay true

- client-side vendor API keys are not allowed
- canonical structured state remains local/operator-scoped
- compiled knowledge remains non-canonical
- raw memory remains support-only
- future answer generation must route through evidence-linked state rather than memory-first shortcuts

## 9. What this note deliberately does not adopt

This note does not adopt:

- a broad chat/memory runtime
- a mandatory local model requirement for every operator
- a shared multi-tenant inference+state platform
- a promise that all future backends will be exposed as equal user-facing options
- a change to current Pydantic contracts or runtime truth ownership

## 10. Operational summary

Current safest recommendation:

- keep data local
- keep search local
- keep state local
- use external inference selectively
- treat local models as valuable optional capability
- keep lab server as a future institution slot

If there is doubt about where a new inference path belongs:

- default to the stricter data boundary
- default to smaller excerpts
- default to preserving local ownership

# Prompt Review 02: Auton Agentic P0 Absorption (2026-03-11)

Status: Historical prompt fit review  
Date: 2026-03-11  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## Source References
- Paper: [arXiv:2602.23720](https://arxiv.org/abs/2602.23720)
- Reference repo: [karpathy/autoresearch](https://github.com/karpathy/autoresearch)

## Reference Summary
The `Auton` paper is much broader than what PaperPipe should absorb now. The useful P0 slice is:
- blueprint/runtime separation
- contract-driven outputs
- deterministic failure handling
- auditability

The rest of the paper is not a good current fit:
- reflector-style consolidation
- DAG scheduling/speculative execution
- constraint manifold enforcement
- RL/self-evolution
- full MCP migration

Those should stay parked.

## Current PaperPipe Fit
This prompt is partly aligned, but several requested deliverables conflict with the existing codebase.

Current PaperPipe already has:
- canonical structured sidecar state:
  - `.pp/<slug>/state.json`
- per-run raw audit output:
  - `.pp/<slug>/runs/<ts>_<action>.json`
- small frontmatter signals:
  - `pp.signals`
- skill output contracts:
  - `src/schemas/skills.py`
- runtime policy gating:
  - `config/skills_policy.yaml`
  - `src/skills/policy.py`
- strong artifact contracts outside skills:
  - `src/contracts/document_artifact_v2.py`

Because of that, the prompt should not create a parallel contract stack or a second canonical policy source.

## What Should Change
1. Do not introduce `paperpipe/contracts/*`.
   - This repo already uses `src/schemas/` and `src/contracts/`.
   - Any new skill/runtime contract work should extend those existing namespaces.

2. Do not duplicate the active skills policy.
   - `config/skills_policy.yaml` is already the runtime policy source.
   - A future `blueprints/skills/` layer may describe or generate policy, but should not silently fork it.

3. Treat audit trail as mostly implemented, not greenfield.
   - `/skills/run` already writes raw run JSON, merges canonical state, and updates only small frontmatter signals.
   - The gap is documentation/examples/validator hardening, not inventing the whole flow.

4. Keep `blueprints/ui/` minimal and documentation-only for now.
   - Current next queued frontend work is `PR-FE-Workbench-Contextual-State-Badges`.
   - That should not be blocked by a new UI blueprint system unless the scope is explicitly widened.

## Adapted Prompt
Use this version instead of the original prompt:

```text
[REF] arXiv:2602.23720 “The Auton Agentic AI Framework”
https://arxiv.org/abs/2602.23720

Goal:
Absorb only the P0 ideas that fit the current PaperPipe architecture:
- blueprint/runtime separation where it reduces duplication
- contract-driven skill/runtime outputs
- deterministic failure recording
- auditable per-run traces

DO (P0 only)
1) Blueprint/Runtime split, but without duplicating existing canonicals
- introduce `blueprints/` only for static agent-facing definitions
- preferred initial scope:
  - `blueprints/search/`
  - `blueprints/skills/`
- runtime code stays where it is and reads blueprint data when applicable
- do not replace existing canonical runtime policy files without an explicit migration plan
- deliverable: `docs/BLUEPRINT_RUNTIME.md`

2) Contract-driven outputs, using existing repo namespaces
- extend `src/schemas/` and/or `src/contracts/` for any missing skill action result contracts
- add a validator layer around `/skills/run` result normalization/validation
- on validation failure:
  - retry normalize/parse up to bounded N
  - if still invalid, record a consistent failed status plus raw error detail

3) Audit trail hardening on top of the existing skills flow
- keep `.pp/<slug>/runs/<ts>_<action>.json` as the raw per-run record
- keep `.pp/<slug>/state.json` as the canonical merged state
- keep frontmatter limited to compact `pp.signals` updates
- deliverable: `docs/AUDIT_TRAIL.md` with examples from the current skills runtime

PARK (doc only, no implementation)
- reflector-driven consolidation
- DAG parallelization / speculative execution / context pruning
- constraint manifold enforcement
- RL/self-evolution
- full MCP migration

Deliverables for a later implementation pass:
- `docs/AUTON_AGENTIC_NOTES.md`
- `docs/BLUEPRINT_RUNTIME.md`
- `blueprints/` with one minimal example
- validator-layer design or implementation in existing `src/schemas/` / `src/contracts/` lanes
- `docs/AUDIT_TRAIL.md`

Acceptance:
- identical input should either validate successfully or fail with a stable recorded status
- blueprint diffs should explain behavior changes without reading arbitrary runtime code diffs
- P1/P2 items remain documented-only and are not implemented
```

## Recommended Future Path
If this prompt is executed later, the clean implementation order is:
1. document the current blueprint/runtime boundary first
2. harden `/skills/run` validation/failure recording using existing schemas
3. only then add minimal `blueprints/` files that point to current canonicals instead of replacing them

This avoids a migration where `blueprints/`, `config/skills_policy.yaml`, and `src/schemas/skills.py` all drift separately.

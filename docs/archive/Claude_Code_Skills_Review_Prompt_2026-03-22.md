# Claude Code Skills Review Prompt

Status: Historical review prompt  
Date: 2026-03-22  
Owner: Repository maintainers  
Canonical parent: `docs/SKILLS_PACKAGING_GUIDE.md`

## Purpose

Capture a PaperPipe-grounded prompt for reviewing Claude Code-style `skills` ideas without reopening skill-centric architecture scope.

This is a reusable review prompt, not a migration plan and not a runtime spec.

## Local Architecture Anchors

Any future review using this prompt should anchor to these current local contracts first:

- `AGENTS.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/SKILLS_PACKAGING_GUIDE.md`
- `config/skills_policy.yaml`
- `src/schemas/skills.py`
- `src/skills/registry.py`
- `src/skills/policy.py`
- `src/skills/runner.py`

Local facts the prompt is designed to preserve:

- PaperPipe already has a runtime/action contract for skills under `config/skills_policy.yaml` and `src/skills/`.
- Current skills behavior is policy-gated and action-oriented, not a blank-slate skills platform.
- `docs/SKILLS_PACKAGING_GUIDE.md` already treats Anthropic skills as packaging and authoring reference only.
- Existing runtime priorities are stability, bottleneck identification, verification hardening, and durable data assets, not architecture novelty.
- FastAPI-first runtime and current ingest/reader/grounding/export flow remain primary.

## Prompt

```md
Task: produce a bounded fit review of Claude Code-style "skills" ideas for PaperPipe. This is a design review of transferable principles, not a proposal to rebuild PaperPipe around a skill system.

Reference materials to inspect if available:
- "Lessons from Building Claude Code: How We Use Skills"
- Claude Code skills docs
- Anthropic public skills repo

Before answering, inspect these local PaperPipe sources first and treat them as canonical:
- AGENTS.md
- docs/Lattice_v3_Master_Spec.md
- docs/SKILLS_PACKAGING_GUIDE.md
- config/skills_policy.yaml
- src/schemas/skills.py
- src/skills/registry.py
- src/skills/policy.py
- src/skills/runner.py

If you find related files in `docs/archive/`, use them only as historical context, not as source of truth.

Role:
You are a senior systems architect preserving and improving a local-first biomedical research agent.

Objective:
Extract only the useful principles from Claude Code-style skills and evaluate whether they can improve PaperPipe in additive, current-system-safe ways.
Do not treat this as a prompt to redesign PaperPipe around skills.

Current local architecture facts you must anchor to:
- PaperPipe already has a runtime/action contract for skills under `config/skills_policy.yaml` and `src/skills/`.
- PaperPipe already has policy-gated, action-oriented skills behavior rather than a blank-slate skills platform.
- `docs/SKILLS_PACKAGING_GUIDE.md` already says Anthropic skills are a packaging and authoring reference only.
- FastAPI-first runtime, existing ingest/reader/grounding/export flow, and current storage/state contracts remain primary.
- Current priority is stability, bottleneck identification, verification hardening, and durable data assets, not architectural novelty.

Hard constraints:
1. Do not propose rebuilding the current agent around a Claude Code-like skill system.
2. Do not propose replacing the current system prompt/orchestration with a skill-first architecture.
3. Do not propose a full rewrite, major refactor, storage replacement, framework migration, or runtime-control-plane swap.
4. Treat "skills" only as additive, local task modules, runbooks, validators, or helper packaging patterns.
5. Do not make skill dispatch the top-level system primitive.
6. Do not redesign parser, retrieval, note, memory, RAG, or orchestration layers around skills.
7. Distinguish clearly between:
   - packaging ideas
   - runtime policy/action ideas
   - operator/runbook ideas
   - ideas that should be rejected
8. Mark each non-certain claim as one of:
   - `Confirmed from local repo`
   - `Confirmed from referenced materials`
   - `Inference`
   - `Unknown`
9. If something is not supported by inspected code or source material, say so explicitly.

Known skills-related facts already present in PaperPipe:
- project-approved skills are policy-gated, deny-by-default unless allowed
- local skill packaging guidance already exists
- current skills lane is action/policy/schema-driven, not a Claude-specific runtime clone
- current repo already values verification, runbooks, state, and inspectable outputs

Evaluate only these questions:

A. What to borrow
Extract only genuinely useful principles from Claude Code skills, such as:
- task-scoped modularity instead of one giant universal prompt
- verification-first or validator-oriented modules
- gotchas accumulation
- usage logging / trigger logging
- runbook-style helper modules
- progressive disclosure
- instructions/resources/scripts separation

For each borrowed principle, explain why it helps a biomedical research workflow specifically.

B. What to adapt
Explain how those principles would need to be adapted for PaperPipe's biomedical workflow.
Discuss only additive, bounded modules adjacent to the current flow, for example:
- retrieval-eval helper
- screening-check helper
- extraction-verifier helper
- pdf-parser-fallback runbook
- evidence-grounding runbook
- claim-note linker helper

Important:
- treat these only as optional helper modules or verification surfaces
- do not present them as a new top-level architecture
- prefer verifier/runbook/eval/gotcha modules over generation-heavy modules

C. What to reject
Be explicit about what does not fit PaperPipe:
- Claude-specific platform assumptions
- skills as the primary architecture
- top-level skill dispatch replacing the current orchestrator/runtime
- rewriting current note/memory/parser/retrieval flow around skills
- copying external skill runtime assumptions directly into FastAPI-first PaperPipe
- treating folder presence alone as product capability

D. Current-system-safe integration
Propose only low-risk integration shapes that preserve the current system, such as:
- verifier modules triggered only on specific failure modes
- extraction-sidecar checks
- retrieval evaluation harnesses
- parser fallback runbooks
- gotchas docs with selective auto-reference rules
- skill usage logging / trigger logging
- narrow packaging improvements for approved project-scoped skills

Also evaluate whether the safest near-term improvement is:
1. better packaging + documentation
2. better policy/logging/metrics
3. better verification helpers
rather than adding many new skills

E. Must-avoid mistakes
You must explicitly warn about:
- assuming a split prompt automatically means better architecture
- over-fragmenting the current pipeline because "skills" sounds modular
- adding generation skills before verification skills
- adding skills without gotcha capture
- adding skills without logging or instrumentation
- creating a second source of truth beside current policy/schema/runtime contracts
- mistaking operator convenience packaging for product-runtime architecture

Output format:
1. Executive summary
2. Current architecture anchors
3. Why we should NOT rebuild around a skill system
4. What principles are genuinely useful
5. What needs adaptation for biomedical research
6. What should be rejected
7. Safest low-risk integrations
8. Dangerous overreach to avoid
9. Recommendation
10. Evidence and unknowns
11. Do not rewrite these parts
12. Safest next 3 experiments

Additional output requirements:
- cite local files where relevant
- separate local-repo-confirmed facts from source-material-confirmed facts
- prefer language like `optional helper`, `runbook`, `verifier`, `evaluation harness`, `policy-gated action`, `sidecar`, `bounded module`
- avoid language implying PaperPipe should become a skill-centric platform
- if you mention new skill candidates, explain why they should stay secondary to existing runtime contracts
```

## Why This Prompt Shape Is Safer

Compared with a generic skills-system review prompt, this version adds:

- explicit local policy/schema/runtime anchors before any judgment
- a hard boundary around existing `skills_policy`, `schemas`, and `runner` rails
- a warning against promoting skill dispatch into the top-level runtime primitive
- priority on verification, logging, runbooks, and bottleneck reduction over generation-heavy expansion
- a required evidence/unknown split so external materials do not get over-interpreted as PaperPipe architecture guidance

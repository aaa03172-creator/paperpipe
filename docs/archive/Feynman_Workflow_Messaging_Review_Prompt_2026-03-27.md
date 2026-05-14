# Feynman Workflow/Messaging Review Prompt

Status: Historical review prompt  
Date: 2026-03-27  
Owner: Repository maintainers  
Canonical parents:
- `AGENTS.md`
- `docs/Product_Positioning_Principles.md`

## Purpose

Capture a PaperPipe-grounded prompt for reviewing what `getcompanion-ai/feynman` can teach the repo about workflow framing, artifact-centered messaging, and docs structure without drifting into generic research-agent positioning or runtime redesign.

This is a reusable review prompt, not an adoption plan, not a migration plan, and not a new product definition.

## Local Anchors

Any future review using this prompt should inspect these local PaperPipe sources first and treat them as canonical:

- `README.md`
- `docs/README.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/WEB_VIEWER.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `frontend/src/App.tsx`
- `backend/main.py`

Local facts the prompt is designed to preserve:

- The current first-product story is paper-first, job/run/artifact-first, local-first, and single-operator-first.
- Current core supported surfaces are paper notes, workbench, deep-read jobs, `Research DNA`, `Meeting Pack`, and bounded artifact viewers.
- `/api/chat` is not a valid basis for chatbot-first messaging.
- `Project Memory` remains gated and must not be used to imply a project-centric runtime.
- Reasoning persona, profile context, and output/view mode are separated concerns; they must not be collapsed into Feynman-style runtime agent roles by default.
- The current README is a runtime guide and should not be turned into a generic landing page or an overclaimed product brochure.

## Official Target Facts Already Verified

As of 2026-03-27, the public `feynman` README shows these baseline facts:

- it presents itself as an open source AI research agent
- it uses task-first command framing such as `deepresearch`, `lit`, `review`, `audit`, `replicate`, `compare`, `draft`, `autoresearch`, `watch`, and `outputs`
- it presents four bundled research-agent roles: `Researcher`, `Reviewer`, `Writer`, and `Verifier`
- it emphasizes artifact outputs, source-grounding, and product-like installation/packaging
- it offers both a full terminal app and installable research skills

These target facts are useful for comparison, but they must not be treated as approval to redefine PaperPipe around a generic multi-agent research shell.

## Prompt

```md
Task: produce a bounded fit review of what PaperPipe can selectively learn from `getcompanion-ai/feynman` for README, product messaging, workflow naming, and docs structure. This is not a redesign of PaperPipe around Feynman.

Reference:
- https://github.com/getcompanion-ai/feynman

Before answering, inspect these local PaperPipe sources first and treat them as canonical:
- README.md
- docs/README.md
- docs/Lattice_v3_Master_Spec.md
- docs/Product_Positioning_Principles.md
- docs/reports/First_Shippable_Product_Bar_2026-03-24.md
- docs/reports/First_Product_Baseline_QA_2026-03-25.md
- docs/PERSONA_MODE_BOUNDARY.md
- docs/WEB_VIEWER.md
- docs/RESEARCH_DNA.md
- docs/MEETING_PACK.md
- frontend/src/App.tsx
- backend/main.py

If you find related files in `docs/archive/`, use them only as historical context, not as source of truth.

Role:
You are a senior AI systems engineer and product architect reading the real repository before making recommendations.

Important framing:
- Do not treat this as a prompt to imitate or re-platform around Feynman.
- Do not redefine PaperPipe as a generic research agent.
- Do not redefine the current product around first-class projects/workspaces unless local canonical docs already support that.
- Do not turn Feynman-style roles into a required multi-agent runtime.
- Do not invent task commands or CLI verbs that the current repo does not actually implement.

Current local product facts you must anchor to:
- The current first-product story is paper-first, job/run/artifact-first, local-first, and single-operator-first.
- Current core supported surfaces are paper notes, workbench, deep-read jobs, Research DNA, Meeting Pack, and bounded artifact viewers.
- `/api/chat` is not a valid basis for chatbot-first messaging.
- `Project Memory` remains gated and should not be used to imply a project-centric runtime.
- Reasoning persona, profile context, and output/view mode are separated concerns; do not collapse them into Feynman-style agent roles by default.

Evaluate the current repo against these four axes only:
1. workflow/task visibility
2. artifact-centered UX and messaging
3. role separation clarity
4. product-message honesty

For each axis, report:
- what the current repo already does well
- what is weak or unclear
- what can be borrowed from Feynman only after adaptation
- what must not be adopted

Allowed recommendation scope:
- README structure improvement
- product copy refinement
- workflow/task naming in docs
- docs information architecture
- clearer explanation of existing roles/personas/modes if already present
- stronger artifact-centered expression of current capabilities

Disallowed:
- full architecture rewrite
- new canonical abstractions that conflict with current data/state contracts
- movement toward generic research-agent positioning
- exaggerated claims
- front-page promises for unimplemented or partial features
- making task-taxonomy docs sound like implemented CLI commands if they are not

Output format:
1. Current repo reading summary
2. What to adopt from Feynman
3. What not to adopt
4. Recommended changes (Immediate / Small implementation / Later)
5. Concrete proposed edits
6. Patch plan

Additional requirements:
- separate repo-confirmed facts from inferences
- if you mention roles, explain whether they are documentation taxonomy, reasoning personas, or runtime agents
- if you mention commands, distinguish clearly between:
  - implemented CLI/runtime commands
  - API routes
  - documentation workflow labels
- prefer wording like `bounded workflow`, `artifact viewer`, `paper-first workspace`, `local-first evidence workflow`
- avoid wording that implies PaperPipe already offers broad autonomous research completion
```

## Why This Prompt Shape Is Safer

Compared with a generic "learn from Feynman" prompt, this version adds:

- explicit local canonical anchors before any comparison
- a hard boundary around PaperPipe's current paper-first, job/run/artifact-first product shape
- a warning against treating `Project Memory` or `/api/chat` as evidence of a broader workspace/chatbot runtime
- a distinction between task-taxonomy docs, API routes, and actually implemented CLI commands
- a distinction between reasoning personas, profile context, output modes, and Feynman-style runtime agent roles
- a bias toward README/docs clarity and honest messaging rather than feature inflation or agent proliferation

## Sources

- https://github.com/getcompanion-ai/feynman
- https://github.com/getcompanion-ai/feynman/blob/main/README.md

# Prompt Review 04: DeerFlow Pattern Extraction (2026-03-11)

Status: Historical prompt fit review  
Date: 2026-03-11  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## Source References
- Reference repo: [bytedance/deer-flow](https://github.com/bytedance/deer-flow)
- Reviewed source files:
  - `README.md`
  - `config.example.yaml`
  - `skills/public/*/SKILL.md` examples
  - `backend/src/config/memory_config.py`
  - `backend/src/config/sandbox_config.py`
  - `backend/src/config/skills_config.py`
  - `backend/src/client.py`
  - `backend/src/sandbox/sandbox_provider.py`

## Reference Summary
The useful parts of DeerFlow are configuration and packaging patterns, not its full runtime stack.

The main transferable ideas are:
1. Markdown-based skill packages with explicit metadata and progressive loading.
2. Sandbox provider abstraction configured by class path, not hardcoded everywhere.
3. Memory behavior controlled by thresholds and injection-token budgets.
4. Execution modes exposed as policy toggles (`thinking_enabled`, `plan_mode`, `subagent_enabled`, recursion limits).
5. Embedded client plus HTTP/streaming concepts for external orchestration.

The non-fit parts are also clear:
- full LangGraph-centered runtime
- global conversational memory as a default platform feature
- InfoQuest and other external/commercial integrations
- messaging channel integration as a core architecture concern

## Current PaperPipe Fit
This prompt is directionally useful, but it does not fit PaperPipe unchanged.

Current PaperPipe already has:
- policy-gated runtime actions:
  - `config/skills_policy.yaml`
  - `src/skills/policy.py`
- canonical structured state and per-run audit:
  - `.pp/<slug>/state.json`
  - `.pp/<slug>/runs/<ts>_<action>.json`
  - `pp.signals`
- viewer/runtime contracts:
  - `src/schemas/skills.py`
  - `docs/WEB_VIEWER.md`
  - `docs/API_CHAT_CONTRACT.md`
- existing runtime modes in practice, though not yet packaged as one explicit user-facing budget toggle:
  - timeout policy
  - local-first vs allowlist network policy
  - native vs docker action sandbox choice
- chat explicitly out of scope for this sprint:
  - `/api/chat` is stub only
  - no memory/RAG/provider runtime is active

That means the main mismatch is timing and duplication risk.
DeerFlow-style memory and skill packaging can be informative, but they should not create a second runtime model beside the current skills/state/policy rails.

## What Should Change
1. Keep this as a reference-pattern review only.
   - No DeerFlow adoption.
   - No runtime migration.
   - No new framework dependency lane.

2. Do not create a new top-level `docs/REF_deerflow.md` unless this becomes an active canonical runbook.
   - Under current doc rules, this belongs in a dated archive/reference note.

3. Do not create `docs/PARKING_LOT.md`.
   - This repo already uses `docs/Pending_PR_Queue.md` for parked or next-up work.

4. Treat memory patterns as P1 or P2 unless chat scope is explicitly reopened.
   - Current PaperPipe intentionally keeps `/api/chat` stub-only.
   - DeerFlow's memory thresholds and injection budgets are useful reference material, but not a current implementation target.

5. Treat markdown skill metadata as a documentation/blueprint idea, not a runtime rewrite.
   - PaperPipe runtime skills are currently action-policy-driven, not DeerFlow-style SKILL.md packages.
   - If a `blueprints/skills_spec.md` appears later, it must complement `config/skills_policy.yaml` and `src/schemas/skills.py`, not replace them.

6. Treat sandbox abstraction as a future design question, not a P0 refactor.
   - PaperPipe already has `native` vs `docker` action policy and that is sufficient for current scope.
   - A generic provider layer could be worthwhile later, but it is not a low-risk immediate change.

7. Map external orchestration ideas onto existing PaperPipe surfaces.
   - Prefer current APIs and run/timeline endpoints over inventing a second agent platform API.

## Adapted Prompt
Use this version instead of the original prompt:

```text
[REF REVIEW ONLY] Bytedance DeerFlow pattern extraction for PaperPipe

Reference repo:
- https://github.com/bytedance/deer-flow

Goal:
Do not adopt or migrate to DeerFlow.
Extract only the configuration and packaging patterns that might help PaperPipe later.
Keep this pass document-only.

Scope:
- Read only the minimum relevant material:
  - `README.md`
  - `config.example.yaml`
  - `skills/` structure and a few representative `SKILL.md` examples
  - minimal sandbox/memory config/code needed to understand the pattern
- Compare those patterns against the current PaperPipe architecture:
  - `config/skills_policy.yaml`
  - `src/skills/policy.py`
  - `src/schemas/skills.py`
  - `src/skills/storage.py`
  - `docs/WEB_VIEWER.md`
  - `docs/API_CHAT_CONTRACT.md`
- Do not change runtime code in this pass unless a tiny schema/doc stub is explicitly requested later.

Tasks:
1) Extract at most 7 DeerFlow patterns.
   For each pattern, summarize:
   - what it is
   - why it could help PaperPipe
   - cost/risk
   - where it would attach in PaperPipe
   - smallest possible PR unit

2) Build one comparison table:
   - DeerFlow concept -> PaperPipe current equivalent / missing piece / overlap
   - Must include:
     - markdown-based skills and progressive loading
     - sandbox provider abstraction
     - memory thresholds and injection-token budgets
     - execution mode toggles (fast vs deep / budget modes)
     - API or run-streaming orchestration concepts

3) Classify the result into P0 / P1 / P2:
   - P0: only 1-3 low-risk, high-ROI ideas that fit the current architecture
   - P1: useful later, but too broad for now
   - P2: not recommended because they conflict with local-first reproducibility or current scope

Deliverables for a later documentation pass:
- one dated reference note under `docs/archive/` summarizing the extracted patterns and the P0/P1/P2 decision
- optional update to `docs/Pending_PR_Queue.md` for 1-2 real follow-up items
- optional `blueprints/skills_spec.md` only if the blueprint/runtime split is explicitly opened as work

Hard limits:
- no DeerFlow migration
- no LangGraph/runtime replacement
- no InfoQuest or other commercial crawling integration into PaperPipe core
- no new heavy runtime dependencies
- no code changes justified only by novelty
- do not reopen chat memory/runtime scope indirectly through this review

Acceptance:
- the document alone should make a P0 decision possible
- each P0 item must be small enough for a single PR
- the output must explain compatibility with PaperPipe's current canonicals:
  - `.pp/<slug>/state.json`
  - `config/skills_policy.yaml`
  - structured card rendering in the web viewer
```

## Recommended Future Path
If this prompt is executed later, the clean order is:
1. write a dated archive note first
2. park only real follow-up items in `docs/Pending_PR_Queue.md`
3. only then decide whether any P0 item deserves an actual implementation pass

This keeps DeerFlow in the right role: a design-pattern reference, not a replacement architecture.

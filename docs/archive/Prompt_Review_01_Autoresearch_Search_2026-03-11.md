# Prompt Review 01: Autoresearch Search Design (2026-03-11)

Status: Historical prompt fit review  
Date: 2026-03-11  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## Source References
- Reference repo: [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- Reviewed source:
  - `README.md` from the repository root

## Reference Summary
The useful core pattern in `autoresearch` is narrow and pragmatic:
- one human-controlled instruction surface (`program.md`)
- one agent-modifiable code surface (`train.py`)
- one fixed evaluation loop (`prepare.py` + fixed 5-minute run + `val_bpb`)
- explicit keep/discard based on a comparable metric
- lightweight experiment log and promotion-by-result discipline

This is narrower than a general agent framework. It is closer to “controlled local optimization loop” than “multi-agent platform”.

## Current PaperPipe Fit
This prompt is directionally useful, but it does not fit PaperPipe unchanged.

Current PaperPipe already has:
- search/profile mutation surface:
  - `config/profiles.yaml`
  - `src/profiles/profile_schema.py`
  - `src/agents/profile_chat_agent.py`
- existing policy gating for runtime actions:
  - `config/skills_policy.yaml`
  - `src/skills/policy.py`
- strong local audit/log patterns:
  - `.pp/<slug>/runs/<ts>_<action>.json`
  - `.pp/<slug>/state.json`
  - `storage/state.db`

Therefore the main mismatch is duplication risk:
- adding a new top-level `config/search_profile.schema.json` without reconciling it with `src/profiles/profile_schema.py` creates two profile contracts
- adding a new `runs.json + results.tsv` path ignores the fact that this repo already uses JSONL/JSON sidecars and SQLite

## What Should Change
1. Do not invent a second canonical search-profile contract.
   - Current canonical contract already lives in `src/profiles/profile_schema.py`.
   - If a JSON Schema export is added later, it should be derived from that model.

2. Do not create a generic agent self-modification loop.
   - The useful import from `autoresearch` is “small editable surface + fixed eval harness”, not code self-editing.
   - In PaperPipe, the editable surface should be profile/policy data, not runtime Python.

3. Keep evaluation local and deterministic.
   - A search evaluation harness is a good fit.
   - Candidate metrics should be based on current search/fetch stack and truncation risk, not LLM chat quality.

4. Use existing repo logging style.
   - Prefer `storage/search_eval/*.jsonl` or a dedicated SQLite table over ad hoc `runs.json`.

## Adapted Prompt
Use this version instead of the original prompt:

```text
Reference:
- https://github.com/karpathy/autoresearch

Goal:
Absorb only the narrow autoresearch pattern that fits PaperPipe:
- minimize the editable surface
- enforce a fixed local evaluation harness
- keep/discard changes based on metrics
- store comparable run logs

Tasks:
1) Summarize the autoresearch design pattern we want to borrow:
   - minimal editable surface
   - fixed evaluation harness
   - keep/discard loop
   - lightweight experiment log

2) Map that pattern onto the current PaperPipe codebase:
   - identify the smallest editable data surface for search tuning
     - default candidate: `config/profiles.yaml`
     - optional later candidate: a blueprint-exported search profile file derived from the same schema
   - identify the fixed search evaluation harness entrypoint
     - candidate: `scripts/evaluate_search.py`
     - evaluate against the current search/fetch stack, not a chatbot loop
   - identify keep/discard/promotion logging
     - prefer `storage/search_eval/` JSONL reports and/or a SQLite-backed record

3) Deliverables for a later implementation pass:
   - `docs/AUTOSEARCH_DESIGN.md`
   - JSON Schema export derived from `src/profiles/profile_schema.py`
   - `scripts/evaluate_search.py` stub with JSON output

4) Scope limits:
   - no chatbot implementation
   - no unrestricted network probing
   - allow only policy-defined sources/allowlists
   - do not let the agent edit arbitrary runtime Python files

Acceptance:
- search behavior changes should be explainable by profile/policy diffs
- evaluation must run against a fixed harness with repeatable metrics
- keep/discard decisions must be logged in a comparable machine-readable format
```

## Recommended Future Path
If this prompt is executed later, the recommended implementation path is:
- keep the profile contract canonical in `src/profiles/profile_schema.py`
- export JSON Schema from that model instead of hand-writing a second schema
- place any future blueprint-aligned search schema under `blueprints/search/` only if the blueprint/runtime split is adopted first
- use `storage/search_eval/` for logs unless a clear reason exists to extend `storage/state.db`

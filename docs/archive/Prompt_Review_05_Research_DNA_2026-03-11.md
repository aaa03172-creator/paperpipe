# Prompt Review 05: Research DNA Workflow (2026-03-11)

Status: Historical prompt fit review  
Date: 2026-03-11  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## Source References
- Prompt context only: Pomelli is treated as workflow inspiration, not a technical dependency or integration target.
- Current PaperPipe search/profile lane reviewed from:
  - `src/profiles/profile_schema.py`
  - `src/profiles/profile_store.py`
  - `src/profiles/patch_schema.py`
  - `src/profiles/patch_apply.py`
  - `src/agents/profile_chat_agent.py`
  - `src/cli.py` (`profiles` / `audit` commands)
  - `tests/test_profiles.py`
  - `tests/test_profile_chat.py`
  - `tests/test_eval_harness.py`
  - `scripts/eval/run_eval.py`
  - `src/services/runtime_paths.py`

## Reference Summary
The useful pattern here is not Pomelli itself. The useful pattern is:
- a reproducible search-profile asset
- a bounded state machine (`DRAFT -> PILOT -> LOCKED`)
- pilot-first validation before scale-up
- append-only decision logging for reproducibility

That pattern does fit PaperPipe in principle.
But it does not fit unchanged because PaperPipe already has a narrower search/profile system and existing audit/eval conventions.

## Current PaperPipe Fit
Current PaperPipe already has:
- a canonical executable search/profile contract:
  - `config/profiles.yaml`
  - `src/profiles/profile_schema.py`
- an LLM-assisted profile mutation lane:
  - `src/agents/profile_chat_agent.py`
  - `src/profiles/patch_schema.py`
  - `src/profiles/patch_apply.py`
- a current operator surface:
  - `paperpipe profiles ...`
  - `paperpipe audit ...`
- existing evaluation/audit patterns that should be reused:
  - append-only JSONL
  - deterministic eval harness under `scripts/eval/`
  - `goldset/` and `snapshots/` conventions
- runtime path helpers for non-hardcoded storage roots:
  - `src/services/runtime_paths.py`

The main mismatch is canonical duplication.
If this prompt is executed naively, PaperPipe would end up with:
- `config/profiles.yaml`
- `research_dna/<dna_id>/profile.yaml`

Both would try to be the canonical search definition.
That would drift quickly.

## What Should Change
1. Do not let `Research DNA` and `config/profiles.yaml` become competing canonicals.
   - Recommended model: `Research DNA` is the higher-order asset for search design and audit.
   - Current `Profile` stays the executable projection / compatibility surface until a migration is explicit.

2. Do not hardcode a new repo-root `research_dna/` path with no path policy.
   - Prefer a runtime path helper with env override, for example a future `research_dna_root()` under `src/services/runtime_paths.py`.
   - The actual root can still resolve to `<paperpipe_home>/research_dna/`.

3. Do not create `docs/PARKING_LOT.md`.
   - This repo already uses `docs/Pending_PR_Queue.md` for parked UI or follow-up work.

4. Reuse existing search/profile mutation primitives.
   - `PatchRequest` / `apply_patch()` is already a good fit for profile diffs and query refinement logging.
   - `ProfileChatAgent` can later power the librarian/researcher interview and refinement proposals.

5. Reuse existing eval/audit conventions instead of inventing a separate reporting world.
   - Pilot metrics and precision proxies can be logged per DNA, but should remain compatible with JSONL and the current `scripts/eval/` style.
   - Goldset-style recall should reuse current `goldset/` thinking where possible.

6. Keep the first implementation bounded to DRAFT/PILOT/LOCKED plus pilot loop only.
   - Full run and scheduled update should remain explicitly deferred until the pilot loop proves stable.

7. Keep UI wizard work parked.
   - Backend hooks, schemas, logs, and docs are enough for the first pass.

8. Keep logic in a service layer, not CLI-only.
   - CLI wrappers are fine.
   - But core logic should be reusable from FastAPI if the feature graduates.

## Adapted Prompt
Use this version instead of the original prompt:

```text
[TITLE] Research DNA (search-design asset) + DRAFT -> PILOT -> LOCKED workflow
Pattern inspiration only. No Pomelli integration.

Context:
PaperPipe already has a narrower executable profile lane (`config/profiles.yaml`, `src/profiles/*`).
The goal is not to replace the repo with a new system, but to add a higher-order search-design asset that improves reproducibility.

Goal:
1) Introduce `Research DNA` as a reproducible search-design asset.
2) Operate it with a bounded state machine: `DRAFT -> PILOT -> LOCKED`.
3) Keep UI wizard work out of scope for this milestone.
4) Keep all pilot/refinement/lock decisions append-only and auditable.

Important architecture rule:
- Do not let `Research DNA` silently duplicate the canonical executable profile contract.
- Recommended approach:
  - `Research DNA` stores the broader interview/scope/pilot/audit state.
  - the current `Profile` model remains the executable query projection or compatibility layer until an explicit migration plan exists.

Scope for a later implementation pass:
A) Data and schema
- add a `ResearchDNA` schema under the existing profile/search lane
  - candidate path: `src/profiles/research_dna_schema.py`
- define state machine rules: `DRAFT`, `PILOT`, `LOCKED`
- define append-only log payloads for:
  - interview
  - runs
  - screening labels
  - decisions
- provide 1-2 sample fixtures in docs or test fixtures, not as ad hoc live runtime data

B) Minimal backend/service hooks
- implement a service layer first, then thin CLI/API wrappers
- minimum operations:
  1. `create_dna(topic, intent)`
  2. `update_dna(dna_id, patch)`
  3. `run_pilot(dna_id)`
  4. `submit_screening(dna_id, labels[])`
  5. `refine_queries(dna_id)`
  6. `lock_dna(dna_id, reason)`
- all write paths must be append-only in the DNA log area
- updates must be blocked or tightly controlled once status is `LOCKED`

C) Path and storage rules
- do not hardcode a bare repo-root directory with no policy
- prefer a runtime path helper and env override
  - example future root: `<paperpipe_home>/research_dna/<dna_id>/`
- inside each DNA root, keep:
  - `profile.yaml` as the DNA asset
  - `versions/`
  - `logs/*.jsonl`

D) Pilot loop
- pilot only for the first pass
- collect N=20..50 from policy-allowed sources only
- dedupe by DOI / PMID / title+year
- store screening decisions:
  - `include | exclude | unclear`
  - `reason_code`
  - optional note
- refinement should create:
  - version bump
  - diffable change record
  - decision log entry
  - summary metrics such as precision proxy and noise distribution

E) Documentation
- `docs/RESEARCH_DNA.md` as the active feature document
- update `docs/Pending_PR_Queue.md` to park the future 3-step wizard UI
- do not create `docs/PARKING_LOT.md`

Non-goals:
- no Pomelli service or API integration
- no chat UI implementation
- no big frontend wizard
- no RL / auto-learning scope
- no full-run scheduler in the first PR

Acceptance:
- a topic-only create flow can produce a `DRAFT` DNA asset
- pilot execution produces a deduped screening queue and append-only logs
- label submission plus refinement creates a version bump and auditable diff trail
- lock prevents casual mutation and requires explicit procedure for change
- compatibility with current PaperPipe canonicals is documented clearly:
  - `config/profiles.yaml`
  - `src/profiles/*`
  - existing eval/audit conventions
```

## Recommended Future Path
If this prompt is executed later, the clean order is:
1. write `docs/RESEARCH_DNA.md` first and settle the canonical boundary between `ResearchDNA` and current `Profile`
2. add schema + store + service layer without UI
3. add pilot logging and refinement hooks
4. only after that decide whether a UI wizard deserves its own milestone

This keeps the good part of the pattern: search reproducibility and auditability.
It avoids the bad part: creating a second undocumented search-profile system that drifts away from the current runtime.

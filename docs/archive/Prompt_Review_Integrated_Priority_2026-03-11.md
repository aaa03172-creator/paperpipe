# Prompt Review Integration: Search/Profile + Agent Pattern Priority (2026-03-11)

Status: Historical prompt integration  
Date: 2026-03-11  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## Integrated Inputs
- `docs/archive/Prompt_Review_01_Autoresearch_Search_2026-03-11.md`
- `docs/archive/Prompt_Review_02_Auton_Agentic_P0_2026-03-11.md`
- `docs/archive/Prompt_Review_03_Fireauto_2026-03-11.md`
- `docs/archive/Prompt_Review_04_DeerFlow_2026-03-11.md`
- `docs/archive/Prompt_Review_05_Research_DNA_2026-03-11.md`
- `docs/archive/Deep_Research_Report5_Fit_Review_2026-03-11.md`

## Purpose
These five prompt reviews overlap, but they are not five separate near-term workstreams.

Taken together, they collapse into:
1. one real future product/runtime lane
2. one adjacent hardening/documentation lane
3. two reference-only operator-pattern lanes

The main goal of this integration note is to prevent duplicate canonicals and scope drift.

## Consolidated Judgment

### 1. The only coherent future product lane is `Research DNA + fixed search evaluation`
This is the one lane that materially fits the current PaperPipe search/profile system.

It combines the useful parts of:
- `autoresearch`: minimal editable surface + fixed eval harness + keep/discard discipline
- `Research DNA`: `DRAFT -> PILOT -> LOCKED` state machine + append-only pilot/refinement logs

This lane fits because PaperPipe already has:
- `config/profiles.yaml`
- `src/profiles/profile_schema.py`
- `src/profiles/patch_schema.py`
- `src/profiles/patch_apply.py`
- `src/agents/profile_chat_agent.py`
- `scripts/eval/run_eval.py`

### 2. `blueprint/runtime separation + validator hardening` is a second, smaller lane
This is useful, but it is not the first thing to build.

It combines the useful parts of:
- `Auton`: blueprint/runtime split, contract-driven outputs, deterministic failure recording
- small pieces of `DeerFlow`: explicit metadata/configuration patterns

This lane should only proceed after the search/profile boundary is clear, otherwise the repo will get:
- a second profile contract
- a second policy source
- a vague `blueprints/` tree with no clear owner

### 3. `fireauto` and most of `DeerFlow` should remain reference-only
They contribute operator and packaging patterns, not runtime architecture.

Useful references:
- bounded loop discipline
- file-boundary ownership for parallel work
- explicit command/runbook packaging
- skill metadata ideas

Not suitable for current adoption:
- plugin runtime abstractions
- Claude/team-specific tooling
- LangGraph-centered runtime replacement
- default chat memory platform
- external commercial integrations

## Canonical Boundary Decisions

### Search/Profile canonical
- Keep `src/profiles/profile_schema.py` as the canonical executable search/profile contract.
- If JSON Schema export is needed later, derive it from that model.
- Do not add a hand-maintained second schema such as `config/search_profile.schema.json`.

### Research DNA canonical
- If implemented later, `ResearchDNA` should be a higher-order design/audit asset.
- It must not silently replace or compete with `config/profiles.yaml` until there is an explicit migration plan.
- Recommended relationship:
  - `ResearchDNA` = broader interview/scope/pilot/governance asset
  - `Profile` = executable query projection / compatibility layer

### Skills/policy canonical
- Keep `config/skills_policy.yaml` as the runtime policy source.
- Keep `src/schemas/skills.py` and `src/contracts/*` as the schema/contract lanes.
- Any future `blueprints/skills/` or `blueprints/skills_spec.md` must describe or point to these canonicals, not fork them.

### Audit/state canonical
- Keep `.pp/<slug>/runs/<ts>_<action>.json` as per-run raw skill output.
- Keep `.pp/<slug>/state.json` as canonical merged viewer/runtime state.
- Keep frontmatter limited to small `pp.signals` indexing fields.

### Backlog/documentation canonical
- Do not create `docs/PARKING_LOT.md`.
- Park future items in `docs/Pending_PR_Queue.md`.
- Keep fit reviews and prompt integration notes under `docs/archive/`.

## Unified Execution Order

### Priority 1: Search/Profile reproducibility lane
Open this lane first if the repo returns to search/research workflow work.

Preferred first deliverable:
- `docs/RESEARCH_DNA.md`

What it should settle first:
- `ResearchDNA` vs `Profile` canonical boundary
- `DRAFT -> PILOT -> LOCKED` rules
- append-only log structure
- pilot metrics
- fixed evaluation expectations

Preferred implementation order after that:
1. `src/profiles/research_dna_schema.py`
2. `src/profiles/research_dna_store.py`
3. `src/services/runtime_paths.py` extension for DNA root resolution
4. service-layer pilot/refinement hooks
5. thin CLI/API wrappers
6. `scripts/evaluate_search.py` as the shared fixed harness for comparable metrics

Why first:
- It fits existing `profiles` code.
- It directly improves reproducibility.
- It does not require chat UI or framework replacement.

### Priority 2: Blueprint/runtime boundary docs + `/skills/run` validator hardening
Open this only after Priority 1 has defined the search/profile boundary.

Preferred deliverables:
- `docs/BLUEPRINT_RUNTIME.md`
- `docs/AUDIT_TRAIL.md`

Possible implementation scope:
- validator layer around `/skills/run`
- stable failed status recording for invalid normalized outputs
- minimal `blueprints/` examples that point to current canonicals

Why second:
- This is a hardening/documentation pass, not a user-visible product lane.
- Doing it first risks creating a speculative structure that the search lane then has to work around.

### Priority 3: Operator-pattern borrowing only
Keep this doc-only unless the earlier lanes prove a concrete need.

Allowed borrowings:
- bounded improvement loops
- explicit completion conditions
- file-boundary ownership in parallel work
- command/runbook packaging ideas
- optional skill metadata standard proposal

Disallowed borrowings:
- plugin runtime import
- session-trap loop hooks
- team/task infrastructure as product runtime
- LangGraph or DeerFlow runtime migration

## Unified P0 / P1 / P2

### P0
Only these are worth near-term implementation consideration.

1. `Research DNA` concept doc + canonical boundary
   - small PR
   - highest leverage
   - reduces search/profile ambiguity before code grows

2. Fixed search evaluation harness
   - likely `scripts/evaluate_search.py`
   - comparable metrics and append-only outputs
   - should align with `storage/search_eval/` and existing eval conventions

3. Minimal `ResearchDNA` schema + append-only logs
   - schema/store only
   - no frontend wizard
   - no scheduler

P0 scope is intentionally narrowed to:
- standards-backed search profile structure
- two-round interview only
  - `Researcher 4`
  - `Librarian 4`
- append-only `query_versions`
- append-only `run_log`
- append-only `approval_audit`
- `pilot -> screening -> refine` loop
- `reason_code`-based query refinement
- recommended DB set separated from actually available DB set
- biomedical example set, not generic/non-biomedical examples

P0 exclusions inside the same lane:
- no full PRESS automation
- no mandatory grey literature at intake
- no external DOI archiving
- no OpenAlex-first design
- goldset sanity check stays optional, not a required gate

### P1
Useful, but only after P0 is stable.

1. `/skills/run` validator hardening with deterministic failed-state recording
2. `docs/BLUEPRINT_RUNTIME.md` plus one minimal `blueprints/` example
3. optional `blueprints/skills_spec.md` to describe skill metadata, if and only if blueprint work is explicitly opened
4. bounded loop/process guidance derived from `fireauto` for engineering operations
5. full PRESS automation for search review support
6. mandatory grey literature intake policy
7. external DOI archiving/export lane
8. broader OpenAlex or meta-index expansion after the core source-policy layer is stable

### P2
Do not start these now.

1. `docs/PARKING_LOT.md` or any parallel backlog system
2. second canonical profile contract or hand-maintained parallel schema
3. DeerFlow-style memory runtime while `/api/chat` is still stub-only
4. sandbox provider generalization as a speculative refactor
5. plugin/team/task abstractions imported from `fireauto`
6. external commercial or crawling integrations justified only by the reference repos
7. runtime migration to DeerFlow, LangGraph, or similar frameworks

## Consolidated Deliverable Choices
If this future lane is reopened, the cleaner active-doc set is:

- keep:
  - `docs/RESEARCH_DNA.md`
  - `docs/BLUEPRINT_RUNTIME.md`
  - `docs/AUDIT_TRAIL.md`

- avoid for now:
  - `docs/PARKING_LOT.md`
  - a separate active `docs/REF_fireauto.md`
  - a separate active `docs/REF_deerflow.md`
  - a separate hand-written `config/search_profile.schema.json`

Why:
- one active doc per bounded area is easier to keep canonical
- the reference-repo work belongs in archive notes unless it turns into active implementation

## Recommended Small-PR Sequence
If implementation starts later, the smallest defensible order is:

1. `docs/RESEARCH_DNA.md`
   - define `ResearchDNA` vs `Profile`
   - define state machine
   - define pilot logs and metrics

2. `src/profiles/research_dna_schema.py` + store/path helpers
   - schema only
   - append-only logs
   - no UI

3. pilot CLI/API hooks
   - `create_dna`
   - `run_pilot`
   - `submit_screening`
   - `lock_dna`

4. `scripts/evaluate_search.py`
   - fixed metrics
   - repeatable output
   - keep/discard comparability

5. `docs/BLUEPRINT_RUNTIME.md` + `/skills/run` validator hardening

This order preserves the current repo's strengths:
- local-first operation
- deterministic JSONL/JSON artifacts
- explicit policy gates
- minimal duplication of canonical contracts

## Residual Risks From Multi-Angle Review

### 1. `ResearchDNA -> Profile` projection is still underspecified
- The note correctly says `ResearchDNA` should be the broader asset and `Profile` should stay the executable projection.
- But the current executable profile model is much narrower than the proposed DNA shape.
- Before any schema/store PR starts, the projection contract must be written explicitly:
  - which DNA fields stay DNA-only
  - which fields compile into `Profile`
  - how version bumps affect the executable profile snapshot

### 2. Search evaluation is not just a wrapper around the current eval harness
- The repo already has deterministic eval patterns, but the current harness is document/goldset oriented.
- A search eval lane still needs its own artifact contract:
  - search inputs
  - source policy scope
  - retrieval outputs
  - dedupe summary
  - precision/recall-style metrics
- Treating this as “just add `scripts/evaluate_search.py`” would understate the real contract work.

### 3. Lock/audit semantics require actor attribution, not just append-only files
- `LOCKED`, `decisions`, and future unlock flows imply fields like `locked_by`, reviewer identity, and change reason.
- The current profile CLI flow does not carry structured actor metadata into saved profile changes.
- If this lane is implemented later, actor identity must be part of the service/API/CLI contract from the start.

### 4. “Policy-allowed sources only” needs a real search-source policy document
- The skills lane has a clear runtime policy source: `config/skills_policy.yaml`.
- The search/profile lane does not yet have an equivalent canonical for source allowlists, pilot scope, or budget rules.
- That gap should be closed in the `Research DNA` doc or an adjacent search-policy doc before pilot execution code is added.

## Boundary Patches (v0)
The following clarifications reduce the four residual risks enough for a later implementation pass to start cleanly.

### 1. `ResearchDNA -> Profile` projection contract (v0)
Until an explicit migration exists:
- `ResearchDNA` owns:
  - `intent`
  - `status`
  - `scope`
  - `criteria`
  - `databases`
  - `filters`
  - `pilot`
  - `governance`
  - interview/refinement/decision history
- `Profile` owns only the executable search projection:
  - `id`
  - `title`
  - `enabled`
  - `schedule`
  - `limits`
  - `query`
  - `notes`

Projection rule:
- each DNA version may produce an executable profile snapshot
- the projection must be deterministic and reproducible from DNA contents
- DNA-only fields must not be silently dropped without being recorded in the DNA version/audit history
- legacy manually maintained profiles remain supported and untouched unless explicitly migrated

Implementation guardrail:
- do not let operators edit both the DNA asset and the projected executable profile as equal peers for the same search program
- a DNA-managed profile must have one clearly documented source of truth

### 2. Search evaluation artifact contract (v0)
The first search-eval lane should use its own explicit artifact set instead of pretending the current quality eval harness already covers it.

Minimum run artifact shape:
- `storage/search_eval/<run_id>/manifest.json`
  - run metadata, DNA/profile reference, source policy reference, timestamps
- `storage/search_eval/<run_id>/queries.json`
  - effective query set used per source/database
- `storage/search_eval/<run_id>/retrieved.jsonl`
  - raw retrieved candidates before screening
- `storage/search_eval/<run_id>/screening_queue.jsonl`
  - deduped candidates presented for review
- `storage/search_eval/<run_id>/metrics.json`
  - comparable metrics for keep/discard
- optional `storage/search_eval/<run_id>/diff.json`
  - comparison to prior version/baseline

Minimum metrics:
- `retrieved_count`
- `deduped_count`
- `dedupe_rate`
- `labeled_count`
- `include_count`
- `exclude_count`
- `unclear_count`
- `precision_proxy`
- `goldset_recall` when goldset exists
- `top_reason_codes`

Implementation guardrail:
- `scripts/evaluate_search.py` must write against this explicit contract
- do not reuse `scripts/eval/run_eval.py` semantics by analogy without defining search-specific inputs and outputs

### 3. Actor attribution contract (v0)
Any future DNA lock/refine/update flow must capture actor metadata structurally.

Minimum append-only decision fields:
- `ts`
- `dna_id`
- `version`
- `actor_type`
  - example: `human_cli`, `human_api`, `system`, `agent`
- `actor_id`
- `action`
  - example: `create`, `approve_pilot`, `refine`, `lock`, `unlock`, `submit_screening`
- `reason`
- `request_id` or `run_id`
- `before_version` / `after_version` when applicable

Implementation guardrail:
- no state transition to `LOCKED`
- no unlock
- no query refinement acceptance
without an actor-attributed decision record

CLI rule:
- CLI may default `actor_id` from the local OS user
- but it must still persist a concrete `actor_type` and `actor_id` in the decision log

### 4. Search-source policy contract (v0)
Before pilot execution exists, PaperPipe needs a canonical source-policy statement for the search lane.

Until a standalone doc exists, the first active version should live inside `docs/RESEARCH_DNA.md`.

Minimum policy fields:
- allowed source list
  - for example: `pubmed`, `openalex`
- per-source query mode rules
- network policy
  - local only / allowlist only
- pilot result cap
- dedupe rules
  - DOI / PMID / title+year precedence
- retry/time budget expectations
- logging requirements for source failures and truncation

Implementation guardrail:
- no pilot runner should call arbitrary web sources
- no source should be added implicitly by prompt wording alone
- any new search source must be declared in the policy layer before code uses it

## What Is Now Safe To Do
With the above boundary patches, the later implementation lane can safely start with:
1. `docs/RESEARCH_DNA.md`
2. projection rules from DNA to executable profile
3. explicit search-eval artifact contract
4. append-only actor-attributed decision log schema

It is still not safe to start with:
- a frontend wizard
- a generic blueprint tree
- memory/chat runtime additions
- a second live profile canonical

## Double-Check Notes
After cross-reviewing all five prompt-fit docs against the current repository:

1. No prompt-derived work should create `docs/PARKING_LOT.md`.
2. No prompt-derived work should create a second canonical search-profile schema.
3. No prompt-derived work should reopen chat memory/runtime while `/api/chat` remains stub-only.
4. No prompt-derived work should replace `config/skills_policy.yaml` or `.pp/<slug>/state.json`.
5. `fireauto` and `DeerFlow` remain reference sources, not adoption candidates.
6. The current queued frontend work in `docs/Pending_PR_Queue.md` is not superseded by this note.
   - This note describes a coherent future search/agent lane, not the current next PR.

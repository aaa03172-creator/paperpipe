# Persona / Mode Roadmap

Status: Active roadmap
Date: 2026-03-17
Owner: Runtime/design maintainers
Canonical parent: `docs/PERSONA_MODE_BOUNDARY.md`

Purpose: turn the boundary in `docs/PERSONA_MODE_BOUNDARY.md` into an incremental implementation plan without breaking the current runtime in one large rename.

## Current implementation status

### Landed
- Backend/API accepts additive `reasoning_persona` and `profile_id` while preserving legacy `persona_id`.
- `src/persona_modes.py` defines the built-in reasoning persona catalog and compatibility normalization.
- `backend/services/job_runner.py` composes reasoning-persona hints and profile-context hints separately.
- Persistence now records `persona_id`, `reasoning_persona`, and `profile_id` in jobs and run metadata.
- `frontend/src/app/pages/AnalysisWorkbench.tsx` exposes separate `Reasoning` and `Profile` controls.
- `frontend/src/app/store/useAppStore.ts` uses `selectedReasoningPersona` and `selectedProfileId`.
- `frontend/src/app/lib/mock.ts` and `tests/test_personas_api.py` now use built-in reasoning personas plus YAML profiles, rather than pseudo-persona families.
- Shared `output_mode_family` exists across `Meeting Pack`, `/api/chat` stub, and `Paper Notes Viewer` presentation surfaces.
- Canonical docs now frame `/personas` and `persona_id` as compatibility surfaces instead of the conceptual model.

### Still incomplete
- Public compatibility naming remains prominent: `/personas` and `persona_id` are still first-class external surfaces.
- Some older artifact contracts and legacy modules still use `persona_id`-only wording and do not yet preserve split lineage everywhere.
- Output/view mode adoption is still partial and presentation-scoped; workbench/chat/viewer behavior is not yet uniformly mode-aware.
- Retired compatibility stubs and historical docs may still contain older persona-centric language.

## Roadmap principles

- keep compatibility first
- do not force a one-shot DB or API rename
- separate reasoning persona, profile context, and output mode one layer at a time
- prefer additive fields and aliases before hard deprecation
- do not create separate agent chains for every output mode

## Phase 0: Spec and fixture alignment

Goal:
- align docs and fixtures with the new boundary before runtime migration

Status:
- Mostly landed.
- Remaining work is cleanup of lower-level contracts and older compatibility docs.

Changes:
- update `docs/Lattice_v3_Master_Spec.md` to describe:
  - core reasoning personas
  - profile context as a separate concept
  - `/personas` as current compatibility surface, not the long-term conceptual model
- update examples that imply arbitrary audience personas
- replace mock persona examples in `frontend/src/app/lib/mock.ts` with:
  - core reasoning personas
  - separate example profile labels where needed
- update tests that currently equate YAML profiles with persona family semantics

Acceptance:
- no canonical doc implies that every audience or deliverable should become a new agent
- mock fixtures no longer advertise pseudo-personas like `clinical-triage` as the preferred model

## Phase 1: Introduce additive runtime split

Goal:
- encode the conceptual split without breaking existing clients

Status:
- Landed for backend/API request handling and normalization.
- Compatibility naming remains intentionally preserved.

Changes:
- extend job/API contracts with additive fields:
  - `reasoning_persona`
  - `profile_id`
- keep `persona_id` as compatibility input/output during migration
- define a small explicit reasoning persona enum:
  - `librarian`
  - `researcher`
  - `extractor_reviewer`
- introduce a backend normalization rule:
  - if legacy `persona_id` matches a core reasoning persona, treat it as `reasoning_persona`
  - otherwise treat it as `profile_id`

Likely file targets:
- `src/jobs/schemas.py`
- `backend/main.py`
- `src/schemas/ops.py`
- `backend/services/job_runner.py`

Acceptance:
- runtime can accept both legacy `persona_id` and the new split fields
- internal execution path can resolve reasoning persona and profile context independently

## Phase 2: Separate reasoning prompts from profile hints

Goal:
- stop using profile YAML as the only source of “persona” behavior

Status:
- Partially landed.
- `backend/services/job_runner.py` already composes reasoning persona hints, profile context hints, and similar-feedback injection separately.
- Remaining work is aligning older reader-side artifact contracts and any lingering persona-only prompt assumptions.

Changes:
- replace `_resolve_persona_hint(persona_id)` with a composition step:
  - reasoning persona prompt fragment
  - profile context fragment
  - similar-feedback fragment
- create a small reasoning-lane instruction source for:
  - librarian
  - researcher
  - extractor_reviewer
- keep profile-derived notes/query focus as contextual overlay only

Likely file targets:
- `backend/services/job_runner.py`
- reasoning prompt/config helper under `src/` or `config/`

Acceptance:
- switching profile does not imply switching reasoning lane
- switching reasoning lane does not require creating a new YAML profile

## Phase 3: Persistence and event-log migration

Goal:
- make the split durable in jobs and run metadata

Status:
- Landed for job rows, queue payloads, bootstrap metadata, and run metadata.
- Remaining work is cleanup of any older lineage surfaces that still expose only `persona_id`.

Changes:
- add nullable columns or JSON params support for:
  - `reasoning_persona`
  - `profile_id`
- keep `persona_id` for compatibility until migration completes
- write both new fields into:
  - `jobs`
  - `execution_runs.params_json`
  - bootstrap metadata

Likely file targets:
- `src/db_utils.py`
- `src/jobs/queue.py`
- `src/services/event_log.py`
- E2E DB bootstrap in `frontend/scripts/run_backend_for_e2e.sh`

Acceptance:
- a run can be reconstructed as:
  - which reasoning lane was used
  - which profile context was used
  - whether any legacy `persona_id` alias was involved

## Phase 4: Frontend terminology migration

Goal:
- teach the right mental model in the UI

Status:
- Largely landed in the workbench and frontend store.
- Compatibility API naming remains (`getPersonas` / `/personas`) until a later cleanup phase.

Changes:
- split the current selector in `AnalysisWorkbench` into:
  - `Reasoning`
  - `Profile` or `Context`
- rename frontend store fields away from `selectedPersonaId`
- keep compatibility mapping in API calls until backend migration is complete
- update mock mode data and E2E expectations

Likely file targets:
- `frontend/src/app/store/useAppStore.ts`
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
- `frontend/src/app/lib/api.ts`
- `frontend/src/app/lib/types.ts`
- `frontend/src/app/lib/mock.ts`

Acceptance:
- users can select a reasoning lane without implying a lab/topic profile
- users can select a profile without implying a different agent family

## Phase 5: Output/view mode foundation

Goal:
- make output/view modes reusable across viewer, meeting-pack, and future chat surfaces

Status update:
- Initial foundation is now in place for `Meeting Pack` via shared `output_mode_family` mapping on saved pack contracts and inspector UI.
- Concrete `Meeting Pack` modes remain unchanged; the shared family is additive and presentation-only.
- `/api/chat` stub now also accepts additive `output_mode_family` input and returns the effective family without changing stub/runtime behavior.
- `Paper Notes Viewer` detail now supports additive `view=learner|builder_debug` presentation modes that change panel emphasis only.

Changes:
- define a lightweight output mode enum/family for shared surfaces:
  - `learner`
  - `lab_meeting`
  - `project_update`
  - `builder_debug`
- keep `MeetingPack`’s existing concrete modes, but map them to an output-mode family
- add optional output-mode handling first where it has clear value:
  - paper notes viewer
  - workbench
  - future `/api/chat`

Non-goal:
- do not create a separate model chain or agent runtime for each output mode

Acceptance:
- output modes can change framing and emphasis without changing evidence truth policy

## Phase 6: Surface-specific adoption

Goal:
- adopt the split only where it improves user outcomes

Priority order:
1. Deep Read / workbench controls
2. Meeting Pack family mapping
3. Viewer `learner` vs `builder_debug` emphasis
4. Future chat/view contracts

Examples:
- `learner`
  - simplified explanation density
  - glossary/help framing
  - no change to claim truth policy
- `builder_debug`
  - trace visibility
  - validation/write-scope emphasis
  - no change to claim truth policy

Acceptance:
- mode differences are clearly presentation-driven
- scientific decision criteria remain anchored to the reasoning lane

## Phase 7: Cleanup and deprecation

Goal:
- retire compatibility naming only after migration is complete

Possible end state:
- keep `/personas` as deprecated alias, or replace with:
  - `/reasoning-personas`
  - `/profiles`
- keep `persona_id` as deprecated alias, or replace with:
  - `reasoning_persona`
  - `profile_id`

Prerequisite:
- all first-party frontend surfaces and tests already use the new split

Acceptance:
- deprecation does not break existing stored jobs or current operators unexpectedly

## Suggested PR sequence

1. `PR-DOC-PersonaMode-Canonical-Alignment`
- finish canonical spec cleanup and remove stale persona-centric wording from active docs

2. `PR-BE-PersonaMode-Lineage-Backfill`
- align remaining artifact and metadata contracts that still omit `reasoning_persona` / `profile_id`

3. `PR-FE-OutputMode-Workbench-Adoption`
- extend presentation-only output mode behavior where it improves workbench or viewer clarity

4. `PR-Cleanup-Persona-Compatibility`
- deprecate old naming only after all first-party surfaces stop depending on it

## Recommended next step

Do not start with destructive renames.

The best next step is:
- finish canonical doc cleanup
- backfill split lineage into any remaining artifact contracts
- only then decide whether `/personas` and `persona_id` can begin formal deprecation

That sequence keeps the runtime understandable while reducing compatibility debt incrementally.

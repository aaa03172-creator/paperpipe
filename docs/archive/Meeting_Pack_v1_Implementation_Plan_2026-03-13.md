# Meeting Pack v1 Implementation Plan (2026-03-13)

Status: Historical implementation plan
Date: 2026-03-13
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/MEETING_PACK.md`

## Progress Update (2026-03-13)
- Phase 1 completed in workspace:
  - `src/schemas/meeting_pack.py`
  - `src/meeting_packs/store.py`
  - `src/services/runtime_paths.py::meeting_packs_root()`
  - `tests/test_meeting_pack_schema.py`
  - `tests/test_meeting_pack_store.py`
  - `tests/test_runtime_paths_meeting_packs.py`
- Minimal Phase 2 completed in workspace:
  - `src/meeting_packs/source_resolver.py`
  - `src/meeting_packs/evidence.py`
  - `tests/test_meeting_pack_source_resolver.py`
  - current supported selectors:
    - `paper_slug`
    - `paper_state`
    - `paper_note`
    - `project_note`
    - `research_note`
    - `screening_decision`
    - `topic` via deterministic structured-signal exact match
    - `project_profile` via deterministic `ResearchDNA` projection-profile resolution
    - `research_profile` via deterministic `ResearchDNA` projection-profile resolution
- Minimal Phase 3/4 completed in workspace:
  - `src/meeting_packs/service.py`
  - `src/meeting_packs/renderer.py`
  - `backend/routers/meeting_packs.py`
  - `tests/test_meeting_pack_service.py`
  - `tests/test_meeting_pack_api.py`
  - real probe recorded in `docs/archive/Meeting_Pack_Real_Probe_2026-03-13.md`
- post-double-check hardening completed:
  - new packs now persist `generation_request` snapshots for regenerate-safe lifecycle recovery
  - `POST /meeting-packs/{pack_id}/regenerate` now regenerates a fresh pack from saved request intent
  - `POST /meeting-packs/{pack_id}/rerender` now rebuilds deterministic markdown from saved `meeting_pack.json`
  - pack IDs now carry microsecond timestamp precision so same-request regenerate does not overwrite the earlier pack when both land in the same second
  - response-level `markdown_sync` now reports whether saved markdown matches the deterministic JSON render
  - pack contract now carries `readiness` (`evidence_backed` vs `background_only`) and `regenerated_from_pack_id`
  - repeatable bundled-vault smoke command now exists under `python3 scripts/check_meeting_pack_real_smoke.py`
  - standard local verify lane now exists under `./scripts/run_meeting_pack_verify.sh`
  - local verify lane now also fails on drifted or regenerate-unavailable saved bundles through `python3 scripts/check_meeting_pack_storage_sync.py`
  - CI workflow now runs the same lane under `.github/workflows/meeting-pack-verify.yml`
  - `GET /meeting-packs/{pack_id}/validate` now reports sync/readiness/regenerate availability in a machine-usable form and only returns regenerate available after rechecking the saved selector set against the current vault
  - legacy packs without `generation_request` can now regenerate only through a bounded deterministic `source_items` fallback
  - bundle save now rolls back on second-write failure so partial `meeting_pack.json` / `meeting_pack.md` artifacts are not left behind
  - exact duplicate `paper_slug` selectors now dedupe at source resolution
  - first evidence slide now points to the actual `source_item_id` even if earlier selected sources had no claims
  - `screening_decision` now requires explicit `<dna_id>:<run_id>` with no latest-run fallback
  - `topic` selector now resolves only by deterministic exact match over explicit topic signals (`tags/topic/topics`, `entities/mesh/outcomes`, claim `tags/outcomes`)
  - `topic` no longer reopens claim/evidence full-text fuzzy search
  - `project_note` / `research_note` no longer reopen free-text note-body fuzzy selection; they require explicit linked papers
  - `paper_note` alone keeps a deterministic same-stem `state.json` fallback
  - `project_profile` / `research_profile` now resolve only through `ResearchDNA` projection metadata (`source_dna_id + source_query_version`) and latest screened include set mapping to existing structured state
  - generic manual profile selectors reject instead of reopening broad or fuzzy corpus selection
  - clean rerun에서 드러난 `service -> resolver` `profiles_path` contract drift를 복구해 profile selectors가 actual override path를 다시 따르도록 정렬
  - primary pack naming/overview/context bullets now prefer structured paper titles over note/screening titles when both are present
  - structured `one_page_summary.consensus_points[]` now records conservative directional convergence
  - structured `one_page_summary.conflicts[]` now records conservative divergence and screening-scope conflicts
  - cross-source adjudication now uses shared focus-family clustering with root-overlap paraphrase matching, limited synonym aliasing, and `increase/decrease/null/benefit/harm` wording buckets
  - limited curated biomedical alias coverage now includes strong non-overlapping families such as `safety` / `tolerability` / `adverse events`
  - `safety` family strong cases now use limited row-level valence mapping so `improved tolerability` and `reduced adverse events` can align without reopening fuzzy matching
  - strong higher-is-better / higher-is-worse focus families now align benefit-like and signed increase/decrease wording at outcome level
  - clear `3+` source majority cases now emit `majority_directional_alignment` partial consensus alongside divergence conflict instead of dropping the dominant trend entirely
  - asymmetric divergence now surfaces majority/outlier count wording instead of only set-level direction labels
  - note/screening context now tunes overview, first key-point uncertainty note, opening/context slide framing, and `discussion_questions[]` / `expected_questions[]` / `next_steps[]` without overriding structured claim/evidence truth
  - multi-source claim slides remain source-specific unless the focus-family heuristic has enough signal to assert convergence or divergence
- Branch review note (2026-03-13, current pass):
  - profile selectors should not reopen fuzzy first-match resolution by accident
  - `project_profile` / `research_profile` must stay bound to explicit deterministic projection-backed resolution and conflict tests
- Remaining next slice:
  - whether the bounded legacy regenerate fallback should remain narrow, tighten further, or expand
  - whether the new CI lane should be made branch-required and whether drift should remain CI-scoped or escalate into stricter operator/API policy
  - deeper contradiction/consensus scoring beyond the current shared-root + limited-alias + clear-majority + same-source-set cross-focus heuristic
  - deeper note/context text tuning beyond the current framing layer

## Midpoint Review (2026-03-13)
- current stable lane:
  - `paper/note/screening/topic/profile -> state.json -> evidence ledger -> draft artifact`
  - when `cross_focus_pattern` exists, it now stays visible at the top summary/limits-slide layer instead of being dropped behind family-level consensus ordering
  - when the same majority subset repeats across multiple focus families inside the same interpreted source population, `cross_focus_majority_pattern` can summarize that partial pattern without dropping family-level conflicts
  - `cross_focus*` label/evidence/source-id ordering is now canonicalized, and partial convergence summaries can carry explicit `outlier_source_item_ids[]`
  - curated glycemic family now closes the strong-case gap between `blood sugar` and `glycemic/glucose` wording without reopening fuzzy synonym search
- next risky lane:
  - broader non-overlapping synonym coverage and looser cross-focus majority/partial-consensus scoring beyond the current root-overlap + limited valence heuristic
  - deeper note/context tuning beyond the current overview/key-point/slide framing enrichment
- fixed rule before expanding:
  - lower-priority notes are `context-only`
  - they may frame discussion but must not override structured claims/evidence
  - screening rationale is also `context-only`
  - when multiple note sources exist, the pack should surface caution instead of implying merged truth

## Purpose
이 문서는 `docs/MEETING_PACK.md`를 실제 코드로 내릴 때, 작은 PR 순서와 acceptance를 고정하기 위한 계획이다.

핵심 원칙:
- `Meeting Pack`은 downstream draft artifact다.
- source truth는 `state.json`과 notes/profiles에 남아 있어야 한다.
- evidence-linked output contract를 먼저 고정하고, presentation export는 뒤로 미룬다.

## Phase 1: Schema + Root Path + Store
목적:
- `Meeting Pack`의 Pydantic contract와 storage root를 먼저 고정한다.

범위:
- `src/schemas/meeting_pack.py`
- `src/services/runtime_paths.py`
  - `meeting_packs_root()`
- `src/meeting_packs/store.py`
  - save/load helpers
  - deterministic markdown/json write helpers
- tests for schema validation and path resolution

비범위:
- generation logic
- FastAPI endpoint
- viewer integration

Acceptance:
- `MeetingPack` JSON을 validate/save/load할 수 있다.
- pack root가 env override와 repo-relative fallback을 지원한다.
- 동일 `pack_id` 재저장은 append dump가 아니라 overwrite/idempotent write semantics를 가진다.

## Phase 2: Source Resolver + Evidence Ledger Builder
목적:
- selected sources에서 mode-independent canonical input bundle을 만든다.

범위:
- `src/meeting_packs/source_resolver.py`
- `src/meeting_packs/evidence.py`
- source selectors:
  - `paper_slug`
  - `paper_state`
  - `paper_note`
  - `project_note`
- `research_note`
- `screening_decision`
- `topic` with deterministic structured-signal exact match
- `project_profile` / `research_profile` with deterministic `ResearchDNA` projection-profile resolution
- `state.json` first merge policy
- deduplicated pack-level `evidence_refs[]` ledger

비범위:
- LLM prompting optimization
- UI selection flow

Acceptance:
- source priority order가 코드로 고정된다.
- conflicting evidence는 collapse되지 않고 surfaced marker로 남는다.
- pack sections가 참조할 stable pack-local evidence ref IDs를 만들 수 있다.

## Phase 3: Mode-Specific Generation Service
목적:
- 같은 source bundle로 mode별 다른 emphasis를 만드는 service layer를 만든다.

범위:
- `src/meeting_packs/service.py`
- mode planners:
  - `journal_club`
  - `literature_update`
  - `project_progress_update`
  - `experiment_proposal`
- generated sections:
  - one-page summary
  - slide outline
  - speaker notes
  - discussion questions
  - expected questions
  - next steps
- uncertainty/conflict markers

비범위:
- PPTX/Google Slides
- figure generation
- chatbot integration

Acceptance:
- 모드별 output structure가 visibly different하다.
- unsupported bullets는 생성되지 않거나 `uncertain`로 표시된다.
- numeric results는 source 없이 생성되지 않는다.

## Phase 4: Markdown Renderer + FastAPI Surface
목적:
- 저장된 pack을 읽고 deterministic markdown draft와 API response로 노출한다.

범위:
- `src/meeting_packs/renderer.py`
- `backend/routers/meeting_packs.py`
- `backend/main.py` router wiring
- endpoints:
  - `POST /meeting-packs/generate`
  - `GET /meeting-packs/{pack_id}`
  - `GET /meeting-packs/{pack_id}/markdown`

비범위:
- frontend pack browser
- paper detail action button

Acceptance:
- API는 thin wrapper이고 core logic은 service에 있다.
- JSON과 Markdown이 같은 pack data에서 deterministic하게 나온다.
- route regression tests가 통과한다.

## Phase 5: Example Output + Docs + Contrast Tests
목적:
- v1 usefulness를 example output과 regression coverage로 잠근다.

범위:
- example fixture or recorded sample output for at least one mode
- `docs/MEETING_PACK.md` example refresh
- tests for:
  - `journal_club`
  - one contrast mode (`experiment_proposal` 권장)
- markdown snapshot or contract-style text assertions

Acceptance:
- 하나 이상의 realistic example pack output이 재생성 가능하다.
- 두 mode의 structure 차이가 테스트에서 드러난다.
- evidence refs가 major sections에 존재하는지 검증된다.

## Cross-Cutting Guardrails

1. API-first
- CLI or script는 thin wrapper여야 한다.

2. Pydantic contracts
- request/response/output files는 `src/schemas/meeting_pack.py`로 고정한다.

3. Evidence-first
- generation 이전에 evidence ledger를 먼저 만든다.

4. Draft-first
- final interpretation처럼 보이는 deterministic tone을 피하고, uncertainty를 남긴다.

5. No source mutation
- source note/state/profile은 읽기 대상이다.
- v1에서 source canonical state를 pack generation이 rewrite하면 안 된다.

## Recommended PR Sequence

1. `PR-DOC-BE-MeetingPack-v1-schema-store`
- schema, root path, store, docs sync

2. `PR-BE-MeetingPack-source-resolver`
- source resolution, evidence ledger, merge/conflict policy

3. `PR-BE-MeetingPack-generation-api`
- mode generators, markdown renderer, FastAPI endpoints

4. `PR-QA-MeetingPack-contrast-coverage`
- example outputs and regression coverage

## Immediate Start Recommendation
첫 구현은 Phase 1 + Phase 2의 얇은 slice로 시작하는 것이 맞다.

이유:
- storage/evidence contract가 먼저 고정돼야 이후 LLM/template tuning이 흔들리지 않는다.
- `Meeting Pack`의 가장 큰 실패 가능성은 wording이 아니라 source/evidence boundary 혼선이다.

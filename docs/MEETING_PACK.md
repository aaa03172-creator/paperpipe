# Meeting Pack

Status: Active spec
Date: 2026-03-17
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/WEB_VIEWER.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/RESEARCH_DNA.md`
- `docs/archive/Meeting_Pack_Fit_Review_2026-03-13.md`
- `docs/archive/Meeting_Pack_v1_Implementation_Plan_2026-03-13.md`
- `docs/archive/Meeting_Pack_Real_Probe_2026-03-13.md`
- `docs/archive/Meeting_Pack_Profile_Projection_Real_Probe_2026-03-13.md`
- `docs/archive/Meeting_Pack_V1_Checklist_Review_2026-03-13.md`

## Current Implementation Status
- Implemented in the current runtime:
  - `src/schemas/meeting_pack.py`
  - `src/meeting_packs/store.py`
  - `src/services/runtime_paths.py::meeting_packs_root()`
  - regression tests for schema/store/runtime paths
- Generation surface is also implemented in the current runtime:
  - `src/meeting_packs/source_resolver.py`
  - `src/meeting_packs/evidence.py`
  - `src/meeting_packs/service.py`
  - `src/meeting_packs/renderer.py`
  - `backend/routers/meeting_packs.py`
  - `GET /meeting-packs`
  - `POST /meeting-packs/generate`
  - `POST /meeting-packs/{pack_id}/regenerate`
  - `POST /meeting-packs/{pack_id}/rerender`
  - `GET /meeting-packs/{pack_id}`
  - `GET /meeting-packs/{pack_id}/trace`
  - `GET /meeting-packs/{pack_id}/validate`
  - `GET /meeting-packs/{pack_id}/markdown`
  - `GET /meeting-packs/{pack_id}/trace` and `GET /meeting-packs` stay debug/ops surfaces, not reader-facing evidence views
  - frontend ops/debug inspector routes: `/meeting-packs` (saved packs index + local search/filter + quick open), `/meeting-packs/{pack_id}` with guarded draft regenerate/rerender actions and carried success notice after regenerate
  - saved `generation_request` snapshot inside `meeting_pack.json`
  - `readiness`, `regenerated_from_pack_id`, and response-level `markdown_sync`
  - `validate` now downgrades regenerate availability to `unavailable` with warnings when the current vault can no longer resolve the saved selector set
  - bundle save now rolls back on second-write failure so partial `meeting_pack.json` / `meeting_pack.md` artifacts are not left behind
  - repeatable real-input smoke command: `python3 scripts/check_meeting_pack_real_smoke.py`
  - stronger actual-paper-aligned developer probe can be rerun by passing `--expect-key-point-substring` and `--require-quality-pass` against an aligned temp vault
  - standard local verify lane: `./scripts/run_meeting_pack_verify.sh`
  - standard local verify lane now fails if the generated saved bundles drift or lose regenerate availability via `python3 scripts/check_meeting_pack_storage_sync.py`
  - CI workflow now runs the same lane under `.github/workflows/meeting-pack-verify.yml`
  - bundle-local `quality_gate.json` now adds a bounded content-risk scan that can downshift `overall_status` to `warn` for generic key-point text, high exact key-point reuse across saved packs, or title/key-point token mismatch without changing canonical `pack.readiness`
  - operator hygiene CLI: `paperpipe archive-meeting-pack-noise`
  - cleanup command is dry-run by default and archives low-value pack directories into `storage/_quarantine/meeting_packs/<timestamp>/` with a `manifest.json` record instead of deleting them in place
  - structured `one_page_summary.consensus_points[]` / `conflicts[]` + Markdown `[Consensus]` / `[Conflict]` rendering
  - saved `retrieval_trace[]` for selector/load observability during pack generation
- Currently deferred or open follow-ups:
  - whether bounded legacy fallback should stay as-is or be tightened/further expanded
  - whether the new CI lane should be made branch-required and whether drift should remain CI-scoped rather than API/operator-blocking
  - current GitHub settings limitation: `scripts/enable_required_checks.sh` cannot currently promote `meeting-pack-verify` to a required branch check on this private repo because the branch protection API returns `403 Upgrade to GitHub Pro or make this repository public`
  - richer contradiction/consensus scoring beyond the current limited-alias + clear-majority heuristic
  - deeper note/context-derived mode tuning beyond the current overview/key-point/slide framing enrichment

현재 구현 경계:
- supported source selectors:
  - `paper_slug`
  - `paper_state`
  - `paper_note`
  - `project_note`
  - `research_note`
  - `screening_decision`
  - `topic`
  - `project_profile`
  - `research_profile`
- exact duplicate selectors는 source resolution 단계에서 dedupe된다.
- `paper_note` / `project_note` / `research_note`는 `context-only` source다.
- `screening_decision`은 `screening run context-only` source다.
- `screening_decision` ref는 현재 slice에서 반드시 `<dna_id>:<run_id>` 형식을 써야 한다.
- `topic`은 exact structured-signal selector다.
- `topic` match는 note frontmatter(`tags/topic/topics`) + structured state(`entities/mesh/outcomes`, claim `tags/outcomes`)에 대한 normalized exact match만 허용한다.
- `topic`은 claim text/evidence text full-text fuzzy search를 다시 열지 않는다.
- `project_profile` / `research_profile`는 deterministic selector이지만, 현재는 generic manual profile이 아니라 `ResearchDNA` projection profile에만 열려 있다.
- profile selector match는 `profile.notes` 안의 projection metadata(`source_dna_id`, `source_query_version`)를 읽고, 해당 query version의 latest screened include set을 existing vault `state.json`에 매핑하는 방식으로만 수행한다.
- profile selector resolution은 `PAPERPIPE_PROFILES_PATH` / service `profiles_path` override와 같은 actual profile config path를 따라야 한다.
- profile selector는 `title` / `notes` free text / `Profile.query.must/should/must_not` / semantic search를 selection에 쓰지 않는다.
- projection metadata가 없거나, include set이 existing structured paper state로 매핑되지 않으면 reject 한다.
- note selector는 linked `paper_state`를 찾아 pack을 구성할 수 있지만, note-derived wording은 structured claim/evidence truth를 override하지 않는다.
- structured paper source가 하나라도 있으면 pack title/overview/opening-context의 primary reference label은 note/screening title보다 paper title을 우선한다.
- `paper_note`만 own note stem과 same-slug `state.json` fallback을 허용한다.
- `project_note` / `research_note`는 explicit linked papers(`paper_slugs/papers/related_papers` 또는 wikilink) 없이 free-text fuzzy selection을 열지 않는다.
- `screening_decision`은 include/exclude rationale와 top `reason_code` 요약을 pack에 올릴 수 있지만, claim evidence처럼 쓰이면 안 된다.
- multi-source convergence/divergence는 `one_page_summary.consensus_points[]` / `conflicts[]`와 slide-level `[Consensus]` / `[Conflict]` wording으로 surfaced 된다.
- current cross-source heuristic은 claim/state structured signals(`tags/outcomes/entities/mesh`)에서 derived된 shared focus family와 directional wording을 보수적으로 잡는다.
- focus family는 normalized root-token overlap heuristic이 기본이지만, 현재 slice에서는 limited alias map/derived family로 strong cases(`memory`/`cognition`, `glucose`/`glycemic`/`blood sugar`, `safety`/`tolerability`/`adverse events`)를 추가로 합친다.
- wording classifier는 `increase/decrease/null/benefit/harm` category를 분리하고, focus family가 clear `higher-is-better` / `higher-is-worse` semantics를 가질 때만 benefit-like와 signed increase/decrease를 outcome-level consensus/conflict로 승격한다.
- `safety` family처럼 row마다 polarity anchor가 다른 strong case는 limited row-level valence mapping으로 `tolerability` vs `adverse events`를 같은 outcome axis로 정리할 수 있다.
- focus-family valence가 불분명하면 benefit-like와 signed increase/decrease는 여전히 자동 consensus로 합치지 않는다.
- `3+` source에서 clear majority directional alignment가 있으면 `consensus_points[]`에 `majority_directional_alignment`를 추가로 남기되, divergence `conflicts[]`도 함께 유지한다.
- 같은 source set이 `2+` distinct focus family에서 같은 directional framing을 반복하고, family evidence set도 실제로 분리되어 있으면 `consensus_points[]`에 `cross_focus_pattern`을 추가로 남길 수 있다.
- `3+` source에서 같은 majority source subset과 같은 interpreted source population이 `2+` distinct focus family에서 반복되면 `consensus_points[]`에 `cross_focus_majority_pattern`을 추가로 남길 수 있다.
- `cross_focus_pattern`은 repeated draft pattern만 뜻하고, 서로 다른 outcome/focus family를 interchangeable한 하나의 outcome으로 취급한다는 뜻은 아니다.
- `cross_focus_majority_pattern`도 partial draft pattern만 뜻하고, outlier source가 남아 있는 상태의 partial convergence를 더 높은 수준에서 요약한 것뿐이다.
- `cross_focus*` label summary와 merged `evidence_refs[]` ordering은 canonicalized되어 claim encounter order에 따라 흔들리면 안 된다.
- generated `source_item_ids[]` / `outlier_source_item_ids[]` ordering도 canonicalized되어 row encounter order에 따라 흔들리면 안 된다.
- `cross_focus_pattern`이 생성되면 summary/top-slide layer에서는 family-level directional consensus보다 먼저 보여야 한다.
- `cross_focus_majority_pattern`도 생성되면 summary/top-slide layer에서는 family-level `majority_directional_alignment`보다 먼저 보여야 한다.
- divergence가 asymmetric하면 conflict summary는 majority/outlier count를 드러내야 한다.
- note/screening context는 현재 overview, first `key_points[*].uncertainty_note`, opening/context slide framing, `discussion_questions[]`, `expected_questions[]`, `next_steps[]`에 mode-specific wording으로 반영되지만, claim text나 claim slide truth를 override하지는 않는다.
- heuristic signal이 약하면 consensus/conflict를 invented하지 않고 source-specific cautions만 남긴다.
- multiple screening runs가 같이 들어오면 selection criteria 차이를 structured conflict로 surfaced 해야 한다.
- new packs persist `generation_request` so the pack can be regenerated from saved intent without guessing selectors from rendered content.
- `rerender`는 saved `meeting_pack.json`에서 deterministic markdown을 다시 생성하는 explicit recovery lane이다.
- response-level `markdown_sync`는 saved markdown과 deterministic render의 drift 여부를 자동으로 surfaced 한다.
- pack contract는 `readiness`로 `evidence_backed` vs `background_only`를 구분한다.
- `evidence_backed`는 claim text 존재만이 아니라 최소 `1`개의 direct structured evidence ref가 있는 경우에만 허용한다.
- direct structured evidence ref가 있더라도 `grounded` / `resolution` metadata가 비어 있거나 unresolved면 pack 안에서 uncertainty로 surfaced 해야 하며, full citation verification처럼 말하면 안 된다.
- regenerated draft는 `regenerated_from_pack_id`로 immediate parent lineage를 남긴다.
- legacy packs that predate `generation_request` storage can still rerender, and regenerate may use a bounded `source_items` fallback only when selector reconstruction is deterministic.
- `validate`는 saved request 또는 bounded legacy fallback이 있더라도 current vault에서 selector set을 다시 풀 수 없으면 `can_regenerate=false` / `regenerate_strategy=unavailable`로 내려야 한다.
- `validate` warnings는 current vault regenerate availability warning뿐 아니라 bounded content-risk review warning도 함께 surfaced 할 수 있어야 한다.
- `save_meeting_pack_bundle()`은 JSON write 뒤 markdown write가 실패해도 이전 bundle state로 롤백되어 partial artifact를 남기지 않아야 한다.

## Multi-Angle Checkpoint (2026-03-13)
현재 기준 multi-angle review 요약은 아래와 같다.

- architecture:
  - `Meeting Pack`이 separate research state로 커지지 않고 downstream draft artifact로 남아 있다.
- implementation:
- current stable lane은 `selector metadata/context -> canonical paper state (+ explicit source artifacts when named) -> evidence ledger -> deterministic markdown`이다.
- current source loading rule should stay `selector metadata/context -> canonical paper state/source artifacts -> evidence ledger -> markdown`.
- retrieval observability should stay deterministic and path/id grounded, not semantic black-box tracing.
- operations:
  - real probe까지 남아 있어 test-only 구현 상태는 아니다.
- evaluation:
  - major sections evidence refs 존재는 regression으로 확인된다.
- risk:
  - 다음 slice의 실제 위험은 broader non-overlapping synonym coverage, looser cross-focus majority/partial-consensus semantics beyond the current same-source-set + distinct-evidence guardrail, deeper note/context-derived synthesis beyond the current framing layer를 current heuristic보다 더 정교하게 다루는 점이다.

따라서 현재 구현 규칙은 아래로 고정한다.
- `project_note` / `research_note`는 `context-only` source다.
- `screening_decision`도 `context-only` source다.
- `topic`은 deterministic selector이고, current exact-match rule 밖의 fuzzy expansion은 허용하지 않는다.
- `project_profile` / `research_profile`도 deterministic selector이고, projection-backed include-set resolution 밖의 fuzzy expansion은 허용하지 않는다.
- non-test runtime에서는 fixture-like structured sidecar state를 real paper truth처럼 source selection에 올리면 안 된다. isolated E2E runtime이나 explicit fixture opt-in일 때만 허용한다.
- secondary note source는 `state.json` claim/evidence truth를 override하지 않는다.
- screening rationale은 selection context를 설명할 수 있지만, effect/evidence truth를 override하지 않는다.
- note-derived framing은 uncertainty/caution layer로만 pack에 반영한다.
- screening-derived framing도 uncertainty/caution layer로만 pack에 반영한다.
- multiple secondary notes가 있으면 merge된 truth처럼 보이게 만들지 않고, explicit caution으로 surfaced 해야 한다.
- pack generation may persist additive `retrieval_trace[]`, but that trace is observability metadata only and does not become scientific truth.
- any future selector/debug inspector API must remain operational metadata only and must not be treated as scientific truth or reader-facing evidence.

## Source Trace Contract
`Meeting Pack` and paper-note detail now share the same narrow trace principle:
- deterministic
- path/id grounded
- operational metadata only
- never scientific truth by itself

`Meeting Pack` side:
- `meeting_pack.json.retrieval_trace[]`
- `GET /meeting-packs/{pack_id}/trace`
- intended to explain:
  - which selector was accepted
  - which paper slugs were matched
  - which `state.json` paths were loaded
  - whether a selector was deduped, resolved, or loaded

paper-note detail side:
- `GET /paper-notes/{slug}` optional `context_trace`
- intended to explain:
  - note load path
  - markdown section filtering
  - reference resolution order
  - related-paper derivation
  - `state.json` load vs missing

Shared rule:
- traces may justify operational behavior
- traces may not override claim/evidence truth
- traces should stay additive and cheap enough to persist without opening a new observability subsystem

## Historical V1 Checklist Review (2026-03-13)
`Meeting Pack` v1 checklist review는 `docs/archive/Meeting_Pack_V1_Checklist_Review_2026-03-13.md`에 기록한다.

현재 판정:
- `generation works from real inputs`: pass
- `modes are meaningfully different`: pass
- `major slides are evidence-linked`: pass
- `outputs are saved as reusable structured artifacts`: pass
- `packs are editable/regenerable`: pass
- `weak/conflicting evidence is surfaced honestly`: pass
- `no fabricated numeric claims`: pass

현재 우선순위는 richer semantics 확장보다 아래 hardening이다.
- bounded legacy regenerate fallback policy
- local drift-enforcing verify lane의 CI/operator escalation 여부

## Purpose
`Meeting Pack`은 PaperPipe가 이미 보유한 structured research state를 바탕으로, 실험실 미팅에서 바로 검토 가능한 발표 초안을 생성하는 downstream draft artifact다.

현재 bounded surface는 아래를 목표로 한다.
- one-page summary
- slide outline (`5-8` slides)
- speaker notes
- discussion questions
- expected PI/advisor questions
- next-step suggestions

이 문서는 중요한 경계 하나를 먼저 고정한다.
- `Meeting Pack`은 canonical research state를 새로 소유하지 않는다.
- `Meeting Pack`은 existing evidence-linked state를 재구성한 draft output이다.
- 현재 surface는 발표 내용의 correctness와 evidence traceability를 먼저 해결하고, visual slide export는 의도적으로 뒤로 미룬다.

## Actual-Paper-Aligned Probe
Current `Meeting Pack` verification now distinguishes between two different smoke levels:

- default real-input smoke:
  - `python3 scripts/check_meeting_pack_real_smoke.py`
  - intended to prove runtime wiring, bundle persistence, and markdown sync against the current bundled vault input
- actual-paper-aligned developer probe:
  - run the same script against a temp vault whose note and `state.json` are aligned to one real paper abstract
  - optionally require:
    - `--expect-key-point-substring "clinical-biological construct"`
    - `--require-quality-pass`

Important boundary:
- the aligned probe is still an abstract-aligned gold path
- it does not claim full-PDF automatic extraction fidelity
- the stricter flags should remain opt-in until the default bundled smoke input is upgraded from its current fixture-lite posture

## Current Judgment
현재 repo 상황에서 `Meeting Pack`은 아래 위치에 놓는 것이 가장 자연스럽다.

- 상위 canonical 입력 truth:
  - `vault/.pp/<slug>/state.json`
  - explicitly named run artifacts under `storage/artifacts/<paper-segment>/<run_id>/`
- context-only secondary inputs:
  - paper note frontmatter/body
  - project/research notes
  - screening rationale
  - `ResearchDNA` projected profiles
- 출력 artifact:
  - `storage/meeting_packs/<pack_id>/meeting_pack.json`
  - `storage/meeting_packs/<pack_id>/meeting_pack.md`
- reversible cleanup/archive artifact:
  - `storage/_quarantine/meeting_packs/<timestamp>/manifest.json`
  - archived pack directories remain bundle-local and non-canonical after quarantine
- interface:
  - backend service + thin FastAPI endpoint 우선
  - CLI/UI는 이후 wrapper or surface로 붙인다
  - current operator CLI wrapper includes `paperpipe archive-meeting-pack-noise` for bounded storage cleanup

이 경로를 택하는 이유는 다음과 같다.
- pack은 단일 paper note를 넘는 multi-source artifact일 수 있다.
- existing `.pp/<slug>/state.json`는 paper-scoped canonical state이므로 pack 자체의 canonical 저장소로 재사용하면 scope가 뒤섞인다.
- `storage/artifacts/`는 ingest/read/verify run 결과물용이므로, meeting draft는 별도 root가 더 명확하다.
- note/profile/screening context는 framing과 selection context를 줄 수 있지만, canonical claim/evidence truth를 새로 소유하지 않는다.

## Supported Modes
모든 모드는 같은 output contract를 사용하지만 강조점이 달라야 한다.

Shared output-mode family mapping:
- `journal_club` -> `lab_meeting`
- `literature_update` -> `lab_meeting`
- `project_progress_update` -> `project_update`
- `experiment_proposal` -> `builder_debug`

이 family는 presentation lane을 설명하는 공통 축이다. concrete `mode`는 meeting-pack-specific framing을 유지하고, family는 다른 surface와 공통 분류를 맞추는 용도로만 쓴다.

### `journal_club`
- focus:
  - 핵심 질문
  - methods/design
  - 주요 결과
  - strengths/limitations
  - discussion
- output-mode family: `lab_meeting`

### `literature_update`
- focus:
  - topic trend
  - key papers and comparison
  - convergence/divergence
  - open questions
- output-mode family: `lab_meeting`

### `project_progress_update`
- focus:
  - 이번 주/최근 변경점
  - 현재 evidence state
  - blockers
  - next actions
- output-mode family: `project_update`

### `experiment_proposal`
- focus:
  - rationale
  - prior evidence
  - proposed design
  - risks/failure modes
  - expected outcomes
- output-mode family: `builder_debug`

## Canonical Boundary

### `Meeting Pack` owns
- draft packaging for a specific meeting context
- mode-specific ordering and framing
- explicit uncertainty markers
- evidence-linked outline/notes/questions
- reusable JSON + Markdown rendering of the pack

### `Meeting Pack` does not own
- canonical claim/evidence truth
- note frontmatter truth
- screening/source-policy truth
- research/profile truth
- final slide design/export

### Guardrails
- outputs are always draft-first and human-reviewed
- do not invent numeric results
- do not present generated notes as final scientific interpretation
- if evidence conflicts, surface the conflict explicitly
- if support is weak, mark uncertainty instead of smoothing it away
- research correctness outranks presentation polish

## Input Priority
Generator는 아래 우선순위를 지켜 source를 읽는다.

1. structured claim/evidence data from `state.json`
2. paper metadata + abstract/fulltext-derived summaries
3. project notes / research notes
4. screening decisions / include-exclude rationale
5. research profile / project profile

추가 규칙:
- higher-priority source와 lower-priority source가 충돌하면 lower-priority source가 higher-priority claim을 silently override하면 안 된다.
- 같은 point를 여러 source가 지지하면 dedupe 후 `consensus_points[]` 또는 multi-source support로 기록한다.
- strong higher-better/higher-worse focus family에서는 benefit-like vs signed increase/decrease도 outcome-level consensus/conflict로 정리할 수 있다.
- 같은 point를 서로 다르게 말하면 `caution_notes` 또는 uncertainty block으로 conflict를 남긴다.
- `topic` selector는 explicit topic field match만 허용하고, full-text semantic/fuzzy search는 지원하지 않는다.
- `project_profile` / `research_profile`는 현재 `ResearchDNA` projection profile에만 열려 있고, `profile.notes` projection metadata를 통해 screened include candidates를 existing structured state에 매핑하는 방식만 허용한다.
- profile selector는 `title` / `notes` / `query.must/should/must_not` / free-text semantic/fuzzy match를 selection에 쓰지 않는다.
- projection metadata가 없거나 mapped `state.json`이 없으면 broad fallback 없이 reject 한다.

## Evidence-Linking Rule
모든 major section은 evidence에 연결되어야 한다.

현재 contract에서는 이 규칙을 아래 수준으로 강제한다.
- `one_page_summary.key_points[*]`는 `evidence_refs[]`를 가진다.
- `one_page_summary.consensus_points[*]`는 `source_item_ids[]`와 `evidence_refs[]`를 가진다.
- partial convergence type은 가능하면 `outlier_source_item_ids[]`도 가져야 한다.
- `consensus_type`은 현재 `directional_alignment`, `majority_directional_alignment`, `cross_focus_pattern`, 또는 `cross_focus_majority_pattern`이다.
- `one_page_summary.conflicts[*]`는 `source_item_ids[]`와 `evidence_refs[]`로 traceable해야 한다.
- 각 slide는 최소 slide-level `evidence_refs[]`를 가진다.
- `speaker_notes[*]`, `discussion_questions[*]`, `expected_questions[*]`, `next_steps[*]`도 가능하면 `evidence_refs[]`를 가진다.
- evidence가 전혀 없는 point는 draft에 넣더라도 `uncertain` 또는 `background-only`로 명시한다.

existing contract 정렬:
- evidence locator field는 `docs/API_CHAT_CONTRACT.md`의 `ChatEvidenceRef`/`ChatLocator` semantics를 따른다.
- 즉, existing `paper_slug`, `claim_id`, `evidence_id`, `run_id`, `locator` 체계를 재사용한다.

## Storage Contract

### Root
- `storage/meeting_packs/<pack_id>/`

### Files
- `storage/meeting_packs/<pack_id>/meeting_pack.json`
- `storage/meeting_packs/<pack_id>/meeting_pack.md`

### Pack identity
- `pack_id`는 unique write key다.
- current recommended format:
  - `meetingpack_<timestamp>_<mode>_<shorthash>`
- current implementation은 same-request regenerate collision을 줄이기 위해 timestamp에 microsecond precision을 쓸 수 있다.
- 같은 `pack_id`를 다시 render/save할 때는 overwrite 가능해야 하지만, append-only duplicate dump를 남기면 안 된다.

## Pydantic Contract
현재 contract는 최소한 아래 구조를 `src/schemas/meeting_pack.py`로 고정한다.

```json
{
  "id": "meetingpack_20260313T090000123456Z_literature_update_a1b2c3d4",
  "mode": "literature_update",
  "title": "Inflammatory pathway literature update draft",
  "created_at": "2026-03-13T09:00:00Z",
  "status": "draft",
  "readiness": "evidence_backed",
  "generation_request": {
    "mode": "literature_update",
    "title": "Inflammatory pathway literature update draft",
    "source_items": [
      {
        "type": "paper_state",
        "ref": "paper-alpha"
      },
      {
        "type": "paper_state",
        "ref": "paper-beta"
      },
      {
        "type": "paper_state",
        "ref": "paper-gamma"
      }
    ],
    "max_slides": 6
  },
  "regenerated_from_pack_id": null,
  "source_items": [
    {
      "id": "src_01",
      "type": "paper_state",
      "ref": "paper-alpha",
      "title": "paper-alpha",
      "priority": 1,
      "included": true
    },
    {
      "id": "src_02",
      "type": "paper_state",
      "ref": "paper-beta",
      "title": "paper-beta",
      "priority": 1,
      "included": true
    },
    {
      "id": "src_03",
      "type": "paper_state",
      "ref": "paper-gamma",
      "title": "paper-gamma",
      "priority": 1,
      "included": true
    }
  ],
  "one_page_summary": {
    "overview": "Draft overview of the current evidence movement.",
    "key_points": [
      {
        "label": "Main finding",
        "text": "The paper reports reduced inflammatory signaling.",
        "evidence_refs": ["evref_01"],
        "uncertainty_note": null
      }
    ],
    "consensus_points": [
      {
        "label": "Partial directional convergence: inflammatory pathway",
        "summary": "2 of 3 sources describe inflammatory pathway with aligned positive-outcome wording under a higher-is-worse framing; 1 source uses null/no-change wording. Treat this as partial convergence only and re-check the outlier sources before presenting a consensus conclusion.",
        "consensus_type": "majority_directional_alignment",
        "source_item_ids": ["src_01", "src_02"],
        "outlier_source_item_ids": ["src_03"],
        "evidence_refs": ["evref_01", "evref_02"]
      }
    ],
    "conflicts": [
      {
        "label": "Possible divergence: inflammatory pathway",
        "summary": "Selected sources describe inflammatory pathway with 2 sources use positive-outcome wording while 1 source uses null/no-change wording under a higher-is-worse framing. Compare source-specific claims before presenting a consensus conclusion.",
        "conflict_type": "possible_divergence",
        "source_item_ids": ["src_01", "src_02", "src_03"],
        "evidence_refs": ["evref_01", "evref_02", "evref_03"]
      }
    ],
    "uncertainties": [
      "Outcome direction is supported, but effect size is not consistently reported."
    ]
  },
  "slides": [
    {
      "slide_title": "Why this paper matters",
      "purpose": "Frame the question and relevance",
      "bullets": [
        "Study asks whether the intervention changes the inflammatory pathway.",
        "Evidence is strongest for directionality, not magnitude."
      ],
      "evidence_refs": ["evref_01", "evref_02"],
      "optional_figure_candidates": [
        {
          "label": "Primary results figure",
          "source_item_id": "src_01",
          "reason": "Best figure for the main outcome"
        }
      ],
      "caution_notes": [
        "Do not quote an effect size unless it is re-verified from source text."
      ]
    }
  ],
  "speaker_notes": [
    {
      "slide_index": 1,
      "text": "Open with the biological question before describing the assay.",
      "evidence_refs": ["evref_01"]
    }
  ],
  "discussion_questions": [
    {
      "question": "How convincing is the causal interpretation?",
      "rationale": "Evidence is directionally supportive but mechanistic depth is limited.",
      "evidence_refs": ["evref_01", "evref_03"]
    }
  ],
  "expected_questions": [
    {
      "question": "What is the strongest limitation of this paper?",
      "suggested_response": "Sample and measurement limitations appear more defensible than overclaiming mechanism.",
      "evidence_refs": ["evref_03"]
    }
  ],
  "next_steps": [
    {
      "action": "Re-check the methods section for assay limitations before presenting.",
      "why": "Methods caveat is likely to come up in discussion.",
      "priority": "high",
      "evidence_refs": ["evref_03"]
    }
  ],
  "evidence_refs": [
    {
      "id": "evref_01",
      "paper_slug": "wenzelShortchainFattyAcids2020",
      "claim_id": "claim_4d5f89ab12cd",
      "evidence_id": "evidence_81b6d88e2f43",
      "run_id": "skill-20260309T000000Z-critical_appraisal",
      "locator": {
        "page": 1,
        "section": "Abstract"
      },
      "support_type": "direct",
      "note": "Supports the primary direction-of-effect statement."
    }
  ]
}
```

### Notes on the contract
- top-level `evidence_refs[]`는 deduplicated ledger다.
- nested `evidence_refs[]`는 pack-local evidence ref IDs를 사용한다.
- nested payload duplication 대신 top-level ledger를 참조한다.
- `speaker_notes`, `discussion_questions`, `expected_questions`, `next_steps`는 string list가 아니라 structured item list로 저장한다.
- `one_page_summary.consensus_points[]`는 reusable structured convergence artifact다.
- `one_page_summary.conflicts[]`는 free text warning이 아니라 reusable structured review artifact다.

## Generation Request Contract
현재 request는 typed source selection을 받아야 한다.

```json
{
  "mode": "journal_club",
  "title": "Optional custom title",
  "source_items": [
    { "type": "paper_slug", "ref": "wenzelShortchainFattyAcids2020" },
    { "type": "project_note", "ref": "Projects/SCFA.md" },
    {
      "type": "screening_decision",
      "ref": "dna_mci_medium_chain_triglycerides_probe_20260312:pilot_mci_mct_probe_20260312_02"
    }
  ],
  "max_slides": 8
}
```

full target selector type:
- `paper_slug`
- `paper_state`
- `paper_note`
- `project_note`
- `research_note`
- `screening_decision`
- `project_profile`
- `research_profile`
- `topic`

이 request shape를 쓰는 이유:
- single paper, multi-paper, project, topic 흐름을 같은 endpoint에서 처리할 수 있다.
- future UI가 paper selection, project selection, topic selection을 각각 따로 제공해도 backend contract는 유지된다.
- 현재 구현은 `paper/note/screening/topic/profile` subset을 지원한다.
- lower-priority inputs가 `state.json` truth를 override하지 못하게 막는 규칙은 현재 지원 subset에서만 먼저 고정한다.

## Generation Flow
현재 generation sequence는 아래를 따른다.

1. resolve selected source items
2. read high-priority structured evidence from `state.json`
3. collect secondary note/rationale context
4. build deduplicated evidence ledger
5. synthesize mode-specific sections
6. mark uncertainty/consensus/conflict explicitly
7. persist `meeting_pack.json`
8. persist original `generation_request`
9. render deterministic `meeting_pack.md`

### Non-goals in the same flow
- no PPTX export
- no Google Slides export
- no auto-designed visual slides

### `screening_decision` ref format
- current ref는 반드시 `<dna_id>:<run_id>`다.
- 이 selector는 개별 candidate row가 아니라 screening run 전체의 decision context를 읽는다.
- pack에는 `include/exclude/unclear` count와 top `reason_code` 요약만 context layer로 올린다.
- no heavy chart/image generation
- no chatbot or memory layer

## Markdown Rendering Contract
`meeting_pack.md`는 사람이 바로 읽고 수정하기 쉬운 draft여야 한다.

최소 섹션:
- title block
- mode + created_at
- sources used
- one-page summary
- slide outline
- speaker notes
- discussion questions
- expected questions
- next steps
- evidence ledger

rendering rules:
- 각 major section은 evidence ref ID를 inline 또는 list suffix로 보여준다.
- structured consensus는 Markdown에서도 `[Consensus]` tag로 드러나야 한다.
- structured conflict는 Markdown에서도 `[Conflict]` tag로 드러나야 한다.
- unsupported point는 `[Uncertain]` 또는 `[Conflict]` tag로 드러낸다.
- Markdown body는 deterministic section order를 가진다.
- 같은 `meeting_pack.json`에서 다시 렌더하면 idempotent output이 나와야 한다.

## API Surface
Current endpoint surface:

- `POST /meeting-packs/generate`
  - request: `MeetingPackGenerateRequest`
  - response: `MeetingPackResponse`
- `POST /meeting-packs/{pack_id}/regenerate`
  - response: `MeetingPackResponse`
  - behavior: generate a fresh pack from saved `generation_request` when the current vault can still resolve the saved selector set
- `POST /meeting-packs/{pack_id}/rerender`
  - response: `MeetingPackResponse`
  - behavior: rebuild deterministic markdown from saved `meeting_pack.json`
- `GET /meeting-packs/{pack_id}`
  - response: `MeetingPackResponse`
- `GET /meeting-packs/{pack_id}/validate`
  - response: `MeetingPackValidationResponse`
  - behavior: report `markdown_sync`, `readiness`, and whether regenerate is currently available after rechecking the saved selector set against the current vault; if source resolution fails, return `can_regenerate=false` with warnings
- `GET /meeting-packs/{pack_id}/markdown`
  - response: plain markdown text or wrapper payload

원칙:
- core logic은 service layer에 있어야 한다.
- router는 thin wrapper여야 한다.
- CLI-only path는 만들지 않는다.
- `MeetingPackResponse`는 current slice에서 `markdown_sync`를 함께 돌려줄 수 있어야 한다.
- `readiness=evidence_backed`는 최소 하나의 direct structured evidence ref를 전제로 해야 하고, missing/unresolved grounding metadata는 uncertainty note로 남겨야 한다.
- local standard verify lane은 `./scripts/run_meeting_pack_verify.sh`를 기준으로 유지하고, targeted pytest + real-input smoke + stored-bundle sync check + docs lint를 한 번에 묶어야 한다.

## Example Output Shape
아래는 `literature_update` 모드용 synthetic markdown excerpt다.

```md
# Inflammatory pathway literature update draft

- Mode: literature_update
- Status: draft
- Sources: paper-alpha, paper-beta, paper-gamma

## One-page Summary
- Main question: Does the intervention alter the inflammatory pathway? `[evref_01]`
- [Consensus] Partial directional convergence: inflammatory pathway. 2 of 3 sources describe inflammatory pathway with aligned positive-outcome wording under a higher-is-worse framing; 1 source uses null/no-change wording. Treat this as partial convergence only and re-check the outlier sources before presenting a consensus conclusion. `[evref_01, evref_02]`
- Main take-away: Directional support exists, but quantitative strength is not consistently extractable. `[evref_01, evref_02]`
- [Conflict] Possible divergence: inflammatory pathway. Selected sources describe inflammatory pathway with 2 sources use positive-outcome wording while 1 source uses null/no-change wording under a higher-is-worse framing. Compare source-specific claims before presenting a consensus conclusion. `[evref_01, evref_02, evref_03]`
- Uncertainty: Methods caveats and outcome granularity should be discussed explicitly. `[evref_03]`

## Slide Outline
1. Why this paper matters
2. Study design and model
3. Main evidence
4. Strengths and limitations
5. What we should discuss

## Discussion Questions
- How much of the conclusion depends on indirect evidence rather than direct mechanism? `[evref_01, evref_03]`

## Expected PI Questions
- What is the most defensible limitation to lead with? `[evref_03]`
```

## Future Path To Slide Export
slide export는 `Meeting Pack` 위에 올라가는 separate lane으로 다뤄야 한다.

current downstream sequence:
1. `Meeting Pack` output contract 안정화
2. mode별 outline quality와 evidence coverage 검증
3. optional slide block/template mapping
4. only then PPTX/Google Slides export consideration

즉, slide export 확장은 `meeting_pack.json`을 consumer로 읽어야 하며, current pack contract를 우회해 direct-to-slide generation을 추가하면 안 된다.

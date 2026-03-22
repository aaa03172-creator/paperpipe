# UX Review Report - Paper Notes List

Status: Current review artifact  
Date: 2026-03-22  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-22
Reviewer: Codex

## Header
- Screen/Flow: `/papers` list search -> row scan -> detail open
- Goal action: 연구자가 structured note와 action-needed note를 목록 단계에서 빠르게 판별하고, 적절한 다음 행동으로 이동한다.
- Primary persona: Obsidian + Zotero 기반으로 많은 논문 노트를 훑어보는 연구자
- Current friction: current master에는 list seed fixture가 부족해서 `/papers` UX regression을 backend e2e에서 안정적으로 재현할 수 없었다.
- Success metric: structured-note open rate, filter recovery success rate, list-to-detail CTR
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - vendored local primitives only; no 21st.dev import in this lane
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## Quick Review (5 min)
- Block: list UI 자체보다 backend e2e fixture drift가 더 큰 block이었다.
- Interpret: row-level `Structured`, `ClaimSet ready`, ops vocabulary, matched signal chips는 왜 이 note가 중요한지 빠르게 해석하게 만든다.
- Act: `Structured only`, quoted-search recovery, token recovery, action-needed wording이 다음 행동을 짧게 만든다.
- Store: list 단계에서 detail을 열기 전에도 structured readiness와 repair need를 읽을 수 있어 반복 사용 학습이 좋아진다.
- Ethics first pass: 과장된 urgency 대신 실제 structured state와 artifact snapshot에서만 언어를 뽑는다.

## Full Review
### P0
- `/papers` list는 detail 진입 전 triage surface여야 한다. 따라서 structured note 여부와 action-needed 상태가 row에서 바로 읽혀야 한다.
- backend e2e가 이 상태를 재현하지 못하면 UI regression을 잡지 못하므로, fixture fidelity는 UX 품질의 일부다.
- `Structured only`가 실제로 unstructured note를 제거하고, missing-stats note가 workbench vocabulary로 보이는지 검증해야 한다.

### P1
- matched structured signals는 query와 직접 연결되어야 하므로 `entities`, `mesh`, `outcomes`, `claim_tags`를 그대로 보여주는 편이 낫다.
- quoted exact-phrase miss와 token-based recovery는 zero-results에서 곧바로 다음 행동을 주어야 한다.
- command-style tag picker는 기존 filter bar보다 더 빠르게 tag narrowing을 유도한다.

### P2
- weighted ranking이나 더 많은 focus controls는 현재 필요하지 않다.
- visual polish보다 search/result explanation fidelity가 우선이다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: 연구자는 많은 note 중 지금 열어야 할 note를 빠르게 골라야 한다.
  - Emotion: detail을 열기 전에 신뢰 가능한 정보 향기를 원한다.
  - Action: list에서 검색하고 filter를 건다.
  - Struggle: zero-results와 unstructured notes 때문에 왜 안 보이는지 이해하기 어렵다.
  - Attempt: structured chips, structured-only toggle, empty-state recovery, ops wording을 추가했다.
  - Happy Ending: list에서 바로 “이 note가 structured/repair-needed 상태구나”를 읽고 이동한다.
- BMAP:
  - Motivation: 높음. 사용자는 빠른 triage를 원한다.
  - Ability: list row에 structured and ops cues를 직접 노출해 판단 비용을 줄인다.
  - Prompt: matched chips와 recovery buttons가 다음 행동 prompt 역할을 한다.
- B.I.A.S:
  - Block: 데이터가 없으면 좋은 UI도 검증되지 않는다. fixture fidelity가 먼저다.
  - Interpret: state badges와 structured chips가 relevance를 짧게 설명한다.
  - Act: toggle, exact-phrase recovery, token recovery가 마찰을 줄인다.
  - Store: 성공/실패 모두에서 일관된 recovery path를 학습시킨다.
- Peak-End:
  - Peak: 검색 직후 matched structured chip이 먼저 읽히는 순간
  - Pit: zero-results가 이유 없이 비어 보이는 순간
  - Transition: search -> row scan -> detail/workbench open
  - End: detail을 열기 전 이미 다음 행동 이유를 이해한 상태
- Ethics:
  - Regret: 통과. 실제 structured state와 artifact snapshot만 사용한다.
  - Black Mirror: 통과. 허위 urgency나 조작적 copy가 없다.
  - In Real-Life: 친절한 연구 도구가 “왜 이 note가 relevant한지” 짧게 설명하는 수준이다.

## BMAP diagnosis
- Motivation: 강하다. `/papers`는 찾아야 할 게 명확한 화면이다.
- Ability: row에서 structured/ops cues를 직접 보여줄수록 detail open 전 판단 비용이 줄어든다.
- Prompt: matched chip, `Structured only`, recovery button이 모두 즉시 행동 신호다.

## B.I.A.S diagnosis
- Block: fixture drift가 UX regression visibility 자체를 막고 있었다.
- Interpret: `ClaimSet ready`, `Structured`, `Action needed`, `Structured signals`는 의미 해석을 빠르게 만든다.
- Act: quoted-search recovery와 token buttons가 empty state를 dead-end로 두지 않는다.
- Store: 반복 사용 시 “검색 실패해도 회복 경로가 있다”는 학습이 남는다.

## Peak-End design notes
- Peak: search result row에서 matched signal과 state badge를 바로 읽는 순간
- Pit: structured search나 repair cue가 backend seed 부족으로 검증되지 않는 순간
- Transition: q/tag/toggle -> row scan -> detail or workbench
- End: 사용자가 다음 화면으로 가기 전에 이미 note 상태를 이해한 채 이동한다

## Concrete changes
- Component/route:
  - `PaperNotesListPage`에 command-style tag picker, structured-only toggle, richer row state badges, contextual empty-state recovery 추가
  - `frontend/e2e/backend.spec.ts`에 `paper notes list` 회귀 시나리오 8개 추가
  - `frontend/scripts/run_backend_for_e2e.sh`에 `/papers` list 검증용 최소 fixture 추가
- Copy:
  - `Structured only`
  - `ClaimSet ready`
  - `Action needed`
  - `Search without quotes`
  - token recovery buttons
- Default action:
  - 구조화된 note가 있을 때는 list에서 바로 식별하고, stats가 비어 있으면 workbench repair vocabulary를 노출한다.
- Upstream component sourcing:
  - No 21st.dev component used in this lane.
  - Local vendored primitives only: `badge`, `button`, `command`, `input`.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "paper notes list"`

## Ethics check results
- Regret / 통과: 실제 structured state와 artifact snapshot에서만 설명 문구를 유도한다.
- Black Mirror / 통과: 클릭 유도를 위한 과장, scarcity, false urgency가 없다.
- In Real-Life / 통과: 도서관 사서가 메모 카드에 짧은 상태를 덧붙이는 수준이다.

## Next PR-sized actions
1. current `/papers` lane가 머지되면, `/papers/:slug` detail surface와 list mental model 간 copy 연결을 따로 점검하기
2. list query miss 사례가 쌓일 때만 weighted ranking을 검토하기
3. chart-pack viewer나 meeting-pack viewer는 이 lane와 분리된 frontend contract lane으로 계속 유지하기

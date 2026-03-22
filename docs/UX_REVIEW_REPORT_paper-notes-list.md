# UX Review Report - Paper Notes List

Status: Current review artifact  
Date: 2026-03-13  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-13
Reviewer: Codex

## Input
- Screen/Flow: `/papers` list search -> list row scan -> detail open
- Goal action: 연구자가 structured note를 목록 단계에서 빠르게 식별하고, 왜 열어야 하는지 이해한 뒤 detail로 들어간다.
- Primary persona: Obsidian + Zotero 기반으로 많은 논문 노트를 훑어보는 연구자
- Current friction: structured search, relevance cue, exact-phrase query, `Structured only`, empty-state recovery는 동작한다. 남은 마찰은 더 무거운 ranking/focus UI를 추가할 가치가 실제로 있는지 아직 검증되지 않았다는 점이다.
- Success metric: list-to-detail CTR, structured-note open rate, structured-signal query success rate
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## 1) Quick Review (5 min)
- Block: 핵심 triage block은 풀렸다. 지금 리스크는 증거 없이 filter/control을 더 늘려 다시 복잡도를 올리는 것이다.
- Interpret: row-level `Structured signals`, matched chip 강조, `relevance first`, contextual empty state까지 있어 why-this-result 해석은 충분히 가능하다.
- Act: `Structured only`, exact-phrase recovery, token-based recovery로 다음 행동 경로도 짧다.
- Store: 남은 일은 새 기능 추가보다, 현재 검색 모델이 실제 연구 노트 사용에서 충분한지 확인하는 것이다.
- Ethics first pass: 과장된 relevance 문구 대신 실제 entities/mesh/outcomes/claim tags만 노출한다.
- Decision: acceptance gap은 없다. search/list backlog는 실사용 miss 패턴이 쌓일 때만 다시 연다.

## 2) Full Review (P0/P1/P2 prioritized)
### Framework coverage snapshot
- 6P storyboard context (Problem/Emotion/Action/Struggle/Attempt/Happy Ending):
  - Problem: 연구자는 많은 note 중 어떤 것이 structured evidence를 갖는지 빨리 골라야 한다.
  - Emotion: detail을 일일이 열기 전에 신뢰할 만한 정보 향기를 원한다.
  - Action: list search 후 row를 스캔한다.
  - Struggle: 현재 남은 문제는 structured search 자체가 아니라, 더 복잡한 ranking/focus UI를 언제 도입할지 판단 근거가 약하다는 점이다.
  - Attempt: row에 structured signal chips, relevance cue, recovery action을 추가했다.
  - Happy Ending: list 단계에서 바로 “왜 relevant한지” 이해하고 detail로 들어간다.
- How BMAP changes the priorities in this review: Ability를 올리는 방향이 우선이다. 새 기능보다 판별 비용을 줄이는 것이 중요하다.
- How B.I.A.S changes the priorities in this review: Interpret를 강화해야 한다. 검색 결과의 의미를 2초 안에 읽을 수 있어야 한다.
- Peak-End implications inside this review: 검색 직후 row scan이 앞단 peak다. 여기서 설명력이 약하면 detail 전환이 떨어진다.
- Ethics implications inside this review: 설명 칩은 실제 structured state에서만 오고, 광고형 urgency는 사용하지 않는다.

### P0
- acceptance 기준의 핵심 요구는 충족됐다. list row는 structured note 여부와 핵심 signals를 직접 보여준다.
- chips는 최대 4개로 제한되어 있고, source는 `entities + mesh + outcomes + claim_tags` 실제 데이터만 사용한다.
- one-tap `Structured only` quick filter, quoted exact-phrase search, relevance-first cue, empty-state recovery가 모두 구현됐다.

### P1
- 모바일과 데스크톱에서 같은 reasoning chips를 유지하고, matched chip을 앞에 두는 현재 모델은 충분히 일관적이다.
- multi-token query는 공백 기준 token AND 매칭으로 동작하고, `Amyloid Neurology`처럼 cross-field query도 지원한다.
- list의 `Structured signals`, detail related의 `structured signals`, empty-state recovery copy는 현재 같은 mental model로 맞춰졌다.
- 남은 개선은 weighted ranking이나 smarter suggestion ordering처럼 선택적 정교화다.

### P2
- no acceptance gap remains on this flow. 추가 search sophistication은 실제 miss 패턴이 보일 때만 열어야 한다.
- quick filter나 ranking UI를 더 늘리는 일은 현재 단계에서 필요하지 않다.

## 3) BMAP diagnosis
- Motivation: 이미 높은 상태다. 사용자는 빠른 triage를 원한다.
- Ability: detail을 열기 전 판단 비용이 높았고, chips가 이를 줄인다.
- Ability: quick filter가 있으면 query/tag 조합 없이도 structured notes로 바로 좁힐 수 있다.
- Prompt: row-level structured signals, 특히 matched chip 강조가 “이 note를 열어라”라는 prompt 역할을 한다.
- Prompt: multi-token query에서도 matched chips가 바로 반응해야 search 학습 비용이 낮다.

## 4) B.I.A.S diagnosis
- Block: 현재 주된 block은 relevance 설명 부족이 아니라, control을 더 늘려 복잡도를 다시 올릴 위험이다.
- Interpret: chips, `relevance first`, contextual empty state가 relevance 근거를 짧게 해석시킨다.
- Act: `Structured only`, token AND 매칭, recovery 버튼이 다음 행동을 단순화한다.
- Store: structured note를 찾는 습관과, 실패해도 recovery path가 있다는 학습이 남는다.

## 5) Peak-End design notes
- Peak: 검색 결과 row에서 query와 맞는 `Amyloid` chip이 먼저 강조되어 보이는 순간
- Pit: structured search는 되는데 row는 왜 relevant한지 설명하지 못하는 순간
- Transition: query -> row scan -> detail open
- End: detail 이동 전에 이미 relevance 이유를 이해한 상태

## 6) Ethics Check
- Regret: 통과. 실제 structured signals만 보여준다.
- Black Mirror: 통과. 개인화 오남용이나 허위 urgency가 없다.
- In Real-Life: 친절한 도서관 사서처럼 “왜 이 자료가 맞는지” 짧게 설명해주는 수준이다.
- 대응:
  - 최대 4개만 노출
  - 실제 sidecar-derived structured 값만 사용
  - marketing copy 대신 factual chips 유지

## 7) Concrete changes
- Component:
  - `PaperNotesListPage` row에 `Structured signals` chips 섹션 추가
  - query와 맞는 chip을 앞에 배치하고 강조
  - `Structured only` quick-toggle 추가
- Route:
  - `/paper-notes?structured_only=true`
- Copy:
  - `Structured signals`
  - `relevance first`
  - contextual empty-state guidance and recovery actions
  - token-based recovery search buttons
- Default action:
  - 검색/정렬 흐름은 유지, row scan 정보 향기만 강화
- Data/API contract:
  - 기존 `entities`, `mesh`, `outcomes`, `claim_tags` 재사용
- Dependency impact:
  - 없음

## 8) Next PR-sized actions
이 섹션은 flow-local trigger backlog다. cross-surface concern으로 커지기 전까지 `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`로 승격하지 않는다.

1. 실제 query miss 사례가 쌓일 때만 weighted token scoring이나 stronger ranking을 검토하기
2. quick filter family가 더 늘어날 때만 collapsed `Focus` 그룹을 검토하기
3. empty-state suggestion이 자주 쓰이면 raw token order 대신 structured signal strength 기반 정렬을 검토하기

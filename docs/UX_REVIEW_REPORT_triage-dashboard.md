# UX Review Report - Triage Dashboard

Status: Current review artifact  
Date: 2026-03-13  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-13
Reviewer: Codex

## Input
- Screen/Flow: `/` root -> `Triage Dashboard` -> `Paper Queue` scan -> `Open Workbench`
- Goal action: 연구자가 지금 가장 먼저 봐야 할 paper를 빠르게 식별하고, `Repair Stats` / `Review issues` / `Open Workbench` 중 무엇을 해야 하는지 즉시 판단한다.
- Primary persona: 로컬 Obsidian/Zotero 환경에서 논문 backlog를 정리하는 연구자/대학원생
- Current friction: artifact health와 content review 신호는 존재하지만, root 화면의 top-level prioritization과 scan hierarchy가 아직 약하다. 실제 root 화면에는 `E2E` seed rows와 긴 논문 title이 같이 섞여 있어 주의가 분산되고, 많은 row가 같은 `Action needed` 문구를 반복해 what-to-do-next가 빠르게 잡히지 않는다.
- Success metric: root -> workbench first-click success rate, 첫 actionable paper 선택 시간, `Action needed` row의 repair completion rate
- Constraints:
  - FastAPI + Vite + React Router + TailwindCSS 유지
  - `--pp-*` 토큰과 dark-first Lattice tone 유지
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## 1) Quick Review (5 min)
- Block: root 화면에서 queue priority가 아직 약하다. 카드마다 정보는 많지만 “지금 뭘 먼저 해야 하는지”는 상단에서 바로 잡히지 않는다.
- Interpret: `Healthy` / `Action needed` / `Content Review` 분리는 좋다. 다만 root에서는 긴 title과 반복된 설명 때문에 status hierarchy가 한눈에 압축되지 않는다.
- Act: `Open Workbench` CTA는 명확하지만, 어떤 row를 눌러야 가장 가치가 큰지 알려주는 global prompt가 부족하다.
- Store: 현재 화면은 작업 관리판에 가깝고, 완료감이나 progress memory는 약하다.
- Ethics first pass: urgency나 dark pattern은 없다. 대신 개발용 `E2E` row가 실제 queue 상단에 섞이면 신뢰를 깎는다.
- Decision: 현재 root flow는 usable하지만, next UX slice는 새 기능보다 `priority framing`과 `scan compression`이어야 한다.

## 2) Full Review (P0/P1/P2 prioritized)
### Framework coverage snapshot
- 6P storyboard context (Problem/Emotion/Action/Struggle/Attempt/Happy Ending):
  - Problem: 연구자는 backlog가 많은 상태에서 어떤 paper를 먼저 열어야 할지 빨리 정해야 한다.
  - Emotion: “지금 제일 중요한 것부터 처리하고 싶다”는 압박이 있다.
  - Action: root queue를 스캔하고 한 paper를 선택한다.
  - Struggle: row마다 정보는 풍부하지만 top-level prioritization이 약해서 눈이 오래 머문다.
  - Attempt: artifact health, content review, workbench CTA가 추가돼 각 row의 정보 향기는 좋아졌다.
  - Happy Ending: 첫 10초 안에 “이 paper는 repair / review / read 중 무엇을 해야 하는지”를 이해하고 workbench로 들어간다.
- How BMAP changes the priorities in this review: Motivation은 이미 높다. 따라서 Ability와 Prompt를 더 줄여야 한다.
- How B.I.A.S changes the priorities in this review: root는 Block과 Interpret가 핵심이다. 의미는 많지만 빠른 판독성이 아직 최적은 아니다.
- Peak-End implications inside this review: root 첫 화면이 앞단 peak다. 여기서 priority가 안 보이면 뒤 flow가 아무리 좋아도 느리게 느껴진다.
- Ethics implications inside this review: 실제 사용자 queue에 테스트/fixture row가 섞이면 product trust를 해친다.

### P0
- 실제 root 화면 상단에 `E2E Seed Paper`, `E2E Content Review Paper` 같은 test fixture row가 먼저 노출된다. 이건 연구자 입장에서 즉시 관련 없는 정보로 읽히며, queue 신뢰와 집중을 떨어뜨린다.
- 현재 root는 “Papers · 62”와 긴 card 반복은 보이지만, `Repair now`, `Review now`, `Ready to read` 같은 top-level queue buckets가 없다. 사용자는 row를 읽어서 직접 우선순위를 계산해야 한다.
- 많은 실제 row가 `Action needed` + `Stats report is missing or empty`로 반복돼, 개별 row 간 차이가 약하게 느껴진다. 이건 정보 부족이 아니라 scan compression 부족이다.

### P1
- Theme toggle(`Dark/Light/System`)는 유용하지만 root triage에서는 low-frequency action이다. 현재 위치는 core queue controls보다 시각적 우선순위가 높다.
- `Content Review`와 artifact health는 분리돼 있지만, root level에서는 여전히 secondary explanation을 읽어야 차이를 알 수 있다. row-level next action pill이 더 직접적이어야 한다.
- `Paper Notes` 단일 link는 존재하지만, root의 primary mental model이 `triage queue`인지 `vault browser`인지 상단에서 조금 섞여 보인다.
- 모바일에서도 같은 long-card density가 유지되면 thumb scan fatigue가 커질 가능성이 높다. 정보는 맞지만 한 화면당 decision 수가 많다.

### P2
- progress/closure memory가 약하다. root에서 “이번 세션에서 몇 건 처리했는지” 같은 lightweight progress reinforcement가 없다.
- `Updated:` 타임스탬프는 유용하지만 queue ordering과 의미 연결이 약해 보인다. stale warning이나 recently touched grouping이 없으면 scan value가 낮다.

## 3) BMAP diagnosis
- Motivation: 높음. 사용자는 이미 triage 목적을 갖고 들어온다.
- Ability: 중간. row 정보는 충분하지만, 우선순위 계산을 사용자가 직접 해야 해 인지 비용이 남아 있다.
- Prompt: 중간. `Open Workbench`는 row 수준 prompt로 좋다. 하지만 global prompt, 즉 “지금 무엇부터”는 약하다.
- Priority implication: next improvement는 기능 추가보다 `Ability`와 `Prompt`를 더 직접적으로 만드는 것이다.

## 4) B.I.A.S diagnosis
- Block:
  - root 첫 화면에 test fixture row와 실제 queue가 섞여 있으면 관련성 필터를 통과하지 못한다.
  - 반복된 `Action needed` 문구는 서로 다른 row를 하나처럼 보이게 만든다.
- Interpret:
  - `Healthy` / `Action needed` / `Content Review` 분리는 좋다.
  - 하지만 상단 queue framing이 약해서 사용자가 “어떤 신호를 우선 읽어야 하는지” 학습 비용이 남는다.
- Act:
  - `Open Workbench`는 좋다.
  - next step을 `Repair Stats`, `Review issues`, `Read summary`처럼 더 직접적인 action language로 압축할 여지가 있다.
- Store:
  - 완료 후 기억에 남는 보상/진행 피드백이 root에는 거의 없다. 지금은 queue 소비 경험에 가깝다.

## 5) Peak-End design notes
- Peak: root에서 첫 actionable row를 정확히 고르는 순간
- Pit: 많은 비슷한 `Action needed` row를 읽으며 priority를 직접 계산하는 순간
- Transition: root queue -> selected paper -> workbench
- End: 현재는 `Open Workbench`가 끝이지만, root로 돌아왔을 때 처리 진척감은 약하다.

## 6) Concrete changes
- Component:
  - root 상단에 `Needs Repair`, `Needs Review`, `Ready` 3-bucket summary strip 추가 검토
  - row 상단 badge 옆에 `Primary next action` pill 추가 검토 (`Repair Stats`, `Review 2 issues`, `Read note`)
  - test/fixture row는 실제 triage surface에서 숨기거나 별도 dev bucket으로 격리
- Route:
  - root는 triage-first를 유지하되, `Paper Notes`는 secondary navigation으로 더 분명히 분리
- Copy:
  - `Action needed` 단독 문구보다 action-specific copy 우선
  - `Stats report is missing or empty`는 detail reason으로 유지하고, row top에는 shorter imperative copy 사용
- Default action:
  - 첫 화면은 `무엇을 먼저 할지`를 알려주는 dashboard여야 하고, browse list는 그 다음이어야 한다.

## 7) Ethics check results
- Regret: 현재 설계는 대체로 통과한다. 다만 test fixture가 실제 queue 최상단에 보이면 사용자는 “이 도구가 내 실제 일을 이해하지 못한다”고 느낄 수 있다.
- Black Mirror: urgency/pressure dark pattern은 없다.
- In Real-Life: 현재 화면은 친절한 조교라기보다 많은 파일을 한꺼번에 들이민 보조원에 가깝다. 정리자는 있지만 우선순위 코치는 약하다.

## 8) Next PR-sized actions
1. root triage 상단에 `Repair / Review / Ready` bucket summary와 count를 추가해 first decision cost를 줄이기
2. row-level `Primary next action` copy를 `Action needed`보다 더 직접적인 imperative language로 교체하기
3. dev/test fixture row를 실제 triage surface에서 분리하거나 숨기는 정책을 추가하기

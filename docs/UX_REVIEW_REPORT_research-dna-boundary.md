# UX Review Report: Research DNA Boundary

Status: Completed review artifact
Date: 2026-03-28
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Research DNA product boundary across onboarding/runtime docs
- Goal action: 사용자가 `Research DNA`를 현재 메인 웹 UI 기능으로 오해하지 않고, API/CLI operator lane으로 이해한다.
- Primary persona: README와 runtime docs를 보고 self-serve로 제품 범위를 파악하는 초기 사용자 또는 운영자
- Current friction: backend/API/CLI에는 `Research DNA`가 구현돼 있지만 frontend viewer route는 없어, 문서에 따라서는 “숨어 있는 웹 기능”처럼 읽힐 수 있다.
- Success metric: README와 web-viewer 문서를 읽은 사용자가 `Research DNA`가 현재 main web viewer route가 아니라는 점을 바로 이해한다.
- Constraints: backend/API contracts는 바꾸지 않음, frontend route를 새로 만들지 않음, 현재 single-operator/API-first 경계를 유지함

## Quick Review (5 min)
- 지금 시점의 문제는 미구현보다 기대치 불일치다.
- `Research DNA`는 실제로 중요한 lane이지만, 현재는 web viewer product surface가 아니라 API/CLI operator lane이다.
- 이 경계를 문서에서 먼저 명확히 하지 않으면 “있는데 왜 안 보이지?”라는 혼란이 반복된다.

## Full Review
### P0
- README에서 `Research DNA`를 현재 가능한 기능으로 소개하되, 메인 웹 route가 아니라는 점을 바로 붙여야 한다.
- web viewer runbook은 `/ui/*` 경계를 설명하는 문서이므로, `Research DNA` 비포함을 명시해야 한다.

### P1
- CLI workflow reference는 이미 이 경계를 말하고 있으므로, README와 web viewer docs를 그 기준에 맞춰 정렬하면 된다.
- 이 결정은 “Research DNA를 제품에서 뺀다”가 아니라 “현재 노출 경계를 정직하게 말한다”는 뜻이다.

### P2
- 향후 Research DNA를 웹으로 올릴 수는 있다. 다만 그때는 read-first viewer와 entry path를 별도 RFC로 다뤄야 한다.

### Full Review Coverage
- 6P storyboard context: Problem은 implemented lane와 visible product lane이 어긋난 점이고, emotion은 “왜 README에 있는데 웹엔 없지?”라는 혼란이며, action은 docs를 읽고 진입하려는 시도다. Struggle은 product boundary가 문서마다 다르게 읽히는 점이다. Attempt는 README/web viewer docs를 CLI boundary에 맞춰 정렬하는 것이다. Happy Ending은 사용자가 현재 경계를 정확히 이해하고 올바른 entry를 선택하는 상태다.
- BMAP: Motivation은 높지만 Ability는 문서 불일치로 떨어진다. Prompt는 경계 문구를 명시하는 것으로 개선된다.
- B.I.A.S: Block은 hidden-lane confusion, Interpret는 “웹에 없다 = 고장인가?” 오해, Act는 wrong-path entry, Store는 제품 신뢰 저하다.
- Peak-End: Peak는 첫 문서에서 현재 경계를 바로 이해하는 순간이고, pit는 문서가 기능을 암시하지만 실제 route는 없는 상태다. Transition은 README -> runtime guide -> CLI reference다. End는 “이 기능은 지금 어디서 쓰는가”를 명확히 아는 것이다.
- Ethics: 구현돼 있다는 이유로 현재 web surface처럼 말하면 과장이다. 현재 노출 경계를 숨기지 않는 것이 더 정직하다.

## BMAP diagnosis
- Motivation: 높음. `Research DNA`는 search-design backbone이라 관심을 끈다.
- Ability: 문서가 엇갈리면 self-serve 이해가 어려워진다.
- Prompt: boundary copy를 front docs에 직접 넣는 것이 가장 작은 개선이다.

## B.I.A.S diagnosis
- Block: backend-only lane가 main UI feature처럼 읽히는 점
- Interpret: 현재 경계가 문서마다 다르게 읽히는 점
- Act: 사용자가 없는 web route를 찾게 되는 점
- Store: 제품이 capability를 숨긴다고 느낄 수 있는 점

## Peak-End design notes
- Peak: README에서 곧바로 “API/CLI operator lane”이라는 문구를 보는 순간
- Pit: main UI surface로 오해하고 route를 찾다가 없는 상태
- Transition: README -> WEB_VIEWER -> CLI reference 흐름이 같은 말을 해야 한다
- End: 사용자가 올바른 진입점으로 이동할 수 있어야 한다

## Concrete changes
- README에 `Research DNA`는 current API/CLI operator lane이고 main web viewer route가 아니라는 점을 추가한다.
- WEB_VIEWER runbook에 `Research DNA` 비포함 경계를 명시한다.
- 기존 CLI workflow reference를 canonical boundary reference로 사용한다.

## Ethics check results
- Regret: 낮음. 현재 제품 경계를 더 정직하게 말한다.
- Black Mirror: 낮음. 없는 web surface를 암시하지 않는다.
- In Real-Life: 운영자와 첫 사용자 모두 어디서 무엇을 해야 하는지 덜 헷갈린다.

## Next PR-sized actions
- Research DNA를 web에 올릴지 여부를 별도 RFC로 결정한다.
- 올린다면 read-first viewer만 먼저 정의하고 write/pilot/screening은 후속으로 분리한다.
- 올리지 않는다면 onboarding 문서와 product-positioning docs도 같은 경계를 따르도록 추가 정렬한다.

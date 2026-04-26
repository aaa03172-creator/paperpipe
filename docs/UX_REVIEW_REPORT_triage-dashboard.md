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

## 9) Priority Summary Strip Checkpoint (2026-03-23)
- Screen/Flow: `/` triage dashboard -> queue scan -> choose the first repair/review/ready paper
- Goal action: 사용자가 row를 여러 개 읽기 전에 현재 queue가 `Needs repair / Needs review / Ready` 중 어디에 몰려 있는지 바로 파악한다.
- Primary persona: paper backlog를 빠르게 훑고 지금 먼저 고칠 paper를 고르는 운영자/연구자
- Current friction:
  - 기존 root triage는 status 신호는 풍부했지만, 우선순위 압축이 약해서 사용자가 row를 읽으며 직접 중요도를 계산해야 했다.
  - `Action needed` row와 content-review row가 섞여 있어, queue 전체의 shape를 첫 5초 안에 파악하기 어려웠다.
- Quick decision:
  - 새 bucket state나 backend field는 추가하지 않는다.
  - 기존 `ops_summary`와 `content review` 신호만 조합해 조용한 summary strip 3개를 queue 상단에 붙인다.
  - `repair`가 있으면 먼저 repair로 분류하고, repair가 없을 때만 flagged/unavailable review를 `Needs review`로 묶는다.
- BMAP:
  - Motivation: 높음. triage 사용자는 이미 “뭘 먼저 해야 하는지”를 알고 싶어서 들어온다.
  - Ability: row-level 정보는 충분하므로, 상단에서 queue shape만 먼저 압축해 주면 인지 비용이 크게 줄어든다.
  - Prompt: `Needs repair / Needs review / Ready` 3-bucket count가 가장 직접적인 global prompt다.
- B.I.A.S:
  - Block: 사용자가 row마다 상태를 다시 해석해야 한다.
  - Interpret: summary strip이 queue 전체의 현재 상태를 먼저 읽게 만든다.
  - Act: `repair -> review -> ready` 순서로 다음 행동을 바로 고르게 만든다.
  - Store: root triage가 단순 목록보다 “정리된 작업판”으로 기억되기 쉬워진다.
- Peak-End:
  - Peak는 root 첫 화면에서 queue 우선순위가 바로 읽히는 순간이다.
  - Pit는 여러 row를 읽고 나서야 repair/review 비중을 스스로 계산하던 상태였다.
  - Transition은 summary strip -> row 선택 -> workbench handoff다.
- Ethics:
  - Regret: 통과. urgency를 과장하지 않고 현재 queue shape만 더 직접적으로 보여준다.
  - Black Mirror: 통과. 사용자를 몰아붙이거나 허위 우선순위를 주지 않는다.
  - In Real-Life: 통과. 실제 연구 backlog를 정리할 때 먼저 어떤 종류의 일이 남았는지 보여주는 수준이다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend triage separates content review cues from operational state|backend triage summarizes repair, review, and ready buckets|backend triage content review action carries flagged context into workbench|backend keeps unavailable content review distinct from clear state"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout"`

## 10) Primary Next Action Checkpoint (2026-03-23)
- Screen/Flow: `/` triage dashboard -> row scan -> choose the immediate next action
- Goal action: 사용자가 `Action needed` 배지를 해석하지 않고도 각 row에서 지금 해야 할 일을 바로 읽는다.
- Primary persona: root queue를 빠르게 훑고 repair/review/workbench 열기 중 하나를 고르는 운영자/연구자
- Current friction:
  - summary strip이 queue shape는 압축해 줬지만, 개별 row에서는 여전히 `Action needed`와 generic CTA를 함께 읽어야 했다.
  - 특히 missing-stats row와 flagged-review row는 각기 다른 다음 행동을 갖는데, row 상단에서 그 차이가 충분히 직접적이지 않았다.
- Quick decision:
  - 새 action system은 만들지 않는다.
  - 기존 `ops_summary.recommended_action`과 content-review flagged state만 사용해 `Primary next action` pill을 각 row에 추가한다.
  - 버튼 동작과 row click behavior는 그대로 두고, interpretation cost만 낮춘다.
- BMAP:
  - Motivation: 높음. triage에서 중요한 건 “뭘 읽을까”보다 “뭘 먼저 할까”다.
  - Ability: next-action pill만으로 row 해석 시간이 줄어든다.
  - Prompt: `Repair stats`, `Review 2 issues`, `Open workbench` 같은 직접적인 action language가 가장 짧고 명확하다.
- B.I.A.S:
  - Block: `Action needed`가 무엇을 의미하는지 사용자가 다시 해석해야 했다.
  - Interpret: row-level next action이 operational fix와 content review를 더 빨리 구분해 준다.
  - Act: repair row와 flagged row가 다른 행동을 요구한다는 점이 즉시 보인다.
  - Store: triage row가 상태표보다 작업 카드처럼 기억되기 쉬워진다.
- Peak-End:
  - Peak는 row를 보는 즉시 `Repair stats`와 `Review 2 issues`가 바로 읽히는 순간이다.
  - Pit는 같은 `Action needed` 배지가 반복돼 다음 행동을 직접 추론해야 하던 상태였다.
  - Transition은 row scan -> button click -> workbench handoff다.
- Ethics:
  - Regret: 통과. 실제 상태를 더 직접적으로 번역할 뿐 허위 urgency를 만들지 않는다.
  - Black Mirror: 통과. 사용자를 특정 행동으로 몰지 않고 이미 존재하는 recommended action을 더 잘 드러낸다.
  - In Real-Life: 통과. backlog row에서 “다음 할 일” 한 줄을 붙이는 수준의 현실적인 개선이다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend triage separates content review cues from operational state|backend triage summarizes repair, review, and ready buckets|backend triage content review action carries flagged context into workbench|backend keeps unavailable content review distinct from clear state"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout"`

## 11) Access Route Visibility Checkpoint (2026-03-28)
- Screen/Flow: `/` triage dashboard -> queue scan -> decide whether the paper already has a local PDF, an OA route, or an institution-assisted route
- Goal action: 사용자가 workbench를 열기 전에 현재 paper의 reachable full-text route를 한 줄로 바로 읽는다.
- Primary persona: local-first queue를 정리하면서 “지금 읽을 수 있는가 / institution route가 필요한가”를 빠르게 판단하는 연구자
- Current friction:
  - backend는 이미 derived `access_summary`를 내려주지만, triage surface에서는 이 access state가 보이지 않았다.
  - operator는 PDF availability를 추측하거나 workbench에 들어가서야 local/OA/institution route를 확인해야 했다.
- Quick decision:
  - shared rail/workbench 전체를 다시 열지 않고, `/` triage row에만 compact access badge와 optional route link를 추가한다.
  - access state는 새 source model이 아니라 기존 `access_summary` 파생값만 사용한다.
  - `Local PDF`, `Open access`, `Institution route`, `No route`만 보여주고 button hierarchy는 그대로 둔다.
- BMAP:
  - Motivation: 높음. triage에서는 “무엇부터 처리할지”뿐 아니라 “지금 바로 읽을 수 있는지”도 빠르게 알고 싶다.
  - Ability: access badge 한 줄이면 PDF reachability 판단 비용이 크게 줄어든다.
  - Prompt: row-level badge + small route link가 가장 직접적인 prompt다.
- B.I.A.S:
  - Block: access state가 invisible해서 읽기 가능성을 사용자가 추정해야 했다.
  - Interpret: `Local PDF` / `Institution route`가 바로 보이면 triage row의 operational meaning이 더 선명해진다.
  - Act: workbench 진입 전에 saved PDF 또는 institution route를 바로 열 수 있다.
  - Store: triage가 단순 queue가 아니라 access-aware 작업판으로 기억되기 쉬워진다.
- Peak-End:
  - Peak는 row를 보는 즉시 현재 읽기 route가 보이는 순간이다.
  - Pit는 PDF availability를 workbench 안에서 뒤늦게 확인해야 하던 상태였다.
  - Transition은 triage row -> optional route open -> workbench handoff다.
- Ethics:
  - Regret: 통과. access 가능성을 더 크게 포장하지 않고 현재 route state만 노출한다.
  - Black Mirror: 통과. institution route를 promise처럼 말하지 않고 “assist route” 수준으로 유지한다.
  - In Real-Life: 통과. 실제 연구자 workflow에서 “지금 local PDF가 있는가”는 triage-level signal로 유용하다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend triage separates content review cues from operational state"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "triage dashboard layout"`

## 12) Start Here Hierarchy Checkpoint (2026-03-29)
- Screen/Flow:
  - `/` triage dashboard header
- Goal action:
  - first-time users should know where to begin before they parse artifact lanes and secondary tools.
- Primary persona:
  - close-user alpha testers and first-session researchers entering the workspace for the first time.
- Current friction:
  - the triage header had too many same-weight links, and advanced lanes competed visually with basic onboarding actions.
- Success metric:
  - the root header reads as `Start here` first and `More tools` second.
- Quick Review:
  - this is a hierarchy patch, not a capability patch.
  - the smallest safe change is to separate first-session actions from secondary tools without changing routes.
- Full Review:
  - P0: group `Add your PDF`, `Browse Paper Notes`, and `Runtime checks` under a clear `Start here` strip.
  - P0: move saved-artifact/helper lanes under `More tools`.
  - P1: keep theme control, but stop giving every route equal top-level weight.
  - P2: preserve existing route contracts and CTA destinations.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when the first three actions are obvious
  - Prompt: `Start here` is the clearest first-session prompt on the home surface
- B.I.A.S diagnosis:
  - Block: too many same-weight header actions
  - Interpret: users had to sort onboarding and advanced tools themselves
  - Act: the new hierarchy makes the first move more obvious
  - Store: root feels more like a guided workspace than a route menu
- Peak-End design notes:
  - Peak is seeing one obvious place to begin.
  - Pit was reading a long toolbar of mixed-level actions.
  - Transition is root -> papers/import -> note/workbench.
  - End is “I know where to start.”
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a supportive teammate would introduce the product

## 12.1) Global Home Safe Placement Checkpoint (2026-03-29)
- Screen/Flow:
  - non-root routes with right-aligned header actions, especially `/image-evidence/:imageEvidenceId`
- Goal action:
  - keep the global `Home` affordance visible without covering primary page actions.
- Primary persona:
  - close-user testers moving across note, artifact, and review routes without learning route-specific navigation.
- Current friction:
  - the fixed top-right `Home` pill could overlap right-edge header actions on dense detail screens.
  - in practice, the `Open note` handoff on the image-evidence detail route could sit directly underneath the fixed pill.

- Quick decision:
  - keep the global `Home` affordance because it reduces navigation anxiety on non-root routes.
  - move it to the bottom-right safe area instead of the top-right header band.
- BMAP diagnosis:
  - Motivation: high, because users do want a guaranteed way back.
  - Ability: improves when `Home` is present but not occluding other actions.
  - Prompt: the pill still works as a global prompt without competing with header CTAs.
- B.I.A.S diagnosis:
  - Block: fixed placement created accidental click interference.
  - Interpret: users could read this as the page being broken rather than the nav being helpful.
  - Act: moving the pill restores direct access to header actions and keeps `Home` discoverable.
  - Store: the workspace feels more considerate and less brittle.
- Peak-End design notes:
  - Peak is having a consistent way home from any route.
  - Pit was covering route-specific actions at the exact moment users wanted to continue their work.
  - Transition is now route action first, escape hatch second.
  - End is “I can go home when I need it, and it never blocks the page.”
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: this matches how a persistent escape hatch should behave in a dense research tool.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend image evidence viewer loads a registered bundle and keeps note handoff on the real route"`

## 12.2) Global Home Dense-Route Regression Checkpoint (2026-03-29)
- Screen/Flow:
  - dense detail routes with persistent shell navigation, especially `meeting-packs/:packId`, `protocol-cards/:protocolId`, and `image-evidence/:imageEvidenceId`
- Goal action:
  - keep the bottom-right `Home` affordance available without overlapping route-local handoff or maintenance actions.
- Primary persona:
  - close-user testers moving between saved artifacts, note review, and maintenance actions in one session.
- Current friction:
  - moving `Home` fixed the top-right collision, but the change still needed a route-level safety rail so later layout tweaks would not quietly reintroduce overlap.
  - the highest-traffic review flow also runs through `paper detail -> workbench`, so the shell needs to stay out of those primary handoff actions too.
- Quick decision:
  - keep the current bottom-right placement.
  - add browser-level non-overlap assertions against high-value actions instead of adding more route-specific navigation.
  - sample both dense artifact routes and the primary note/workbench review flow.
- BMAP diagnosis:
  - Motivation: high, because dense review routes still need a stable escape hatch.
  - Ability: improves when `Home` is visible but physically separate from note handoff and rerender/export actions.
  - Prompt: `Home` remains a helpful background affordance rather than competing with workflow CTAs.
- B.I.A.S diagnosis:
  - Block: overlap regressions are subtle and easy to miss without browser geometry checks.
  - Interpret: if `Home` covers a CTA, users read it as a broken route rather than helpful navigation.
  - Act: sampling multiple dense routes keeps the shell trustworthy while preserving direct task actions.
  - Store: the workspace feels calmer when global navigation never interrupts local work.
- Peak-End design notes:
  - Peak is having a guaranteed path home that never steals the click target you actually need.
  - Pit is a persistent shell action covering right-rail artifact controls.
  - Transition is now route action first, shell affordance second, across multiple detail routes.
  - End is “the shell stays out of my way.”
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: a research workspace should always make the next review action easier, not harder.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route|backend protocol knowledge index can create a new protocol card from the browser|backend image evidence viewer loads a registered bundle and keeps note handoff on the real route|backend paper note to workbench to protocol create journey stays connected in the browser"`

## 13) Home Note Context Load Checkpoint (2026-04-13)
- Screen/Flow:
  - `/` triage dashboard initial load
- Goal action:
  - keep the same root summary and resume-card behavior while reducing repeated note-index work during boot.
- Primary persona:
  - returning operator who opens root to decide whether to resume reading, repair saved checks, or continue review.
- Current friction:
  - the dashboard previously paged through every `/paper-notes` page just to compute saved-note counts, latest-note timestamp, and note-slug joins for the resume card.
  - because `GET /paper-notes` rebuilds the vault index on every request, multi-page home loading multiplied the same index-build cost.
- Quick decision:
  - do not change the visible triage copy or hierarchy.
  - add a narrow `GET /paper-notes/home-context` contract that returns only `saved_notes`, `structured_notes`, `latest_note_updated_at`, `note_context_limited`, and `note_slug_by_paper_id`.
  - keep `needs_review` and `blocked` derived from the already-loaded `/papers` list so we do not introduce another broad paper summary request.
- BMAP diagnosis:
  - Motivation: unchanged. users still want the same quick resume and context signals.
  - Ability: improved indirectly because the page reaches stable state with less redundant background work.
  - Prompt: unchanged at the UI layer; the improvement is operational rather than presentational.
- B.I.A.S diagnosis:
  - Block: repeated note-index rebuilds slowed the dashboard for no user-visible gain.
  - Interpret: the root screen still shows the same summary, but it now gets note context from one additive contract instead of full note pagination.
  - Act: unchanged. users still jump from the same resume card and queue lens actions.
  - Store: unchanged visually; improved operational reliability should reduce “why is home slow?” frustration.
- Peak-End design notes:
  - Peak remains the first actionable paper selection.
  - Pit was hidden repeated note-list loading before the user even acted.
  - Transition remains root summary -> queue lens or note/workbench handoff.
  - End is a faster, quieter home load without changing the task model.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a real operator dashboard should summarize saved note state.
- Verification:
  - `./.venv/bin/python -m pytest -q tests/test_paper_notes_api.py -k "paper_notes_home_context"`
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workspace context keeps global counts while search filters the action list"`

## 14) Beginner-First Home Copy Checkpoint (2026-04-13)
- Screen/Flow:
  - `/` triage dashboard hero -> `Start here` strip -> `Workspace context`
- Goal action:
  - first-session users should understand the paper-first entry path within a few seconds and know that the safest first move is still `add one paper -> open its note -> continue in the workbench`.
- Primary persona:
  - close-user alpha testers and first-session researchers who are curious about the product but do not yet know the note/workbench split.
- Current friction:
  - the current hero and helper copy are honest, but they still lean a little too much toward internal product language.
  - phrases like `Research workspace`, `meeting outputs`, and `Project framing stays light here` make sense after orientation, but they are not the clearest first-session translation of what the user should do next.
  - the home surface should stay paper-first and should not imply a first-class project dashboard.
- Success metric:
  - first-session users can explain the start path in one sentence after reading the header.
  - the home header reads as a guided paper-first starting point, not as a generalized project/workspace product.

### Quick Review (5 min)
- Block: the existing header is usable, but the first sentence still asks the user to translate internal structure into a beginner action plan.
- Interpret: the benefit is present, yet it arrives after product language rather than before it.
- Act: `Start here` already exists; the smallest safe improvement is to make the helper copy more explicit instead of adding more controls.
- Store: the best memory for this screen is “I know how to begin,” not “I saw many surfaces.”
- Ethics first pass: no dark pattern risk here. The main risk is accidental overclaiming of a project/workspace surface that does not exist.

### Full Review
#### P0
- the hero must explain the product in paper-first language before it mentions advanced downstream outputs.
- the `Start here` strip should keep one clear beginner path and avoid sounding like a route catalog.
- `Workspace context` copy should stay honest about current product boundaries and avoid implying a first-class project container.

#### P1
- advanced lanes like saved outputs should remain visible, but they should stay secondary to the first paper/note/workbench loop.
- runtime checks copy should read like a safety/support action, not a competing primary CTA.

#### P2
- the current `Queue lens` label is already established in the runtime and tests; this slice should not rename it.
- deeper triage summary language can stay as-is for now because the first-session friction is concentrated in the header and helper copy.

### Full Review Coverage
- 6P storyboard context:
  - Problem: a new user wants to know where to begin without learning the whole system first.
  - Emotion: curiosity mixed with caution; they do not want to start in the wrong place.
  - Action: they land on `/` and scan the hero and the first action strip.
  - Struggle: product-accurate but insider-flavored wording slows first understanding.
  - Attempt: tighten the copy around one paper-first action path.
  - Happy Ending: the user can say “start with one paper note, then continue in review when needed.”
- BMAP:
  - Motivation is already present.
  - Ability improves when the first action path is phrased in plain language.
  - Prompt is strongest when the header and `Start here` strip repeat the same beginner-safe story.
- B.I.A.S:
  - Block: internal terminology adds avoidable interpretation work.
  - Interpret: benefit-first copy makes the paper/note/workbench flow easier to parse.
  - Act: clearer helper copy reduces hesitation before opening `Paper Notes`.
  - Store: the root screen is more likely to be remembered as a guided start point.
- Peak-End:
  - Peak is understanding the first move instantly.
  - Pit is wondering whether this is a project dashboard, an artifact index, or a paper reader.
  - Transition is hero -> `Start here` -> first paper note -> workbench.
  - End is “I know how to start and what comes next.”
- Ethics:
  - do not use inflated product language that implies capabilities we have not adopted.

### BMAP diagnosis
- Motivation: high
- Ability: slightly lower than it should be because the header still asks for product translation
- Prompt: strong once the hero, start strip, and workspace helper copy tell the same paper-first story

### B.I.A.S diagnosis
- Block: internal-facing wording competes with the beginner action path.
- Interpret: the home surface should explain the benefit before it explains the lane taxonomy.
- Act: the user should see one obvious first-session route without losing access to secondary tools.
- Store: the strongest memory should be clarity, not density.

### Peak-End design notes
- elevate the early peak by making the first sentence about starting with one paper.
- repair the pit by removing wording that sounds broader than the current runtime.
- keep the transition explicit: paper -> note -> workbench.
- end with confidence that the current home is a paper-first starting point, not a promised future dashboard.

### Concrete changes
- keep the existing layout, routes, and CTA structure
- tighten the hero label and description around the paper-first loop
- rewrite `Start here` helper text so it reads like a first-session guide rather than a lane inventory
- simplify `Workspace context` body copy so it explains “what is already active and what to pick up next” without project-platform language
- keep `Queue lens` naming unchanged in this slice

### Ethics check results
- Regret: improved. The screen is less likely to overpromise what the current product is.
- Black Mirror: safe. This is transparency work, not persuasion pressure.
- In Real-Life: closer to a helpful teammate who says where to begin first, then mentions the advanced tools.

### Next PR-sized actions
1. if beginner confusion remains, add a lightweight `why start with Paper Notes` helper near the first-session strip
2. revisit whether `Saved outputs` needs a softer label for first-session users without hiding artifact continuity
3. later, consider whether the papers list itself should inherit a shorter `what happens next` cue from the home surface

### Verification
- `cd frontend && npm run build`

## 15) Start-Here Manual Import Alignment Checkpoint (2026-04-17)
- Screen/Flow:
  - `/` triage dashboard hero
  - `/` first-session `Start here` strip
  - `/` workspace-context empty-note copy
- Goal action:
  - first-session users should hear the same recovery story on home that they now hear on `/ready`, `/papers`, and the imported note detail: import one paper, land in the saved note, then continue into review when needed.
- Primary persona:
  - a new or returning close-user tester who lands on home before any saved note is active and wants one obvious first action.
- Current friction:
  - home already told a roughly correct paper-first story, but its first-run wording lagged behind the newer manual-import flow.
  - `Add your PDF` still pointed to generic `/papers`, and the helper copy stopped short of the now-established payoff that import opens the saved note right away.
- Success metric:
  - the first-session `Add your PDF` CTA points directly to `/papers#import-pdf`.
  - the hero, `Start here`, and empty-note workspace-context copy all repeat the same “import -> saved note -> review” loop.
- Quick Review:
  - this is a consistency patch, not a new home feature.
  - the smallest safe change is to sharpen the `Add your PDF` destination and align the surrounding copy with the current manual-import payoff language.
- Full Review:
  - P0: `Add your PDF` should point to `#import-pdf`, not generic `/papers`.
  - P0: home copy should say users land in the saved note, not just that they add a paper.
  - P1: keep `Browse Paper Notes` and `Runtime checks` as secondary options in the same strip.
  - P2: keep resume-card and queue-lens behavior unchanged for returning users.
- BMAP diagnosis:
  - Motivation: high. first-session users want one concrete way to begin.
  - Ability: improves when the first CTA lands on the exact import affordance and explains the immediate result.
  - Prompt: “open the saved note right away” is a stronger first prompt than “add your PDF.”
- B.I.A.S diagnosis:
  - Block: home still required users to infer what happened after import.
  - Interpret: aligned wording makes root feel like part of one continuous paper-first loop instead of a separate surface with slightly different language.
  - Act: users can start faster because the first CTA and its payoff are both explicit.
  - Store: the remembered story becomes stable across surfaces.
- Peak-End design notes:
  - Peak is seeing a first-run CTA that lands on the exact manual-import affordance.
  - Pit was starting from home and getting a slightly more generic story than the downstream screens now tell.
  - Transition is home -> `/papers#import-pdf` -> saved note -> review.
  - End is a user who already expects the saved note handoff before they click.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a helpful teammate would introduce the product in one sentence instead of three partially different ones
- Concrete changes:
  - `Add your PDF` now points to `/papers#import-pdf`
  - hero copy now says users land in the saved note
  - `Start here` and empty-note workspace-context copy now repeat the same saved-note payoff
  - `Browse Paper Notes` copy now keeps reading/review language concise without changing structure
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend home start-here strip points first-time users to manual import|backend workspace context keeps global counts while search filters the action list"`

## 16) Resume Card Saved-Note Handoff Checkpoint (2026-04-17)
- Screen/Flow:
  - `/` triage dashboard `Continue current work` card for returning users
- Goal action:
  - returning users should understand whether the next step is to reopen the saved note or jump into review, without the resume card sounding like a separate product lane.
- Primary persona:
  - a returning operator deciding whether to keep reading a saved note or continue review from that same paper thread.
- Current friction:
  - the resume card was operationally correct, but some labels still used older wording like `Resume reading and note review` or generic `Continue evidence review for this paper`.
  - after the recent first-run alignment work, that made the returning-user card slightly less explicit than the rest of the loop about the saved-note handoff.
- Success metric:
  - reading resumes say `reopen the saved note`, review resumes say `saved note thread` when a note-backed handoff exists, and the fallback helper text no longer talks about a generic evidence-backed thread.
- Quick Review:
  - this is a wording alignment patch, not a resume-priority rewrite.
  - the smallest safe change is to preserve the existing state selection and CTA destinations while tightening state-specific copy around the saved-note loop.
- Full Review:
  - P0: reading resumes should explicitly say `saved note`.
  - P0: review resumes should say `saved note thread` whenever the current paper has a note-backed handoff.
  - P1: blocked resumes can use the same saved-note language when the blocker belongs to saved note checks.
  - P2: keep the ranking logic, CTA labels, and destinations unchanged.
- BMAP diagnosis:
  - Motivation: high. returning users want to re-enter the right paper thread quickly.
  - Ability: improves when the card tells them whether they are re-entering reading or review from the saved note itself.
  - Prompt: state-specific saved-note wording is a better prompt than generic `paper` or `evidence review` phrasing.
- B.I.A.S diagnosis:
  - Block: the card still asked users to translate some generic wording into the new saved-note mental model.
  - Interpret: clearer reading/review copy makes the card feel like part of the same loop as `/ready`, `/papers`, and imported note detail.
  - Act: users can choose the next step faster because the card names the destination more concretely.
  - Store: returning users should remember one stable paper-thread model instead of a first-run model and a returning-user model.
- Peak-End design notes:
  - Peak is seeing `reopen the saved note` or `continue review from the saved note thread` at a glance.
  - Pit was a card that was correct but slightly more generic than the surrounding surfaces.
  - Transition is home resume card -> saved note or review.
  - End is a calmer return-to-work loop.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a thoughtful teammate would say “pick up this note again” instead of “continue some paper work”
- Concrete changes:
  - reading resume copy now says `Reopen the saved note and keep reading`
  - note-backed review resumes now say `saved note thread`
  - note-backed blocker copy now says `Repair saved note checks before review`
  - fallback helper text now says `saved note or review thread`
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend home resume card keeps saved-note reading handoff clear|backend home resume card keeps saved-note review handoff clear|backend home resume card keeps saved-note blocker handoff clear"`

## 17) Workspace Context Saved-Note Return Checkpoint (2026-04-17)
- Screen/Flow:
  - `/` triage dashboard `Workspace context` card for returning users
- Goal action:
  - returning users should understand that workspace context is not just a count panel; it should reinforce that they reopen a saved note to keep reading and move into review when evidence work is next.
- Primary persona:
  - a returning operator landing on home with existing saved notes and needing one clear mental model for where to resume.
- Current friction:
  - first-run home copy already said `import -> saved note -> review`, but the returning-user workspace context still spoke in generic count language like `Latest note updated` and `Saved notes, paper markers, and current review load`.
  - that made the lower summary card weaker than the first-run strip and the resume card at reminding users what those counts mean in practice.
- Success metric:
  - the workspace summary names `saved notes` as the reading re-entry point, the detail line says `Latest saved note updated`, and returning users are reminded they can keep reading or move into review from the same loop.
- Quick Review:
  - this is a copy-and-test alignment patch, not a data-model or IA rewrite.
  - the safest change is to preserve the existing counts, links, and queue behavior while making the summary/detail copy more explicit about the saved-note return path.
- Full Review:
  - P0: the returning-user summary should say saved notes help reopen reading, not just list data buckets.
  - P0: the detail line should say `Latest saved note updated` and remind users what to do next.
  - P1: the zero-note summary should keep the same import -> saved note -> review payoff as the rest of home.
  - P2: do not change counts, links, or search/filter semantics.
- BMAP diagnosis:
  - Motivation: returning users want to recover context quickly, not decode another generic dashboard sentence.
  - Ability: improves when the summary explains what the counts mean for the next action, not just what exists.
  - Prompt: `reopen reading` and `move into review` are stronger prompts than `latest note updated`.
- B.I.A.S diagnosis:
  - Block: generic count language is easy to skim past because it looks like passive status.
  - Interpret: naming the saved note and review payoff makes the card legible as part of the same paper-first loop.
  - Act: users can choose whether to keep reading or review with less translation effort.
  - Store: consistent saved-note language across home increases the chance users remember one stable resume story.
- Peak-End design notes:
  - Peak is seeing that the latest saved note is still the entry point back into the paper thread.
  - Pit was a summary card that looked informative but under-explained the next move.
  - Transition is home workspace context -> saved note -> review.
  - End is a calmer returning-user home that sounds like one product, not separate panels.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to a teammate saying what the current workspace state is for
- Concrete changes:
  - returning-user workspace summary now says saved notes reopen reading and review load shows what may need evidence work next
  - returning-user detail now says `Latest saved note updated` and reminds users to keep reading or move into review
  - zero-note summary now uses the same import -> saved note -> review wording as the rest of home
  - route-stub coverage now fixes both first-run and returning-user workspace-context copy
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workspace context keeps global counts while search filters the action list|backend home start-here strip points first-time users to manual import|backend home workspace context keeps saved-note return path clear"`

## 18) Workspace Context Limited-Note Recovery Checkpoint (2026-04-17)
- Screen/Flow:
  - `/` triage dashboard `Workspace context` card when saved note context is limited but the live paper queue still loads
- Goal action:
  - returning users should understand that home still knows the current review load, but they need to reopen reading from Paper Notes directly while note-level context is limited.
- Primary persona:
  - a returning operator on a partially healthy machine where the main queue works but saved note context has fallen back or narrowed.
- Current friction:
  - the limited-context branch correctly hid saved-note counts, but its wording was more diagnostic than directional.
  - that made the fallback branch weaker than the rest of home at telling users where to resume reading and how to stay inside the same paper-first loop.
- Success metric:
  - the limited-context summary says `reopen reading from Paper Notes directly`, the detail line says `saved note detail is limited`, and the marker-limited note still points to Paper Notes with the same saved-note recovery story.
- Quick Review:
  - this is a recovery-copy patch, not a data-availability rewrite.
  - the safest change is to keep the unavailable counts and live review metrics as they are, while making the fallback text more explicit about the saved-note recovery path.
- Full Review:
  - P0: the limited-context summary should tell users where to resume reading.
  - P0: the detail line should say `saved note detail is limited` and explain the next safe action.
  - P1: the marker-limited note should point to reopening a saved note, not just generic note-level inspection.
  - P2: preserve the current `Unavailable` treatment for saved-note counts and keep review/block metrics untouched.
- BMAP diagnosis:
  - Motivation: users want to continue the same paper thread even when one surface is degraded.
  - Ability: improves when the fallback text tells them exactly which surface still works for reading recovery.
  - Prompt: `Open Paper Notes directly` is a stronger prompt than a generic warning about limited context.
- B.I.A.S diagnosis:
  - Block: purely diagnostic copy looks like passive system state and is easy to skip.
  - Interpret: naming the saved-note recovery path makes the fallback easier to understand.
  - Act: users can reopen reading from Paper Notes without guessing whether home is fully broken.
  - Store: the degraded branch now sounds like the same product loop instead of a separate diagnostic branch.
- Peak-End design notes:
  - Peak is realizing the paper-first loop still survives even when note context is partially degraded.
  - Pit was a limited-context warning that described the problem more than the recovery path.
  - Transition is home limited-context branch -> Paper Notes -> saved note -> review.
  - End is a fallback state that still preserves operator confidence.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to a teammate saying “this panel is limited, but here’s where to keep going”
- Concrete changes:
  - limited-context summary now says reopen reading from Paper Notes directly
  - limited-context detail now says saved note detail is limited and points users back to Paper Notes before review
  - limited marker note now says Paper Notes can reopen a saved note or check starred/triaged papers
  - route-stub coverage now fixes the limited-context copy and the `Unavailable` count treatment together
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend home workspace context keeps limited note context handoff clear|backend workspace context keeps global counts while search filters the action list|backend home workspace context keeps saved-note return path clear"`

## 19) Saved Outputs Paper-Thread Continuity Checkpoint (2026-04-17)
- Screen/Flow:
  - `/` triage dashboard `Saved outputs` card
- Goal action:
  - users should understand that saved outputs are downstream artifacts they open after the current paper thread is ready, not a competing primary lane on home.
- Primary persona:
  - a first-session or returning operator who sees downstream artifact links on home and needs to know when to use them.
- Current friction:
  - the existing `Saved outputs` label was fine, but the helper sentence was still generic enough to sound like a parallel workspace area.
  - after the recent saved-note alignment work, the card was one of the last home surfaces not explicitly tied back to the current paper thread.
- Success metric:
  - the card says saved outputs open after the current paper thread is finished and names reading, review, or blocker repair as the lead-in states.
- Quick Review:
  - this is a continuity-copy patch, not an IA or link rewrite.
  - the smallest safe change is to keep the label and links while tightening the helper sentence so it reads as a downstream handoff.
- Full Review:
  - P0: `Saved outputs` should sound secondary to the paper thread, not parallel to it.
  - P0: the helper copy should name the three main upstream states users actually pass through on home.
  - P1: keep artifact continuity visible; do not hide downstream surfaces from first-session users.
  - P2: preserve the current link set and route structure.
- BMAP diagnosis:
  - Motivation: users want to know when an artifact surface is relevant.
  - Ability: improves when the card explains the prerequisite state in plain language.
  - Prompt: “after you finish the current paper thread” is a better prompt than a generic “after evidence or blocker work.”
- B.I.A.S diagnosis:
  - Block: generic artifact wording is easy to mentally file as another dashboard category.
  - Interpret: naming the paper thread makes the relationship to the rest of home clearer.
  - Act: users are less likely to click downstream links before they have stabilized the current paper.
  - Store: home now reinforces one sequence instead of several seemingly equal lanes.
- Peak-End design notes:
  - Peak is understanding that saved outputs are a handoff stage, not the start.
  - Pit was a secondary card that could read like another primary workspace slice.
  - Transition is paper thread -> saved output handoff.
  - End is a cleaner mental model for when artifact links matter.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to a teammate saying “open those artifacts after you finish this paper”
- Concrete changes:
  - kept the `Saved outputs` label and links unchanged
  - updated the helper line to say outputs open after the current paper thread, whether the user is finishing reading, review, or blocker repair
  - added stable test coverage for the helper copy in live home and first-run home states
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend mode stays out of mock fallback|backend home start-here strip points first-time users to manual import"`

## 20) Access Link Label Honesty Checkpoint (2026-04-21)
- Screen/Flow:
  - `/` triage dashboard queue rows and other surfaces that reuse the shared `accessSummary` helper
- Goal action:
  - users should understand where an access link goes without reading route-shaped implementation language.
- Primary persona:
  - an operator scanning queue rows to decide whether they can open an OA PDF immediately or need an institution-assisted page first.
- Current friction:
  - the access badge labels were already product-shaped: `Open access`, `Institution route`, `Local PDF`.
  - but the optional link labels still said `Open PDF route` and `Open institution route`, which leaked implementation language back into the UI.
- Success metric:
  - shared access links use user-facing destination language: `Open available PDF`, `Open institution page`, and `Open saved PDF`.
- Quick Review:
  - this is a shared helper copy cleanup, not a hierarchy or data-model change.
  - the safest fix is to keep the badge states and URLs unchanged while renaming the optional links.
- Full Review:
  - P0: access links should say what opens, not that a route exists.
  - P0: institution-assisted access should stay honest and avoid implying guaranteed success.
  - P1: keep the shared helper so home, triage, rail, and workbench stay consistent.
  - P2: preserve existing badge labels because those are already part of the current product language.
- BMAP diagnosis:
  - Motivation: high when a user is deciding whether to read now or switch to an institution-assisted path.
  - Ability: improves when the link label names the destination directly.
  - Prompt: `Open available PDF` and `Open institution page` are clearer prompts than route-language labels.
- B.I.A.S diagnosis:
  - Block: route-shaped labels force users to translate UI wording before acting.
  - Interpret: destination-shaped labels better match what users expect the click to do.
  - Act: users can choose the right access path more quickly from the queue.
  - Store: the dashboard feels more like a paper workspace and less like a router/debug surface.
- Peak-End design notes:
  - Peak is understanding the access destination at a glance from the row itself.
  - Pit was seeing user-facing UI fall back to `route` wording after the badge already explained the state well.
  - Transition is queue scan -> open available PDF or institution page -> continue reading/review.
  - End is a more trustworthy access cue in shared helper-driven surfaces.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided by keeping `Institution route` as the badge state and using `Open institution page` rather than promising access success
  - In Real-Life: closer to how a teammate would actually point someone to the next place to open
- Concrete changes:
  - changed shared access-summary link labels from `Open PDF route` / `Open institution route` to `Open available PDF` / `Open institution page`
  - kept badge labels, URL destinations, and hierarchy unchanged
  - added route-stub browser coverage for both open-access and institution-assisted access rows
- Verification:
  - `python3 scripts/lint_docs.py docs/UX_REVIEW_REPORT_triage-dashboard.md`
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend triage access links keep open and institution routes in user language"`

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

## 9) Header Copy and Orientation Checkpoint (2026-03-22)
- Screen/Flow: `/papers` first-load scan, filter orientation, search handoff into detail
- Goal action: 사용자가 첫 스캔에서 이 화면이 note storage 설명이 아니라 실제 검색/선별 작업 표면이라는 점을 바로 이해한다.
- Primary persona: 많은 논문 노트를 빠르게 찾고 structured signal이 있는 note를 열어보려는 연구자
- Current friction:
  - `Lattice · Paper Notes Viewer`, `Obsidian vault note index...` 같은 문구는 제품 언어보다 내부/저장소 언어에 가깝다.
  - search placeholder도 읽기 동작보다 필드 나열처럼 느껴진다.
- Quick decision:
  - H1, route, filter 구조는 유지한다.
  - 대신 eyebrow, subtitle, search placeholder를 작업 중심 언어로 바꾼다.
- BMAP:
  - Motivation: 높음. 사용자는 note를 찾고 싶은 것이지 vault 구조 설명을 읽고 싶지 않다.
  - Ability: 첫 화면 문구를 더 직접적으로 바꾸면 시작 비용이 줄어든다.
  - Prompt: `Search notes...` 수준의 직접적 문구가 가장 적절하다.
- B.I.A.S:
  - Block: 내부 구현 맥락이 먼저 보이면 작업 의미가 늦게 읽힌다.
  - Interpret: storage 설명 대신 search/filter/open 흐름을 먼저 보여주면 즉시 해석된다.
  - Act: placeholder와 subtitle이 다음 행동을 짧게 가리킨다.
  - Store: 첫 인상이 calmer working surface로 남아 장기 사용 피로를 낮춘다.
- Peak-End:
  - Peak는 첫 스캔에서 "이제 여기서 note를 찾으면 된다"가 바로 읽히는 순간이다.
  - Pit는 vault/debug 냄새가 강해 product surface보다 internal browser처럼 보이는 순간이다.
  - Transition은 search -> row scan -> detail open이며, copy가 이 전환을 직접 지원해야 한다.
- Ethics:
  - Regret: 통과. 더 직접적이고 덜 내부적인 언어로 시간을 절약한다.
  - Black Mirror: 통과. 과장된 promise나 urgency 없이 작업 의미만 분명히 한다.
  - In Real-Life: 통과. 친절한 연구 도구처럼 읽힌다.
- Concrete change:
  - eyebrow를 `Paper note index`로 교체
  - subtitle을 `Search notes, filter structured signals, and open the paper detail you need.`로 교체
  - search placeholder를 `Title, alias, or slug`로 정리

## 10) Desktop Visual Threshold Checkpoint (2026-03-23)
- Screen/Flow: `/papers` desktop visual regression coverage
- Goal action: paper notes list의 screenshot diff가 실제 hierarchy drift를 더 민감하게 잡고, 과하게 느슨한 tolerance에 의존하지 않게 한다.
- Primary persona: list search/header/filter rhythm이 의도치 않게 무너지는지 검토하는 maintainer
- Current friction:
  - desktop `/papers` visual spec는 core full-page routes보다 훨씬 큰 `maxDiffPixels`를 쓰고 있었다.
  - 그 값이면 header/list density drift가 생겨도 visual review가 지나치게 관대해질 수 있었다.
  - audit 중 확인한 결과, darwin desktop baseline도 이전 header copy 상태를 보존하고 있어 threshold 판단 전에 baseline refresh가 필요했다.
- Quick decision:
  - runtime UI는 바꾸지 않는다.
  - desktop paper-notes-list screenshot threshold를 좁힌다.
  - stale desktop baseline을 current UI로 다시 고정한 뒤 targeted rerun으로 안정성을 확인한다.
- BMAP:
  - Motivation: 중간 이상. `/papers`는 core browse surface라 regression review 신뢰도가 중요하다.
  - Ability: baseline과 route가 이미 안정적이므로 threshold만 좁게 조정하면 된다.
  - Prompt: “full-page routes와 비슷한 수준으로 맞춘다”는 원칙이 가장 간단하다.
- B.I.A.S:
  - Block: 너무 큰 tolerance가 drift를 숨길 수 있다.
  - Interpret: 더 타이트한 threshold는 screenshot diff를 더 신뢰할 수 있게 만든다.
  - Act: 이후 layout drift를 보고 바로 판단하기 쉬워진다.
  - Store: `/papers`도 다른 core surfaces와 같은 verification discipline을 갖게 된다.
- Peak-End:
  - Peak는 desktop `/papers`가 current UI baseline과 더 타이트한 threshold 둘 다 맞춘 순간이다.
  - Pit는 full-page route인데 tolerance가 과하게 크고 baseline도 예전 copy를 가리키던 상태였다.
  - Transition은 threshold audit -> baseline refresh -> targeted rerun -> stable green이다.
- Ethics:
  - Regret: 통과. UI를 바꾸지 않고 검증 신뢰도만 높인다.
  - Black Mirror: 통과. “green”을 더 값싸게 만드는 방향이 아니라 반대로 엄격하게 만든다.
  - In Real-Life: 통과. maintainers가 실제 화면 변화를 더 정확히 검토하게 된다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper notes list layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "paper notes list layout"`

## 11) Search / Filter Keyboard Recovery Checkpoint (2026-03-30)
- Screen/Flow:
  - `/papers` filter header, especially search -> tag search -> recovery filters
- Goal action:
  - keyboard users should move from top-of-page search into tags, status, sort, page size, and structured-only recovery without getting forced through tag suggestions they did not ask to open.
- Primary persona:
  - repeat researchers narrowing the note index quickly with keyboard-first search and recovery habits.
- Current friction:
  - focusing the tag search input opened the suggestion menu even when the field was empty.
  - that meant suggested tag buttons entered the normal tab order before `Status`, `Sort`, `Page size`, and `Only structured notes`, which made the recovery controls feel farther away than they visually were.
- Success metric:
  - on an untouched `/papers` load, tab order reaches `Search`, `Search tags`, `Status`, `Sort`, `Toggle sort order`, `Page size`, and `Only structured notes` before any tag suggestion buttons.
- Quick Review:
  - this is a recovery-flow hygiene fix, not a search model rewrite.
  - the smallest safe change is to keep tag suggestions available on typing and arrow-key intent, but stop auto-opening them on empty focus.
- Full Review:
  - P0: do not open the tag suggestion menu on focus when the tag input is empty.
  - P0: give the list search and recovery controls explicit accessible labels so keyboard regression can verify them by name.
  - P1: keep suggestion buttons available once the user types or intentionally navigates the tag field.
  - P2: leave search ranking, tag matching, and filter semantics unchanged.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when recovery filters are reachable without burning several unexpected tab stops
  - Prompt: `Status`, `Sort`, and `Only structured notes` should remain easy next steps after search, not hidden behind unsolicited suggestions
- B.I.A.S diagnosis:
  - Block: suggestion buttons were intercepting the normal recovery path
  - Interpret: the filter bar could feel denser and less predictable than it looked
  - Act: empty-focus no longer expands suggestions, so the keyboard loop stays aligned with visible filter intent
  - Store: the list should feel easier to revisit and refine repeatedly
- Peak-End design notes:
  - Peak is moving from `Search` into the real recovery controls without surprise detours.
  - Pit was tabbing through tag suggestions before reaching status/sort/page-size.
  - Transition is search -> tag intent -> recovery filters -> note rows.
  - End is a calmer, more direct list-refinement loop.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a considerate search tool should behave when the user has not yet asked for tag suggestions
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - current runtime tab audit on `/ui/papers` confirms `Search -> Search tags -> Status -> Sort -> Toggle sort order -> Page size -> Only structured notes` before note rows

## 12) Active Filters Keyboard Recovery Checkpoint (2026-04-01)
- Screen/Flow:
  - `/papers` with active tag and structured filters, especially the recovery strip after `Search tags`
- Goal action:
  - keyboard users should be able to remove a selected tag, clear selected tags, and clear all filters with explicit control names before continuing into the rest of the recovery strip.
- Primary persona:
  - repeat researchers revisiting a narrowed note index and refining or undoing filters quickly without switching to the mouse.
- Current friction:
  - once a tag was already selected, the recovery path itself stayed structurally healthy, but the active-filter controls were under-specified.
  - the selected tag chip read like plain content (`Medicine/Neurology`), the tag reset button read only as `Clear`, and the broader reset affordance read as `Clear filters`, which made the path harder to understand in keyboard and regression snapshots.
- Success metric:
  - on `/papers?tags=Medicine%2FNeurology&structured=1`, tab order reaches `Search`, `Search tags`, `Remove tag Medicine/Neurology`, `Clear selected tags`, `Status`, `Sort`, `Toggle sort order`, `Page size`, `Only structured notes`, and `Clear all filters` in that order.
- Quick Review:
  - this is a naming and recovery-path hygiene fix, not a filter behavior rewrite.
  - the smallest safe change is to keep the existing controls and active-filter structure, but give the remove and clear affordances explicit accessible names and then lock the sequence in a targeted keyboard regression.
- Full Review:
  - P0: label the selected-tag chip action as `Remove tag <tag>`.
  - P0: label the tag reset affordance as `Clear selected tags`.
  - P0: label the broader reset affordance as `Clear all filters`.
  - P1: keep the current active-filter ordering and recovery semantics unchanged.
  - P2: verify the real current-runtime route with active filters, not just the default empty-filter strip.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when the active-filter strip says exactly what each recovery action will do
  - Prompt: `Remove tag`, `Clear selected tags`, and `Clear all filters` become clearer next steps than raw chip text and generic `Clear`
- B.I.A.S diagnosis:
  - Block: active-filter controls were present but semantically vague
  - Interpret: keyboard users could understand the strip less clearly than mouse users who can infer intent from position and layout
  - Act: explicit labels make recovery actions easier to choose and easier to verify
  - Store: the filtered list should feel more controllable on repeated visits
- Peak-End design notes:
  - Peak is moving from `Search tags` straight into named remove/reset controls and then back into `Status`/`Sort`.
  - Pit was landing on a chip that sounded like content and a reset button that sounded too generic.
  - Transition is search -> active filter removal/reset -> recovery controls -> note rows.
  - End is a calmer filtered-state recovery loop.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a considerate filter bar should describe destructive and reversible actions
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|paper notes list supports command-style tag selection|paper notes list supports structured-only quick toggle|paper notes list active filters keep removal and recovery controls in keyboard order"`
  - current runtime tab audit on `/ui/papers?tags=Medicine%2FNeurology&structured=1` confirms `Search -> Search tags -> Remove tag Medicine/Neurology -> Clear selected tags -> Status -> Sort -> Toggle sort order -> Page size -> Only structured notes -> Clear all filters`

## 13) First Note Entry Checkpoint (2026-04-17)
- Screen/Flow:
  - `/papers` first empty state and manual import fallback
- Goal action:
  - first-time operators should know exactly how to get one paper into Lattice and reach the saved note without hunting through the page.
- Primary persona:
  - a researcher opening Paper Notes before automatic pickup is ready on the current machine.
- Current friction:
  - the page explained that manual import existed, but the first empty state itself did not finish the job.
  - users had to infer that the dashed import callout above was the next step, and the payoff after import was not stated clearly enough.
  - this made the very first success feel more like UI interpretation than product guidance.
- Success metric:
  - first empty-state sessions can start an import or open runtime setup directly from the empty state, and import-to-note-open remains the fastest path to first meaningful success.
- Quick Review:
  - the gap was not search quality or row hierarchy.
  - the gap was first-entry completion: the empty state told users what was missing, but not strongly enough what to do next.
  - the smallest safe fix is to keep the current page structure and add starter actions plus a clearer import payoff.
- Full Review:
  - P0: give the first empty state a direct `Import PDF` action when the live backend is available.
  - P0: keep `Check automatic pickup setup` adjacent so setup and manual fallback stay visible together.
  - P0: state plainly that importing one PDF opens the saved note immediately.
  - P1: promote the import callout from `Optional fallback` to `Start here` only when the list is truly empty and unfiltered.
  - P2: leave search, filter, and list-row behavior unchanged once notes exist.
- Full Review Coverage:
  - 6P storyboard context:
    - Problem: a first-time operator lands on an empty Paper Notes surface.
    - Emotion: they want reassurance that one small action will get them into a real note quickly.
    - Action: they look for the fastest way to add a paper.
    - Struggle: the screen previously required them to connect the empty state and the dashed import box on their own.
    - Attempt: add starter actions inside the empty state and clarify the import payoff in the callout.
    - Happy Ending: one import leads straight into the saved note, where deeper structure and review can continue.
  - BMAP:
    - Motivation is already high; Ability and Prompt were the weak points.
  - B.I.A.S:
    - the main failure was Interpret -> Act; users had to infer the right next click.
  - Peak-End:
    - the first peak should be “I can start with one PDF right here,” not “where is the import control?”
  - Ethics:
    - factual guidance only; no false urgency, no misleading promise beyond the actual note-open handoff.
- BMAP diagnosis:
  - Motivation: high. the user arrived because they want to work with a paper now.
  - Ability: rises when the empty state itself contains the start action instead of only explanatory copy.
  - Prompt: the strongest prompt is a direct import action paired with a setup link.
- B.I.A.S diagnosis:
  - Block: the first empty state was one step short of being actionable.
  - Interpret: users could read “use Import PDF here” without immediately seeing that as the dominant next action.
  - Act: starter actions now turn the empty state into a true launch surface.
  - Store: the page should now teach a simple mental model: if pickup is not ready, import one PDF and continue from the saved note.
- Peak-End design notes:
  - Peak: seeing a direct `Import PDF` action inside the first empty state.
  - Pit: reading an empty-state explanation and still needing to visually search the page for the real control.
  - Transition: empty state -> import or runtime setup -> saved note detail.
  - End: the imported note opens immediately, so the user leaves the first-run state with concrete progress.
- Concrete changes:
  - promote the import callout copy to `Start here` / `Import your first PDF` when `/papers` is truly empty
  - explain that importing one PDF opens the saved note immediately
  - add empty-state starter actions for `Import PDF` and `Check automatic pickup setup`
  - keep the current search/filter recovery controls unchanged for filtered empty states
- Ethics check results:
  - Regret: improved. the screen is clearer and wastes less time.
  - Black Mirror: avoided. this is guidance, not coercion.
  - In Real-Life: closer to how a considerate operator tool would onboard someone standing next to you.
- Next PR-sized actions:
  1. if first-import sessions still stall, add a lightweight success banner on the note detail that points to the next structured action
  2. if pickup remains the dominant entry path, mirror the same “opens the saved note immediately” payoff language on `/ready`
  3. if empty-state usage becomes common in packaged installs, consider a dedicated first-run summary card above the filter bar
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend paper notes index can import a local PDF from the browser|paper notes first empty state offers starter actions when no notes are indexed|paper notes list empty state explains structured-only misses|paper notes list empty state can remove quotes from an exact-phrase miss|paper notes list empty state suggests token-based recovery searches"`

## 14) Primary Loop Home-Button Suppression Checkpoint (2026-04-17)
- Screen/Flow:
  - `/papers` list/import route inside the primary paper-first loop
- Goal action:
  - operators on the Paper Notes index should focus on import, search, and note selection without a floating `Home` affordance competing with those primary actions.
- Primary persona:
  - a first-time or returning operator using `/papers` as the main entry into the paper thread.
- Current friction:
  - the global floating `Home` button was helpful on downstream routes, but on `/papers` it sat beside the primary loop’s strongest CTA surface.
  - that made the list/import route feel slightly more like a general dashboard than a dedicated note-entry surface.
- Success metric:
  - `/papers` keeps its local paper-first actions fully dominant, while downstream routes still retain the floating `Home` escape hatch.
- Quick Review:
  - this is not a navigation-system rewrite.
  - the smallest safe fix is to suppress the global `Home` only on the exact `/papers` route and leave the rest of the runtime unchanged.
- Full Review:
  - P0: `/papers` should not have a floating `Home` button competing with import and note-selection actions.
  - P0: downstream routes should keep the global `Home` affordance because they benefit from a clear way back.
  - P1: the paper-note detail route can stay unchanged for now because it already has local paper-thread controls and existing overlap coverage.
  - P2: do not rename the button or redesign global navigation in this slice.
- Full Review Coverage:
  - 6P storyboard context:
    - Problem: a user lands on the Paper Notes list to import or reopen one paper.
    - Emotion: they want one clear paper-first action, not a mixed dashboard feeling.
    - Action: they scan the strongest CTA on `/papers`.
    - Struggle: a floating `Home` chip introduces a second high-visibility navigation target on the same surface.
    - Attempt: suppress the floating `Home` only on the list/import route.
    - Happy Ending: `/papers` feels like a dedicated paper-entry surface again.
  - BMAP:
    - Motivation stays high; Ability improves when the surface has fewer competing prompts.
  - B.I.A.S:
    - the main improvement is Block -> Act by removing a competing high-contrast action from the first scan.
  - Peak-End:
    - the early peak should be “import or reopen a note here,” not “there are multiple equally loud destinations.”
  - Ethics:
    - this is simplification, not restriction; the user still has normal browser/navigation options and downstream routes keep the escape hatch.
- BMAP diagnosis:
  - Motivation: high. people reach `/papers` because they want to work with a paper now.
  - Ability: better when import and note-selection cues stay visually dominant.
  - Prompt: the page’s own import/search controls are the right prompts on this surface.
- B.I.A.S diagnosis:
  - Block: the floating `Home` button adds a second salient target during the first scan.
  - Interpret: suppressing it makes `/papers` read more clearly as a paper-entry route.
  - Act: the user is more likely to import, search, or reopen a note first.
  - Store: the page leaves a stronger memory of “this is where I start or resume a paper.”
- Peak-End design notes:
  - Peak: seeing one clear paper-entry surface.
  - Pit: a global navigation chip competing with the local primary loop.
  - Transition: `/papers` -> note detail -> review or downstream lanes.
  - End: a calmer first scan on the main paper index.
- Concrete changes:
  - suppress the global floating `Home` button on the exact `/papers` route
  - keep the button unchanged on downstream routes
  - add regression coverage for both the live import route and the stubbed first empty state
- Ethics check results:
  - Regret: improved. the primary loop wastes less attention.
  - Black Mirror: avoided. no capability is hidden where it is safety-critical.
  - In Real-Life: closer to how a thoughtful tool would stop shouting “go somewhere else” while you are starting the main task.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend paper notes index can import a local PDF from the browser|paper notes first empty state offers starter actions when no notes are indexed|backend paper note to workbench to protocol create journey stays connected in the browser"`

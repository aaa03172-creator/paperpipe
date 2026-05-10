# UX Review Report - Cross-Cutting Systems

Status: Current review plan
Date: 2026-03-30
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

Date: 2026-03-30
Reviewer: Codex

## Input
- Screen/Flow: global shell, search/filter/recovery, runtime readiness, import transparency, mobile dense layouts, keyboard/focus, route-direct entry
- Goal action: 사용자가 PaperPipe를 반복적으로 쓸수록 더 빠르고 더 신뢰 가능한 local-first research workspace로 느끼게 만든다.
- Primary persona: 매일 같은 runtime을 반복 사용하는 연구자/운영자 혼합 사용자
- Current friction: route-specific UX는 많이 좋아졌지만, 고속 조작성·회수성·shell safety·local-first trust 같은 cross-cutting 기준은 separate artifact로 관리되지 않는다.
- Success metric:
  - direct-open and shell stability 유지
  - import/readiness 이해 가능성 증가
  - search/filter recovery friction 감소
  - dense routes에서 overlap/focus 문제 없는 상태 유지
- Constraints:
  - existing global shell and route system 유지
  - no new design system rewrite
  - `rules/product-psychology/SKILL.md`
  - `rules/product-psychology/references/review-checklist.md`
  - `rules/product-psychology/references/bias-framework.md`
  - `rules/product-psychology/references/ethics-checklist.md`
  - `rules/product-psychology/references/prompt-templates.md`

## Quick Review (5 min)
- Block: 개별 화면이 좋아도 findability, shell safety, runtime trust가 약하면 전체 UX는 쉽게 흔들린다.
- Interpret: PaperPipe는 일반 SaaS보다 local-first transparency와 dense desktop usability가 중요하다.
- Act: cross-cutting review를 route 밖의 system layer로 분리한다.
- Store: 사용자는 결국 “이 도구가 오래 써도 버틸 만한가”로 제품을 기억한다.
- Ethics first pass: 새 기능보다 stability, honesty, recovery를 우선하는 계획이라 적절하다.
- Decision: shell, readiness, import, recovery, keyboard/focus는 별도 audit lane으로 둔다.

## Full Review
### P0
- current system review의 첫 축은 trust다.
- import flow, readiness page, mock/fallback honesty, direct-open stability, current-runtime data transparency는 PaperPipe의 local-first identity를 직접 보여준다.
- [RuntimeReadinessPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/RuntimeReadinessPage.tsx), [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx), [App.tsx](/Users/jangseongjin/paperpipe/frontend/src/App.tsx) 는 route-specific UI보다 더 system-level contract를 담당한다.

### P1
- 두 번째 축은 recovery and speed다.
- triage search, note list search/filter, direct note reopen, shell `Home`, mobile drawers, overlap safety, focus order는 모두 “자주 쓸수록 더 빠른가”를 결정한다.
- 지금까지 일부 shell overlap은 browser geometry로 rail에 들어갔으므로, 이 cross-cutting audit은 regression-friendly system checklist여야 한다.

### P2
- 세 번째 축은 accessibility and commandability다.
- current repo는 keyboard-first shell이 강하지 않으므로, 이 항목은 당장 리디자인보다 baseline audit이 먼저다.
- focus order, visible action labels, mobile sticky CTA, dense panels의 scroll behavior를 우선 본다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: 반복 사용성은 개별 화면보다 system consistency에서 갈린다.
  - Emotion: 사용자는 제품이 한 번만 되는지, 매일 믿고 쓸 수 있는지를 빨리 감지한다.
  - Action: direct-open, import, search, note reopen, shell navigation, runtime checks를 반복한다.
  - Struggle: 작은 shell collision이나 route honesty 부족은 조용하지만 신뢰를 크게 깎는다.
  - Attempt: cross-cutting systems를 route-specific review에서 분리해 상시 점검 대상으로 둔다.
  - Happy Ending: PaperPipe가 “조금 거칠지만 믿고 계속 쓸 수 있는 도구”로 느껴진다.
- BMAP:
  - Motivation: 높다. 반복 사용자는 속도와 신뢰를 원한다.
  - Ability: recovery, shell safety, import clarity, focus order가 중요하다.
  - Prompt: readiness guidance, import CTA, global home, list search, sticky actions가 system prompts다.
- B.I.A.S:
  - Block: 작은 시스템 불안정성은 cumulative friction을 만든다.
  - Interpret: 사용자는 이를 feature bug보다 “덜 믿을 만한 앱”으로 해석한다.
  - Act: shell safety와 recovery affordance를 system layer에서 검토한다.
  - Store: local-first trust와 반복 사용성이 기억의 핵심이 된다.
- Peak-End:
  - Peak: current runtime direct-open이 조용하고 빠르게 되는 순간이다.
  - Pit: shell overlap, console noise, mock ambiguity, import confusion이 저점이다.
  - Transition: entry -> route -> action -> return loop의 안정성이 중요하다.
  - End: 작업 후 다시 찾기 쉬운가, 다시 열기 쉬운가가 마지막 기억을 만든다.
- Ethics:
  - Regret: 낮다. trust와 recovery를 더 먼저 보려는 계획이다.
  - Black Mirror: 낮다. flashy redesign보다 operational honesty를 우선한다.
  - In Real-Life: local-first tool은 결국 “안정적이고 다시 찾기 쉬운가”로 평가된다.

## BMAP diagnosis
- Motivation: 반복 사용성과 trust는 research workspace의 장기 가치다.
- Ability: search, import, readiness, shell safety가 체감 ability를 결정한다.
- Prompt: global and local system prompts를 함께 본다.

## B.I.A.S diagnosis
- Block: route-specific 리뷰만으로는 system friction이 숨어버린다.
- Interpret: 작은 shell/runtime 문제는 전체 앱 신뢰를 깎는다.
- Act: cross-cutting checklist를 별도 운영한다.
- Store: 안정성과 honesty가 제품 기억의 핵심이 된다.

## Peak-End design notes
- peak는 direct-open과 note/workbench/action loop가 조용하게 유지되는 상태다.
- pit는 overlap, noisy fallback, confusing import/setup이다.
- transition은 entry/readiness/import/search에서 main work loop로 넘어가는 순간이다.
- end는 다시 돌아왔을 때 recovery가 쉬운가다.

## Concrete changes
- 이 문서는 다음 system audit checklist로 쓴다.
  - shell safety:
    - global `Home`
    - overlap regression
    - mobile sticky actions
  - findability/recovery:
    - triage search
    - papers search/filter
    - note reopen
  - local-first trust:
    - `/ready`
    - import CTA
    - watch-folder honesty
    - direct-open `/ui/*`
  - baseline accessibility:
    - focus order
    - visible action labels
    - keyboard reachability
- 우선 체크할 실제 파일:
  - [App.tsx](/Users/jangseongjin/paperpipe/frontend/src/App.tsx)
  - [RuntimeReadinessPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/RuntimeReadinessPage.tsx)
  - [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx)
  - [PaperNotesListPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNotesListPage.tsx)
  - [WorkbenchLayout.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/layouts/WorkbenchLayout.tsx)

## Ethics check results
- Regret: 낮음
- Black Mirror: 낮음
- In Real-Life: flashy UI보다 실제 반복 사용성에 가까운 계획이다.

## Next PR-sized actions
1. current runtime direct verification checklist를 이 문서 기준으로 정리한다.
2. shell safety, import, readiness, search를 한 묶음으로 보는 smoke checklist를 만든다.
3. keyboard/focus baseline audit을 별도 작은 PR 범위로 시작한다.

## 7.1) Keyboard / Focus Baseline Checkpoint (2026-03-30)
- Screen/Flow: `/ui`, `/ui/papers/:slug`, `/ui/workbench/:paperId`, `/ui/image-evidence/:imageEvidenceId`
- Goal action: keyboard-only user가 primary CTA를 early tab order에서 만나고, static metadata blocks가 action flow를 끊지 않는다.
- Primary persona: mouse 없이 dense research surfaces를 훑는 반복 사용자
- Current friction:
  - baseline audit에서 note detail은 nested interactive structure 때문에 duplicate focus stops가 보였다.
  - image-evidence detail은 scrollable `<pre>` blocks가 Chromium tab order에 들어와 non-interactive metadata가 action loop를 끊었다.
- Quick decision:
  - 이번 slice는 smallest-safe로 image-evidence focus drift와 note-detail nested interactive만 먼저 줄인다.
  - papers list와 workbench는 baseline audit에서 healthy하게 보였으므로, 이번엔 current-runtime high-value routes의 hygiene fix와 regression codification까지 닫는다.
- Verification:
  - `cd frontend && npm run build`
  - targeted current-runtime tab sequence audit on papers list, note detail, workbench, and image-evidence detail
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes"`
  - confirm note detail no longer emits duplicate focus stops, workbench/list keep primary actions early, and non-interactive `<pre>` no longer receives tab focus

## 7.2) Workbench Repeated Controls Regression Checkpoint (2026-03-30)
- Screen/Flow: `/ui/workbench/:paperId` desktop repeated-action controls after the main run controls
- Goal action: keyboard users should reach maintenance toggles, appearance controls, and rail search in a named, repeatable order.
- Primary persona: repeat users moving quickly through workbench controls and the paper rail without leaving the keyboard.
- Current friction:
  - the first baseline audit proved workbench was broadly healthy, but the deeper repeated-control sequence was still only inferred from raw element text.
  - checkbox and select names were not explicit enough for a stable regression story.
- Quick decision:
  - add explicit accessible labels to the repeated controls instead of rearranging the workbench.
  - expand the regression to cover `Verify checks`, `Fresh retrieval`, `Theme`, `View`, `Highlight`, and `Search papers`.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - current runtime tab audit on `/ui/workbench/:paperId` confirms named stops through repeated controls into rail search

## 7.3) Papers List Recovery Keyboard Checkpoint (2026-03-30)
- Screen/Flow: `/ui/papers` search and filter header
- Goal action: keyboard users should reach the main recovery filters without being pulled into tag suggestions before they have asked for them.
- Primary persona: repeat users searching paper notes quickly and then tightening results with lightweight filters.
- Current friction:
  - the tag search field opened its suggestion menu on empty focus.
  - this caused suggestion buttons to enter the normal tab path ahead of `Status`, `Sort`, `Page size`, and `Only structured notes`, which made the recovery strip feel noisier than the visual layout implied.
- Quick decision:
  - keep the tag suggestion menu available for typed input and arrow-key intent.
  - stop opening it automatically on empty focus, and give the filter controls explicit names so the keyboard regression can verify them by label.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - current runtime tab audit on `/ui/papers` confirms `Search -> Search tags -> Status -> Sort -> Toggle sort order -> Page size -> Only structured notes`

## 7.4) Workbench Panel Jump Keyboard Checkpoint (2026-03-30)
- Screen/Flow: `/ui/workbench/:paperId` rail search into document/artifact/timeline panels
- Goal action: keyboard users should be able to jump from the paper rail into the deeper review panels without tabbing through every paper row.
- Primary persona: repeat users moving between rail search, document review, artifact inspection, and timeline checks on the same workbench.
- Current friction:
  - after `Search papers`, the next keyboard stops were the paper-row buttons in the rail.
  - this was honest DOM order, but it made the deeper panels feel farther away than the visual layout implied.
- Quick decision:
  - keep the panel layout and rail list as-is.
  - add explicit jump controls under the rail search field and make the panel wrappers focusable targets for those controls.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - current runtime tab audit on `/ui/workbench/:paperId` confirms `Search papers -> Jump to document panel -> Jump to artifact panel -> Jump to timeline`

## 7.5) Artifact Panel Static Preview Focus Checkpoint (2026-03-31)
- Screen/Flow: `/ui/workbench/:paperId` after `Jump to artifact panel`
- Goal action: keyboard users should stay on claim review, sync, and disclosure controls before any static preview content.
- Primary persona: repeat users using the new workbench jump controls to inspect saved checks and mirror details quickly.
- Current friction:
  - the new panel jump made the artifact panel reachable faster, but the artifact panel still had two scrollable `<pre>` previews that could receive tab focus.
  - this pulled keyboard users off the interactive review path and into static preview text.
- Quick decision:
  - keep the artifact panel structure intact.
  - remove those preview `<pre>` blocks from tab order with `tabIndex={-1}` and extend the keyboard regression so the first artifact-panel stops stay interactive.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - current runtime `/ui/workbench/:paperId` audit confirms the first artifact-panel tab sequence includes claim buttons, sync, and summaries, and excludes `<pre>` stops

## 7.6) Timeline Filter Keyboard Checkpoint (2026-04-01)
- Screen/Flow: eventful `/ui/workbench/:paperId` timeline state after `Jump to timeline`
- Goal action: keyboard users should land on the timeline filter controls first and hear stable control names.
- Primary persona: repeat users reviewing run history with the keyboard after moving through the workbench via panel jumps.
- Current friction:
  - the shared runtime mostly exposes a no-event timeline state, so the meaningful keyboard audit had to use an eventful fixture route.
  - the timeline filter buttons were visible, but their accessible names were tied to changing counts, which made the path harder to inspect and the regression more brittle.
- Quick decision:
  - keep the timeline layout and read-only event rows intact.
  - add explicit `aria-label`s to the four filter buttons and verify the eventful jump path via fixture-backed Playwright coverage.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser|backend timeline falls back to all when status events are unavailable|backend timeline surfaces user-triggered actions distinctly|backend timeline jump keeps filter controls ahead of pinned and event content"`
  - current runtime `/ui/workbench/:paperId` still focuses the timeline panel cleanly and keeps the honest no-event copy when no events are available

## 7.7) Active Filter Recovery Keyboard Checkpoint (2026-04-01)
- Screen/Flow: `/ui/papers?tags=Medicine%2FNeurology&structured=1`
- Goal action: once filters are already active, keyboard users should hear explicit remove/reset actions before continuing into status, sort, page size, and structured-only recovery controls.
- Primary persona: repeat users reopening a narrowed note list and quickly backing out one tag or clearing broader filters.
- Current friction:
  - the filtered-state layout itself was fine, but the active-filter controls were semantically weak for keyboard users.
  - the selected tag chip sounded like plain content, the chip reset button sounded only like `Clear`, and the broader reset affordance sounded only like `Clear filters`.
- Quick decision:
  - keep the active-filter strip and recovery order intact.
  - add explicit accessible names to the selected-tag removal and reset controls, then lock the current-runtime filtered route in the backend keyboard regression.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|paper notes list supports command-style tag selection|paper notes list supports structured-only quick toggle|paper notes list active filters keep removal and recovery controls in keyboard order"`
  - current runtime `/ui/papers?tags=Medicine%2FNeurology&structured=1` now confirms `Remove tag Medicine/Neurology`, `Clear selected tags`, and `Clear all filters` before the rest of the recovery strip

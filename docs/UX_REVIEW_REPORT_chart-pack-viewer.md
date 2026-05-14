# UX Review Report: Chart Pack Viewer

Status: Active
Date: 2026-03-20
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Chart Pack viewer (`/chart-packs`, `/chart-packs/:chartPackId`)
- Goal action: Inspect a saved chart pack and decide whether its CSV/spec artifacts are safe to reuse downstream.
- Primary persona: Operator reviewing deterministic chart outputs before handoff into notes, slides, or external plotting work.
- Current friction: Backend `chart_pack` generation exists, but there is no direct viewer for chart scope, warning concentration, source lineage, or saved CSV/spec artifacts.
- Success metric: Operator can open a saved chart pack, understand what each chart represents, inspect warnings and transforms, and export CSV/spec payloads without leaving the viewer.
- Constraints: Read-only v0 lane; no inline editing, no bespoke chart rendering engine, preserve `--pp-*` tokens and dark-first Lattice tone, keep the viewer framed as artifact QA rather than statistical truth validation.

## Quick Review (5 min)
- The first read needs to answer three questions quickly: what charts are in the pack, which ones carry warnings, and what source artifact each chart came from.
- The index should prioritize search plus warning visibility over dense filters or chart thumbnails.
- The detail page should keep chart cards central, then place caution notes, source refs, and markdown nearby so the operator can review before export.

## Full Review
### P0
- Keep the viewer read-only. Editing chart definitions or numbers inside the viewer would blur whether a value came from saved artifacts or operator intervention.
- Surface pack warnings and per-chart warnings in the primary viewport. If warnings only appear after opening downloads, users will over-trust clean-looking tables.

### P1
- Show chart source refs, transform steps, and a snapshot preview together on each chart card so the operator does not have to inspect raw JSON to understand the bundle.
- Keep CSV/spec export on the same card as the preview. The handoff should happen from the review surface, not from a secondary file browser.
- In mock mode, downloads should still work locally from saved payloads so the interaction model matches real mode.

### P2
- Show render environment and pack-level caution notes in the sidebar to reinforce the bounded, template-driven nature of the lane.
- Keep a lightweight markdown preview at the bottom because the saved markdown is part of the pack contract and often the easiest handoff artifact to scan.

### Full Review Coverage
- 6P storyboard context: Problem is derived chart bundles becoming opaque once saved; emotion is low trust in chart polish without lineage; action is open a chart pack; struggle is understanding warnings, transforms, and export scope; attempt is inspect cards then export; happy ending is a reusable pack whose limits are obvious.
- BMAP: Motivation is high because chart packs are downstream communication artifacts; ability drops when preview and lineage are split across files; prompt should bring warnings and exports into the first screen.
- B.I.A.S: Block comes from hidden lineage and unclear source scope; interpret improves when chart cards show source, transforms, preview, and warnings together; act improves with direct CSV/spec downloads; store improves when every pack uses the same card structure.
- Peak-End: Peak should be immediate recognition of chart purpose and warning state; pit is a file-list-only viewer; transition is from index card to chart card detail; end is explicit caution notes plus export actions.
- Ethics: The viewer must not imply that charts are validated scientific conclusions. Warnings, source refs, and caution notes should remain prominent, and chart polish should not conceal skipped or excluded data.

## BMAP diagnosis
- Motivation: High. Saved chart packs are handoff artifacts and need a fast review loop.
- Ability: Medium before this viewer. Raw JSON/CSV/spec files are inspectable but too indirect for routine QA.
- Prompt: Weak before this viewer. There was no dedicated place to review a pack before export.

## B.I.A.S diagnosis
- Block: No dedicated read surface for chart-pack QA.
- Interpret: Users need to see chart purpose, source, transforms, and warnings together.
- Act: The next action is usually export CSV/spec or pass the pack onward; the viewer should support that directly.
- Store: Repeated chart-card structure makes future pack review predictable.

## Peak-End design notes
- Peak: A chart card should show its template, warning state, and snapshot preview immediately.
- Pit: Avoid over-designed chart canvases that feel authoritative without exposing lineage.
- Transition: Keep the index lightweight, then move into a chart-card review layout on detail.
- End: Finish the detail page with caution notes and markdown preview so users leave with the correct trust boundary.

## Concrete changes
- Route level: add `/chart-packs` index and `/chart-packs/:chartPackId` detail routes.
- Component level: render chart cards with source summary, transforms, warning chips, snapshot preview tables, and direct CSV/spec downloads.
- Copy level: frame the viewer as a saved artifact review surface, not as a chart authoring tool.
- Default-action level: primary action on index is `Open chart pack`; primary actions on detail are per-chart `Export CSV` and `Open spec JSON`.
- Runtime contract: real-mode downloads should use backend attachment routes; mock mode should keep download semantics through saved in-memory payloads.

## 7.1) Header Copy Refinement Checkpoint (2026-03-23)
- Screen/Flow: `/chart-packs` index header and `/chart-packs/:chartPackId` detail header
- Goal action: 사용자가 이 route를 generic viewer shell이 아니라 saved chart-pack review surface로 즉시 이해한다.
- Primary persona: 저장된 차트 번들을 열어 warning/source/export readiness를 검토한 뒤 downstream handoff로 넘기는 운영자
- Current friction:
  - `Lattice · Chart Pack Viewer`는 내부 shell 이름처럼 읽히고, route의 실제 책임을 직접 말하지 않는다.
  - `Index filters`는 기능은 맞지만, 사용자가 여기서 무엇을 찾고 여는지보다 도구 패널 이름처럼 들린다.
- Quick decision:
  - route 구조, chart cards, export links, sidebar summary는 유지한다.
  - eyebrow, subtitle, index title만 더 직접적인 review language로 정리한다.
- BMAP:
  - Motivation: 높음. chart packs는 downstream communication artifact라 first-read trust framing이 중요하다.
  - Ability: copy만 정리해도 이 route가 authoring tool이 아니라 review surface라는 점이 빨리 읽힌다.
  - Prompt: header와 index title이 chart-pack review responsibility를 직접 말하는 것이 가장 안전하다.
- B.I.A.S:
  - Block: viewer shell wording은 artifact QA surface를 더 추상적으로 느끼게 만든다.
  - Interpret: `Chart pack review`는 route 책임을 더 직접적으로 설명한다.
  - Act: `Search chart packs`와 `Saved chart-pack artifacts`는 index에서 다음 행동을 더 빠르게 보여준다.
  - Store: chart-pack lane도 다른 viewer routes와 같은 restrained product language를 갖게 된다.
- Peak-End:
  - Peak는 첫 진입에서 “저장된 chart-pack artifact를 검토한다”가 바로 읽히는 순간이다.
  - Pit는 generic viewer shell처럼 보여 review 목적이 늦게 드러나는 순간이다.
  - Transition은 index search -> pack detail -> export handoff이며, header copy가 그 시작점을 분명히 해야 한다.
- Ethics:
  - Regret: 통과. 기능을 과장하지 않고 route responsibility만 더 직접적으로 말한다.
  - Black Mirror: 통과. chart polish나 deterministic generation이 곧 truth라는 인상을 더 강하게 만들지 않는다.
  - In Real-Life: 통과. 운영자가 “저장된 chart pack 검토”라고 설명할 수 있는 수준의 조용한 안내다.
- Concrete change:
  - eyebrow를 `Chart pack review`로 교체
  - subtitle을 `Review saved chart-pack artifacts before export or downstream reuse.`로 정리
  - `Index filters`를 `Search chart packs`로 교체
  - `Saved chart packs`를 `Saved chart-pack artifacts`로 교체

## 7.2) Backend Visual Coverage Checkpoint (2026-03-23)
- Screen/Flow: `/chart-packs` index and `/chart-packs/:chartPackId` detail visual regression coverage
- Goal action: wording cleanup 이후에도 desktop/mobile chart-pack viewer hierarchy drift가 screenshot 레일에서 바로 보이게 한다.
- Primary persona: 저장된 chart-pack artifact를 검토하고 export 전에 warning/source context를 확인하는 운영자
- Current friction:
  - chart-pack route는 backend real-route smoke와 mock coverage는 있었지만 visual baseline이 없었다.
  - 그래서 header/card-density/sidebar drift가 생겨도 text assertions만으로는 놓칠 수 있었다.
- Quick decision:
  - runtime UI는 바꾸지 않는다.
  - backend visual spec에 index/detail snapshot 4개만 추가한다.
  - `Created`/`Generated` timestamp만 mask 처리해 baseline noise를 줄인다.
- BMAP:
  - Motivation: 높음. chart-pack viewer도 method-comparison/image-evidence처럼 screenshot review 레일이 있어야 wording과 density drift를 빨리 잡을 수 있다.
  - Ability: 이미 backend route fixture generation이 있으므로 visual spec만 좁게 추가하면 된다.
  - Prompt: detail/index 두 화면만 고정해도 route-level hierarchy regression을 충분히 잡을 수 있다.
- B.I.A.S:
  - Block: visual coverage 부재로 viewer-route regression review가 불균형했다.
  - Interpret: current UI contract를 baseline 이미지로 남기면 변화 해석이 쉬워진다.
  - Act: wording/layout drift가 생기면 snapshot diff로 바로 확인할 수 있다.
  - Store: chart-pack viewer도 다른 core viewer routes와 같은 verification discipline을 갖게 된다.
- Peak-End:
  - Peak는 index/detail 둘 다 current review surface를 baseline으로 남긴 순간이다.
  - Pit는 real-route smoke는 green인데 screenshot 기준선이 없는 상태였다.
  - Transition은 backend fixture generation -> visual snapshot update -> re-run green이다.
- Ethics:
  - Regret: 통과. runtime behavior를 바꾸지 않고 verification만 강화한다.
  - Black Mirror: 통과. 시각 polish를 과장하지 않고 drift detection 레일만 추가한다.
  - In Real-Life: 통과. maintainers가 실제 viewer 변화를 더 정확히 검토할 수 있다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|chart pack index layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|chart pack index layout"`

## 7.3) Create-From-UI Checkpoint (2026-03-28)
- Screen/Flow: `/chart-packs` index create lane
- Goal action: 사용자가 저장된 chart pack이 없어도 stats-report-backed chart pack 하나를 직접 만들고, 곧바로 saved review surface로 들어간다.
- Primary persona: saved stats report를 검토 가능한 차트 아티팩트로 빠르게 묶어 downstream handoff 전에 warnings/source/export를 확인하려는 연구 운영자
- Current friction:
  - backend `POST /chart-packs/generate`는 있었지만 UI는 saved viewer-only였다.
  - zero-state는 “여기서 볼 수 있다”까지만 말하고, 실제 시작점은 제공하지 않았다.
  - chart pack lane은 method comparison/meeting pack에 비해 workflow entry가 늦게 열려 있었다.
- Quick decision:
  - backend contract는 바꾸지 않는다.
  - document-table까지 넓히지 않고, first create path는 `stats_report` preset 1-chart pack으로 제한한다.
  - paper ID, run ID, preset, optional titles만 받아 생성 후 곧바로 detail route로 이동한다.
- BMAP:
  - Motivation: 높음. chart pack은 downstream communication artifact라 “먼저 하나 만들어 보기”가 중요하다.
  - Ability: 기존에는 saved artifact가 있어야만 route가 의미 있었고, 이번 create card로 첫 행동 장벽을 낮춘다.
  - Prompt: `Start a new chart pack` card와 `Create chart pack` CTA가 index에서 다음 행동을 분명히 만든다.
- B.I.A.S:
  - Block: saved-only surface라 첫 사용자 행동이 막혀 있었다.
  - Interpret: create card가 chart-pack route를 viewer가 아니라 workflow lane으로 다시 해석하게 만든다.
  - Act: 사용자는 paper/run IDs를 넣고 바로 생성할 수 있다.
  - Store: chart pack lane도 “start -> review -> export” 기억 구조를 갖게 된다.
- Peak-End:
  - Peak는 생성 직후 saved detail landing에서 source lineage와 export links가 바로 이어지는 순간이다.
  - Pit는 run IDs 같은 입력이 아직 운영 친화적인 점이다.
  - Transition은 index search lane 옆에 create lane을 붙여 짧게 유지한다.
  - End는 created pack detail에서 CSV/spec export까지 바로 닿는 것이다.
- Ethics:
  - Regret: 통과. empty state에서 멈추지 않게 한다.
  - Black Mirror: 통과. one-chart stats-report preset이라는 bounded scope를 숨기지 않는다.
  - In Real-Life: 통과. 운영자가 “저장된 stats report 하나를 바로 chart pack으로 묶어 검토한다”고 설명할 수 있다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack index can create a new chart pack from the browser"`

## 7.4) Saved-Run Quick-Pick And Honest Error Checkpoint (2026-03-28)
- Screen/Flow: `/chart-packs` index create lane
- Goal action: 외부 테스트 사용자가 `paper_id`와 `run_id`를 외우지 않아도 최근 저장된 stats-report run을 골라 chart pack 생성을 시작하고, 잘못된 입력을 넣었을 때도 무엇을 해야 하는지 이해한다.
- Primary persona: workbench에서 저장된 check run을 chart artifact로 바로 묶어보려는 연구 운영자와 early external tester
- Current friction:
  - `paper id`와 `run id`를 둘 다 직접 입력해야 해서 첫 시도 장벽이 높다.
  - 잘못된 입력을 넣으면 backend raw path error가 그대로 보여 제품 신뢰를 깎는다.
- Quick decision:
  - backend contract는 유지한다.
  - index create card에서 최근 saved run quick-pick을 제공해 `paper id`와 `run id`를 함께 채운다.
  - missing-run 실패는 숨기지 않고, workbench에서 무엇을 먼저 해야 하는지 설명하는 recovery copy로 바꾼다.
- BMAP:
  - Motivation: 높음. chart pack은 downstream artifact라 “하나 바로 만들어 보기” 가치가 크다.
  - Ability: run 기억/복사 부담이 높았고, quick-pick으로 낮춘다.
  - Prompt: `Recent saved runs`가 첫 행동을 직접 제시한다.
- B.I.A.S:
  - Block: operator-style ID 입력과 raw backend error
  - Interpret: quick-pick이 이 lane을 더 startable한 workflow로 읽히게 한다
  - Act: 클릭 한 번으로 `paper/run` pair를 채울 수 있다
  - Store: 실패해도 “왜 안 되는지”가 사람 말로 남는다
- Peak-End:
  - Peak는 recent saved run을 눌러 두 필드가 함께 채워지는 순간이다.
  - Pit는 `Artifact run directory not found` 같은 raw path error였다.
  - Transition은 `pick saved run -> create -> detail` 또는 `pick saved run -> fix in workbench`이다.
  - End는 failure도 recovery copy로 닫는 것이다.
- Ethics:
  - Regret: 통과. 실패를 숨기지 않되, 사용자가 다시 무엇을 해야 하는지 바로 알게 한다.
  - Black Mirror: 통과. fake success 대신 honest failure를 유지한다.
  - In Real-Life: 통과. 실제로는 사람들은 title은 기억해도 run id는 기억하지 않으므로, quick-pick이 더 인간적인 시작 경로다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack index can create a new chart pack from the browser|backend chart pack index explains missing saved runs in user language"`

## Ethics check results
- Regret: Low if warning states and caution notes remain visible before export.
- Black Mirror: Risk appears if the interface renders charts as polished truth without showing skipped-data or template bounds. Countermeasure is warning-forward cards and explicit source summaries.
- In Real-Life: A reviewer should be able to explain what a chart measures, which artifact it came from, and why it is safe or unsafe to reuse. The viewer should make that trivial.

## Next PR-sized actions
- Add a real-backend smoke that opens a generated chart pack and exercises one CSV/spec export path.
- If users start asking for visual plots, gate that behind a separate RFC instead of smuggling chart rendering into this review surface.
- Consider row-level source-paper handoff only after operators confirm they need to jump from chart cards into notes.

## 7.5) Quick-Pick Journey Checkpoint (2026-03-28)
- Screen/Flow: `/chart-packs` index quick-pick create lane
- Goal action: close-user tester가 raw ids를 복사하지 않고 recent saved run을 눌러 chart pack을 만들고 saved detail로 바로 들어간다.
- Primary persona: 가까운 사람에게 알파를 보여주기 전에 bounded chart artifact flow를 빠르게 검토하려는 연구 운영자
- Current friction:
  - 기존 backend smoke는 manual `paper id` / `run id` 입력 경로만 지켰다.
  - 실제로 가까운 사람에게 안내할 경로는 `Recent saved runs` quick-pick인데, 그 경로는 별도 regression이 없었다.
- Quick decision:
  - chart UI는 더 바꾸지 않는다.
  - backend Playwright에 quick-pick 기반 real-browser journey smoke를 추가한다.
- BMAP:
  - Motivation: 높음. 외부 테스트 직전에는 “제일 쉽게 설명할 수 있는 경로”가 살아 있어야 한다.
  - Ability: quick-pick이 실제로 보이고 채워져야 user-friendly create lane이라고 말할 수 있다.
  - Prompt: `Recent saved runs`는 지금 가장 강한 start prompt다.
- B.I.A.S:
  - Block: manual-id create path만 green이고 quick-pick path는 비어 있을 수 있다는 불안
  - Interpret: quick-pick smoke가 있으면 chart lane을 더 자신 있게 guided alpha path로 쓸 수 있다
  - Act: one-click prefill -> create -> detail이 regression rail에 들어간다
  - Store: chart lane도 “실제로 시작되는 lane”으로 기억될 가능성이 높아진다
- Peak-End:
  - Peak는 quick-pick button이 보이고, 클릭 후 create detail landing까지 이어지는 순간이다.
  - Pit는 quick-pick section은 있는데 실제 버튼이나 regression rail이 없는 상태였다.
  - Transition은 `open chart-packs -> pick recent run -> create -> saved detail`이다.
  - End는 chart pack detail에서 source lineage를 확인하는 지점이다.
- Ethics:
  - Regret: 통과. 가까운 사람에게 가장 쉬운 경로를 실제로 지킨다.
  - Black Mirror: 통과. 더 쉬운 경로를 smoke로 보호할 뿐, fake success를 만들지 않는다.
  - In Real-Life: 통과. 실제 사람은 id보다 “최근 저장한 run”을 기준으로 행동한다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack quick-pick journey stays connected in the browser"`

## 7.6) Header Context Strip Checkpoint (2026-03-29)
- Screen/Flow: `/chart-packs` index and `/chart-packs/:chartPackId` detail header
- Goal action: 사용자가 이 lane를 saved chart review surface로 더 빨리 이해하고, 어떤 run/source refs에서 파생됐는지 header에서 바로 읽는다.
- Primary persona: chart bundle을 notes, slides, CSV/spec export로 넘기기 전에 source/run provenance를 다시 확인하는 연구 운영자
- Current friction:
  - 기존 header는 review 목적은 말했지만, `언제 이 lane를 쓰는지`와 `무엇에서 파생됐는지`를 한 번에 말하지 않았다.
  - source lineage는 detail card 안에는 있었지만 header framing은 약했다.
- Quick decision:
  - existing header shell과 export controls는 유지한다.
  - header 바로 아래에 reusable context strip을 추가해 `When to use`와 `Derived from`을 고정한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack index can create a new chart pack from the browser"`

## 7.7) Re-entry CTA Checkpoint (2026-04-01)
- Screen/Flow: `/chart-packs/:chartPackId` detail source-items sidebar
- Goal action: 사용자가 saved chart pack을 검토한 뒤 바로 source paper review로 다시 들어간다.
- Primary persona: 차트 CSV/spec를 재사용하기 전에 source paper 상태와 saved checks를 다시 확인하려는 연구 운영자
- Current friction:
  - 실화면 기준으로 chart pack detail에는 source `paper_id / run_id`만 있고 `/papers`나 `/workbench`로 이어지는 CTA가 전혀 없었다.

## 7.8) SVG Preview Checkpoint (2026-04-20)
- Screen/Flow: `/chart-packs/:chartPackId` detail chart cards
- Goal action: 사용자가 저장된 chart-pack artifact 안에서 실제 SVG render를 바로 보고, 그래도 warning/source/spec보다 더 강한 truth로 오해하지 않는다.
- Primary persona: saved chart bundle을 notes, slides, meeting pack으로 넘기기 전에 chart appearance와 saved bundle completeness를 함께 확인하려는 연구 운영자
- Current friction:
  - backend에는 `render.svg` export가 생겼지만 detail viewer에서는 바로 볼 수 없어서, 사용자가 CSV/spec만 보고 별도 route를 열어야 했다.
  - 반대로 preview를 너무 앞세우면 chart-pack viewer가 authoring tool이나 polished figure surface처럼 읽힐 위험이 있었다.
- Quick decision:
  - preview는 추가하되 chart card의 trust order는 유지한다.
  - `source/spec/CSV/actions -> warnings -> transforms -> render preview -> snapshot preview` 순서를 지킨다.
  - preview copy는 live에서는 `saved SVG render`, mock에서는 `local mock preview`라고 명시해 honesty를 유지한다.
- Quick Review (5 min):
  - saved render가 카드 안에서 직접 보이는가
  - warning/source/export가 preview보다 먼저 보이는가
  - 다음 행동이 `Open SVG`/`Export CSV`/`Open spec JSON`으로 분명한가
  - mock mode에서도 preview surface가 완전히 사라지지 않는가
  - chart polish가 source limits를 덮지 않는가
- Full Review:
  - P0: warnings와 source lineage는 preview보다 앞에 남아 있어야 한다. preview가 첫 신호가 되면 derived artifact가 evidence truth처럼 보인다.
  - P1: preview는 bounded-height, non-editable, action-adjacent surface여야 한다. chart authoring affordance나 zoom-heavy canvas는 피한다.
  - P2: mock mode는 live와 같은 interaction shape를 흉내 내되, “saved render”가 아니라 “mock preview”라고 밝혀야 한다.
- Full Review Coverage:
  - 6P storyboard context: Problem은 저장된 chart render를 viewer 안에서 바로 확인할 수 없던 점이고, struggle은 별도 export route를 열어야 했던 점이다. Attempt는 chart card 안에서 render/source/spec를 함께 보는 것이고, happy ending은 downstream handoff 전에 chart appearance와 trust boundary를 같이 확인하는 것이다.
  - BMAP: Motivation은 높다. Ability는 preview absence 때문에 떨어졌고, 이번 변화는 `Open SVG`와 inline preview로 ability를 보완한다. Prompt는 preview section title과 explicit action links가 맡는다.
  - B.I.A.S: Block는 render 확인 경로의 분리였다. Interpret는 preview를 source/warnings 뒤에 둬서 “derived render”로 읽히게 만드는 데 있다. Act는 `Open SVG` 추가와 inline preview로 좋아진다. Store는 chart cards가 항상 같은 review order를 유지할 때 강화된다.
  - Peak-End: Peak는 card 안에서 saved render를 바로 확인하는 순간이다. Pit는 polished chart가 truth처럼 보이는 순간이다. Transition은 `review metadata -> preview -> export/re-entry`로 짧아야 하고, end는 여전히 caution/source review로 닫혀야 한다.
  - Ethics: Regret 통과. preview existence를 숨기지 않고, derived status도 숨기지 않는다. Black Mirror 통과. chart polish가 warning보다 앞서지 않도록 배치한다. In Real-Life 통과. 사람 운영자가 “일단 source/warnings부터 보고, render는 그 다음에 본다”고 설명할 수 있다.
- Concrete changes:
  - component level: 각 chart card에 `Open SVG` action과 bounded `Render preview` section 추가
  - copy level: live는 `Saved SVG render`, mock은 `Mock preview synthesized from saved CSV/spec`
  - layout level: preview는 warnings/transforms 아래, snapshot preview 위에 둔다
  - verification level: mock/backend Playwright와 backend visual snapshot을 갱신해 preview drift를 screenshot rail에 넣는다
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack viewer loads a generated chart pack and keeps exports on real routes|backend chart pack viewer keeps warning-heavy scatter packs honest on the real route"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|chart pack index layout" --update-snapshots=all`
  - 그래서 saved chart pack을 열고 나면 downstream artifact는 볼 수 있어도 원문 review surface로 다시 이어서 쓰지 못했다.
- Quick decision:
  - 새 viewer lane나 복잡한 handoff 카드 없이, 기존 `Source Items` 카드에 source paper 기준 `Open review` 링크만 추가한다.
  - note slug가 보장되지 않으므로 우선순위는 `/workbench/:paperId` handoff에 둔다.
- BMAP:
  - Motivation: 높음. 차트 artifact를 믿기 전에 source paper review로 되돌아가고 싶은 순간이 명확하다.
  - Ability: 기존에는 id를 복사해 수동 이동해야 해서 능력 장벽이 컸다.
  - Prompt: source item 아래 `Open review` 한 개면 다음 행동이 분명해진다.
- B.I.A.S:
  - Block: source provenance는 보이지만 이어가기 행동이 숨어 있어 사용자가 흐름이 끊긴다고 느낀다.
  - Interpret: `Open review`는 “이 차트의 근거 paper로 돌아간다”는 의미를 즉시 해석하게 한다.
  - Act: manual copy/paste 없이 한 번의 클릭으로 continuation을 만든다.
  - Store: saved chart pack도 다시 이어서 쓰는 artifact라는 기억을 남긴다.
- Peak-End:
  - Peak는 chart pack 검토 후 바로 source review로 이어지는 순간이다.
  - Pit는 source ids만 남고 실제 행동이 끊기던 detail sidebar였다.
  - Transition은 `chart pack detail -> source item -> workbench review`다.
  - End는 workbench에서 PDF/review panel을 다시 보는 지점이다.
- Ethics:
  - Regret: 통과. 숨겨진 유도 없이, 사용자가 이미 보고 있는 provenance를 따라가는 투명한 CTA다.
  - Black Mirror: 통과. 외부 전환이나 광고성 이동이 아니라 source verification 복귀다.
  - In Real-Life: 통과. 좋은 리뷰 도구라면 “이 차트의 원래 paper 다시 볼래?”를 자연스럽게 제공해야 한다.
- Verification:
  - direct browser check before fix: no `/papers` or `/workbench` links on saved chart-pack detail
  - post-fix:
    - `cd frontend && npm run build`
    - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack index can create a new chart pack from the browser"`
    - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout" --update-snapshots`

## 7.8) Review-Priority Rail Checkpoint (2026-04-13)
- Screen/Flow: `/chart-packs/:chartPackId` detail right rail
- Goal action: 사용자가 CSV/spec export 전에 이 pack이 지금 재사용 가능한지, 아니면 warnings/caution notes를 먼저 다시 봐야 하는지 첫 스캔에서 판단한다.
- Primary persona: saved chart artifact를 notes, slides, downstream plotting 전에 검토하는 연구 운영자
- Current friction:
  - right rail이 `Snapshot` metadata로 시작해서, 경고가 있는 pack도 created/generated/coverage를 먼저 읽게 만들었다.
  - 그래서 `warning-forward review surface`라기보다 metadata viewer처럼 읽힐 순간이 남아 있었다.
- Quick decision:
  - route, export contract, chart cards, source-item handoff는 유지한다.
  - right rail 최상단에 `Review priority` summary를 두고, `Caution Notes`와 `Pack Warnings`를 `Snapshot`보다 먼저 읽히게 한다.
- BMAP:
  - Motivation: 높음. chart pack은 downstream artifact라 “지금 export 가능한가” 판단이 첫 행동이다.
  - Ability: warning/caution/source-review recommendation을 첫 카드에서 요약하면 판단 비용이 줄어든다.
  - Prompt: `Review priority`가 metadata보다 먼저 보이면 사용자는 자연스럽게 caution-first review를 시작한다.
- B.I.A.S:
  - Block: created/generated metadata가 risk signal보다 먼저 노출됐다.
  - Interpret: pack detail은 artifact catalog보다 review surface로 먼저 읽혀야 한다.
  - Act: 사용자는 caution notes와 warning-marked charts를 먼저 보고, 그다음 snapshot/export로 이동한다.
  - Store: chart pack lane도 “metadata를 보는 화면”보다 “reusability를 판단하는 화면”으로 기억된다.
- Peak-End:
  - Peak는 `Review priority` 카드에서 clean-state 또는 warning-state recommendation을 바로 읽는 순간이다.
  - Pit는 `Snapshot`이 먼저 보여 경고가 늦게 체감되던 기존 rail이었다.
  - Transition은 review priority -> caution notes -> pack warnings -> snapshot -> source items다.
  - End는 export 전에 source-item review로 다시 돌아갈 수 있다는 점이 더 분명해진다.
- Ethics:
  - Regret: 통과. warning과 caution을 숨기지 않고 더 앞에 둔다.
  - Black Mirror: 통과. polished metadata로 risk를 덮지 않고, 오히려 export 전 멈춤 신호를 먼저 준다.
  - In Real-Life: 통과. 실제 리뷰어도 생성 시각보다 “이 pack을 믿어도 되나?”를 먼저 본다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack viewer loads a generated chart pack and keeps exports on real routes|backend chart pack viewer keeps warning-heavy scatter packs honest on the real route|backend chart pack index can create a new chart pack from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|mobile.*chart pack detail layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|mobile.*chart pack detail layout"`

## 7.9) Saved Quality Gate Visibility Checkpoint (2026-04-17)
- Screen/Flow: `/chart-packs/:chartPackId` detail right rail saved bundle review lane
- Goal action: 사용자가 saved `quality_gate.json` 상태를 review rail에서 바로 읽고, bundle-local handoff readiness와 warning-driven stop conditions를 metadata보다 먼저 이해한다.
- Primary persona: chart CSV/spec를 notes, slides, plotting code, or external handoff 전에 다시 검토하는 연구 운영자
- Current friction:
  - backend는 이미 `quality_gate.json`을 저장했지만 viewer는 그 상태를 전혀 보여주지 않아, bundle-local review signal이 실제 검토 화면에서 사라져 있었다.
  - 그래서 handoff contract가 있어도 사용자는 pack warnings와 caution notes만 보고, saved bundle completeness / handoff readiness는 파일을 직접 열어야 알 수 있었다.
- Quick decision:
  - 새 authoring control이나 별도 route는 추가하지 않는다.
  - existing right rail에 `Quality gate` 카드 하나만 읽기 전용으로 추가하고, `Review priority` 바로 아래에 둔다.
  - older bundles처럼 `quality_gate.json`이 없는 경우도 깨지지 않게 fallback copy로 처리한다.
- BMAP:
  - Motivation: 높음. downstream reuse 전 마지막 판단은 “이 bundle이 정말 handoff-ready인가?”다.
  - Ability: saved gate를 rail에서 바로 읽으면 json artifact를 직접 열지 않아도 된다.
  - Prompt: `Review priority -> Quality gate -> Caution Notes` 순서가 멈춤 신호와 handoff 상태를 먼저 읽게 만든다.
- B.I.A.S:
  - Block: saved quality gate가 backend artifact로만 남아 viewer surface에서 숨겨져 있었다.
  - Interpret: rail에 `Status / Bundle ready / Handoff ready / Reason codes`를 함께 보여주면 pack contract를 더 정확히 해석할 수 있다.
  - Act: 사용자는 `pass`면 정상 source-item review 후 export하고, `warn/fail`이면 flagged checks를 먼저 다시 본다.
  - Store: chart pack lane을 “CSV/spec export 전에 saved bundle contract를 확인하는 곳”으로 더 선명하게 기억하게 된다.
- Peak-End:
  - Peak는 clean pack에서 `Saved bundle checks passed`가 바로 읽히는 순간이다.
  - Pit는 saved `quality_gate.json`이 있어도 viewer에서는 전혀 보이지 않던 상태였다.
  - Transition은 `Review priority`에서 멈춤 필요성을 읽고, `Quality gate`에서 saved contract readiness를 확인한 뒤 source-item review로 넘어가는 흐름이다.
  - End는 export 직전에도 `pass/warn/fail`의 근거가 rail에 남아 있다는 점이다.
- Ethics:
  - Regret: 통과. hidden gate를 드러내는 change라서 사용자가 나중에 “왜 아무도 말 안 해줬지?”라고 느낄 위험을 줄인다.
  - Black Mirror: 통과. polished chart preview가 bundle incompleteness를 가리지 못하게 한다.
  - In Real-Life: 통과. 실제 운영자는 파일을 뒤지기보다 검토 화면에서 readiness를 먼저 보고 싶어 한다.
- Concrete change:
  - `ChartPackResponse`에 optional `quality_gate`를 추가하고 viewer는 저장된 gate가 있을 때만 read-only summary/checks를 렌더링한다.
  - clean packs는 `pass`, warning-heavy packs는 `warn`, missing gate는 older-bundle fallback copy로 구분한다.
  - detail right rail 순서를 `Review priority -> Quality gate -> Caution Notes -> Pack Warnings -> Snapshot`로 고정한다.
- Verification:
  - `pytest -q tests/test_chart_pack_handoff_artifacts.py tests/test_chart_pack_store.py tests/test_chart_pack_service.py tests/test_chart_packs_api.py`
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/chart-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend chart pack viewer loads a generated chart pack and keeps exports on real routes|backend chart pack viewer keeps warning-heavy scatter packs honest on the real route|backend chart pack index can create a new chart pack from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|mobile.*chart pack detail layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "chart pack detail layout|mobile.*chart pack detail layout"`

# UX Review Report: Method Comparison Viewer

Status: Active
Date: 2026-03-18
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Method Comparison viewer (`/method-comparisons`, `/method-comparisons/:comparisonId`)
- Goal action: Inspect an evidence-linked comparison snapshot and decide whether it is reusable as-is or needs manual review.
- Primary persona: Operator reviewing extracted study methods before downstream export or discussion.
- Current friction: Backend generation exists, but there is no direct viewer for row/field status, warning concentration, or per-cell evidence lineage.
- Success metric: Operator can open a saved comparison, identify conflict/missing cells, and trace non-missing values back to claimset lineage without leaving the viewer.
- Constraints: Read-only v0 lane; no edit UI, no document/table fallback, no new theme system, preserve `--pp-*` tokens and dark-first Lattice tone.

## Quick Review (5 min)
- The first read needs to answer three questions fast: what was compared, which cells are safe, and where evidence comes from.
- The index should act as a staging area, not a spreadsheet editor. Search and warning visibility matter more than dense controls.
- The detail page should keep the comparison table central, then place warnings and provenance nearby so review loops stay short.

## Full Review
### P0
- Make conflict and missing cells visually obvious in the main grid. If the viewer buries them in a secondary panel, the operator will over-trust the comparison.
- Keep the page read-only. Editing before the storage and provenance rules settle would blur whether a value came from claimset extraction or a manual override.

### P1
- Provide an evidence trace section that groups by paper and field, not by raw evidence id. The operator thinks in cells first.
- Keep CSV export reachable from the detail header so the user does not have to leave the review surface to hand off a snapshot, but style it as a secondary handoff action because review priority and evidence trace remain the first trust step.
- CSV export should stay route-backed with attachment semantics in real mode, and note handoff should resolve only canonical paper-note candidates rather than arbitrary markdown files.

### P2
- Show source-priority and warning counts in the index cards so the operator can triage before opening each comparison.
- Offer direct links back to `Paper Notes` when a row has a resolved `paper_slug`.

### Full Review Coverage
- 6P storyboard context: Problem is scattered method extraction review; emotion is low trust in derived tables; action is open a comparison; struggle is locating conflicts and lineage; attempt is scanning rows then checking evidence; happy ending is a reusable comparison snapshot with clear review boundaries.
- BMAP: Motivation is high because comparison tables are downstream assets; ability drops when provenance is hidden; prompt should bring warnings and evidence trace into the first viewport.
- B.I.A.S: Block comes from unclear safe-to-reuse state; interpret improves when status tones are attached to each cell; act improves with direct CSV export and note links; store improves when the same table and trace layout repeat across comparisons.
- Peak-End: Peak should be immediate visibility into conflicts; pit is a wall of undifferentiated cells; transition is from index card to detail table; end is a clear warning summary plus export path.
- Ethics: The viewer must not overstate truth. Missing and conflict cells should stay explicit, and the UI should not imply that table completeness equals scientific confidence.

## BMAP diagnosis
- Motivation: High. Operators already need these comparisons for packs, notes, and manual synthesis.
- Ability: Medium. Raw JSON and CSV files are too indirect for routine review.
- Prompt: Weak before this viewer. There was no obvious place to inspect comparison quality after generation.

## B.I.A.S diagnosis
- Block: No dedicated read surface for comparison QA.
- Interpret: Users need per-cell status and warnings, not just a stored artifact id.
- Act: The next action is usually export or reopen a source note; the viewer should support both without implying editability.
- Store: Repeated layout across comparisons builds confidence in how to review them.

## Peak-End design notes
- Peak: Show status-coded cells inside the primary table.
- Pit: Avoid spreadsheet-style density that hides provenance.
- Transition: Keep index cards lightweight, then shift to a table-plus-trace layout on detail.
- End: Finish the page with warnings and source-discipline notes so the operator leaves with the right trust boundary.

## Concrete changes
- Route level: add `/method-comparisons` index and `/method-comparisons/:comparisonId` detail routes.
- Component level: show a horizontally scrollable comparison grid with status badges, evidence-ref counts, and note links per row.
- Copy level: label the viewer as `claimset-only v0` and explain that missing cells reflect absent deterministic evidence, not failed rendering.
- Default-action level: primary action on index is `Open comparison`; detail export remains reachable but secondary, with review priority and evidence trace remaining visible before reuse.
- Runtime contract: real-mode CSV export should come from the backend attachment route, and `Open note` should only target notes that satisfy the paper-note candidate rules used by the notes viewer.

## 7.3) Create-From-UI Checkpoint (2026-03-28)
- Screen/Flow: `/method-comparisons` index left rail `Start a new comparison`
- Goal action: 사용자가 saved snapshot이 없어도 paper ids와 비교할 field만으로 comparison review lane을 직접 시작한다.
- Primary persona: downstream handoff 전에 method-like fields를 빠르게 대조해야 하는 연구 운영자
- Current friction:
  - backend `POST /method-comparisons/generate`는 있었지만 index route는 saved snapshots viewer에 머물러 있었다.
  - 그래서 비교 lane은 “이미 저장된 것이 있어야만 의미가 생기는 화면”처럼 느껴졌다.
- Quick decision:
  - detail viewer는 그대로 둔다.
  - index left rail에 bounded create form만 추가한다.
  - 입력은 `paper ids`, optional `title`, selected `fields`로 제한한다.
- BMAP:
  - Motivation: 높음. method comparison은 회의/노트/export 전 review artifact로 가치가 크다.
  - Ability: create entry가 없어서 시작이 막혀 있었다.
  - Prompt: `Start a new comparison`이 saved viewer와 별개로 첫 행동을 직접 제시해야 한다.
- B.I.A.S:
  - Block: saved snapshot이 없으면 route가 사실상 빈 브라우저였다.
  - Interpret: create form이 생기면 이 route가 viewer-only가 아니라 workflow lane으로 읽힌다.
  - Act: paper ids를 넣고 바로 detail review로 넘어가는 것이 가장 짧은 loop다.
  - Store: 사용자는 method comparison lane을 “열기 전용”보다 “직접 시작 가능한 비교 도구”로 기억한다.
- Peak-End:
  - Peak는 index에서 submit 후 바로 comparison detail로 landing 되는 순간이다.
  - Pit는 field choice가 너무 많아 설정 화면처럼 느껴지는 순간이다.
  - Transition은 `index -> create -> detail export/review`.
  - End는 warning/conflict가 detail에서 계속 visible한 상태여야 한다.
- Ethics:
  - Regret: 통과. generated comparison도 saved snapshot이라는 점을 유지하고 conflict/missing을 숨기지 않는다.
  - Black Mirror: 통과. create form이 comparison completeness를 과장하지 않는다.
  - In Real-Life: 통과. 사용자는 artifact lane 안에서 시작하고 바로 review context를 얻는다.
- Concrete change:
  - left rail에 create card 추가
  - `paper ids` textarea와 field checklist 추가
  - submit 시 backend real generate 또는 honest mock fallback 후 detail route landing
  - mock/backend browser coverage 둘 다 추가

## 7.4) Recent Paper Quick-Pick Checkpoint (2026-03-28)
- Screen/Flow: `/method-comparisons` index create card
- Goal action: 사용자가 paper id를 외우지 않아도 최근 paper를 눌러 비교를 시작한다.
- Primary persona: saved comparison이 아니라 “지금 있는 논문들 몇 개를 바로 비교하고 싶은” 바쁜 연구 운영자
- Current friction:
  - create lane가 열려 있어도 실제 입력은 여전히 operator-friendly했다.
  - `paper ids` textarea만 있으면 사용자는 다른 화면에서 id를 복사해 와야 하고, 첫 세션에서는 무엇을 넣어야 하는지 망설이기 쉽다.
- Quick decision:
  - 기존 textarea는 유지한다.
  - index load 시 recent papers를 함께 불러와 quick-pick buttons를 노출한다.
  - 선택된 paper는 같은 버튼을 다시 눌러 제거할 수 있게 한다.
- BMAP:
  - Motivation: 높음. 비교하고 싶은 paper는 이미 있는데 id 복사가 능력 장벽이 된다.
  - Ability: recent-paper quick-pick으로 시작 비용을 낮춘다.
  - Prompt: `Recent papers` 라벨과 토글 버튼이 다음 행동을 직접 제시한다.
- B.I.A.S:
  - Block: textarea-only 입력은 기억/복사 부담이 크다.
  - Interpret: quick-pick이 있으면 이 route가 “이미 저장된 것만 보는 곳”이 아니라 “바로 비교를 시작하는 곳”으로 읽힌다.
  - Act: 한두 개 paper를 클릭해 바로 입력을 구성할 수 있다.
  - Store: create lane가 더 approachable한 도구로 기억된다.
- Peak-End:
  - Peak는 최근 paper를 눌렀을 때 textarea가 즉시 채워지는 순간이다.
  - Pit는 id를 외워서 붙여넣어야 하는 순간이었다.
  - Transition은 `recent papers -> selected ids -> create -> detail`.
  - End는 여전히 saved comparison detail이 책임진다.
- Ethics:
  - Regret: 통과. power-user textarea를 없애지 않고 초보자 경로만 더했다.
  - Black Mirror: 통과. 선택된 paper가 무엇인지 숨기지 않는다.
  - In Real-Life: 통과. 실제 사용자는 논문 제목을 기억하지 id를 기억하지 않는다.
- Concrete change:
  - `getPapers()`를 index load와 함께 호출
  - create card에 `Recent papers` quick-pick buttons 추가
  - selected paper ids는 textarea와 동기화된 토글 방식으로 유지

## 7.5) Export Handoff Emphasis Checkpoint (2026-05-14)
- Screen/Flow: `/method-comparisons/:comparisonId` detail header and review rail
- Goal action: keep CSV export available while preventing the header action from visually outranking review priority, warnings, and evidence trace.
- Primary persona: researcher/operator exporting a derived comparison after checking conflict, missing-cell, and upstream note context.
- Current friction:
  - `Review priority` already tells users to inspect warnings and conflict-backed cells before export.
  - The header `Export CSV` action was styled as an accent action, which made export look more primary than the review boundary.
- Quick decision:
  - Keep the export route and label unchanged.
  - Downgrade the header export visual style to a secondary outline action.
  - Add a native title hint: `Review priority and evidence trace before exporting.`
- BMAP:
  - Motivation: high, because CSV export is the downstream handoff.
  - Ability: unchanged; export is still one click.
  - Prompt: improved; review priority remains the stronger visual prompt.
- B.I.A.S:
  - Block: avoids a bright export CTA stealing attention from review state.
  - Interpret: export is a handoff after review, not proof of readiness.
  - Act: users can still export when ready.
  - Store: method comparisons feel like derived review artifacts rather than finished spreadsheet products.
- Peak-End:
  - Peak: review priority and evidence trace define whether the artifact is reusable.
  - Pit: a polished export button implies the comparison is already ready.
  - Transition: detail review -> source note spot-check if needed -> CSV export.
  - End: exported CSV remains tied to provenance memory.
- Ethics:
  - Regret: reduced by not over-promoting export before review.
  - Black Mirror: avoids fake approval/readiness through button hierarchy.
  - In Real-Life: a careful reviewer would say “check the warning/evidence trace, then export.”

## 7.1) Header Copy Refinement Checkpoint (2026-03-23)
- Screen/Flow: `/method-comparisons` index header and `/method-comparisons/:comparisonId` detail header
- Goal action: 사용자가 이 route를 generic viewer shell이 아니라 saved comparison review surface로 즉시 이해한다.
- Primary persona: 비교 스냅샷을 열어 conflict/missing 상태를 검토하고 CSV export나 note handoff로 넘어가는 운영자
- Current friction:
  - `Lattice · Method Comparison Viewer`는 내부 shell 이름처럼 읽히고, route의 실제 책임을 직접 말하지 않는다.
  - `Index filters`도 기능은 맞지만, 사용자가 여기서 무엇을 찾고 여는지보다 도구 패널 이름처럼 들린다.
- Quick decision:
  - route 구조, table/evidence-trace/snapshot layout, export CTA는 유지한다.
  - eyebrow, subtitle, index title만 더 직접적인 review language로 정리한다.
- BMAP:
  - Motivation: 높음. comparison은 downstream 자산이라 first-read trust framing이 중요하다.
  - Ability: copy만 정리해도 이 route가 “편집기”가 아니라 “검토 surface”라는 점이 빨리 읽힌다.
  - Prompt: header와 index title이 snapshot review responsibility를 직접 말하는 것이 가장 안전하다.
- B.I.A.S:
  - Block: viewer shell wording은 table QA surface를 더 추상적으로 느끼게 만든다.
  - Interpret: `Method comparison review`는 route 책임을 더 직접적으로 설명한다.
  - Act: `Search comparisons`와 `Saved comparison snapshots`는 index에서 다음 행동을 바로 보여준다.
  - Store: method-comparison lane도 다른 viewer routes와 같은 restrained product language를 갖게 된다.
- Peak-End:
  - Peak는 첫 진입에서 “저장된 비교 스냅샷을 검토한다”가 바로 읽히는 순간이다.
  - Pit는 generic viewer shell처럼 보여 review 목적이 늦게 드러나는 순간이다.
  - Transition은 index search -> comparison detail -> export/note handoff이며, header copy가 그 시작점을 분명히 해야 한다.
- Ethics:
  - Regret: 통과. 기능을 과장하지 않고 route responsibility만 더 직접적으로 말한다.
  - Black Mirror: 통과. completeness나 claim truth를 더 강하게 암시하지 않는다.
  - In Real-Life: 통과. 운영자가 “비교 스냅샷 검토”라고 설명할 수 있는 수준의 조용한 안내다.
- Concrete change:
  - eyebrow를 `Method comparison review`로 교체
  - subtitle을 `Review saved comparison snapshots before export, note handoff, or downstream discussion.`로 정리
  - `Index filters`를 `Search comparisons`로 교체
  - `Saved comparisons`를 `Saved comparison snapshots`로 교체

## 7.2) Backend Visual Coverage Checkpoint (2026-03-23)
- Screen/Flow: `/method-comparisons` index and `/method-comparisons/:comparisonId` detail visual regression coverage
- Goal action: wording cleanup 이후에도 desktop/mobile comparison viewer hierarchy drift가 screenshot 레일에서 바로 보이게 한다.
- Primary persona: 저장된 comparison snapshot을 검토하고 CSV export나 note handoff 전에 품질을 확인하는 운영자
- Current friction:
  - method comparison route는 backend real-route smoke와 mock coverage는 있었지만 visual baseline이 없었다.
  - 그래서 header/title/card-density drift가 생겨도 text assertions만으로는 놓칠 수 있었다.
- Quick decision:
  - runtime UI는 바꾸지 않는다.
  - backend visual spec에 index/detail snapshot 4개만 추가한다.
  - `Created`/`Generated` timestamp만 mask 처리해 baseline noise를 줄인다.
- BMAP:
  - Motivation: 높음. comparison viewer도 image-evidence/detail처럼 screenshot review 레일이 있어야 wording/spacing drift를 빨리 잡을 수 있다.
  - Ability: 이미 backend route fixture generation이 있으므로 visual spec만 좁게 추가하면 된다.
  - Prompt: detail/index 두 화면만 고정해도 route-level hierarchy regression을 충분히 잡을 수 있다.
- B.I.A.S:
  - Block: visual coverage 부재로 screenshot-based regression review가 불균형했다.
  - Interpret: current UI contract를 baseline 이미지로 남기면 변화 해석이 쉬워진다.
  - Act: wording/layout drift가 생기면 snapshot diff로 바로 확인할 수 있다.
  - Store: comparison viewer도 다른 core viewer routes와 같은 verification discipline을 갖게 된다.
- Peak-End:
  - Peak는 index/detail 둘 다 current review surface를 baseline으로 남긴 순간이다.
  - Pit는 text assertions는 green인데 screenshot 기준선이 없는 상태였다.
  - Transition은 backend fixture generation -> visual snapshot update -> re-run green이다.
- Ethics:
  - Regret: 통과. runtime behavior를 바꾸지 않고 verification만 강화한다.
  - Black Mirror: 통과. 과장된 polish가 아니라 drift detection 레일 추가다.
  - In Real-Life: 통과. maintainers가 실제 UI 변화를 더 정확히 검토할 수 있다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "method comparison detail layout|method comparison index layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "method comparison detail layout|method comparison index layout"`

## Ethics check results
- Regret: Low if conflicts and missing values remain visible and export stays framed as a snapshot, not a validated truth table.
- Black Mirror: Risk appears if the UI quietly normalizes conflict cells into polished outputs. Countermeasure is explicit conflict styling and warning copy.
- In Real-Life: A reviewer should be able to explain why a cell exists and where it came from. The viewer should make that answer trivial.

## Next PR-sized actions
- Add the read-only index/detail viewer with warning-forward cards and evidence trace.
- If real users start reusing CSV outputs, add a thin “open source note” handoff for each row before any edit features.
- Delay document/table fallback until claimset-only review proves stable on real comparisons.

## 7.6) Header Context Strip Checkpoint (2026-03-29)
- Screen/Flow: `/method-comparisons` index and `/method-comparisons/:comparisonId` detail header
- Goal action: 사용자가 comparison lane를 generic table viewer가 아니라 `언제 쓰는지 / 무엇에서 파생됐는지`가 보이는 review surface로 이해한다.
- Primary persona: claimset-backed method grid를 note handoff, CSV export, meeting discussion 전에 검토하는 연구 운영자
- Current friction:
  - header는 review 목적을 말하지만, comparison이 어떤 source family에서 왔는지와 언제 열어야 하는지까지는 한 번에 안 보였다.
  - `paper_ids`와 `fields`는 body에 들어가면 보이지만, route identity 자체는 늦게 읽혔다.
- Quick decision:
  - existing comparison grid와 trace layout은 유지한다.
  - header 아래에 reusable context strip을 추가해 `When to use`와 `Derived from`을 먼저 보여준다.
- Verification:

## Implementation follow-up (2026-04-13, recent quick-pick contract slimming)
- The create-card quick-pick still stays on the same bounded UI, but it no longer needs the full `/papers?limit=5000` payload.
- A lighter backend contract now serves recent DB-backed paper choices for this surface, and the index page uses that dedicated recent-paper call instead of the heavy general `/papers` list.
- This keeps the `Recent papers` affordance intact while reducing unnecessary coupling between the method-comparison create lane and the workbench/triage paper rail contract.
- Verification target:
  - backend contract test for the new recent-paper endpoint
  - `cd frontend && npm run build`
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend method comparison index can create a new comparison from the browser"`

## 7.7) Review Priority Rail Checkpoint (2026-04-13)
- Screen/Flow: `/method-comparisons/:comparisonId` detail right rail
- Goal action: 사용자가 comparison snapshot detail에 들어오자마자 이 grid를 바로 export/reuse해도 되는지, 아니면 warnings/conflict/missing부터 봐야 하는지 즉시 판단한다.
- Primary persona: CSV export나 note handoff 전에 methods grid를 다시 확인하는 연구 운영자
- Current friction:
  - detail right rail은 `Snapshot` metadata가 먼저 나오고, 실제 reuse risk를 말해 주는 `Warnings`는 그 아래로 밀려 있었다.
  - 그래서 첫 판단이 metadata-first가 되고, warning/conflict가 있는 비교도 한 박자 늦게 읽혔다.
- Quick decision:
  - table, evidence trace, export CTA, source-discipline contract는 그대로 둔다.
  - right rail 맨 위에 `Review priority` 요약을 추가해 warning/conflict/missing 여부와 다음 행동을 먼저 말한다.
  - `Warnings` card도 metadata보다 먼저 배치해 detailed caution이 top-of-rail에서 더 빨리 읽히게 한다.
- BMAP:
  - Motivation: 높음. comparison은 downstream artifact라서 “지금 export 가능한가?” 판단이 제일 중요하다.
  - Ability: improves when the first rail card summarizes reuse risk instead of leading with timestamps.
  - Prompt: `Review priority` becomes the first prompt, with `Warnings`, `Conflict`, and `Missing` counts as immediate scan cues.
- B.I.A.S:
  - Block: metadata-first rail makes risk feel secondary even when it should lead the decision.
  - Interpret: users need a clear “review first vs export okay” message before they care about created/generated timestamps.
  - Act: surface risk summary first, then leave detailed warning text and source-discipline context one step below.
  - Store: the lane should be remembered as a review surface that tells you whether reuse is safe, not just when the snapshot was saved.
- Peak-End:
  - Peak는 right rail 첫 카드에서 바로 `Review warnings and conflict-backed cells before export.` 또는 clean-state 요약을 읽는 순간이다.
  - Pit는 `Snapshot` metadata가 먼저 보이면서 실제 review risk가 아래로 밀려 있던 점이다.
  - Transition은 review priority -> warnings detail -> snapshot metadata -> source discipline이다.
  - End는 export decision이 더 납득 가능해진다는 점이다.
- Ethics:
  - Regret: 통과. conflict/missing/warning을 숨기지 않고 더 앞세운다.
  - Black Mirror: 통과. polished summary로 위험을 덮지 않고, 오히려 reuse caution을 더 강하게 드러낸다.
  - In Real-Life: 실제 reviewer도 먼저 “문제 있는 셀이 있나?”를 보고, 그다음 생성 시간이나 source priority를 확인한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/method-comparison.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend method comparison viewer loads a generated comparison and keeps export on the real csv route|backend method comparison index can create a new comparison from the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "method comparison detail layout|mobile.*method comparison detail layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "method comparison detail layout|mobile.*method comparison detail layout"`

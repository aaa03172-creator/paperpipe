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

## Ethics check results
- Regret: Low if warning states and caution notes remain visible before export.
- Black Mirror: Risk appears if the interface renders charts as polished truth without showing skipped-data or template bounds. Countermeasure is warning-forward cards and explicit source summaries.
- In Real-Life: A reviewer should be able to explain what a chart measures, which artifact it came from, and why it is safe or unsafe to reuse. The viewer should make that trivial.

## Next PR-sized actions
- Add a real-backend smoke that opens a generated chart pack and exercises one CSV/spec export path.
- If users start asking for visual plots, gate that behind a separate RFC instead of smuggling chart rendering into this review surface.
- Consider row-level source-paper handoff only after operators confirm they need to jump from chart cards into notes.

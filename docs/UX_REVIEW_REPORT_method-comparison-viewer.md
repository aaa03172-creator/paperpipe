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
- Keep CSV export reachable from the detail header so the user does not have to leave the review surface to hand off a snapshot.
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
- Default-action level: primary action on index is `Open comparison`; primary action on detail is `Export CSV`, with review context remaining visible.
- Runtime contract: real-mode CSV export should come from the backend attachment route, and `Open note` should only target notes that satisfy the paper-note candidate rules used by the notes viewer.

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

## Ethics check results
- Regret: Low if conflicts and missing values remain visible and export stays framed as a snapshot, not a validated truth table.
- Black Mirror: Risk appears if the UI quietly normalizes conflict cells into polished outputs. Countermeasure is explicit conflict styling and warning copy.
- In Real-Life: A reviewer should be able to explain why a cell exists and where it came from. The viewer should make that answer trivial.

## Next PR-sized actions
- Add the read-only index/detail viewer with warning-forward cards and evidence trace.
- If real users start reusing CSV outputs, add a thin “open source note” handoff for each row before any edit features.
- Delay document/table fallback until claimset-only review proves stable on real comparisons.

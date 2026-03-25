# UX Review Report: Protocol Knowledge Inspector

Status: Active
Date: 2026-03-23
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Protocol Knowledge inspector (`/protocol-cards`, `/protocol-cards/:protocolId`)
- Goal action: Inspect a saved protocol card and decide whether its current version and evidence-linked snapshots are safe to reference downstream.
- Primary persona: Operator reviewing protocol-oriented knowledge extracted or adapted from paper-linked evidence before reuse in notes, planning, or manual protocol drafting.
- Current friction: Backend `protocol_card` storage and thin API exist, but there is no direct review surface for protocol identity, current-version status, version history, or evidence-backed change reasons.
- Success metric: Operator can open a saved protocol card, understand which version is current, inspect version snapshots and source-ref density, and decide whether the protocol is safe to cite or still draft-only.
- Constraints: Read-only v0 lane; no inline editing, no execution/workflow semantics, preserve `--pp-*` tokens and dark-first Lattice tone, keep the surface framed as knowledge review rather than lab-runtime automation.

## Quick Review (5 min)
- The first read needs to answer four questions quickly: what this protocol is for, which version is current, whether it is still draft-like, and how much source evidence backs each version.
- The index should emphasize search, validation state, current-version visibility, and version count over rich filters or editing affordances.
- The detail page should keep `current version + version rail + trust boundary` central so the operator does not mistake a saved protocol snapshot for experimentally verified truth.

## Full Review
### P0
- Keep the inspector read-only. Inline protocol editing would blur whether a step came from saved evidence-linked state or operator intervention.
- Surface validation status and current-version identity in the first viewport. If users have to inspect raw JSON or scroll deep to find the active snapshot, they will over-trust stale or draft versions.

### P1
- Show version status, change reason, source-ref count, and content snapshot together on each version card so the operator can understand change history without opening backend files.
- Keep the current version visually distinct from older versions. The read surface should reduce ambiguity about which snapshot downstream notes should reference.
- Make linked papers and note slugs visible but secondary. They matter as provenance and handoff, not as the main review unit.

### P2
- Show a compact markdown preview or saved summary near the bottom so the operator can compare the canonical bundle mirror with the version cards.
- Keep the index search lightweight. Protocol cards are likely to stay a small bounded family at first, so dense filter chrome would add more friction than value.

### Full Review Coverage
- 6P storyboard context: Problem is protocol knowledge becoming opaque once saved; emotion is low trust in whether a card is still draft, mixed, or paper-derived; action is open a saved protocol card; struggle is deciding which version is current and how strongly it is evidence-linked; attempt is inspect versions and provenance; happy ending is a reusable protocol reference whose limits are explicit.
- BMAP: Motivation is high because protocol knowledge is likely to be reused downstream; ability drops when version history and validation state are split across raw files; prompt should bring current-version and trust state into the first screen.
- B.I.A.S: Block comes from hidden version hierarchy and unclear trust state; interpret improves when each version card shows status, change reason, and evidence count together; act improves with direct note/paper handoff; store improves when every protocol card uses the same version-first layout.
- Peak-End: Peak should be immediate recognition of the current version and its trust boundary; pit is a file-list-only inspector; transition is from summary card to current-version detail; end is explicit trust-boundary language plus historical version context.
- Ethics: The inspector must not imply that saved protocol content is experimentally validated procedure. Draft, mixed-source, and paper-derived states should remain visible, and the UI must not look like an execution console.

## BMAP diagnosis
- Motivation: High. Protocol cards are downstream reference artifacts and need fast trust calibration.
- Ability: Medium before this inspector. JSON files and version blobs are inspectable but too indirect for routine review.
- Prompt: Weak before this inspector. There was no dedicated place to review protocol status before reuse.

## B.I.A.S diagnosis
- Block: No dedicated read surface for protocol-card QA.
- Interpret: Users need to see protocol identity, current version, version history, and source-ref density together.
- Act: The next action is usually open a paper note or carry the current version into another artifact; the viewer should support that directly.
- Store: Repeated version-card structure makes future protocol review predictable.

## Peak-End design notes
- Peak: The current version card should show version number, validation state, status, and source-ref density immediately.
- Pit: Avoid authoring-tool styling or workflow metaphors that make the page feel like a protocol executor.
- Transition: Keep the index lightweight, then move into a version-first review layout on detail.
- End: Finish the detail page with trust-boundary language and markdown preview so users leave with the correct confidence level.

## Concrete changes
- Route level: add `/protocol-cards` index and `/protocol-cards/:protocolId` detail routes.
- Component level: render a current-version spotlight, historical version cards, linked paper/note badges, and markdown preview.
- Copy level: frame the surface as `Protocol knowledge review`, not as editing or execution.
- Default-action level: primary action on index is `Open protocol card`; primary actions on detail are `Open note` when available and `Back to index`.
- Runtime contract: real mode reads the thin backend API; mock mode mirrors index/detail consistency without inventing extra editor behavior.
- Verification level: keep mock smoke, real-backend smoke, and backend visual snapshots for `/protocol-cards` index/detail in sync so the read-first shell does not drift quietly.

## Ethics check results
- Regret: Low if draft/mixed/reviewed states remain prominent and the page stays read-only.
- Black Mirror: Risk appears if the page looks like validated lab automation despite containing draft paper-derived content. Countermeasure is warning-forward trust framing and explicit validation state.
- In Real-Life: A reviewer should be able to explain which version is current, why it changed, and how strongly it is evidence-linked. The inspector should make that trivial.

## Next PR-sized actions
- Treat `protocol-knowledge` as an active bounded spec and prefer spec-following hardening over scope expansion.
- If the lane keeps proving useful, add more granular backend visual coverage for selected subregions rather than opening editor controls.
- Defer editor or activation controls until repeated usage proves the lane should move beyond read-only review.

## 7.1) Visual Threshold Discipline Checkpoint (2026-03-24)
- Screen/Flow: `/protocol-cards` index/detail desktop + mobile visual regression coverage
- Goal action: protocol inspector screenshots가 과하게 느슨한 tolerance 없이도 hierarchy drift를 잡게 만든다.
- Primary persona: protocol knowledge route의 shell drift를 visual review로 확인하는 maintainer
- Current friction:
  - protocol route는 backend visual coverage는 있지만, detail/index tolerance가 다른 full-page routes보다 다소 느슨했다.
  - 그 상태에서는 current-version emphasis나 version-card density 변화가 충분히 민감하게 잡히지 않을 수 있다.
- Quick decision:
  - runtime UI는 바꾸지 않는다.
  - desktop/mobile detail/index threshold만 한 단계 낮춰 rerun으로 안정성을 확인한다.
- BMAP:
  - Motivation: 중간 이상. protocol route는 active bounded spec이라 drift를 quietly 허용하면 안 된다.
  - Ability: current snapshots와 route fixtures가 이미 있어 threshold 조정만으로 확인 가능하다.
  - Prompt: “한 단계만 낮추고 rerun”이 가장 작은 audit 방식이다.
- B.I.A.S:
  - Block: 느슨한 tolerance가 shell drift를 숨길 수 있다.
  - Interpret: tighter threshold는 current protocol shell contract를 더 선명하게 만든다.
  - Act: 이후 version hierarchy나 trust framing drift를 diff에서 더 빨리 읽을 수 있다.
  - Store: protocol route도 다른 core viewers와 비슷한 verification discipline을 갖게 된다.
- Peak-End:
  - Peak는 desktop/mobile 4개 protocol visual tests가 더 낮은 threshold에서도 green으로 통과한 순간이다.
  - Pit는 visual coverage는 있어도 tolerance가 너무 커서 drift를 놓칠 수 있던 상태다.
  - Transition은 threshold reduction -> targeted rerun -> stable green이다.
- Ethics:
  - Regret: 통과. UI를 바꾸지 않고 verification만 엄격하게 한다.
  - Black Mirror: 통과. 느슨한 green을 허용하지 않고 실제 shell drift를 더 잘 잡게 만든다.
  - In Real-Life: 통과. maintainers가 protocol route 변화를 더 정확히 검토할 수 있다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "protocol knowledge detail layout|protocol knowledge index layout"`

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
- Reassess whether repeated real usage justifies promoting `protocol-knowledge` beyond a bounded pilot.
- If the lane keeps proving useful, add more granular backend visual coverage for selected subregions rather than opening editor controls.
- Defer editor or activation controls until repeated usage proves the lane should move beyond read-only review.

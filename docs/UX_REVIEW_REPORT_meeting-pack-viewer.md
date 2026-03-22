Status: Active
Date: 2026-03-23
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: Meeting Pack viewer (`/meeting-packs`, `/meeting-packs/:packId`)
- Goal action: Inspect a saved meeting-pack draft, decide whether it is in sync and reviewable, and then rerender, regenerate, or hand off with the right caution.
- Primary persona: Operator reviewing saved draft artifacts and trace/validation state before downstream reuse.
- Current friction: The route already exposes draft, trace, and validation state, but its header and index language read like an internal inspector shell instead of a bounded review surface.
- Success metric: Operator can open the route, understand that it is an operational review surface, find a saved pack quickly, and distinguish draft management from canonical evidence review.
- Constraints: Preserve the current route structure, operational capabilities, trace controls, and warning model; keep the route read-only except for existing rerender/regenerate actions; do not imply that meeting-pack drafts replace canonical evidence review.

## Quick Review (5 min)
- The first read needs to answer three questions quickly: what this route is for, whether it is operational or presentation-facing, and how to open the right saved pack.
- The index should prioritize finding a saved pack and understanding trace state over inspector jargon.
- The detail page should keep draft summary, validation, and trace intact while the header makes the route’s operational-review purpose explicit.

## Full Review
### P0
- Keep the route operational and read-only except for the existing rerender/regenerate actions. This surface should not drift into a general editor.
- Avoid `Inspector` and `Ops / Debug` shell language in the first read. The route already has enough operational detail in-body; the header should explain the job to be done.

### P1
- Default index headings should say “saved meeting packs” rather than generic inspector language.
- Opening a pack by id is a useful advanced action, but the label should describe the action directly instead of reading like a developer tool affordance.

### P2
- The existing in-body copy still leans operational, which is acceptable for this lane because the route is explicitly draft-management oriented.
- This route does not appear to have dedicated backend visual coverage yet, so wording changes should rely on build plus mock-route verification for now.

### Full Review Coverage
- 6P storyboard context: Problem is opaque saved draft state; emotion is low trust in draft artifacts without quick operational context; action is open meeting-pack index or direct pack id; struggle is decoding inspector-style framing; attempt is review title, status, trace, and validation before acting; happy ending is a bounded draft review surface whose role is immediately obvious.
- BMAP: Motivation is high because meeting packs are downstream communication artifacts; ability drops when the route sounds like an internal debugger instead of an operational review tool; prompt should make “review saved draft state” obvious at the top.
- B.I.A.S: Block comes from inspector jargon; interpret improves when the route is framed as meeting-pack review; act improves with direct “Open pack” language; store improves when this route uses the same restrained product language as adjacent viewers.
- Peak-End: Peak should be immediate recognition that this is a saved draft review lane; pit is an internal debugger vibe; transition is from saved-pack index to draft detail; end is clear awareness that rerender/regenerate affects only the saved draft.
- Ethics: The viewer must not imply that draft sync or trace completeness equals evidence quality. The route should stay explicit that canonical evidence review lives elsewhere.

## BMAP diagnosis
- Motivation: High. Meeting packs are reused downstream and need quick operational review.
- Ability: Medium. The route already has the right controls, but the shell language makes first interpretation more technical than necessary.
- Prompt: Medium. The current route is powerful, but the header/index language undersells the immediate task.

## B.I.A.S diagnosis
- Block: `Inspector` and `Ops / Debug` language make the route feel more internal than necessary.
- Interpret: Users need to see “saved meeting-pack review” first, then absorb the operational controls.
- Act: The next action is usually search, open a saved pack, rerender, or regenerate.
- Store: Repeated “review” language across viewer routes makes the system easier to scan.

## Peak-End design notes
- Peak: The route should immediately read as “review saved meeting packs.”
- Pit: Inspector language can make the route feel like a dev-only surface.
- Transition: Keep index search -> open pack -> rerender/regenerate flow intact.
- End: Leave the operator with the right trust boundary around draft state vs canonical evidence.

## Concrete changes
- Copy level:
  - eyebrow `Meeting pack review`
  - status badge `Operational`
  - default H1 `Saved meeting packs`
  - subtitle `Review saved meeting-pack drafts, validation state, and trace coverage before rerender or downstream reuse.`
  - button label `Open pack`
  - index title `Saved meeting packs`
  - secondary card title `Open by pack ID`
- Layout level: no route, panel, or control structure changes.
- Runtime contract: rerender/regenerate, trace filters, and validation UI stay unchanged.

## Ethics check results
- Regret: Low. The route is easier to read without hiding its operational nature.
- Black Mirror: Low if the route continues to say that draft controls do not replace canonical evidence review.
- In Real-Life: An operator should be able to explain this route as “review and manage saved meeting-pack drafts” without sounding like they are opening a debugger.

## Next PR-sized actions
- Add dedicated UX review coverage if the route gets broader user-facing use beyond current operational workflows.
- If this route gains backend visual coverage later, snapshot the index shell and a representative detail header.
- Keep future work focused on trace readability or action safety, not on broadening the route into an editor.

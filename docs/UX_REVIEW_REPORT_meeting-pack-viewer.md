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
- Backend visual coverage now exists for index/detail shells, so future work can focus on trace readability or action-safety checks rather than more header cleanup.

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

## 7.2) Backend Visual Coverage Checkpoint (2026-03-23)
- Screen/Flow: `/meeting-packs` index and `/meeting-packs/:packId` detail visual regression coverage
- Goal action: wording cleanup 이후에도 desktop/mobile meeting-pack viewer hierarchy drift가 screenshot 레일에서 바로 보이게 한다.
- Primary persona: 저장된 meeting-pack draft를 열어 review context와 operational controls를 함께 확인하는 운영자
- Current friction:
  - meeting-pack route는 mock coverage는 있었지만 backend visual baseline이 없었다.
  - generated `meetingpack_*` ids와 created timestamps가 화면에 직접 보여서, baseline을 추가해도 mask strategy가 없으면 매번 흔들릴 수 있었다.
- Quick decision:
  - runtime UI는 바꾸지 않는다.
  - backend visual spec에 index/detail snapshot 4개만 추가한다.
  - `Created` 값과 displayed `meetingpack_*` ids만 mask 처리해 baseline noise를 줄인다.
- BMAP:
  - Motivation: 높음. meeting-pack route도 viewer lane의 일부라 screenshot review 레일이 있어야 wording/spacing drift를 빨리 잡을 수 있다.
  - Ability: backend generate route가 있으므로 one-paper fixture를 만들어 visual spec만 좁게 추가하면 된다.
  - Prompt: index/detail 두 화면만 고정해도 route-level hierarchy regression을 충분히 잡을 수 있다.
- B.I.A.S:
  - Block: visual coverage 부재로 meeting-pack route만 regression review가 상대적으로 약했다.
  - Interpret: current UI contract를 baseline 이미지로 남기면 변화 해석이 쉬워진다.
  - Act: wording/layout drift가 생기면 snapshot diff로 바로 확인할 수 있다.
  - Store: meeting-pack route도 다른 viewer routes와 같은 verification discipline을 갖게 된다.
- Peak-End:
  - Peak는 index/detail 둘 다 current review surface를 baseline으로 남긴 순간이다.
  - Pit는 mock text assertions는 green인데 backend screenshot 기준선이 없는 상태였다.
  - Transition은 backend fixture generation -> visual snapshot update -> re-run green이다.
- Ethics:
  - Regret: 통과. runtime behavior를 바꾸지 않고 verification만 강화한다.
  - Black Mirror: 통과. 시각 polish를 과장하지 않고 drift detection 레일만 추가한다.
  - In Real-Life: 통과. maintainers가 실제 viewer 변화를 더 정확히 검토할 수 있다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack detail layout|meeting pack index layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack detail layout|meeting pack index layout"`

## 7.3) Visual Threshold Discipline Checkpoint (2026-03-24)
- Screen/Flow: `/meeting-packs` index/detail desktop + mobile visual regression coverage
- Goal action: meeting-pack screenshots가 generated id/time mask를 유지하면서도 과하게 느슨한 tolerance 없이 hierarchy drift를 잡게 만든다.
- Primary persona: meeting-pack route의 shell drift와 density 변화를 visual review로 확인하는 maintainer
- Current friction:
  - meeting-pack route는 visual coverage는 있었지만 detail/index tolerance가 다른 full-page viewers보다 더 느슨했다.
  - created timestamps와 `meetingpack_*` ids는 이미 mask 처리하지만, tolerance까지 크게 두면 shell drift를 지나치게 쉽게 통과시킬 수 있다.
- Quick decision:
  - runtime UI는 바꾸지 않는다.
  - existing mask strategy는 유지한 채 desktop/mobile detail/index threshold를 한 단계 낮춰 rerun으로 안정성을 확인한다.
- BMAP:
  - Motivation: 중간 이상. meeting-pack route는 operational review surface라 shell drift도 quietly 허용하면 안 된다.
  - Ability: current snapshots와 masking이 안정적이어서 threshold만 조정해도 확인 가능하다.
  - Prompt: dynamic mask는 유지하고 threshold만 줄이는 게 가장 작은 audit이다.
- B.I.A.S:
  - Block: 느슨한 tolerance가 operational-shell drift를 숨길 수 있다.
  - Interpret: tighter threshold는 current meeting-pack shell contract를 더 신뢰 가능하게 만든다.
  - Act: 이후 wording/layout drift가 생기면 snapshot diff를 더 빨리 믿고 판단할 수 있다.
  - Store: meeting-pack route도 protocol/chart-pack과 비슷한 verification discipline을 갖게 된다.
- Peak-End:
  - Peak는 desktop/mobile 4개 meeting-pack visual tests가 더 낮은 threshold에서도 green으로 통과한 순간이다.
  - Pit는 mask는 충분한데 tolerance까지 커서 drift를 놓칠 수 있던 상태다.
  - Transition은 threshold reduction -> targeted rerun -> stable green이다.
- Ethics:
  - Regret: 통과. UI를 바꾸지 않고 verification만 엄격하게 한다.
  - Black Mirror: 통과. generated ids/timestamps를 가린다고 해서 shell drift까지 관대하게 보지 않는다.
  - In Real-Life: 통과. maintainers가 meeting-pack route 변화를 더 정확히 검토할 수 있다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack detail layout|meeting pack index layout"`

## Ethics check results
- Regret: Low. The route is easier to read without hiding its operational nature.
- Black Mirror: Low if the route continues to say that draft controls do not replace canonical evidence review.
- In Real-Life: An operator should be able to explain this route as “review and manage saved meeting-pack drafts” without sounding like they are opening a debugger.

## Next PR-sized actions
- Add dedicated UX review coverage if the route gets broader user-facing use beyond current operational workflows.
- If future changes touch action safety, add a narrow interaction-focused check around rerender/regenerate result notices.
- Keep future work focused on trace readability or action safety, not on broadening the route into an editor.

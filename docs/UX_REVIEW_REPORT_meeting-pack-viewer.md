Status: Active
Date: 2026-03-28
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: Meeting Pack viewer (`/meeting-packs`, `/meeting-packs/:packId`)
- Goal action: Start a meeting-pack draft from one paper slug or inspect a saved draft, then decide whether it is ready to reuse, rerender, or regenerate.
- Primary persona: Researcher or operator preparing a meeting-ready draft and checking trace/validation state before downstream reuse.
- Current friction: The route exposed saved draft inspection well enough, but it still behaved like a saved-artifact browser. First-time users had no direct UI path to create their first pack, so empty states ended in explanation instead of action.
- Success metric: A user can open `/meeting-packs`, understand the route’s purpose, create a first draft from one paper slug, and land in the saved draft detail view with the right trust boundaries intact.
- Constraints: Preserve the current route structure, trace controls, and warning model; keep creation bounded to a thin `paper_slug`-driven entry path; do not imply that meeting-pack drafts replace canonical evidence review.

## Quick Review (5 min)
- The first read needs to answer three questions quickly: what this route is for, whether it is operational or presentation-facing, and how to open the right saved pack.
- The index should prioritize finding a saved pack and understanding trace state over inspector jargon.
- The detail page should keep draft summary, validation, and trace intact while the header makes the route’s operational-review purpose explicit.

## Full Review
### P0
- Add one bounded create path without turning the route into an editor. The safest first move is a single `paper_slug` request that reuses the existing backend generate contract.
- Avoid `Inspector` and `Ops / Debug` shell language in the first read. The route already has enough operational detail in-body; the header should explain the job to be done.

### P1
- Default index headings should say “saved meeting packs” rather than generic inspector language.
- Opening a pack by id is a useful advanced action, but it should sit behind a clearer “start a new draft” entry rather than being the only action besides list browsing.

### P2
- The existing in-body copy still leans operational, which is acceptable for this lane because the route is explicitly draft-management oriented.
- Backend visual coverage now exists for index/detail shells, so future work can focus on trace readability or action-safety checks rather than more header cleanup.

### Full Review Coverage
- 6P storyboard context: Problem is opaque saved draft state plus no first-draft entry; emotion is low trust and low momentum when the route only offers saved-output browsing; action is create or open a pack; struggle is decoding inspector-style framing and knowing where to start; attempt is create a pack from one paper slug, then review title, trace, and validation before acting; happy ending is a bounded draft workflow whose role is immediately obvious.
- BMAP: Motivation is high because meeting packs are downstream communication artifacts; ability drops when the route sounds like an internal debugger or requires a pre-existing pack; prompt should make “start a new draft or open a saved one” obvious at the top.
- B.I.A.S: Block comes from inspector jargon and empty-state dead ends; interpret improves when the route is framed as meeting-pack review plus a first-draft start; act improves with direct “Create draft” and “Open pack” language; store improves when this route uses the same restrained product language as adjacent viewers.
- Peak-End: Peak should be immediate recognition that this is a meeting-pack lane with both create and review actions; pit is an internal debugger vibe or a dead-end empty state; transition is from draft creation to saved-pack detail; end is clear awareness that rerender/regenerate affects only the saved draft.
- Ethics: The viewer must not imply that draft sync or trace completeness equals evidence quality. The route should stay explicit that canonical evidence review lives elsewhere.

## BMAP diagnosis
- Motivation: High. Meeting packs are reused downstream and need quick operational review.
- Ability: Medium. The route already has the right review controls, but first-time users need a thin create path before the lane feels usable.
- Prompt: Medium. The current route is powerful, but the header/index language and old empty state undersold the immediate task.

## B.I.A.S diagnosis
- Block: `Inspector` and `Ops / Debug` language, plus an empty state that offered no direct start path.
- Interpret: Users need to see “start a draft or open a saved one” first, then absorb the operational controls.
- Act: The next action is usually create a draft, search, open a saved pack, rerender, or regenerate.
- Store: Repeated “review” language across viewer routes makes the system easier to scan.

## Peak-End design notes
- Peak: The route should immediately read as “review saved meeting packs.”
- Pit: Inspector language and dead-end empty states can make the route feel like a dev-only surface.
- Transition: Keep create/search -> open pack -> rerender/regenerate flow intact.
- End: Leave the operator with the right trust boundary around draft state vs canonical evidence.

## Concrete changes
- Copy level:
  - eyebrow `Meeting pack review`
  - status badge `Operational`
  - default H1 `Saved meeting packs`
  - subtitle `Review saved meeting-pack drafts, validation state, and trace coverage before rerender or downstream reuse.`
  - new secondary action card `Start a new draft`
  - new button label `Create draft`
  - button label `Open pack`
  - index title `Saved meeting packs`
  - secondary card title `Open a saved pack by ID`
- Layout level: keep the existing route structure and detail view, but let the right rail host a minimal create form above the direct-open helper.
- Runtime contract: rerender/regenerate, trace filters, and validation UI stay unchanged; the new create form reuses the existing generate endpoint with a single `paper_slug` selector.

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
- Regret: Low. The route is easier to start without hiding its operational nature.
- Black Mirror: Low if the route continues to say that draft controls do not replace canonical evidence review.
- In Real-Life: A researcher should be able to explain this route as “start or review a meeting-pack draft” without sounding like they are opening a debugger.

## Next PR-sized actions
- Add a cancel/retry pattern if meeting-pack generation becomes asynchronous or long-running.
- If future changes touch action safety, add a narrow interaction-focused check around rerender/regenerate result notices.
- Keep future work focused on trace readability and first-session guidance, not on broadening the route into a full editor.

## 7.4) Header Context Strip Checkpoint (2026-03-29)
- Screen/Flow: `/meeting-packs` index and `/meeting-packs/:packId` detail header
- Goal action: 사용자가 meeting-pack lane를 saved-draft browser가 아니라 `언제 쓰는지 / 무엇에서 파생됐는지`가 보이는 downstream review surface로 이해한다.
- Primary persona: meeting-ready draft를 source coverage와 trace 기준으로 다시 확인한 뒤 discussion이나 sharing으로 넘기는 연구자/운영자
- Current friction:
  - existing header는 route 목적은 말하지만, draft를 언제 열어야 하는지와 어떤 saved source/evidence context에서 왔는지를 header 수준에서 말하지 않았다.
  - provenance는 detail body에서야 읽혔다.
- Quick decision:
  - existing route shell, create form, and trace controls는 유지한다.
  - header 바로 아래에 reusable context strip을 추가해 `When to use`와 `Derived from`만 먼저 고정한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`

## 7.5) Continue In Note Checkpoint (2026-03-29)
- Screen/Flow: `/meeting-packs/:packId` detail sidebar
- Goal action: 사용자가 saved draft를 읽은 뒤 canonical evidence 확인이 필요하면 바로 source note로 돌아간다.
- Primary persona: meeting-ready draft를 다듬기 전에 upstream note와 evidence를 다시 확인하려는 연구자
- Current friction:
  - pack detail은 downstream artifact review는 강했지만, upstream note review로 돌아가는 다음 행동이 늦게 보였다.
  - 사용자는 trace나 source refs를 해석해서 직접 note slug를 찾아야 했다.
- Quick decision:
  - saved draft shell, validation, trace cards는 유지한다.
  - detail sidebar에 `Continue from this draft` card를 추가해 linked source note를 먼저 보여준다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`

## 7.6) Live Continue In Note Coverage Checkpoint (2026-03-29)
- Screen/Flow: `/meeting-packs` browser create flow and `/meeting-packs/:packId` live backend detail handoff
- Goal action: 사용자가 live backend에서도 draft를 만든 뒤 `Continue from this draft`에서 실제 paper note로 돌아간다.
- Primary persona: meeting-ready draft를 브라우저에서 바로 만든 뒤 upstream note evidence를 다시 확인하려는 연구자
- Current friction:
  - note-first continuation card는 mock rail에서는 고정됐지만, live backend detail에서 같은 handoff가 계속 유지되는지 아직 직접 보장되지 않았다.
  - close-user 관점에서는 mock-only confidence보다 browser-create 이후 real note handoff가 더 중요하다.
- Quick decision:
  - UI shell은 그대로 둔다.
  - backend Playwright에 browser-create -> detail -> continue-in-note path 하나만 추가해 live rail을 고정한다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`

## 7.7) Rerender-Safe Continue In Note Checkpoint (2026-03-29)
- Screen/Flow: `/meeting-packs/:packId` live backend detail after `Rerender markdown`
- Goal action: 사용자가 saved markdown을 다시 그린 뒤에도 같은 draft에서 source note review로 안정적으로 돌아간다.
- Primary persona: draft wording만 다시 렌더한 뒤 upstream note evidence를 바로 재확인하려는 연구자
- Current friction:
  - live continuation coverage는 생겼지만, detail action 이후에도 같은 note-first card가 안정적으로 남는지는 아직 직접 보장되지 않았다.
  - rerender success notice가 뜨는 순간 continuation cue가 밀리거나 사라지면 사용자는 다시 다음 행동을 추론해야 한다.
- Quick decision:
  - UI shell과 action contract는 그대로 둔다.
  - existing live backend browser test 안에서 `Rerender markdown` 후에도 `Continue from this draft`와 `Continue in note`가 유지되는지만 추가로 고정한다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`

## 7.8) Regenerate-Safe Continue In Note Checkpoint (2026-03-29)
- Screen/Flow: `/meeting-packs/:packId` live backend detail after `Regenerate draft`
- Goal action: 사용자가 saved selector set으로 draft를 다시 만든 뒤에도 source note review로 안정적으로 돌아간다.
- Primary persona: draft wording과 source selection을 다시 만든 뒤 upstream note evidence를 곧바로 재확인하려는 연구자
- Current friction:
  - `Rerender markdown` 이후 continuation coverage는 생겼지만, `Regenerate draft`는 saved pack route가 바뀔 수도 있어서 note-first cue가 계속 유지되는지 아직 직접 보장되지 않았다.
  - regenerate success 뒤 continuation card가 사라지면 새 draft가 isolated artifact처럼 느껴질 수 있다.
- Quick decision:
  - UI shell과 regenerate contract는 그대로 둔다.
  - existing live backend browser test 안에서 `Regenerate draft` 후에도 `Continue from this draft`와 `Continue in note`가 유지되는지만 추가로 고정한다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`

## 7.9) Canonical Note Handoff Checkpoint (2026-04-02)
- Screen/Flow: `/meeting-packs/:packId` detail sidebar `Continue from this draft`
- Goal action: 사용자가 saved draft에서 upstream note로 돌아갈 때 raw selector ref가 아니라 실제 note identity를 보고 이동한다.
- Primary persona: saved meeting draft를 본 뒤 canonical note context와 evidence를 다시 확인하려는 연구자/운영자
- Current friction:
  - live real-paper draft에서는 `Continue in note`가 source selector ref인 `zoterodubois...`를 그대로 보여 줬다.
  - route 자체는 note detail로 이어졌지만, 사용자는 실제 note title보다 internal selector를 먼저 보게 되어 continuation confidence가 떨어졌다.
- Quick decision:
  - saved draft shell, validation, trace cards는 그대로 둔다.
  - detail sidebar에서 `paper_slug` selector를 직접 노출하지 말고, 가능한 경우 실제 paper-note detail을 resolve해서 canonical note slug/title로 handoff를 정규화한다.
  - resolve가 안 되면 기존 selector ref fallback을 유지한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`

## 7.10) Note-Backed Workbench PDF Continuity Checkpoint (2026-04-02)
- Screen/Flow: `/meeting-packs/:packId -> Continue in note -> Open review`
- Goal action: 사용자가 saved meeting draft에서 upstream note를 거쳐 workbench로 돌아갔을 때도 `No route`나 placeholder shell이 아니라 실제 local PDF review surface를 본다.
- Primary persona: saved draft를 기준으로 note evidence를 다시 확인한 뒤 바로 source PDF와 claim review를 이어가려는 연구자
- Current friction:
  - canonical note handoff는 정리됐지만, sampled Dubois lane은 `Open review` 후 workbench가 `No route` + `Placeholder PDF active`로 내려가 continuity가 끊겼다.
  - root cause는 UI보다 backend contract에 있었다. canonical DB `papers` row가 없는 note-backed paper는 workbench가 `/papers/{paper_id}` 와 `/papers/{paper_id}/pdf`에서 아무것도 못 받아 synthesize된 빈 shell로 남았다.
- Quick decision:
  - meeting-pack or note-detail UI에 새 workaround를 얹지 않는다.
  - existing workbench contract를 그대로 살리고, backend `papers` API가 note-backed paper detail과 local PDF route를 얇게 보강한다.
  - resulting UX contract:
    - `Continue in note`
    - `Open review`
    - `Local PDF`
    - live `pdf-viewer`
- Verification:
  - `pytest -q tests/test_papers_api.py -k 'note_backed_local_pdf or derived_access_summary or pdf_exists_and_missing_status'`
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - `cd frontend && npm run e2e:backend`
  - direct-screen real-smoke capture:
    - `output/playwright/real-paper-qa/meeting-pack-real-workbench-post-fallback-fix-final.png`

## 7.11) Recent-First Reveal Checkpoint (2026-04-07)
- Screen/Flow: `/meeting-packs` index with a large saved-draft inventory
- Goal action: 사용자가 dozens of near-duplicate saved drafts가 쌓인 current runtime에서도 첫 화면에서 최근 draft를 빠르게 훑고, 필요할 때만 older drafts를 더 연다.
- Primary persona: recent meeting drafts를 반복적으로 다시 열어보는 연구자/운영자
- Current friction:
  - shared current runtime inventory가 `95+` saved drafts까지 커지면서, index가 technically searchable하지만 first screen에서는 revisitability보다 raw volume을 먼저 보여주고 있었다.
  - 특히 같은 title을 가진 browser-generated drafts가 여러 개 쌓이면, route가 “찾기 쉬운 saved lane”보다 “끝없는 artifact feed”처럼 느껴질 수 있었다.
- Quick decision:
  - search, trace filter, direct-open, and create flow는 그대로 둔다.
  - default index는 recent-first로 일부만 먼저 보여 주고, older drafts는 explicit `Show older drafts` reveal로 뒤로 보낸다.
  - 이렇게 하면 검색과 direct-open helper는 유지하면서 첫 화면의 choice load만 줄일 수 있다.
- BMAP:
  - Motivation: 높음. meeting pack은 다시 열어보는 lane이라 recent draft를 빨리 훑는 게 중요하다.
  - Ability: improves when the route shows a skimmable recent subset first instead of dumping every saved pack at once.
  - Prompt: `Show older drafts` is a cleaner prompt than forcing the user to visually triage dozens of similar cards immediately.
- B.I.A.S:
  - Block: 너무 많은 same-weight saved cards가 first read를 막았다.
  - Interpret: 사용자는 “이 lane은 saved draft를 찾는 곳”보다 “저장물이 너무 많은 곳”으로 해석할 수 있었다.
  - Act: recent-first reveal keeps the first action on recent drafts, while still allowing full history access.
  - Store: the lane should now feel more like a controllable library than a growing feed.
- Peak-End:
  - Peak는 최근 draft만 먼저 보이고 older drafts가 명시적 reveal 아래로 밀린 순간이다.
  - Pit는 95+ drafts가 한 화면 flow에 같은 무게로 놓여 있던 상태였다.
  - Transition은 recent scan -> optional older reveal -> direct-open/detail review다.
  - End는 “필요하면 더 열 수 있지만, 처음엔 덜 과하다”는 느낌이다.
- Ethics:
  - Regret: 통과. older drafts를 숨기는 것이 아니라 optional reveal로 미뤄 cognitive load만 줄인다.
  - Black Mirror: 통과. engagement를 늘리기 위한 withholding이 아니라 scanability 보호다.
  - In Real-Life: 실제 saved library는 최근 것부터 보고, 오래된 것은 필요할 때 펼치는 편이 더 자연스럽다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime `/ui/meeting-packs` direct check after restart confirms:
    - `rows = 24`
    - `Showing 24 of 99 saved packs. Recent drafts stay visible first so this list stays skimmable.`
    - `Show 24 older drafts`

## 7.12) Duplicate-Title Secondary Identity Checkpoint (2026-04-07)
- Screen/Flow: `/meeting-packs` index cards when many browser-generated drafts share the same title
- Goal action: 사용자가 repeated draft titles를 보더라도 each card의 saved moment와 source context를 title 바로 근처에서 구분한다.
- Primary persona: 같은 paper에서 generated drafts를 여러 번 만들고, 가장 최근/적절한 saved draft를 다시 열어보는 연구자/운영자
- Current friction:
  - recent-first reveal로 first-screen volume은 줄었지만, 첫 24개 안에도 `Browser generated meeting draft`처럼 같은 title이 반복되면 title line alone으로는 빠른 재식별이 어려웠다.
  - created time은 카드 아래쪽 metadata에 있었기 때문에 title cluster를 빠르게 훑을 때는 늦게 보였다.
- Quick decision:
  - route behavior, reveal model, search, and filters는 그대로 둔다.
  - card title 바로 아래에 `Saved <timestamp>` identity line을 올리고, lower metadata는 `Slides / Sources`만 남겨 중복을 줄인다.
  - full pack id는 action row에 계속 남겨 exact ref 확인도 유지한다.
- BMAP:
  - Motivation: 높음. meeting-pack revisit은 같은 title draft 중 하나를 빠르게 재식별해야 하는 작업이 자주 생긴다.
  - Ability: improves when the card tells the user when this draft was saved before they have to parse the lower metadata block.
  - Prompt: `Saved 4/7/2026, 12:25:51 PM` becomes the immediate differentiator when titles repeat.
- B.I.A.S:
  - Block: repeated titles reduced the usefulness of the top card line.
  - Interpret: users could see the route as “many similar cards” instead of “recent saved drafts I can distinguish quickly.”
  - Act: the saved-time identity line restores fast scanability without requiring a filter first.
  - Store: the lane should feel more like a revisit library and less like a stack of near-duplicates.
- Peak-End:
  - Peak는 repeated title 바로 아래에서 saved timestamp를 즉시 읽는 순간이다.
  - Pit는 important differentiator가 card 아래쪽에 늦게 있었던 상태였다.
  - Transition은 title -> saved time -> badges/source -> open pack이다.
  - End는 duplicate-title drafts도 더 빨리 구분되는 느낌이다.
- Ethics:
  - Regret: 통과. hidden ranking trick 없이 existing metadata를 더 빨리 보이게만 했다.
  - Black Mirror: 통과. 더 많은 클릭을 유도하는 패턴이 아니라 scan friction reduction이다.
  - In Real-Life: 같은 이름의 저장물이 많아질 때는 “언제 저장됐는지”를 먼저 보여주는 편이 자연스럽다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime `/ui/meeting-packs` direct check confirms first card includes:
    - title `Browser generated meeting draft`
    - identity line `Saved 4/7/2026, 12:25:51 PM`
    - `Show 24 older drafts`

## 7.13) Active-Filter Reveal Semantics Checkpoint (2026-04-07)
- Screen/Flow: `/meeting-packs` index with active search or trace filters applied
- Goal action: 사용자가 search/trace filters를 켠 뒤에도 지금 보고 있는 list가 전체 library가 아니라 “matching saved drafts”라는 점을 summary와 reveal copy만 보고 바로 이해한다.
- Primary persona: repeated browser-generated drafts를 search/filter로 좁힌 뒤, matching subset 안에서 다시 적절한 saved draft를 고르는 연구자/운영자
- Current friction:
  - recent-first reveal과 duplicate-title identity는 좋아졌지만, active filters가 켜져 있어도 summary와 hidden-draft card는 여전히 generic `saved packs` language에 더 가까웠다.
  - 특히 `Browser generated meeting draft` search처럼 100+ matching results가 있는 상태에서는, 사용자가 filtered subset을 보고 있다는 사실이 card volume보다 덜 선명하게 읽힐 수 있었다.
- Quick decision:
  - filtering behavior, reveal model, and card layout은 그대로 둔다.
  - active filter state일 때 summary, hidden-draft card, and reveal CTA를 `matching saved packs` / `older matching drafts` language로 바꿔, current subset semantics만 더 명확히 한다.
  - filtered state copy는 regression test id로 고정한다.
- BMAP:
  - Motivation: 높음. meeting-pack revisit은 “지금 조건에 맞는 draft만 보고 있다”는 확신이 있어야 빠르게 고를 수 있다.
  - Ability: improves when the route says filtered-state semantics explicitly instead of making users infer that from the search box alone.
  - Prompt: `Showing 24 of 105 matching saved packs` and `Show 24 older matching drafts` become clearer prompts for what is hidden and why.
- B.I.A.S:
  - Block: generic copy made filtered subsets sound too much like the whole saved library.
  - Interpret: users could still read the lane as “all saved packs, somehow narrowed” instead of a deliberate matching subset.
  - Act: explicit matching-language helps users decide whether to refine filters further or reveal older matches.
  - Store: the lane should feel more like a controllable saved-draft library and less like a raw dump with a search box.
- Peak-End:
  - Peak는 filtered `/meeting-packs`에서 `matching saved packs`와 `older matching drafts`가 같이 읽히는 순간이다.
  - Pit는 active filters가 켜져 있어도 summary copy가 너무 generic했던 상태였다.
  - Transition은 filter -> recent matching subset -> optional older matching reveal이다.
  - End는 reveal affordance가 “전체 list expand”가 아니라 “older matches 보기”로 더 정확히 읽히는 느낌이다.
- Ethics:
  - Regret: 통과. filtering behavior를 숨기거나 ranking을 조작하지 않고, 현재 state를 더 정확히 설명하기만 한다.
  - Black Mirror: 통과. click 유도보다 comprehension을 높이는 copy correction이다.
  - In Real-Life: filtered library는 현재 subset semantics가 분명할수록 다시 찾기가 쉬워진다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime `/ui/meeting-packs` direct checks confirm:
    - search `Browser generated meeting draft` => `Showing 24 of 105 matching saved packs`
    - reveal CTA `Show 24 older matching drafts`
    - `With trace` active state keeps the same matching-language contract

## 7.14) Save-Day Grouping Checkpoint (2026-04-08)
- Screen/Flow: `/meeting-packs` index with large repeated-title inventories
- Goal action: 사용자가 같은 title의 meeting drafts가 많이 쌓여도 “어느 날 생성된 묶음인가”를 먼저 보고 recent revisit를 더 빨리 시작한다.
- Primary persona: browser-generated meeting drafts를 여러 세션에 걸쳐 반복 생성하고, 가장 최근 또는 특정 날짜의 saved draft를 다시 여는 연구자/운영자
- Current friction:
  - recent-first reveal과 `Saved <timestamp>` identity는 이미 도움이 되었지만, inventory가 `119 / 113 browser-generated`까지 커지면서 visible 24개 안에서도 timestamps만으로는 scan path가 여전히 길어질 수 있었다.
  - 특히 같은 날 생성된 drafts가 연속으로 쌓이면 사용자는 card-by-card로 시간을 읽어야 했다.
- Quick decision:
  - ranking, reveal model, and card actions는 그대로 둔다.
  - visible subset만 local save-day 기준으로 group section으로 묶고, each group header에서 day label과 draft count를 먼저 보여 준다.
  - filtered state에서는 같은 group header가 `matching drafts` count를 말해 주도록 한다.
- BMAP:
  - Motivation: 높음. revisit lane에서는 “어느 날의 draft 묶음인가”가 가장 빠른 orientation signal이 된다.
  - Ability: improves when the route compresses many near-duplicate cards into a few day-level chunks before users scan timestamps.
  - Prompt: day headers like `Wed, April 8, 2026 · 10 drafts` become the first scanning prompt, then `Saved <time>` handles within-day differentiation.
- B.I.A.S:
  - Block: repeated timestamps still forced card-by-card scanning.
  - Interpret: users could still experience the lane as a long stack of similar cards even after reveal and subtitle cleanup.
  - Act: day grouping creates a faster top-level choice before exact card selection.
  - Store: the route should feel more like a revisit library organized by sessions, not just a flat artifact list.
- Peak-End:
  - Peak는 current runtime first screen이 `2026-04-08` and `2026-04-07` day groups로 immediately split되는 순간이다.
  - Pit는 previously every card had to carry its own orientation burden.
  - Transition은 day group -> card timestamp -> open pack이다.
  - End는 repeated meeting drafts가 훨씬 calmer하게 읽히는 느낌이다.
- Ethics:
  - Regret: 통과. older drafts를 숨기지 않고, current visible subset만 더 이해하기 쉽게 묶는다.
  - Black Mirror: 통과. engagement trick이 아니라 revisit friction reduction이다.
  - In Real-Life: saved libraries가 커질수록 day/session grouping은 자연스럽고 친숙한 정리 방식이다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime `/ui/meeting-packs` direct checks confirm:
    - default first screen groups: `2026-04-08`, `2026-04-07`
    - filtered `Browser generated meeting draft` state keeps the same day grouping
    - filtered group counts read as `10 matching drafts`, `14 matching drafts`

## 7.15) Within-Day Exact Identity Checkpoint (2026-04-08)
- Screen/Flow: `/meeting-packs` index cards inside a same-day grouped section
- Goal action: 사용자가 같은 날 같은 title의 drafts가 여러 개 있을 때도 card-by-card exact selection을 빠르게 한다.
- Primary persona: one day/session 안에서 browser-generated meeting drafts를 여러 번 만들고, 그중 정확한 saved draft 하나를 다시 여는 연구자/운영자
- Current friction:
  - save-day grouping으로 top-level orientation은 좋아졌지만, `2026-04-08`처럼 one day bucket 안에 10개 이상의 repeated drafts가 있으면 기존 `Saved <date+time>` line은 date 중복이 많고 exact differentiation은 여전히 약했다.
  - 실제 current runtime에서도 `10:17:29 PM`처럼 같은 second가 반복되는 pairs가 있었다.
- Quick decision:
  - day grouping은 유지한다.
  - card identity line은 full date-time 대신 precise local save time with fractional seconds로 바꿔, within-day exact selection에 집중시킨다.
  - date responsibility는 group header가 맡고, card subtitle은 exact time responsibility만 갖게 한다.
- BMAP:
  - Motivation: 높음. 같은 day bucket 안에서 정확한 draft를 다시 고르는 게 revisit lane의 마지막 마찰이다.
  - Ability: improves when users no longer have to re-read the day on every card and can focus on exact save time.
  - Prompt: `Saved 10:27:58.145 PM` becomes the immediate within-day differentiator.
- B.I.A.S:
  - Block: within-day duplicates still required card-by-card timestamp comparison.
  - Interpret: users could still feel that grouped cards were “better, but still a little too similar.”
  - Act: precise time identity adds one more layer of disambiguation without changing order or grouping.
  - Store: the lane should feel more precise and less ambiguous during rapid revisit.
- Peak-End:
  - Peak는 grouped section 안에서 `Saved 10:27:58.145 PM`처럼 exact time이 immediately 보이는 순간이다.
  - Pit는 previous subtitle이 group header와 date responsibility를 중복하고 있었던 상태다.
  - Transition은 day group -> exact time -> open pack이다.
  - End는 same-day duplicates도 더 confidently 고를 수 있다는 느낌이다.
- Ethics:
  - Regret: 통과. extra metadata를 숨기지 않고 already available created time을 더 useful하게 재배치했다.
  - Black Mirror: 통과. click trick이 아니라 selection friction reduction이다.
  - In Real-Life: save-day grouping 뒤에는 exact save time이 natural next differentiator다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime `/ui/meeting-packs` direct checks confirm first grouped cards read like:
    - `Saved 10:27:58.145 PM`
    - `Saved 10:27:57.763 PM`
    - `Saved 10:17:29.650 PM`

## 7.16) Source-Aware Generated Title Hygiene Checkpoint (2026-04-08)
- Screen/Flow: `/meeting-packs` index and detail when saved drafts keep the generic browser-generated title
- Goal action: 사용자가 `Browser generated meeting draft` 같은 generic saved title 대신 source-aware title을 먼저 보고, current draft가 어떤 paper-driven draft인지 더 빨리 식별한다.
- Primary persona: 같은 paper에서 journal-club meeting drafts를 여러 번 만들고, saved library에서 다시 적절한 draft를 여는 연구자/운영자
- Current friction:
  - recent-first reveal, day grouping, and precise-time identity로 list-shell scanability는 좋아졌지만, current runtime inventory가 `127 / 121 browser-generated`까지 늘어나면서 generic title 자체가 다시 top-line clarity를 약하게 만들고 있었다.
  - current cards already exposed `Primary source:` lower in the card, but that source cue arrived too late to replace a weak generic title.
- Quick decision:
  - stored `title` value와 backend contract는 그대로 둔다.
  - only the UI display title changes: when the saved title is the generic browser-generated placeholder and a primary source title exists, the list card and detail header display the primary source title instead.
  - when the source-aware display title already equals the primary source title, the lower `Primary source:` line is removed to avoid duplicate wording.
- BMAP:
  - Motivation: 높음. revisit lane에서는 “어느 source-driven draft인가”가 title level에서 바로 보여야 한다.
  - Ability: improves when users can identify the paper-driven draft from the top card line rather than waiting for lower metadata.
  - Prompt: a source-aware title like `Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation` becomes a much stronger first prompt than `Browser generated meeting draft`.
- B.I.A.S:
  - Block: generic generated titles weakened the top line of the card even after list-shell cleanup.
  - Interpret: users could still read the lane as a pile of machine-produced drafts instead of a library of source-backed meeting artifacts.
  - Act: source-aware display titles make the top line carry the same paper cue users already rely on downstream.
  - Store: the lane should feel more like a paper-driven artifact library and less like a generic generation log.
- Peak-End:
  - Peak는 current runtime filtered list 첫 카드가 `Browser generated meeting draft` 대신 source title로 immediately 읽히는 순간이다.
  - Pit는 source cue가 lower `Primary source:` metadata에 늦게 숨어 있던 상태였다.
  - Transition은 day group -> source-aware title -> precise save time -> open pack이다.
  - End는 repeated browser-generated drafts도 더 paper-centric하게 읽힌다는 느낌이다.
- Ethics:
  - Regret: 통과. stored contract를 숨기거나 rewrite하지 않고 user-facing display only를 개선했다.
  - Black Mirror: 통과. click 유도가 아니라 generic machine naming을 human-meaningful source naming으로 치환한 것이다.
  - In Real-Life: saved artifact library는 생성 방식보다 upstream source가 먼저 읽히는 편이 자연스럽다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime `/ui/meeting-packs` direct checks confirm:
    - search `Browser generated meeting draft` still matches the same saved drafts
    - first visible title now renders the primary source title instead of the raw generic title
    - detail route banner heading also renders the source-aware title after load

## 7.17) Generated-Title Placeholder Normalization Checkpoint (2026-04-08)
- Screen/Flow: `/meeting-packs` create flow when the request carries the generic browser-generated placeholder title
- Goal action: 사용자가 generic browser-generated placeholder를 제출해도 새 saved draft가 다시 generic title로 저장되지 않고, source-aware title로 바로 정규화된다.
- Primary persona: browser automation이나 quick manual flow로 meeting draft를 반복 생성하지만, saved library는 계속 source-aware artifact names로 유지하고 싶은 연구자/운영자
- Current friction:
  - source-aware display title hygiene로 existing library read path는 좋아졌지만, upstream generate contract는 여전히 `Browser generated meeting draft`를 raw saved title로 받아들일 수 있었다.
  - 그 상태면 old data는 보기 좋아져도 새 drafts는 계속 generic title로 저장될 수 있었다.
- Quick decision:
  - custom titles are still respected.
  - but the exact placeholder `Browser generated meeting draft` is treated as a non-meaningful placeholder, not a true custom title.
  - backend generation and mock generation both normalize that placeholder to the selected source title before saving the pack and its saved generation request.
- BMAP:
  - Motivation: 높음. saved library quality는 read-path만이 아니라 new artifact naming policy까지 같이 지켜져야 한다.
  - Ability: improves when newly created drafts no longer add more generic entries into the library.
  - Prompt: source title becomes the default prompt for future revisit, rather than a generic machine label.
- B.I.A.S:
  - Block: upstream create path could still create more generic saved titles.
  - Interpret: users could feel the lane was improving visually but still accumulating low-signal saved names underneath.
  - Act: normalize the placeholder at generation time instead of treating it as a real custom title.
  - Store: the lane should now preserve its paper-first naming hygiene as new drafts are created.
- Peak-End:
  - Peak는 live `POST /meeting-packs/generate` with the generic placeholder returning the source title in both `pack.title` and `generation_request.title`인 순간이다.
  - Pit는 UI read path는 좋아졌는데 upstream create path는 still generic title을 허용하던 상태였다.
  - Transition은 display-title cleanup에서 create-time title policy cleanup으로 이어진 점이다.
  - End는 old library뿐 아니라 new library growth도 더 차분해졌다는 느낌이다.
- Ethics:
  - Regret: 통과. meaningful custom titles는 유지하고, placeholder-like generic title only를 normalize한다.
  - Black Mirror: 통과. user intent를 빼앗는 rename이 아니라 low-signal placeholder를 source-aware default로 치환한다.
  - In Real-Life: saved artifact systems는 obviously generic placeholder를 계속 저장하는 것보다 source-aware naming으로 접어주는 편이 더 자연스럽다.
- Verification:
  - `pytest -q tests/test_meeting_pack_service.py -k generic_browser_title`
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime direct checks confirm:
    - `POST /meeting-packs/generate` with `title="Browser generated meeting draft"` returns the source title in both `pack.title` and `generation_request.title`
    - `/ui/meeting-packs` still shows the same filtered subset but newly created placeholder-driven packs no longer add new generic saved names

## 7.18) Same-Title Day Subgrouping Checkpoint (2026-04-09)
- Screen/Flow: `/meeting-packs` index first-screen scan inside a single save-day bucket with repeated source-aware titles
- Goal action: 사용자가 같은 날 같은 source title로 저장된 drafts가 많이 쌓여도, 먼저 title cluster를 고른 뒤 exact save time으로 개별 draft를 빠르게 고른다.
- Primary persona: 같은 paper/source로 meeting draft를 여러 번 생성하고, saved library에서 가장 최근 또는 특정 exact draft를 다시 여는 연구자/운영자
- Current friction:
  - day grouping, precise-time identity, and source-aware display title까지 들어간 뒤에도 current runtime first screen의 visible 24 drafts가 사실상 같은 source-aware title 한 묶음으로 보였다.
  - 그 상태에서는 day header는 helpful했지만, row마다 같은 title이 반복되어 card-by-card scan cost가 다시 올라갔다.
- Quick decision:
  - current reveal/filter/detail model은 유지한다.
  - same-day visible drafts는 display title 기준으로 한 번 더 subgrouping한다.
  - title subgroup header가 shared title과 draft count를 맡고, subgroup 안의 rows는 time-first identity와 actions에 집중시킨다.
- BMAP:
  - Motivation: 높음. large saved library에서 revisit lane은 “어느 day인가?” 다음 바로 “어느 repeated title cluster인가?”를 빠르게 알아야 한다.
  - Ability: improves when users stop rereading the same source-aware title on every row and instead scan exact save times within a shared cluster.
  - Prompt: the subgroup header becomes the shared title prompt, and `Saved 11:52:35.652 PM` becomes the exact-card prompt.
- B.I.A.S:
  - Block: same-title rows inside one save-day bucket still behaved like a flat repeated stack.
  - Interpret: users could feel that the route had become cleaner overall, but still too repetitive in the most active current session.
  - Act: subgroup repeated rows by shared display title while keeping the most recent title cluster first.
  - Store: the route should feel more like a session-organized saved library and less like a long feed of near-identical cards.
- Peak-End:
  - Peak는 current runtime first screen이 `2026-04-08` day group 안에서 shared source title `24 drafts` subgroup으로 먼저 읽히는 순간이다.
  - Pit는 같은 title이 row마다 반복돼 top-level distinction이 약했던 상태였다.
  - Transition은 day group -> title subgroup -> exact time -> open pack이다.
  - End는 same-source/day density가 훨씬 calmer하게 읽힌다는 느낌이다.
- Ethics:
  - Regret: 통과. hide/reorder trick 없이 existing visible drafts를 더 honest하게 조직했다.
  - Black Mirror: 통과. extra clicks를 강제하는 collapse가 아니라 repeated information을 subgroup header로 승격했다.
  - In Real-Life: session-heavy saved libraries에서는 shared title cluster와 exact save time을 분리해서 보여주는 편이 자연스럽다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - current runtime `/ui/meeting-packs` direct checks confirm:
    - summary reads `Showing 24 of 162 saved packs. Recent drafts stay visible first so this list stays skimmable.`
    - first day group is `2026-04-09` and its first title subgroup reads `2 drafts`
    - the next day group is `2026-04-08` and its first title subgroup reads `22 drafts`
    - both grouped sections share the source-aware title `Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation`
    - grouped rows beneath those subheaders continue to read by exact save time, e.g. `Saved 9:52:43.867 PM` and `Saved 11:52:35.652 PM`

## 7.19) Historical Generic-Title Backfill Checkpoint (2026-04-09)
- Screen/Flow: saved `meeting_pack.json` bundles that still persist the legacy placeholder title `Browser generated meeting draft`
- Goal action: 기존 historical meeting packs도 future cleanup path가 생겨, current UI hygiene와 future saved-library naming policy가 서로 어긋나지 않게 한다.
- Primary persona: 오랫동안 browser-generated meeting drafts를 많이 저장해 왔고, old saved inventory도 source-aware naming으로 정리하고 싶은 연구자/운영자
- Current friction:
  - UI display title hygiene, day grouping, title subgrouping, and create-time normalization은 이미 들어갔지만, historical storage에는 still `Browser generated meeting draft`가 남아 있었다.
  - current runtime dry-run 기준 candidate가 `149`개라, 지금 UX는 좋아도 stored library와 saved generation requests는 still generic placeholder를 품고 있었다.
- Quick decision:
  - live storage를 바로 mutate하지는 않는다.
  - 대신 service owner에 bundle-safe backfill helper를 추가하고, markdown + handoff artifacts까지 같이 rerender하는 maintenance path를 만든다.
  - bounded script는 dry-run default로 두고, explicit `--apply`일 때만 in-place normalization을 한다.
- BMAP:
  - Motivation: 높음. saved library quality는 앞으로 쌓이는 drafts뿐 아니라 already stored historical drafts에도 eventually 적용돼야 한다.
  - Ability: improves when the cleanup path can update title, request title, markdown heading, and handoff artifacts together instead of leaving partial drift.
  - Prompt: dry-run output itself becomes the operator prompt by saying exactly how many historical bundles are eligible.
- B.I.A.S:
  - Block: historical stored bundles still kept the legacy generic placeholder.
  - Interpret: users could feel that the lane had become cleaner in the UI but was still carrying a large generic archive underneath.
  - Act: add a bounded maintenance path instead of mutating live data ad hoc.
  - Store: the lane should now feel governable, not just cosmetically improved.
- Peak-End:
  - Peak는 dry-run summary가 `candidate_count: 149`, `updated_count: 0`, `dry_run: true`로 current impact를 선명하게 보여준 순간이다.
  - Pit는 generic historical titles가 UI cleanup 뒤에도 storage에 그대로 남아 있던 상태였다.
  - Transition은 display hygiene -> create-time normalization -> storage-safe maintenance path다.
  - End는 live data를 바로 건드리지 않고도 cleanup readiness가 생긴 상태다.
- Ethics:
  - Regret: 통과. live saved artifacts를 implicit rewrite하지 않았다.
  - Black Mirror: 통과. maintenance path는 explicit apply opt-in이고 dry-run이 기본이다.
  - In Real-Life: historical cleanup은 actual user data rewrite를 포함할 수 있으니 dry-run first가 맞다.
- Verification:
  - `pytest -q tests/test_meeting_pack_service.py -k "backfill_meeting_pack_titles or generic_browser_title"`
  - `./.venv/bin/python scripts/backfill_meeting_pack_titles.py`
  - dry-run summary confirms:
    - `candidate_count: 149`
    - `updated_count: 0`
    - `dry_run: true`
    - first candidate rewrites `Browser generated meeting draft` to `Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation`

## 7.20) Historical Generic-Title Backfill Apply Checkpoint (2026-04-09)
- Screen/Flow: live stored meeting-pack bundles after explicit backfill apply
- Goal action: historical saved meeting packs stop exposing the legacy generic title in storage, API summaries, and the current meeting-pack library view.
- Primary persona: 기존 meeting-pack archive를 실제 usable saved library로 유지하고 싶은 연구자/운영자
- Current friction:
  - dry-run scope was clear, but the stored archive still had `149` generic-title packs until an explicit apply happened.
  - UI display hygiene alone could hide that problem, but API list items and stored markdown/request snapshots would still lag behind.
- Quick decision:
  - execute the bounded maintenance path explicitly with `--apply`.
  - immediately rerun dry-run and runtime checks to confirm the archive is now actually normalized.
- BMAP:
  - Motivation: 높음. old saved artifacts should not remain the one place where generic naming survives.
  - Ability: improves when API, markdown, request snapshot, and UI all tell the same source-aware naming story.
  - Prompt: after apply, the library title itself remains the strongest first prompt instead of relying on UI-only translation.
- B.I.A.S:
  - Block: historical storage drift between display title and persisted raw title.
  - Interpret: users could still feel that the archive was more machine-generated than source-backed if they inspected API/storage-derived surfaces.
  - Act: apply the bundle-safe backfill and rerender the deterministic artifacts.
  - Store: the lane should now feel coherent across storage, API, and UI.
- Peak-End:
  - Peak는 apply summary가 `updated_count: 149`로 끝나고, immediately after dry-run이 `candidate_count: 0`으로 떨어진 순간이다.
  - Pit는 storage에 generic placeholder가 많이 남아 있던 상태였다.
  - Transition은 maintenance path creation에서 explicit archive cleanup execution으로 넘어간 점이다.
  - End는 current runtime `/meeting-packs`에서도 generic title이 보이지 않는다는 점이다.
- Ethics:
  - Regret: 통과. live rewrite는 explicit user instruction 이후에만 실행했다.
  - Black Mirror: 통과. UI만 속이는 정리가 아니라 stored bundle, markdown, and request snapshot까지 같이 정리했다.
  - In Real-Life: historical cleanup은 explicit apply와 post-apply verification이 같이 있어야 안전하다.
- Verification:
  - `./.venv/bin/python scripts/backfill_meeting_pack_titles.py --apply`
  - `./.venv/bin/python scripts/backfill_meeting_pack_titles.py`
  - `curl -s http://127.0.0.1:8000/health`
  - `GET /api/meeting-packs` post-apply direct check
  - current runtime `/ui/meeting-packs` direct check
  - post-apply observations:
    - apply summary: `candidate_count: 149`, `updated_count: 149`, `dry_run: false`
  - post-apply dry-run: `candidate_count: 0`
  - `/api/meeting-packs`: `generic_titles: 0`
  - `/ui/meeting-packs`: first visible subgroup title is `Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation`
  - current runtime body no longer contains `Browser generated meeting draft`

## 7.21) Maintenance Disclosure Checkpoint (2026-04-13)
- Screen/Flow: `/meeting-packs/:packId` detail right rail after the note-handoff card
- Goal action: 사용자가 saved draft detail에서 canonical note review를 먼저 읽고, regenerate/rerender는 필요할 때만 여는 maintenance step으로 이해한다.
- Primary persona: meeting-ready draft를 열었을 때 먼저 upstream note evidence를 다시 보고, 그 다음에만 saved draft maintenance를 하려는 연구자/운영자
- Current friction:
  - `Continue from this draft` card는 이미 있었지만, 바로 아래 validation card 안에서 `Regenerate draft`와 `Rerender markdown`가 항상 펼쳐져 있어 first scan이 note-first review보다 toolset-first로 읽힐 수 있었다.
  - 두 action은 artifact maintenance인데, 시각적으로는 same-priority next step처럼 보였다.
- Quick decision:
  - route, trace, and validation contract는 그대로 둔다.
  - note-handoff card 안에 `Recommended order`만 추가해 note review -> draft maintenance 순서를 짧게 고정한다.
  - validation card 안의 action block은 `Draft maintenance` disclosure로 내려 first scan noise를 줄인다.
- BMAP:
  - Motivation: 높음. saved draft를 열었을 때 연구자는 먼저 source-backed note review가 가능한지 확인해야 한다.
  - Ability: improves when the default rail shows note-first guidance and keeps maintenance controls one click behind a clearly named disclosure.
  - Prompt: `Recommended order`와 `Draft maintenance` summary가 각각 upstream review와 downstream maintenance를 구분하는 prompt가 된다.
- B.I.A.S:
  - Block: open action buttons can read like the primary next step even when they should be secondary.
  - Interpret: the route should feel like a source-grounded review surface, not a maintenance console.
  - Act: lower low-frequency maintenance behind a disclosure while keeping validation state visible.
  - Store: users should remember this lane as “re-open note first, then refresh the draft if needed.”
- Peak-End:
  - Peak는 `Continue from this draft` 바로 아래에서 `Recommended order`가 note-first sequence를 짧게 말해 주는 순간이다.
  - Pit는 maintenance buttons가 펼쳐진 상태로 same-priority action처럼 읽히던 점이다.
  - Transition은 note handoff -> validation snapshot -> explicit maintenance disclosure다.
  - End는 regenerate/rerender가 task order를 흐리지 않으면서도 여전히 가까이에 있다는 점이다.
- Ethics:
  - Regret: 통과. 사용자를 막지 않고, 더 위험한 maintenance action에만 작은 friction을 추가했다.
  - Black Mirror: 통과. hidden upsell이나 dark pattern이 아니라 task hierarchy correction이다.
  - In Real-Life: 실제로도 evidence를 다시 보고 난 뒤 draft maintenance를 여는 흐름이 더 자연스럽다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack detail layout|mobile.*meeting pack detail layout" --update-snapshots`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "meeting pack detail layout|mobile.*meeting pack detail layout"`

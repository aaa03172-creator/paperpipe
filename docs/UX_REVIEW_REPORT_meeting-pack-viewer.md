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

## 7.9) Fallback Readiness Honesty Checkpoint (2026-04-08)
- Screen/Flow: `/meeting-packs/:packId` auto-fallback draft detail when backend generate succeeds only via mock fallback
- Goal action: 사용자가 backend-unavailable fallback draft를 열었을 때 placeholder bundle을 discussion-ready evidence로 오해하지 않는다.
- Primary persona: live backend outage 중에도 draft shell을 검토하려는 운영자
- Current friction:
  - fallback-created draft는 action gating과 warning copy는 정직했지만, main readiness badge는 `evidence_backed`처럼 보여 operator trust boundary를 흐릴 수 있었다.
  - 이 route에서 readiness badge는 가장 먼저 읽히는 신호 중 하나라, placeholder content라도 optimistic badge면 downstream reuse를 과대 유도한다.
- Quick decision:
  - runtime route shell은 유지한다.
  - fallback-created mock draft의 readiness만 `background_only`로 낮추고, browser fallback rail에서 그 badge를 직접 고정한다.
- BMAP:
  - Motivation: 높음. outage 상황일수록 operator는 badge-level shorthand에 더 의존한다.
  - Ability: 높음. owner는 mock draft factory 하나와 existing fallback browser rail 하나로 좁다.
  - Prompt: `background_only` badge가 fallback warning copy와 함께 가장 빠른 truth signal이 된다.
- B.I.A.S:
  - Block: fallback warning은 읽어야 알 수 있었지만, readiness badge는 더 눈에 띄는 긍정 신호였다.
  - Interpret: badge를 낮추면 draft가 placeholder shell이라는 해석이 즉시 맞춰진다.
  - Act: operator는 regenerate/reuse보다 backend 복구와 upstream note 확인을 먼저 떠올리게 된다.
  - Store: `background_only`는 “fallback shell은 live evidence가 아님”이라는 습관을 강화한다.
- Peak-End:
  - Peak는 fallback draft 진입 직후 badge와 disabled actions가 같은 메시지를 내는 순간이다.
  - Pit는 read-only fallback인데도 discussion-ready처럼 읽히던 이전 optimism이다.
  - Transition은 create fallback success notice -> detail view trust boundary 정렬이다.
  - End는 operator가 “이건 shell만 열렸고 evidence는 아직 아니다”를 기억하고 나가는 상태다.
- Ethics:
  - Regret: 통과. placeholder content를 과장하지 않는다.
  - Black Mirror: 통과. outage resilience를 fake confidence로 포장하지 않는다.
  - In Real-Life: 통과. 실제 운영자도 장애 중엔 “작동하는 모양”보다 “얼마나 믿어도 되는지”가 더 중요하다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.meeting-pack.fallback.config.ts e2e/meeting-pack.fallback.spec.ts -g "meeting pack create auto-fallback keeps the generated draft reachable when the backend is unavailable"`

## 7.10) Index 5xx Honesty Checkpoint (2026-04-08)
- Screen/Flow: `/meeting-packs` saved-pack index when the backend list route returns a real server error
- Goal action: 사용자가 saved-pack index가 실제로 깨졌을 때 mock library를 진짜 데이터처럼 오해하지 않는다.
- Primary persona: 저장된 meeting-pack draft를 다시 열려는 운영자
- Current friction:
  - index는 `4xx`는 잘 surface했지만, `500` 같은 server-side failure는 여전히 generic mock library로 덮을 수 있었다.
  - 이 경우 사용자는 실제 saved-pack storage/runtime가 깨졌다는 사실 대신 plausible mock drafts를 보게 된다.
- Quick decision:
  - create fallback resilience는 유지한다.
  - saved-pack index는 real HTTP error를 mock success로 덮지 않고 그대로 보여준다.
- BMAP:
  - Motivation: 높음. saved-pack reopen flow에서 operator는 list truth를 가장 먼저 믿는다.
  - Ability: 높음. owner는 index fetch path 하나와 existing fallback Playwright rail 하나로 충분하다.
  - Prompt: explicit `500` error가 mock library보다 훨씬 정확한 next-step signal이다.
- B.I.A.S:
  - Block: mock library는 시각적으로 정상처럼 보여 real failure를 가렸다.
  - Interpret: explicit server error는 “지금은 진짜 saved packs를 못 읽는다”로 즉시 해석된다.
  - Act: operator는 retry/repair로 움직이고, mock drafts를 진짜 saved state로 오해하지 않는다.
  - Store: index error는 fallback demo가 아니라 runtime problem이라는 규칙이 강화된다.
- Peak-End:
  - Peak는 broken index에서도 진실한 error를 먼저 보게 된 순간이다.
  - Pit는 server crash가 mock success처럼 읽히던 이전 path다.
  - Transition은 saved-pack browser 진입 직후 truth boundary correction이다.
  - End는 operator가 현재 state를 정확히 이해하고 나가는 것이다.
- Ethics:
  - Regret: 통과. 장애를 정상처럼 포장하지 않는다.
  - Black Mirror: 통과. recovery path를 fake confidence 위에 쌓지 않는다.
  - In Real-Life: 통과. 실제 도구도 저장 목록이 깨지면 데모 데이터보다 오류를 먼저 보여줘야 한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.meeting-pack.fallback.config.ts e2e/meeting-pack.fallback.spec.ts -g "meeting pack index surfaces backend 400 instead of silently showing the mock library|meeting pack index surfaces backend 500 instead of silently showing the mock library"`

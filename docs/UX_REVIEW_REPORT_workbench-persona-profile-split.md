# UX Review Report - Workbench Persona/Profile Split

Status: Active
Date: 2026-03-17
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `AnalysisWorkbench` run controls (`/workbench/:paperId`)
- Goal action: configure and launch a Deep Read run with the correct reasoning lane and profile context
- Primary persona: research operator reviewing a paper and deciding how the next run should reason
- Current friction: one `Persona` selector conflates reasoning lane and profile context, so the UI teaches the wrong model
- Success metric: user can choose reasoning and context separately without guessing whether a profile is also an agent

## Quick Review (5 min)
- Block: current single dropdown packs unrelated concepts into one label, which raises interpretation cost before the primary CTA.
- Interpret: `Persona` is vague and no longer matches runtime behavior after the additive backend split.
- Act: users cannot confidently change reasoning without also feeling like they are changing lab/topic context.
- Store: after a run completes, the resulting configuration is not reflected as two distinct choices, so the mental model remains muddy.
- Ethics: this is confusion, not manipulation, but it still wastes operator attention.

## Full Review
### P0
- None. The flow is functional; the issue is conceptual friction rather than breakage.

### P1
- The current `Persona` selector in [AnalysisWorkbench.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/AnalysisWorkbench.tsx) collapses reasoning and context into a single choice, which directly conflicts with the documented runtime boundary.
- Because the selector mixes built-in reasoning lanes and YAML profiles, the operator cannot tell whether changing one value changes evidence standards, lab context, or both.
- Mobile controls inherit the same confusion, so the smallest screen receives the highest interpretation burden at the exact point of action.

### P2
- The current control cluster gives no hint that `default` is only a compatibility alias.
- The run request path does not make the reasoning/context split legible in UI state, so future output-mode work would land on top of a still-ambiguous base.

### Full Review Coverage
- 6P storyboard context:
  - Problem: the operator wants to run the paper through the right lens quickly.
  - Emotion: low tolerance for ambiguous controls because a wrong run wastes time and trust.
  - Action: open Workbench, inspect paper, configure run, click `Deep Read Run`.
  - Struggle: one overloaded selector forces the operator to decode internal implementation history.
  - Attempt: pick a label that sounds right and hope it maps to the intended behavior.
  - Happy Ending: choose reasoning and context independently, then launch with confidence.
- BMAP:
  - Motivation is already high because the operator wants a useful run.
  - Ability is the weak point because the control does not match the user’s mental model.
  - Prompt is acceptable because the CTA is clear, but the selector preceding it is ambiguous.
- B.I.A.S:
  - Block: overloaded dropdown increases cognitive filtering cost.
  - Interpret: the label `Persona` does not explain what actually changes.
  - Act: ambiguity creates hesitation before the primary CTA.
  - Store: the product fails to reinforce the new boundary after use.
- Peak-End:
  - Peak should remain the `Deep Read Run` action, not the configuration puzzle before it.
  - Pit is the moment the user opens the selector and sees mixed concepts.
  - Transition from paper inspection to run configuration should feel explicit and low-friction.
  - End should leave the user with a clean mental model for the next run.
- Ethics:
  - Regret: no dark pattern, but the current control burns operator time needlessly.
  - Black Mirror: low risk, though ambiguity could cause avoidable evidence mistakes in high-stakes review flows.
  - In Real-Life: the current control feels like an insider tool, not a considerate assistant.

## BMAP diagnosis
- Motivation: strong. The operator is already in a paper-specific workbench and wants the next run to be useful.
- Ability: weak. The single dropdown asks the user to understand internal taxonomy instead of making the choice obvious.
- Prompt: adequate. The CTA placement is fine, but the pre-CTA configuration needs clearer prompts.

## B.I.A.S diagnosis
- Block: mixed option families in one selector create avoidable scanning work.
- Interpret: `Persona` is semantically overloaded and no longer accurate.
- Act: the user has to translate “What kind of reasoning do I want?” into an implementation-specific dropdown.
- Store: current runs do not leave a memorable distinction between reasoning lane and profile overlay.

## Peak-End design notes
- Peak: keep the main peak on `Deep Read Run`, not on advanced configuration.
- Pit: remove the concept collision in the selector row.
- Transition: make the move from “inspect paper” to “configure run” feel structured with two explicit inputs.
- End: preserve the sense that the chosen configuration was deliberate and legible.

## Concrete changes
- Replace the single `Persona` selector with `Reasoning` and `Profile` selectors in desktop and mobile control groups.
- Use `Auto` as the lowest-friction reasoning default and `No profile` as the profile default.
- Keep backend compatibility by still deriving `persona_id`, but send `reasoning_persona` and `profile_id` explicitly.
- Rename frontend store fields away from `selectedPersonaId` so the codebase stops reinforcing the old model.
- Filter `/personas` into reasoning vs profile families in the UI instead of exposing the raw compatibility registry directly.

## Ethics check results
- Regret / Black Mirror / In Real-Life: Pass with minor caution
- Caution: do not overload the new selectors with extra explanatory copy that turns a simple configuration step into a lecture.

## Next PR-sized actions
- Split `AnalysisWorkbench` controls into `Reasoning` and `Profile` selectors with compatibility request mapping.
- Add lightweight visual verification for the updated control row in mock and backend workbench flows.
- After selector adoption, evaluate the first shared output/view mode surface separately instead of bundling it into this change.

## 7.1) Backend Workbench Shell Coverage Checkpoint (2026-03-24)
- Screen/Flow: `/workbench/:paperId` desktop + mobile shell layout
- Goal action: workbench header, rail, PDF shell, artifact column, and timeline hierarchy drift가 route-level screenshot에서 바로 보이게 한다.
- Primary persona: workbench shell drift를 visual regression으로 확인하는 maintainer
- Current friction:
  - workbench는 rail screenshot과 claim-highlight subregion coverage는 있었지만, shell 전체를 한 번에 보는 route-level baseline이 없었다.
  - 그래서 header/control row/column balance가 흔들려도 PDF highlight와 rail subregion만으로는 변화를 늦게 알아차릴 수 있었다.
- Quick decision:
  - runtime UI는 바꾸지 않는다.
  - existing rail + claim-highlight subregion coverage는 유지한다.
  - 기본 workbench shell을 interaction 없이 연 뒤 desktop/mobile viewport screenshot 2개를 추가한다.
  - timeline 시각값만 mask 처리해 locale/time noise를 줄인다.
- BMAP:
  - Motivation: 높음. workbench는 core reading/action surface라 shell drift를 조용히 허용하면 안 된다.
  - Ability: 기존 backend route와 PDF/rail readiness check가 있어 full-page contract를 좁게 추가할 수 있다.
  - Prompt: route-level shell screenshot 하나가 header/control/three-pane balance를 가장 직접적으로 고정한다.
- B.I.A.S:
  - Block: subregion-only coverage는 shell hierarchy drift를 바로 보여주지 못했다.
  - Interpret: full-page shell baseline이 current workbench contract를 더 직접적으로 설명한다.
  - Act: 이후 header/control/timeline density drift를 diff에서 더 빨리 판단할 수 있다.
  - Store: workbench도 triage, paper notes, viewer routes와 같은 backend visual discipline을 갖게 된다.
- Peak-End:
  - Peak는 desktop/mobile workbench shell이 current UI 기준선으로 추가된 순간이다.
  - Pit는 rail/PDF는 green인데 route shell 전체는 screenshot contract가 없던 상태였다.
  - Transition은 existing workbench open helper 분리 -> shell snapshot 추가 -> rerun green이다.
- Ethics:
  - Regret: 통과. runtime behavior를 바꾸지 않고 verification만 강화한다.
  - Black Mirror: 통과. PDF highlight subregion과 shell baseline을 함께 두어 UI polish를 과장하지 않는다.
  - In Real-Life: 통과. maintainers가 실제 workbench shell drift를 더 빠르게 검토할 수 있다.
- Verification:
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout"`

## 7.2) Parser Pilot Status Clarity Checkpoint (2026-03-24)
- Screen/Flow: `/workbench/:paperId` run controls and terminal log drawer during bounded parser-pilot runs
- Goal action: understand whether the workbench requested `docling` and whether the runtime actually resolved to `docling` or fell back to `fitz_pdfplumber`
- Primary persona: research operator running a bounded parser pilot behind the existing hidden query-param lane
- Current friction:
  - before this patch, the workbench could imply that a requested parser override definitely ran even when backend config silently resolved to the default backend
  - parser status also disappeared when switching papers inside the workbench rail, which made multi-paper pilot sessions easy to misread
  - stale terminal hydration could overwrite the just-enqueued parser pilot log line with a completed fixture run, which blurred the operator's current action
- Quick decision:
  - keep the parser pilot surface hidden and bounded to the existing query lane
  - make requested vs effective parser state explicit in existing workbench copy
  - preserve the current parser query only for workbench-internal paper switching
  - prove the real backend path with one seeded backend e2e fixture rather than widening the UI
- BMAP:
  - Motivation: high; a parser pilot is only useful if the operator can trust which backend actually ran.
  - Ability: previously weak because requested and effective parser state were conflated.
  - Prompt: the existing control row and terminal drawer are enough if the copy is explicit.
- B.I.A.S:
  - Block: silent fallback hid the true runtime decision.
  - Interpret: the operator could read a requested override as an effective backend.
  - Act: this creates the wrong follow-up decision about parser quality or pilot readiness.
  - Store: ambiguous status would teach the wrong mental model for every later pilot run.
- Peak-End:
  - Peak should stay on the run result, not on guessing the backend.
  - Pit was the silent ambiguity after enqueue or after opening a completed run.
  - Transition is now explicit: requested parser first, resolved parser when known.
  - End should leave a clean audit trail in both the control copy and terminal drawer.
- Ethics:
  - Regret: pass; the change removes ambiguity rather than nudging behavior.
  - Black Mirror: pass; no hidden upsell or coercive control, only runtime truthfulness.
  - In Real-Life: pass; operators should be able to trust what backend actually ran before interpreting parser output quality.
- Concrete changes:
  - preserve `?parser_backend=...` only during workbench rail navigation
  - treat the route query as pre-run seed state only; once a persisted job loads, rely on requested/effective backend metadata from the backend
  - show `Parser fitz_pdfplumber (requested docling)` when the backend resolves away from the requested parser
  - keep `Requested parser docling` for queued/requested-only states
  - refresh effective parser after completion only when the current workbench screen still owns that paper/job
  - append the parser-resolution line during initial terminal hydration so the real backend path is visible on first load, not only after stream updates
  - isolate backend parser e2e runs onto a dedicated runtime DB so cold-load verification does not inherit parser pilot metadata from a previous session
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "parser"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "requested and resolved parser backends separately|does not infer requested parser from route query when persisted job metadata is absent"`
  - `cd frontend && PAPERPIPE_E2E_ENABLE_PARSER_WORKER=1 npx playwright test -c playwright.backend.parser.config.ts e2e/backend.spec.ts -g "deep read run resolves parser fallback in the browser flow"`

## 7.3) Access Route Visibility Checkpoint (2026-03-28)
- Screen/Flow: shared `Rail` inside `/workbench/:paperId` plus workbench header context
- Goal action: operator가 현재 paper의 reachable full-text route를 workbench 안에서도 바로 읽는다.
- Primary persona: local-first workbench에서 evidence debugging을 하면서 현재 PDF reachability를 즉시 알고 싶은 연구자
- Current friction:
  - derived `access_summary`는 API와 triage에는 보이지만, workbench shared rail과 current-paper header context에서는 보이지 않았다.
  - operator는 rail에서 paper를 고르거나 workbench 안에 머물 때 local/OA/institution route를 다시 추정해야 했다.
- Quick decision:
  - shared `Rail`에는 compact badge만 추가한다.
  - workbench header에는 badge + optional route link만 추가한다.
  - runtime behavior, downloader flow, and action hierarchy는 그대로 둔다.
- BMAP:
  - Motivation: 높음. workbench는 long-stay surface라 현재 reading route가 더 직접적으로 보일수록 좋다.
  - Ability: shared access helper 하나로 rail/header 모두 같은 language를 쓸 수 있다.
  - Prompt: `Local PDF` / `Institution route` badge와 optional link가 가장 작은 prompt다.
- B.I.A.S:
  - Block: workbench current-paper context에 access signal이 없었다.
  - Interpret: rail과 header가 같은 access language를 쓰면 current paper state를 더 빨리 읽을 수 있다.
  - Act: operator가 workbench를 벗어나지 않고도 saved PDF route를 바로 열 수 있다.
  - Store: workbench가 triage와 같은 access-aware surface로 이어진다.
- Peak-End:
  - Peak는 header와 shared rail에서 current access route가 일관되게 보이는 순간이다.
  - Pit는 workbench 안에서 access state가 다시 invisible해지던 상태였다.
  - Transition은 triage -> rail -> workbench header에서 같은 route language를 유지하는 것이다.
- Ethics:
  - Regret: 통과. current route만 노출하고 success를 과장하지 않는다.
  - Black Mirror: 통과. institution route를 guaranteed access처럼 포장하지 않는다.
  - In Real-Life: 통과. local-first operator는 현재 PDF route를 계속 확인할 수 있어야 한다.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench reuses the same operational state summary language as list and rail"`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|workbench rail layout" --update-snapshots=all`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/visual-backend.backend.spec.ts -g "workbench shell layout|workbench rail layout"`

## 7.4) Review-First Workbench Header Checkpoint (2026-03-29)
- Screen/Flow:
  - `/workbench/:paperId` header and mobile control summary
- Goal action:
  - users should understand the workbench as a paper-review surface before they interpret run controls.
- Primary persona:
  - researchers opening Workbench from a note detail and deciding whether to inspect evidence, refresh saved checks, or continue into artifacts.
- Current friction:
  - the H1 contract was stable, but the top of the page still leaned toward tool-shell wording.
  - access route, saved-check health, and claim-review state existed elsewhere on the screen, yet the header itself did not summarize them.
  - mobile `Workbench controls` described a container, not the job the controls help the user do.
- Success metric:
  - the workbench subtitle reads as a review action, the header meta shows access + saved-check + claim-review context, and mobile controls read as review/run actions instead of shell controls.
- Quick Review:
  - this is a hierarchy and tone patch, not a new workbench model.
  - the smallest safe change is to reuse existing access, operational-state, and content-review primitives in the header.
- Full Review:
  - P0: keep `Analysis Workbench` as the H1 to preserve route/test continuity.
  - P0: replace the subtitle with a research-review sentence instead of showing only the paper title.
  - P0: add compact header meta blocks for access route, saved-check state, and claim-review state.
  - P1: rename the mobile details summary from `Workbench controls` to `Review & run controls`.
  - P1: rename the return link from `Paper Notes` to `Back to notes`.
  - P2: keep run buttons and advanced repair actions structurally unchanged.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when the workbench explains its review purpose before the operator reads controls
  - Prompt: header state blocks and the mobile summary should clarify what this surface is for
- B.I.A.S diagnosis:
  - Block: top-of-screen language still felt closer to an operator tool than a research review surface
  - Interpret: users had to infer review readiness from deeper panels
  - Act: clearer header framing makes run/repair actions feel contextual instead of mechanical
  - Store: the route should be remembered as “where I inspect evidence and saved checks,” not just “where I run jobs”
- Peak-End design notes:
  - Peak is understanding review readiness from the workbench header itself.
  - Pit was landing on a dense tool shell and parsing intent after the fact.
  - Transition is note detail -> workbench header -> claim/evidence/artifact panels.
  - End is a stronger sense that the workbench belongs to the research loop, not a side console.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a careful teammate would frame a review workspace before suggesting actions
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend workbench preserves content review context when opened in issue focus mode|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "mobile triage cards and workbench collapsed controls work"`
  - mobile regression now treats the primary review action as state-aware (`Run deep read` or `Cancel run`) so it verifies the control surface instead of overfitting to one initial job state

## 7.5) Review Maintenance Tone Checkpoint (2026-03-29)
- Screen/Flow:
  - `/workbench/:paperId` advanced repair controls in desktop and mobile control groups
- Goal action:
  - users should read rebuild and retrieval controls as review maintenance actions, not internal operator switches.
- Primary persona:
  - researchers inspecting saved checks who only want to intervene when the current review snapshot looks stale or inconsistent.
- Current friction:
  - `Advanced actions`, `Rebuild checks`, and `Clean Reindex` leaked backend/operator language into an otherwise review-first surface.
  - the controls were functionally correct, but they made the workbench feel more like an internal console than a research workspace.
- Success metric:
  - the advanced area reads as optional maintenance for review state, and the labels explain why to use the actions without introducing new concepts or route changes.
- Quick Review:
  - this is a copy-only tone cleanup.
  - the smallest safe patch is to keep the controls, keep the booleans, and rewrite the labels around saved review state.
- Full Review:
  - P0: rename the advanced disclosure to `Review maintenance`.
  - P0: rename the primary repair CTA to `Rebuild saved checks`.
  - P1: replace `Clean Reindex` with `Fresh retrieval` because the latter describes user intent instead of an implementation detail.
  - P1: rewrite rebuild helper copy so it explains when to use the action, not how the backend is wired.
  - P2: leave the rest of the control row intact so the change stays narrow and reversible.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when the labels explain maintenance intent in user language
  - Prompt: `Review maintenance`, `Rebuild saved checks`, and `Fresh retrieval` are clearer prompts than operator-facing terms
- B.I.A.S diagnosis:
  - Block: backend-flavored labels add unnecessary interpretation cost
  - Interpret: users had to decode whether these controls were safe maintenance actions or risky internal switches
  - Act: softer, review-specific language makes intervention feel more deliberate and less intimidating
  - Store: the workbench is more likely to be remembered as a review surface than a maintenance console
- Peak-End design notes:
  - Peak is seeing advanced controls framed as optional maintenance for saved review state.
  - Pit was the moment a user hit `Clean Reindex` and had to infer what that meant.
  - Transition is review header -> core actions -> optional maintenance.
  - End is a calmer sense that these controls exist to repair review state, not expose internals.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a teammate would describe “refresh the review snapshot” instead of “run a clean reindex”
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend repair stats action appears only when stats artifact is missing and hides after repair|backend rebuild stats action stays under advanced controls and overwrites the current snapshot"`
  - `cd frontend && npx playwright test -c playwright.mock.config.ts e2e/mock.spec.ts -g "mobile triage cards and workbench collapsed controls work"`

## 7.6) Note-Backed Fetch Noise Checkpoint (2026-03-29)
- Screen/Flow:
  - `/workbench/:paperId` opened from a note-backed `zotero:` paper id on the live UI route
- Goal action:
  - keep the workbench review surface visually stable without avoidable 404 noise from alias probing or placeholder-PDF fallbacks.
- Primary persona:
  - close-user testers and researchers opening a note-backed paper directly into the workbench.
- Current friction:
  - the workbench could render correctly while still producing a small burst of console 404s for paper, artifact, PDF, and mirror alias lookups.
  - this did not break the route, but it weakened the local-first trust signal during direct runtime verification.
- Success metric:
  - note-backed workbench loads without those avoidable alias/PDF/mirror 404s, while preserving the placeholder PDF and mirror panels when they are genuinely needed.
- Quick Review:
  - this is a fetch-order and fallback patch, not a new workbench data model.
  - the smallest safe change is to prefer note-backed paper resolution for workbench, prefer canonical stripped ids for artifact/mirror lookups, and skip live PDF fetches when `pdf_exists` is already false.
- Full Review:
  - P0: let `getPaper(..., { preferNoteDetail: true })` short-circuit to the resolved note when the workbench opens a note-backed paper id.
  - P0: prefer stripped paper ids for artifact and mirror reads so alias probing does not generate a guaranteed first 404.
  - P1: if `pdf_exists === false`, go straight to the placeholder PDF instead of first attempting impossible live PDF fetches.
  - P2: keep the workbench layout and review content unchanged; this is trust cleanup, not a UI redesign.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when the workbench feels stable and intentional on first load
  - Prompt: users should be prompted by review state, not by hidden network churn
- B.I.A.S diagnosis:
  - Block: avoidable 404s create quiet doubt even when the page works
  - Interpret: users may read repeated missing-resource requests as “this route is half wired”
  - Act: cleaner first load keeps the user in the review loop instead of making them question the runtime
  - Store: the workbench should be remembered as grounded and calm, not noisy-but-functional
- Peak-End design notes:
  - Peak is a note-backed workbench load that just settles into review state.
  - Pit was seeing or inferring a stack of alias/PDF/mirror misses behind an otherwise healthy page.
  - Transition is paper detail -> workbench review header -> claims/evidence/artifacts without fetch churn.
  - End is “this route is ready for review” instead of “it worked, but something feels off.”
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: a trustworthy local-first tool should avoid asking the browser to prove obvious misses before showing the fallback it already intends to use.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend paper note to workbench to protocol create journey stays connected in the browser"`

## 7.7) Repeated Controls Keyboard Checkpoint (2026-03-30)
- Screen/Flow:
  - `/workbench/:paperId` desktop repeated-action controls after the main run buttons
- Goal action:
  - keyboard users should move from the main run controls into maintenance toggles and appearance/search controls with clear names and a stable order.
- Primary persona:
  - repeat researchers who revisit the workbench often and use keyboard navigation to move between run, maintenance, and paper-selection surfaces.
- Current friction:
  - the earlier keyboard baseline closed the biggest note/image issues, but workbench repeated controls were only loosely covered.
  - checkbox and select controls were keyboard-reachable, yet their names were not explicit enough for a durable regression or for clear current-runtime inspection.
- Success metric:
  - workbench repeated controls expose explicit accessible names and a regression test now locks the expected order through `Verify checks`, `Fresh retrieval`, `Theme`, `View`, `Highlight`, and `Search papers`.
- Quick Review:
  - this is not a workbench layout rewrite.
  - the smallest safe change is to add explicit labels to the repeated controls and expand the existing keyboard regression instead of moving controls around.
- Full Review:
  - P0: give desktop/mobile repeated controls explicit accessible names.
  - P0: lock the workbench tab sequence past the main run controls into maintenance toggles and then search.
  - P1: keep the current control ordering because current-runtime baseline already reads as stable and intentional.
  - P2: leave advanced panel structure and core run/cancel behavior unchanged.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when repeated controls announce themselves clearly instead of relying on incidental wrapper text
  - Prompt: the keyboard path should keep moving from “run or refresh” into “adjust or search” without ambiguity
- B.I.A.S diagnosis:
  - Block: repeated controls were under-specified in the keyboard regression
  - Interpret: without explicit names, the surface is harder to trust and harder to inspect repeatably
  - Act: explicit control naming plus regression coverage lowers future drift risk
  - Store: the workbench should feel like a dependable dense workspace, not a fragile one-off shell
- Peak-End design notes:
  - Peak is tabbing from run controls into named maintenance toggles and then straight into paper search.
  - Pit was relying on incidental text/value snapshots instead of real control names.
  - Transition is core run actions -> repeated controls -> rail search.
  - End is a more inspectable and repeatable keyboard loop.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a trustworthy power-user tool should behave when people navigate it repeatedly by keyboard
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`

## 7.8) Panel Jump Keyboard Checkpoint (2026-03-30)
- Screen/Flow:
  - `/workbench/:paperId` rail search into deeper document, artifact, and timeline panels
- Goal action:
  - keyboard users should be able to leave the paper rail quickly after `Search papers` and jump straight into the deeper workbench panels without tabbing through every paper row first.
- Primary persona:
  - repeat users reviewing one paper in depth who use the rail search to orient, then want to move directly into document evidence, derived artifacts, or the timeline.
- Current friction:
  - the earlier keyboard baseline stopped at `Search papers`, but the next real stop on the shared runtime was a long run of paper-row buttons.
  - this made the deeper workbench panels technically reachable but too far away for a calm keyboard loop.
- Success metric:
  - after `Search papers`, the workbench now exposes three explicit jump controls for `document panel`, `artifact panel`, and `timeline`, and clicking them moves focus to the intended panel container.
- Quick Review:
  - this is a navigation affordance, not a workbench layout rewrite.
  - the smallest safe change is to add jump buttons inside the rail search area and make the target panel containers programmatically focusable.
- Full Review:
  - P0: add `Jump to document panel`, `Jump to artifact panel`, and `Jump to timeline` directly below the rail search input.
  - P0: give the document, artifact, and timeline panel containers stable ids plus `tabIndex={-1}` so the buttons move real focus instead of only scrolling.
  - P1: extend the existing keyboard regression to verify the new buttons appear immediately after `Search papers`.
  - P2: keep the underlying paper rail, panel order, and artifact/timeline content unchanged.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when the keyboard path does not force users through a long rail list before the deeper review panels
  - Prompt: `Search papers` should naturally flow into “jump where you want to review next”
- B.I.A.S diagnosis:
  - Block: rail paper rows became the default next stop even when the user wanted the deeper panels
  - Interpret: the workbench could feel denser and more tiring than it looks
  - Act: jump controls let the user choose document, artifact, or timeline review explicitly
  - Store: the workbench is more likely to be remembered as a controllable dense workspace instead of a long tab tunnel
- Peak-End design notes:
  - Peak is reaching `Search papers` and then immediately seeing three jump options for the deeper panels.
  - Pit was having to tab through the entire rail paper list before touching artifacts or timeline.
  - Transition is rail search -> panel jump -> focused review surface.
  - End is a shorter and more intentional keyboard loop.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a trustworthy power-user research tool should behave when keyboard users want to move quickly between dense panels.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - current runtime tab audit on `/ui/workbench/:paperId` confirms `Search papers -> Jump to document panel -> Jump to artifact panel -> Jump to timeline`

## 7.9) Artifact Panel Keyboard Checkpoint (2026-03-31)
- Screen/Flow:
  - `/workbench/:paperId` jump into `ArtifactPanel` and continue tabbing through claim review and Obsidian snapshot surfaces
- Goal action:
  - once keyboard users jump into the artifact panel, they should stay on interactive review controls rather than landing on scrollable preview blocks that do not advance the workflow.
- Primary persona:
  - repeat users reviewing claims and saved checks from the artifact panel after using the new rail jump controls.
- Current friction:
  - current-runtime audit showed the artifact jump itself was good, but the scrollable `Generated Markdown` and `Raw Artifact JSON` previews were still entering Chromium tab order because of `overflow-auto`.
  - this created the same kind of non-interactive focus drift we already removed from image-evidence metadata previews.
- Success metric:
  - after `Jump to artifact panel`, the first keyboard stops stay on claim buttons, sync, and disclosure summaries, and the preview `<pre>` blocks are no longer tabbable.
- Quick Review:
  - no layout or panel order change is needed here.
  - the smallest safe patch is to remove the non-interactive preview `<pre>` blocks from tab order and extend the existing workbench keyboard regression to guard that behavior.
- Full Review:
  - P0: set `tabIndex={-1}` on the artifact panel's scrollable markdown and raw-JSON previews.
  - P0: extend the keyboard regression so `Jump to artifact panel` is followed by interactive review controls and does not hit a `<pre>` stop.
  - P1: keep disclosure summaries keyboard-reachable because they are real controls, not static content.
  - P2: timeline jump was audited in the same pass; on the shared runtime it remains an honest no-event state and did not require a product patch in this slice.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when artifact review stays on claim/sync/disclosure controls instead of preview blocks
  - Prompt: the artifact panel should keep prompting “review or sync next,” not “land on raw preview text”
- B.I.A.S diagnosis:
  - Block: scrollable preview `<pre>` blocks quietly interrupted the review loop
  - Interpret: keyboard users could read the panel as rougher and less intentional than it looked
  - Act: removing those static preview stops keeps focus on real artifact actions
  - Store: the artifact panel is more likely to be remembered as a review tool, not a tab maze
- Peak-End design notes:
  - Peak is `Jump to artifact panel` followed by claim buttons, sync, and disclosure summaries only.
  - Pit was landing on generated-markdown or raw-JSON preview blocks before the loop was really finished.
  - Transition is rail jump -> artifact review controls -> optional disclosures.
  - End is a calmer and shorter artifact-panel keyboard path.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a trustworthy dense review surface should behave when the previews are informative but not actionable.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser"`
  - current runtime tab audit on `/ui/workbench/:paperId` confirms `Jump to artifact panel` no longer reaches a `<pre>` stop in the first artifact-panel tab sequence

## 7.10) Timeline Panel Keyboard Checkpoint (2026-04-01)
- Screen/Flow:
  - `/workbench/:paperId` jump into `TimelinePanel` when eventful fixture data is available
- Goal action:
  - after `Jump to timeline`, keyboard users should reach the timeline filter controls first, not incidental content blocks.
- Primary persona:
  - repeat users who use workbench jumps to move quickly between artifact review and run-history inspection.
- Current friction:
  - the shared runtime still mostly exposes an honest no-event timeline state, so the next useful audit had to use an eventful fixture route.
  - the timeline filter buttons were reachable already, but their accessible names were count-coupled (`All (n)`, `Status (n)`, etc.), which made keyboard inspection and regression unnecessarily brittle.
- Success metric:
  - timeline filter controls expose stable accessible names and a fixture-backed keyboard regression now confirms the first timeline stops after the jump are `all`, `status`, `error`, and `done` filters.
- Quick Review:
  - no timeline layout change was needed.
  - the smallest safe improvement is to give the filter buttons explicit names and verify the eventful path through an existing fixture route.
- Full Review:
  - P0: add explicit accessible names to the four timeline filter buttons.
  - P0: add a backend keyboard regression that uses `Jump to timeline` on an eventful workbench fixture and asserts the first four stops are the filter controls.
  - P1: keep pinned events and timeline rows non-focusable; they are read-only content, not controls.
  - P2: confirm the shared current runtime still exposes an honest no-event state and that the timeline jump still focuses the panel wrapper there.
- BMAP diagnosis:
  - Motivation: high
  - Ability: improves when eventful timeline routes present stable, named controls instead of count-shaped labels
  - Prompt: the timeline should say “filter the run history” before it says “read a wall of entries”
- B.I.A.S diagnosis:
  - Block: eventful timeline keyboard inspection was under-specified because filter names changed with counts
  - Interpret: the panel could feel less intentional and harder to verify than it really was
  - Act: stabilize names and lock the filter-first keyboard path in a fixture route
  - Store: the timeline is more likely to be remembered as a controllable history surface, not just a passive log dump
- Peak-End design notes:
  - Peak is `Jump to timeline` followed immediately by `all`, `status`, `error`, and `done` filters.
  - Pit was having the panel be keyboard-reachable but under-described.
  - Transition is rail jump -> timeline filter controls -> pinned events and rows.
  - End is a cleaner and more durable keyboard contract for the eventful timeline state.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a trustworthy run-history panel should behave for keyboard-first users.
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend keyboard focus keeps primary actions ahead of static content on core routes|backend paper note to workbench to protocol create journey stays connected in the browser|backend timeline falls back to all when status events are unavailable|backend timeline surfaces user-triggered actions distinctly|backend timeline jump keeps filter controls ahead of pinned and event content"`
  - current runtime audit on `/ui/workbench/:paperId` confirms `Jump to timeline` still focuses the no-event panel and preserves the honest empty-state copy

## 7.11) Compiled Knowledge Surface Checkpoint (2026-04-10)
- Screen/Flow: `/workbench/:paperId` artifact panel
- Goal action: 연구자가 latest paper synthesis를 “canonical answer”가 아니라 optional compiled-knowledge artifact로 읽고, 필요할 때 raw markdown를 다시 연다.
- Primary persona: note/workbench review를 마친 뒤 downstream synthesis bundle이 있는지 확인하려는 biomedical research operator
- Current friction:
  - `paper_synthesis` lane은 backend/CLI에는 있었지만 workbench 안에서는 invisible했다.
  - 그래서 compiled knowledge가 실제로 저장돼 있어도 operator는 artifact family 안에서 이 lane을 발견할 수 없었고, 반대로 있더라도 canonical state와 어떻게 다른지 UI에서 배울 수 없었다.
- Success metric:
  - workbench artifact panel에 latest saved paper synthesis가 read-only card로 보이고, card만 읽어도 `non-canonical`, readiness/freshness, source/evidence count, raw markdown reopen path가 immediately visible하다.

### Quick Review (5 min)
- Block: compiled knowledge lane가 workbench 안에 안 보여서 존재와 boundary를 동시에 놓치기 쉬웠다.
- Interpret: 이 surface는 새 viewer가 아니라 existing artifact panel 안의 one more downstream card여야 한다.
- Act: operator는 metadata를 먼저 읽고, 필요할 때만 raw markdown를 연다.
- Store: synthesis는 “helpful derived note”로 기억돼야지 “새 truth store”로 기억되면 안 된다.
- Ethics: boundary를 더 선명하게 하는 패치라서 persuasion risk는 낮다.

### Full Review
#### P0
- workbench artifact panel은 이미 downstream review artifacts를 모으는 자리이므로, `paper_synthesis`도 여기서 read-only로 보여주는 게 가장 작고 일관된 추가다.
- card first-read에서 `Non-canonical` 배지와 readiness/freshness를 같이 보여줘야 compiled knowledge와 canonical state의 경계가 흐려지지 않는다.

#### P1
- source/evidence/warning count를 같이 보여주면 operator가 raw markdown를 열기 전에 provenance density를 빠르게 읽을 수 있다.
- open action은 raw markdown 직접 링크 정도로 제한해 viewer/inline editor를 새로 만들지 않는 편이 현 단계에 맞다.

#### P2
- empty state도 보여줘야 “lane exists but is optional”이라는 product memory가 남는다.
- 현재는 paper-scoped latest item 하나만 보이고 list/index UI는 아직 추가하지 않는다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: operator wants to know whether a compiled paper synthesis exists for the current note.
  - Emotion: low patience for ambiguous derived artifacts in a biomedical review workspace.
  - Action: open workbench, inspect artifacts, decide whether to reopen a derived markdown note.
  - Struggle: today the lane exists off-screen, so the operator cannot build a clean mental model.
  - Attempt: search docs/CLI or assume the lane does not exist.
  - Happy Ending: the artifact panel shows one honest card that explains the lane and links to the raw markdown.
- BMAP:
  - Motivation: high because this sits after evidence review and before downstream handoff.
  - Ability: improves when the lane is visible in the existing artifact family instead of hidden behind API/CLI only.
  - Prompt: a single card with boundary labels is enough; a full viewer would be too much right now.
- B.I.A.S:
  - Block: hidden lane means no cue that compiled knowledge exists or how it differs from truth state.
  - Interpret: the UI should teach “derived note” rather than “new answer source.”
  - Act: a direct markdown reopen path supports cautious use.
  - Store: users should remember that compiled knowledge is downstream and reviewable.
- Peak-End:
  - Peak: seeing `Non-canonical` and counts before opening the note.
  - Pit: previously there was no visible lane at all.
  - Transition: evidence review -> artifact panel -> optional compiled markdown reopen.
  - End: user leaves with a clearer mental boundary, not more surface area.
- Ethics:
  - Regret: pass; it reduces ambiguity rather than pushing a derived artifact.
  - Black Mirror: pass; the card does not overclaim truth or automation.
  - In Real-Life: pass; researchers often want a quick derived-note check, but they still need a way back to source/evidence.

## BMAP diagnosis
- Motivation: high. This is a post-review handoff moment where one saved synthesis can save time.
- Ability: moderate today because the lane was invisible; the card lowers discovery cost without widening the workflow.
- Prompt: the smallest useful prompt is “Compiled knowledge” plus `Non-canonical`, readiness, freshness, and markdown reopen.

## B.I.A.S diagnosis
- Block: hidden lane increased recall burden.
- Interpret: without boundary copy, operators could misread synthesis as another truth surface.
- Act: a raw-markdown reopen link is enough for the next action.
- Store: repeated exposure inside artifact panel should teach that compiled knowledge is downstream of canonical review.

## Peak-End design notes
- Peak: make the first glance teach boundary before convenience.
- Pit: avoid a mini viewer that makes the lane feel bigger or truer than it is.
- Transition: keep the action as “open markdown,” not “continue analysis” or “promote answer.”
- End: the card should leave the user feeling oriented, not invited into a new subproduct.

## Concrete changes
- add optional `paper_slug` filtering to `/paper-syntheses` so the UI can ask for the latest item without inventing a new endpoint
- resolve note slug from the existing structured-state lookup already used by workbench
- render one `Compiled knowledge` card in `ArtifactPanel` with `Non-canonical`, readiness, freshness, counts, and raw markdown reopen
- keep missing-state copy honest: the lane is optional and the current workbench surface stays read-only

## Ethics check results
- Regret / Black Mirror / In Real-Life: Pass
- Caution: do not add inline editing or “use this answer” CTA on this card until canonical/promotion rules are stronger.

## Next PR-sized actions
- add a dedicated detail viewer only if operators actually need more than metadata + raw markdown reopen
- if more compiled templates ship later, keep the same card contract and expand by template kind instead of inventing a separate UI family
- add lightweight browser verification once a stable backend fixture includes a saved paper synthesis bundle

## 7.12) Compiled Knowledge Lineage Checkpoint (2026-04-10)
- Screen/Flow: `/workbench/:paperId` compiled knowledge card
- Goal action: operator가 compiled markdown를 읽기 전에 “이 카드가 어떤 upstream lineage를 다시 열어야 하는지”를 즉시 파악한다.
- Primary persona: evidence review 뒤에 derived note를 재사용하려는 biomedical research operator
- Current friction:
  - counts와 badges만으로는 minimum trust-reopen path가 직접 보이지 않았다.
  - 그래서 `non-canonical`임은 보여도, 실제 answer route가 canonical state -> evidence lineage라는 점은 markdown를 열기 전에는 약했다.
- Success metric:
  - workbench card first read에서 answer route와 minimum lineage badges가 보이고, additive review sidecars도 secondary로 구분된다.

### Quick Review (5 min)
- Block: compiled card가 존재해도 “무엇을 다시 열어야 신뢰를 복구할 수 있는가”가 암묵적이었다.
- Interpret: 새 viewer 대신 current card 안에 trust-reopen summary를 넣는 것이 현재 repo boundary와 맞다.
- Act: operator는 markdown reopen 전에 canonical state / resolved claimset / run metadata를 머릿속에 다시 잡는다.
- Store: compiled knowledge는 “reopenable derived note”로 기억돼야 한다.
- Ethics: trust boundary를 더 명시하는 패치라서 overclaim risk를 줄인다.

### Full Review
#### P0
- minimum upstream lineage 세 가지를 card 안에 직접 보여줘야 compiled prose가 truth처럼 읽히는 것을 줄일 수 있다.
- answer route는 human-readable 하게 보여주되, underlying contract는 existing `canonical_state_then_upstream_evidence` wording을 유지하는 편이 안전하다.

#### P1
- additive review artifacts는 sidecar로만 보여주고 required lineage와 같은 위상으로 섞지 않는다.
- 기존 markdown reopen action은 그대로 두고, lineage 요약만 같은 card 안에 얹는다.

#### P2
- 지금은 latest item 한 장만 다루므로 lineage detail viewer까지 넓히지 않는다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: operator can see a compiled artifact but still hesitate about what makes it trustworthy to reopen.
  - Emotion: low trust in derived biomedical prose unless provenance is explicit.
  - Action: inspect compiled knowledge card, decide whether to open markdown.
  - Struggle: boundary copy alone does not fully explain the minimum upstream path.
  - Attempt: infer the path from counts or open markdown and parse frontmatter manually.
  - Happy Ending: card itself teaches the trust-reopen path before the click.
- BMAP:
  - Motivation: high because this is right before downstream reuse.
  - Ability: improves when lineage is explicit in the same panel instead of hidden in markdown/frontmatter only.
  - Prompt: a short answer-route label plus three lineage chips is enough.
- B.I.A.S:
  - Block: lineage stayed implicit.
  - Interpret: the card could still feel more self-sufficient than intended.
  - Act: explicit path reduces guesswork before reopening markdown.
  - Store: users are more likely to remember that compiled notes stay subordinate to canonical/evidence layers.
- Peak-End:
  - Peak: seeing `Canonical state -> upstream evidence` next to the existing non-canonical badge.
  - Pit: counts alone can look authoritative without showing the route back.
  - Transition: metadata summary -> trust-reopen path -> raw markdown reopen.
  - End: user leaves with a stronger provenance mental model, not a larger feature surface.
- Ethics:
  - Regret: pass; boundary got clearer.
  - Black Mirror: pass; no automation pressure or authority inflation was added.
  - In Real-Life: pass; this is closer to how cautious research operators inspect derived notes.

## BMAP diagnosis
- Motivation: high. This is the moment where a derived artifact either feels safely reviewable or suspiciously opaque.
- Ability: improved by making the answer route visible before the click.
- Prompt: the trust-reopen path is now the main prompt, not the markdown link alone.

## B.I.A.S diagnosis
- Block: implicit lineage summary.
- Interpret: users could overread the card as self-contained.
- Act: explicit lineage chips make the next check obvious.
- Store: repeated exposure should teach the canonical-state-first rule.

## Peak-End design notes
- Peak: keep the answer route short and visible.
- Pit: avoid turning lineage into a dense provenance table.
- Transition: trust-reopen summary should sit between counts and markdown reopen.
- End: the card should feel more honest, not more complex.

## Concrete changes
- add derived `lineage_summary` to paper synthesis list/detail payloads
- render one `Trust reopen path` block in the existing compiled knowledge card
- keep `source_refs` as the underlying provenance owner; summary is additive only
- verify the backend browser fixture still shows populated, honest-empty, and auditable open states

## Ethics check results
- Regret / Black Mirror / In Real-Life: Pass
- Caution: do not let the summary replace direct `source_refs` or markdown frontmatter in future detail surfaces.

## Next PR-sized actions
- expose the same lineage summary in any future dedicated detail page only if the current card proves insufficient
- if operators ask for more depth, add a compact detail fetch for `source_refs` instead of widening the list lane further
- investigate the intermittent combined-`pytest` linger separately from this feature lane

## 7.13) Compiled Knowledge Source-Ref Inspector Checkpoint (2026-04-10)
- Screen/Flow: `/workbench/:paperId` compiled knowledge card, inline source-ref inspector
- Goal action: operator가 현재 card를 벗어나지 않고 saved `source_refs`를 다시 열어 provenance owner를 직접 확인한다.
- Primary persona: compiled note를 downstream reuse하기 전에 exact upstream file/run lineage를 짧게 확인하려는 biomedical research operator
- Current friction:
  - lineage summary만으로는 answer route는 보이지만, 실제 saved `source_refs` 항목과 path는 markdown를 열기 전까지 보이지 않았다.
  - full viewer를 새로 만들기에는 아직 lane이 작고, raw markdown만 강제하는 것도 약간 과했다.
- Success metric:
  - operator가 workbench card 안에서 `Inspect source refs`를 열면 saved source refs, run ids, and file paths를 확인하고 다시 닫을 수 있다.

### Quick Review (5 min)
- Block: trust-reopen path는 보였지만 exact saved refs는 card 밖에 있었다.
- Interpret: 새 페이지보다 inline inspector가 current lane size와 더 잘 맞는다.
- Act: operator는 card에서 직접 source refs를 확인한 뒤 markdown를 열지 말지 결정한다.
- Store: compiled knowledge는 summary + inspector + raw markdown의 3단계 read path로 기억돼야 한다.
- Ethics: provenance owner를 더 노출하는 변화라 authority inflation risk는 낮다.

### Full Review
#### P0
- `source_refs`는 provenance owner이므로, 필요 시 card 안에서 직접 다시 볼 수 있어야 한다.
- inline inspector는 on-demand fetch여야 한다. 기본 card load를 무겁게 만들 필요는 없다.

#### P1
- source ref cards는 `kind`, `run_id`, `path`, `note` 정도만 보여주고, 여기서 editing이나 promotion CTA는 넣지 않는다.
- inspector open도 user action으로 남겨 auditability를 유지한다.

#### P2
- 지금은 exact path visibility만 추가하고, file preview나 JSON viewer까지 넓히지 않는다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: operator sees the trust-reopen summary but still needs the exact saved refs.
  - Emotion: cautious, because biomedical compiled notes need concrete reopenability.
  - Action: expand source refs inside the card.
  - Struggle: previously the next step jumped straight to markdown or API mental model.
  - Attempt: infer from badges or open the full markdown.
  - Happy Ending: card reveals the saved refs inline and still stays obviously read-only.
- BMAP:
  - Motivation: high because this is the last check before reuse.
  - Ability: improves when exact saved refs are one toggle away.
  - Prompt: `Inspect source refs` is clearer than forcing a markdown detour.
- B.I.A.S:
  - Block: exact refs were hidden.
  - Interpret: the card still risked feeling more summarized than inspectable.
  - Act: inline inspector reduces the gap between summary and provenance owner.
  - Store: users should remember that compiled knowledge can be audited in-place.
- Peak-End:
  - Peak: opening the inspector and immediately seeing `structured state`, `resolved claimset`, `run metadata`.
  - Pit: avoid turning this into a mini artifact browser.
  - Transition: summary -> inspector -> optional markdown reopen.
  - End: operator leaves with stronger trust and little extra surface area.
- Ethics:
  - Regret: pass.
  - Black Mirror: pass.
  - In Real-Life: pass; this matches cautious provenance inspection better than a forced page jump.

## BMAP diagnosis
- Motivation: high. This is a provenance confirmation step.
- Ability: improved by letting exact refs appear inline.
- Prompt: the new prompt is “Inspect source refs,” not “go elsewhere to trust this.”

## B.I.A.S diagnosis
- Block: exact saved refs were hidden behind another surface.
- Interpret: users could still feel the card was too abstract.
- Act: inspector reduces unnecessary navigation.
- Store: compiled knowledge now teaches both summary and underlying provenance owner.

## Peak-End design notes
- Peak: the first expanded view should show the required refs first.
- Pit: do not add raw-file previews or editing controls.
- Transition: keep the inspector compact and secondary.
- End: the user should feel better oriented, not deeper in tooling.

## Concrete changes
- mark `GET /paper-syntheses/{id}` as a compatibility bundle fetch rather than the preferred inspection path
- keep the frontend structured detail fetch on `/paper-syntheses/{id}/manifest`, not the compatibility bundle route
- switch the inline inspector to a manifest-only structured fetch so provenance inspection does not need the markdown export payload
- render an inline `Inspect source refs` details block in the existing compiled knowledge card
- log `workbench_open_paper_synthesis_source_refs` when the inspector opens
- verify the browser fixture can load and display saved source refs without leaving the card

## Ethics check results
- Regret / Black Mirror / In Real-Life: Pass
- Caution: keep `source_refs` display read-only and secondary to the summary block.

## Next PR-sized actions
- only add a dedicated compiled-knowledge detail page if the inline inspector proves insufficient
- if operators need richer inspection, add targeted open-file affordances rather than a generalized explorer
- keep combined-`pytest` troubleshooting separate from this UI/provenance lane

## 7.8) Access Label Honesty Checkpoint (2026-04-21)
- Screen/Flow: `AnalysisWorkbench` header `Workspace context` access card plus the shared rail/home access helper continuity
- Goal action: let operators read access state in workbench language without falling back to route-shaped wording, while keeping the same shared helper copy aligned across home and workbench.
- Primary persona: an operator moving between home, rail, and workbench who wants to know whether the current paper opens from a local PDF, an available OA PDF, or an institution-assisted page.
- Current friction:
  - shared access link labels were already cleaned up, but the workbench header eyebrow still said `Access route`.
  - the workbench strip description still said `access route`, which left one route-shaped phrase visible in the shared header copy.
  - browser coverage also still skewed toward the `Local PDF` path, which left the `open` and `institution_required` states under-sampled on home/workbench.
- Quick decision:
  - rename the workbench header eyebrow from `Access route` to `Access`.
  - tighten the strip description from `access route` to `access`.
  - keep badge labels and destinations unchanged.
  - add narrow browser coverage for `Open access` and `Institution route` on the home resume card and for `Open access` plus `Institution route` continuity across workbench rail/header.
- BMAP:
  - Motivation: high because access state is part of deciding whether to keep reading here or leave the app for a source route.
  - Ability: improves when the header uses direct task language and the shared helper is verified across surfaces.
  - Prompt: `Access` plus the existing badge/link pair is the smallest honest prompt.
- B.I.A.S:
  - Block: `route` wording adds implementation flavor right where the user is trying to decide what can be opened.
  - Interpret: `Access` reads as a user-facing state, not a routing concept.
  - Act: users can keep moving from home to workbench without translating the helper differently on each surface.
  - Store: the product feels more consistent because access is described as a reading aid, not a router detail.
- Peak-End:
  - Peak is seeing the same access language from resume card to workbench header.
  - Pit was a mostly-clean helper still landing in a route-shaped header label.
  - Transition is home/workbench continuity, not another route-specific vocabulary shift.
  - End is a calmer memory that access state stays readable everywhere.
- Ethics:
  - Regret: pass. this reduces jargon without changing any promise about actual access success.
  - Black Mirror: pass. `Institution route` remains the bounded status label; only the surrounding wording gets simpler.
  - In Real-Life: pass. this sounds more like a teammate pointing to the next opening path than a developer naming an internal surface.
- Concrete change:
  - rename the workbench header eyebrow to `Access`
  - rewrite the workbench strip description to say `Keep access, saved checks, and claim review status aligned while you validate evidence.`
  - keep `Open access`, `Institution route`, and `Local PDF` badge semantics unchanged
  - add browser coverage for open-access and institution-linked home resume states plus shared access-label continuity across workbench rail/header
- Verification:
  - `python3 scripts/lint_docs.py docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md`
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend home resume card keeps institution access links in user language|backend home resume card keeps open-access links in user language|backend workbench keeps shared access labels aligned across rail and header|backend workbench preserves content review context when opened in issue focus mode"`

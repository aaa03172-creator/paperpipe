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

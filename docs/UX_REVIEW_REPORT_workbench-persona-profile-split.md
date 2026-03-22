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

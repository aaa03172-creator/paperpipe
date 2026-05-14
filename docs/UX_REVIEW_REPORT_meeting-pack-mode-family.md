# UX Review Report - Meeting Pack Mode Family Framing

Status: Current review artifact
Date: 2026-03-17
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: `/meeting-packs` saved packs index and `/meeting-packs/:packId` detail summary
- Goal action: understand what kind of presentation lane a saved meeting pack belongs to without mistaking that lane for a separate reasoning agent
- Primary persona: research operator or maintainer reopening a saved meeting pack draft
- Current friction: the screen shows the concrete meeting-pack mode, but it does not explain the broader output/view family, so the product still looks mode-specific rather than mode-family aware
- Success metric: user can distinguish concrete pack mode from reusable output-mode family in one glance
- Constraints:
  - keep existing Meeting Pack concrete modes intact
  - do not imply a new runtime or evidence policy per family
  - keep the inspector operational and low-noise

## Quick Review (5 min)
- Block: current Meeting Pack cards expose concrete `mode` only, so users do not see the reusable family concept.
- Interpret: without a family label, `journal_club` and `experiment_proposal` still look like isolated product-specific modes.
- Act: reopening or scanning saved packs remains workable, but the system does not teach the cross-surface model yet.
- Store: users remember the pack by a one-off mode name instead of a reusable presentation lane.
- Ethics: this is taxonomy friction, not manipulation, but it still increases interpretation cost.

## Full Review
### P0
- None. The current flow works and does not mis-execute user actions.

### P1
- The saved pack list and detail summary in [MeetingPackPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx) surface only the concrete mode, so the first shared output/view-mode adoption remains invisible to users.
- Without an explicit family label, operators cannot tell whether `journal_club` and `literature_update` are siblings in the same presentation lane or separate conceptual buckets.
- The detail page explains regenerate/drift mechanics well, but it does not reinforce that output mode changes presentation framing rather than evidence policy.

### P2
- Search on the saved-pack index does not currently benefit from family terms like `lab meeting` or `builder debug`.

### Full Review Coverage
- 6P storyboard context:
  - Problem: the operator reopens a saved pack and needs to understand what kind of draft it is.
  - Emotion: low patience for internal taxonomy when the goal is to reuse or debug a draft quickly.
  - Action: scan saved packs or open one pack detail.
  - Struggle: only the concrete mode is visible, so the reusable family concept stays hidden.
  - Attempt: show a small family label beside the existing mode and restate the distinction in detail view copy.
  - Happy Ending: user sees both the concrete mode and the broader presentation lane immediately.
- BMAP:
  - Motivation is already high because the user wants to inspect or reuse a saved draft.
  - Ability weakens when the shared taxonomy is invisible.
  - Prompt is strong enough once family labels are visible in the list and detail summary.
- B.I.A.S:
  - Block: family concept is hidden behind implementation knowledge.
  - Interpret: concrete mode alone is too narrow to teach the design model.
  - Act: the user can continue, but with extra mental translation.
  - Store: the product does not leave a reusable mode-family memory.
- Peak-End:
  - Peak should stay on pack diagnostics and draft understanding, not taxonomy decoding.
  - Pit is the moment a user sees only a concrete mode and cannot infer how it generalizes.
  - Transition from list scan to detail summary should make the relationship explicit.
  - End should leave the user with a clearer reusable mental model.
- Ethics:
  - Regret: safe. The change clarifies rather than persuades.
  - Black Mirror: low risk because no ranking or nudging changes.
  - In Real-Life: the product becomes more considerate by explaining itself without adding clutter.

## BMAP diagnosis
- Motivation: strong. Saved-pack reopen and debugging are already intentional actions.
- Ability: moderate. The user can operate the screen, but the conceptual model is still underspecified.
- Prompt: family badges and one sentence of framing copy are enough; anything heavier would over-teach.

## B.I.A.S diagnosis
- Block: hidden shared taxonomy.
- Interpret: concrete modes are legible, but the broader family is not.
- Act: users can still open packs, but they cannot easily generalize the framing model.
- Store: the current UI stores mode names, not the reusable product concept.

## Peak-End design notes
- Peak: keep the strongest moment on “I understand this draft and what to do next.”
- Pit: avoid turning the screen into a taxonomy lecture.
- Transition: list badge -> detail summary field -> one-line explanatory copy.
- End: the user leaves with concrete mode plus family in memory.

## Concrete changes
- Add `output_mode_family` to Meeting Pack pack/list contracts and persist it in saved pack JSON.
- Show a muted family badge alongside the concrete mode on the saved-pack index.
- Show `Output mode family` and `Concrete mode` as separate detail summary fields.
- Add one short sentence clarifying that family is a presentation lane, not a different evidence policy.
- Let saved-pack search match family labels such as `Lab Meeting` and `Builder / Debug`.

## Ethics check results
- Regret / Black Mirror / In Real-Life: Pass
- Note: keep family labeling descriptive only. Do not rank one family above another or imply stronger evidence.

## Next PR-sized actions
- Extend the same shared family treatment to any future viewer/chat framing control, but only where it changes presentation emphasis.
- If Meeting Pack generation UI gets added later, use the family distinction to structure choices without replacing concrete modes.
- Consider a lightweight shared formatter/helper on the frontend if a second surface starts rendering the same family labels.

# /ux-review

Status: Active
Date: 2026-03-13
Owner: Lattice runtime maintainers
Canonical: `docs/ux-review.md`
Template: `docs/UX_REVIEW_TEMPLATE.md`

Use this command when reviewing or designing:
- Landing pages
- Onboarding
- Pricing/paywall
- Key CTA and conversion flows
- Error/empty states
- Core product flows (signup, purchase, explore, approve/export)

## Required references (read first)
- `rules/product-psychology/SKILL.md`
- `rules/product-psychology/references/review-checklist.md`
- `rules/product-psychology/references/bias-framework.md`
- `rules/product-psychology/references/ethics-checklist.md`
- `rules/product-psychology/references/prompt-templates.md`

## Input
- Screen/Flow
- Goal action
- Primary persona
- Current friction
- Success metric
- Constraints (tech/design/business)

## Output
1. Quick Review (5 min)
2. Full Review (P0/P1/P2 prioritized)
3. BMAP diagnosis
4. B.I.A.S diagnosis
5. Peak-End design notes
6. Concrete changes (component/route/copy/default-action level)
7. Ethics check results (Regret / Black Mirror / In Real-Life)
8. Next PR-sized actions (1-3 items)

## Full Review Coverage (mandatory)
- 6P context (Problem/Emotion/Action/Struggle/Attempt/Happy Ending)
- BMAP (Motivation / Ability / Prompt)
- B.I.A.S (Block / Interpret / Act / Store)
- Peak-End (peak, pit, transition, end)
- Ethics checks (Regret / Black Mirror / In Real-Life)

## Starter prompt template
```md
/ux-review
Screen/Flow:
Goal action:
Primary persona:
Current friction:
Success metric:
Constraints:
```

## Required file outputs
- Template: `docs/UX_REVIEW_TEMPLATE.md`
- Per-flow report: `docs/UX_REVIEW_REPORT_<flow>.md`

## Viewer/workbench follow-up rule
- If the change touches `/papers`, `/papers/:slug`, triage, rail, or workbench note-context surfaces:
  - update `docs/UX_REVIEW_REPORT_paper-notes-viewer.md`
  - keep flow-local trigger backlog in the matching `docs/UX_REVIEW_REPORT_<flow>.md`
  - review `docs/PAPER_NOTES_WORKBENCH_QUEUE.md` only when the change creates or reopens a shared cross-surface follow-up item

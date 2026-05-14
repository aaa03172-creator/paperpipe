# Research Workspace UX Slice Signoff (2026-04-03)

## Scope
- Home resume-first entry
- Home workspace-context framing
- Home queue-lens naming
- Shared note/workbench workspace-context strip
- Note-detail review bridge
- Read/Review task-language cleanup
- Artifact continuity on detail viewers

## Signoff judgment
- This slice is stable enough to pause.
- The repo now reads more clearly as:
  - `project-framed`
  - `paper-executed`
  - `source-grounded`
  - `review-forward`
- The current improvements are meaningful without pretending the runtime already has:
  - a true project list
  - a real queue container
  - a heavier project ownership model

## What is now locked
- Home starts with `Continue current work`.
- Home uses `Workspace context` as a lightweight, honest context block.
- The lower home table is framed as a `Queue lens`, not a second home.
- Note detail and workbench use the same `Workspace context` strip grammar.
- Paper workspace language is task-first:
  - `Read`
  - `Review`
  - `Open reading`
  - `Open review`
- Artifact detail viewers consistently say:
  - `Derived artifact`
  - `Canonical evidence lives upstream`

## What should not be stretched further right now
- Do not add fake `Active projects` rows on home without a real runtime contract.
- Do not turn `Queue lens` into a heavier queue container without stronger queue state semantics.
- Do not expand project chrome until the repo has a clearer project-backed payload.
- Do not add more top-level IA just because the current wording cleanup succeeded.

## Why pausing here is product-correct
- The biggest gains came from better truthfulness and continuity, not from adding more chrome.
- The UI now explains the research loop more clearly without over-promising capabilities that do not exist yet.
- Further IA expansion at this point is more likely to create conceptual debt than user value.

## Verification status
- `cd frontend && npm run verify:frontend:mock` passed
- `cd frontend && npm run verify:frontend:backend` passed
- backend verify result:
  - `98 passed`
  - `4 skipped`
- The only persistent non-blocking warning remains the existing `pdfjs-dist` eval warning.

## Recommended next entry point
- Leave this UX slice signed off unless one of these becomes true:
  - a real project-list/runtime contract is added
  - a real queue-state/runtime contract is added
  - a new user-facing research loop exposes a fresh clarity gap

## Smallest next move when that happens
- Add runtime-backed context before adding more chrome.
- Prefer one honest new surface over multiple partially-true wrappers.

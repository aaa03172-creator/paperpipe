# Frontend Worksurface UI Refinement Prompt

Status: Historical review prompt  
Date: 2026-03-22  
Owner: Repository maintainers  
Canonical parent: `docs/ux-review.md`

## Purpose

Capture a PaperPipe-grounded prompt for refining the main app work surfaces without drifting into landing-page redesign or frontend rewrites.

This is a reusable review-and-implementation prompt, not a new UI spec and not a replacement for the current viewer/workbench contracts.

## Local UI Anchors

Any future use of this prompt should anchor to these current local sources first:

- `AGENTS.md`
- `docs/ux-review.md`
- `docs/UX_REVIEW_TEMPLATE.md`
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- `docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `docs/UX_REVIEW_REPORT_paper-notes-viewer.md`
- `frontend/src/App.tsx`
- `frontend/src/styles/tokens.css`
- `frontend/src/index.css`
- `frontend/src/app/pages/TriageDashboard.tsx`
- `frontend/src/app/pages/PaperNotesListPage.tsx`
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
- `frontend/src/app/layouts/WorkbenchLayout.tsx`
- `frontend/package.json`

Local facts the prompt is designed to preserve:

- core app surfaces are `/`, `/papers`, `/papers/:slug`, and `/workbench/:paperId`
- current Paper Notes viewer/list/workbench routes already have active UX and layout contracts
- current visual system already uses `--pp-*` tokens and a restrained dark-first tone
- current frontend stack is Vite + React Router + TailwindCSS
- current work should focus on visual hierarchy, reading rhythm, copy cleanup, and usability refinement, not route or state-model redesign

## Prompt

```md
Task: refine PaperPipe's frontend so the core research workflow is clearer, more credible, and easier to use. This is an app-surface refinement task, not a landing-page redesign or a frontend rewrite.

Before making changes, inspect these local sources first and treat them as canonical:
- AGENTS.md
- docs/ux-review.md
- docs/UX_REVIEW_TEMPLATE.md
- docs/Lattice_Paper_Notes_Web_Viewer_Spec.md
- docs/UX_REVIEW_REPORT_paper-notes-list.md
- docs/UX_REVIEW_REPORT_paper-notes-viewer.md
- frontend/src/App.tsx
- frontend/src/styles/tokens.css
- frontend/src/index.css
- frontend/src/app/pages/TriageDashboard.tsx
- frontend/src/app/pages/PaperNotesListPage.tsx
- frontend/src/app/pages/PaperNoteDetailPage.tsx
- frontend/src/app/pages/AnalysisWorkbench.tsx
- frontend/src/app/layouts/WorkbenchLayout.tsx
- frontend/package.json

If you find related files in `docs/archive/`, use them only as historical context, not as source of truth.

Role:
You are a product-minded frontend designer and conservative UI engineer.
Your job is not to make the app flashier. Your job is to make the core research work surfaces clearer, calmer, and more trustworthy.

Primary scope:
Start with the core research surfaces only:
- `/`
- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`

Do not drift into meeting packs, method comparisons, chart packs, or unrelated routes unless a shared primitive is being refined and the change is clearly reusable.

Hard constraints:
1. Respect the current information architecture first.
2. Do not prioritize decoration over work support.
3. Do not import landing-page grammar into app screens.
4. Do not add hero sections, large marketing copy, aspirational taglines, or narrative product framing to the default app screens.
5. Do not default to stacked-card SaaS dashboard patterns.
6. Use layout, spacing, typography, alignment, and grouping to create hierarchy before adding new surfaces.
7. Only additive UI refinement is allowed.
8. No large refactor, no state-management redesign, no route redesign.
9. If unsure, clarify the existing surface instead of inventing a new one.
10. Reuse the existing `--pp-*` token system before adding any new tokens.
11. Preserve the existing font families unless a change is strongly justified; typography refinement should mainly come from scale, weight, rhythm, and spacing.
12. Prefer existing local UI primitives and current Tailwind patterns over introducing a new component system.

Current product context:
- biomedical literature research agent
- users need to search papers, filter/screen, read note detail, inspect PDF/evidence, review extraction results, check parser/evidence state, and open linked notes/exports
- the UI should support reading, comparison, judgment, and review
- the UI should feel restrained, credible, and high-signal, not promotional

Current route and layout context you must preserve:
- `frontend/src/App.tsx` defines the current route structure
- `/papers` is the list/search/filter surface
- `/papers/:slug` is the note detail + related/reference + structured state surface
- `/workbench/:paperId` is the PDF/evidence/timeline working surface
- `WorkbenchLayout` already defines the main three-column desktop structure and mobile controls pattern
- existing Paper Notes viewer/list contracts in `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md` remain authoritative

Visual-system constraints:
- audit the existing tokens in `frontend/src/styles/tokens.css` first
- refine existing canvas/surface/border/text/accent/status tokens before inventing a new theme
- typefaces: keep at most the current 2-family system
- accent color: keep restrained and singular in emphasis
- fixed and floating controls must never cover reading content, buttons, or evidence targets
- desktop and mobile must both remain stable

Content constraints:
- use product-language, not placeholder copy
- prefer direct task language such as:
  - Search papers
  - Screening queue
  - Selected evidence
  - Extraction review
  - Parser result
  - Linked notes
  - Export status
- remove internal/dev-only phrasing when it leaks into user-visible UI
- avoid words like:
  - AI-powered
  - seamless
  - next-generation
  - platform
  - solution
- do not let the first screen read like a generic SaaS card grid

Work method:
1. analyze the current screens before proposing changes
2. separate issues into:
   - visual hierarchy
   - information architecture
   - spacing
   - copy
   - interaction
   - responsiveness
3. prioritize the highest-leverage refinements that preserve structure
4. implement the smallest safe patch
5. explain before/after impact clearly

Repo-specific UX rule:
Before calling the UI work done, update the required UX review artifacts:
- `docs/UX_REVIEW_TEMPLATE.md`
- the matching flow report(s)
- if the work touches `/papers`, `/papers/:slug`, triage, rail, or workbench note-context surfaces, update:
  - `docs/UX_REVIEW_REPORT_paper-notes-list.md`
  - `docs/UX_REVIEW_REPORT_paper-notes-viewer.md`

Output format:
First, provide the required `/ux-review` output:
1. Quick Review (5 min)
2. Full Review (P0/P1/P2 prioritized)
3. BMAP diagnosis
4. B.I.A.S diagnosis
5. Peak-End design notes
6. Concrete changes
7. Ethics check results
8. Next PR-sized actions

Then provide the implementation brief:
1. Current UI diagnosis
2. Top 5 problems hurting quality
3. Visual direction
4. Design tokens to refine
5. Layout/hierarchy changes
6. Copy cleanup recommendations
7. Interaction polish recommendations
8. Responsive risks
9. Smallest safe implementation plan

Implementation preferences:
- keep the existing React + Tailwind stack
- minimize new dependencies
- prefer refining spacing/hierarchy/state expression over adding new components
- preserve the current three-pane / sheet-drawer reading model
- reduce card feeling where possible by using quieter sectioning and stronger typographic grouping

Required verification after changes:
- `cd frontend && npm run build`
- run the relevant Playwright coverage
- if the touched surfaces are the core app routes, prefer:
  - `cd frontend && npm run verify:frontend`
- verify explicitly that:
  - desktop/mobile layouts do not break
  - fixed/floating controls do not cover content or buttons
  - search, filters, detail panels, and section/tab transitions still work
  - the first screen does not read like a generic SaaS card grid
  - section headings communicate real task meaning
  - visual hierarchy is consistently expressed through type size, spacing, and alignment

Required close-out:
- What I did not redesign
- Safest next 3 UI improvements
- verification that was run
- any remaining visual or interaction risk
```

## Why This Prompt Shape Is Safer

Compared with a generic “make the frontend prettier” prompt, this version adds:

- explicit route, layout, and UX-review anchors before any design judgment
- a hard boundary around the current `/papers`, detail, and workbench contracts
- a warning against landing-page grammar, generic dashboard card grids, and unnecessary component/system churn
- an explicit requirement to refine the existing token system before inventing a new theme
- repo-specific verification and UX-review artifact updates as part of done criteria

## Known Current UI Smells Worth Targeting

This prompt is especially useful when current surfaces show issues like:

- internal/dev-facing copy leaking into user-visible headers
- weak hierarchy despite good underlying information structure
- card feeling overwhelming the reading surface
- route-to-route status language drifting
- mobile/desktop layout differences that increase scan cost

## Sources

- `AGENTS.md`
- `docs/ux-review.md`
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- `docs/UX_REVIEW_REPORT_paper-notes-list.md`
- `docs/UX_REVIEW_REPORT_paper-notes-viewer.md`
- `frontend/src/App.tsx`
- `frontend/src/styles/tokens.css`
- `frontend/src/index.css`
- `frontend/src/app/pages/TriageDashboard.tsx`
- `frontend/src/app/pages/PaperNotesListPage.tsx`
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
- `frontend/src/app/layouts/WorkbenchLayout.tsx`
- `frontend/package.json`

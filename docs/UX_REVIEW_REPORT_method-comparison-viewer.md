# UX Review Report: Method Comparison Viewer

Status: Active
Date: 2026-03-18
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Method Comparison viewer (`/method-comparisons`, `/method-comparisons/:comparisonId`)
- Goal action: Inspect an evidence-linked comparison snapshot and decide whether it is reusable as-is or needs manual review.
- Primary persona: Operator reviewing extracted study methods before downstream export or discussion.
- Current friction: Backend generation exists, but there is no direct viewer for row/field status, warning concentration, or per-cell evidence lineage.
- Success metric: Operator can open a saved comparison, identify conflict/missing cells, and trace non-missing values back to claimset lineage without leaving the viewer.
- Constraints: Read-only v0 lane; no edit UI, no document/table fallback, no new theme system, preserve `--pp-*` tokens and dark-first Lattice tone.

## Quick Review (5 min)
- The first read needs to answer three questions fast: what was compared, which cells are safe, and where evidence comes from.
- The index should act as a staging area, not a spreadsheet editor. Search and warning visibility matter more than dense controls.
- The detail page should keep the comparison table central, then place warnings and provenance nearby so review loops stay short.

## Full Review
### P0
- Make conflict and missing cells visually obvious in the main grid. If the viewer buries them in a secondary panel, the operator will over-trust the comparison.
- Keep the page read-only. Editing before the storage and provenance rules settle would blur whether a value came from claimset extraction or a manual override.

### P1
- Provide an evidence trace section that groups by paper and field, not by raw evidence id. The operator thinks in cells first.
- Keep CSV export reachable from the detail header so the user does not have to leave the review surface to hand off a snapshot.
- CSV export should stay route-backed with attachment semantics in real mode, and note handoff should resolve only canonical paper-note candidates rather than arbitrary markdown files.

### P2
- Show source-priority and warning counts in the index cards so the operator can triage before opening each comparison.
- Offer direct links back to `Paper Notes` when a row has a resolved `paper_slug`.

### Full Review Coverage
- 6P storyboard context: Problem is scattered method extraction review; emotion is low trust in derived tables; action is open a comparison; struggle is locating conflicts and lineage; attempt is scanning rows then checking evidence; happy ending is a reusable comparison snapshot with clear review boundaries.
- BMAP: Motivation is high because comparison tables are downstream assets; ability drops when provenance is hidden; prompt should bring warnings and evidence trace into the first viewport.
- B.I.A.S: Block comes from unclear safe-to-reuse state; interpret improves when status tones are attached to each cell; act improves with direct CSV export and note links; store improves when the same table and trace layout repeat across comparisons.
- Peak-End: Peak should be immediate visibility into conflicts; pit is a wall of undifferentiated cells; transition is from index card to detail table; end is a clear warning summary plus export path.
- Ethics: The viewer must not overstate truth. Missing and conflict cells should stay explicit, and the UI should not imply that table completeness equals scientific confidence.

## BMAP diagnosis
- Motivation: High. Operators already need these comparisons for packs, notes, and manual synthesis.
- Ability: Medium. Raw JSON and CSV files are too indirect for routine review.
- Prompt: Weak before this viewer. There was no obvious place to inspect comparison quality after generation.

## B.I.A.S diagnosis
- Block: No dedicated read surface for comparison QA.
- Interpret: Users need per-cell status and warnings, not just a stored artifact id.
- Act: The next action is usually export or reopen a source note; the viewer should support both without implying editability.
- Store: Repeated layout across comparisons builds confidence in how to review them.

## Peak-End design notes
- Peak: Show status-coded cells inside the primary table.
- Pit: Avoid spreadsheet-style density that hides provenance.
- Transition: Keep index cards lightweight, then shift to a table-plus-trace layout on detail.
- End: Finish the page with warnings and source-discipline notes so the operator leaves with the right trust boundary.

## Concrete changes
- Route level: add `/method-comparisons` index and `/method-comparisons/:comparisonId` detail routes.
- Component level: show a horizontally scrollable comparison grid with status badges, evidence-ref counts, and note links per row.
- Copy level: label the viewer as `claimset-only v0` and explain that missing cells reflect absent deterministic evidence, not failed rendering.
- Default-action level: primary action on index is `Open comparison`; primary action on detail is `Export CSV`, with review context remaining visible.
- Runtime contract: real-mode CSV export should come from the backend attachment route, and `Open note` should only target notes that satisfy the paper-note candidate rules used by the notes viewer.

## Ethics check results
- Regret: Low if conflicts and missing values remain visible and export stays framed as a snapshot, not a validated truth table.
- Black Mirror: Risk appears if the UI quietly normalizes conflict cells into polished outputs. Countermeasure is explicit conflict styling and warning copy.
- In Real-Life: A reviewer should be able to explain why a cell exists and where it came from. The viewer should make that answer trivial.

## Next PR-sized actions
- Add the read-only index/detail viewer with warning-forward cards and evidence trace.
- If real users start reusing CSV outputs, add a thin “open source note” handoff for each row before any edit features.
- Delay document/table fallback until claimset-only review proves stable on real comparisons.

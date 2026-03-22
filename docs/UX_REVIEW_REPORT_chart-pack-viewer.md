# UX Review Report: Chart Pack Viewer

Status: Active
Date: 2026-03-20
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Chart Pack viewer (`/chart-packs`, `/chart-packs/:chartPackId`)
- Goal action: Inspect a saved chart pack and decide whether its CSV/spec artifacts are safe to reuse downstream.
- Primary persona: Operator reviewing deterministic chart outputs before handoff into notes, slides, or external plotting work.
- Current friction: Backend `chart_pack` generation exists, but there is no direct viewer for chart scope, warning concentration, source lineage, or saved CSV/spec artifacts.
- Success metric: Operator can open a saved chart pack, understand what each chart represents, inspect warnings and transforms, and export CSV/spec payloads without leaving the viewer.
- Constraints: Read-only v0 lane; no inline editing, no bespoke chart rendering engine, preserve `--pp-*` tokens and dark-first Lattice tone, keep the viewer framed as artifact QA rather than statistical truth validation.

## Quick Review (5 min)
- The first read needs to answer three questions quickly: what charts are in the pack, which ones carry warnings, and what source artifact each chart came from.
- The index should prioritize search plus warning visibility over dense filters or chart thumbnails.
- The detail page should keep chart cards central, then place caution notes, source refs, and markdown nearby so the operator can review before export.

## Full Review
### P0
- Keep the viewer read-only. Editing chart definitions or numbers inside the viewer would blur whether a value came from saved artifacts or operator intervention.
- Surface pack warnings and per-chart warnings in the primary viewport. If warnings only appear after opening downloads, users will over-trust clean-looking tables.

### P1
- Show chart source refs, transform steps, and a snapshot preview together on each chart card so the operator does not have to inspect raw JSON to understand the bundle.
- Keep CSV/spec export on the same card as the preview. The handoff should happen from the review surface, not from a secondary file browser.
- In mock mode, downloads should still work locally from saved payloads so the interaction model matches real mode.

### P2
- Show render environment and pack-level caution notes in the sidebar to reinforce the bounded, template-driven nature of the lane.
- Keep a lightweight markdown preview at the bottom because the saved markdown is part of the pack contract and often the easiest handoff artifact to scan.

### Full Review Coverage
- 6P storyboard context: Problem is derived chart bundles becoming opaque once saved; emotion is low trust in chart polish without lineage; action is open a chart pack; struggle is understanding warnings, transforms, and export scope; attempt is inspect cards then export; happy ending is a reusable pack whose limits are obvious.
- BMAP: Motivation is high because chart packs are downstream communication artifacts; ability drops when preview and lineage are split across files; prompt should bring warnings and exports into the first screen.
- B.I.A.S: Block comes from hidden lineage and unclear source scope; interpret improves when chart cards show source, transforms, preview, and warnings together; act improves with direct CSV/spec downloads; store improves when every pack uses the same card structure.
- Peak-End: Peak should be immediate recognition of chart purpose and warning state; pit is a file-list-only viewer; transition is from index card to chart card detail; end is explicit caution notes plus export actions.
- Ethics: The viewer must not imply that charts are validated scientific conclusions. Warnings, source refs, and caution notes should remain prominent, and chart polish should not conceal skipped or excluded data.

## BMAP diagnosis
- Motivation: High. Saved chart packs are handoff artifacts and need a fast review loop.
- Ability: Medium before this viewer. Raw JSON/CSV/spec files are inspectable but too indirect for routine QA.
- Prompt: Weak before this viewer. There was no dedicated place to review a pack before export.

## B.I.A.S diagnosis
- Block: No dedicated read surface for chart-pack QA.
- Interpret: Users need to see chart purpose, source, transforms, and warnings together.
- Act: The next action is usually export CSV/spec or pass the pack onward; the viewer should support that directly.
- Store: Repeated chart-card structure makes future pack review predictable.

## Peak-End design notes
- Peak: A chart card should show its template, warning state, and snapshot preview immediately.
- Pit: Avoid over-designed chart canvases that feel authoritative without exposing lineage.
- Transition: Keep the index lightweight, then move into a chart-card review layout on detail.
- End: Finish the detail page with caution notes and markdown preview so users leave with the correct trust boundary.

## Concrete changes
- Route level: add `/chart-packs` index and `/chart-packs/:chartPackId` detail routes.
- Component level: render chart cards with source summary, transforms, warning chips, snapshot preview tables, and direct CSV/spec downloads.
- Copy level: frame the viewer as a saved artifact review surface, not as a chart authoring tool.
- Default-action level: primary action on index is `Open chart pack`; primary actions on detail are per-chart `Export CSV` and `Open spec JSON`.
- Runtime contract: real-mode downloads should use backend attachment routes; mock mode should keep download semantics through saved in-memory payloads.

## Ethics check results
- Regret: Low if warning states and caution notes remain visible before export.
- Black Mirror: Risk appears if the interface renders charts as polished truth without showing skipped-data or template bounds. Countermeasure is warning-forward cards and explicit source summaries.
- In Real-Life: A reviewer should be able to explain what a chart measures, which artifact it came from, and why it is safe or unsafe to reuse. The viewer should make that trivial.

## Next PR-sized actions
- Add a real-backend smoke that opens a generated chart pack and exercises one CSV/spec export path.
- If users start asking for visual plots, gate that behind a separate RFC instead of smuggling chart rendering into this review surface.
- Consider row-level source-paper handoff only after operators confirm they need to jump from chart cards into notes.

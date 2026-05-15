# UX Review Report: Obsidian Lattice Return Link

Status: Active UX review report
Date: 2026-05-14
Owner: Runtime/product maintainers

## Header
- Screen/Flow: Obsidian synced paper note -> Lattice workbench return path
- Goal action: open the canonical Lattice review surface from a mirrored Obsidian note
- Primary persona: single-operator biomedical researcher reviewing saved paper notes
- Current friction: Obsidian notes are readable mirrors, but they do not provide a direct path back to the evidence-linked runtime surface.
- Success metric: synced Obsidian notes include one stable Lattice review link generated from `paper_id`.
- Constraints: Obsidian remains a mirror/export layer, not a canonical truth owner; links must not expose private filesystem paths or backend secrets.

## Quick Review (5 min)
- First meaningful success: a researcher opens an Obsidian paper note and can return to the Lattice workbench with one click.

## Full Review
### P0
- Keep the link pointed at canonical Lattice state (`/ui/workbench/{paper_id}`), not at a local file path or detached export.
- Keep the Obsidian note explicitly described as a mirror so the link does not promote markdown to source-of-truth status.

### P1
- Use one primary action, `Review in Lattice`, instead of a bundle of competing links.
- Generate the link inside the idempotent agent marker block so future syncs replace it safely.

### P2
- Future work may add secondary links to paper detail or source PDF only if those routes are stable and do not crowd the note.

### Full Review Coverage
- 6P storyboard context: the user is reading an Obsidian note, realizes they need evidence state or artifact actions, and returns to Lattice without searching for the paper again.
- BMAP: motivation is high at the moment of review; ability improves because one link removes route hunting; the link is the timely prompt.
- B.I.A.S: one link avoids choice overload, the label explains the benefit, the action is direct, and the boundary note preserves trust.
- Peak-End: the peak is landing in the workbench with evidence and operational state intact; the end is confidence that the Obsidian note is not a dead export.
- Ethics: the link saves time, respects attention, and avoids nudging users toward external SaaS or hidden data movement.

## BMAP diagnosis
- Motivation: high when a reader wants to inspect evidence, repair artifacts, or generate downstream outputs.
- Ability: one local URL is easier than manually finding the matching paper in the app.
- Prompt: the link appears near the synced AI analysis block, where the review need naturally arises.

## B.I.A.S diagnosis
- Block: avoid a large command panel in the note.
- Interpret: `Review in Lattice` is clearer than a generic app link.
- Act: link directly to `/ui/workbench/{paper_id}`.
- Store: the product feels recoverable because Obsidian is no longer a one-way export.

## Peak-End design notes
- Peak: opening the workbench and seeing the same paper state, evidence, and artifact actions.
- Pit: stale exported notes that do not reveal where the live review state lives.
- Transition: the link sits in the generated marker block and travels with each sync.
- End: the operator remembers Obsidian as a readable mirror with a reliable return path.

## Concrete changes
- Add a `Lattice Return Path` block to generated Obsidian sync markdown.
- Link to `/ui/workbench/{paper_id}` using a configurable public base URL.
- Keep the boundary copy inside the generated block: Obsidian is a mirror; Lattice owns canonical paper state.

## Ethics check results
- Regret: pass; the feature shortens the operator's path and does not hide data movement.
- Black Mirror: pass with caution; the link must remain local/public-base controlled and avoid secrets or private paths.
- In Real-Life: pass; a helpful assistant would leave a clear way back to the live workspace.

## Next PR-sized actions
1. Add the generated return link to Obsidian sync markdown.
2. Add targeted backend tests for mirror and sync output.
3. Document the boundary in viewer/runtime docs.

## Verification
- Targeted backend tests for `/obsidian/mirror` and `/obsidian/sync`.
- Docs lint after docs updates.

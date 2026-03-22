# UX Review Report: Image Evidence Viewer

Status: Active
Date: 2026-03-22
Owner: Lattice runtime maintainers
Canonical parent: `docs/ux-review.md`

## Header
- Screen/Flow: Image Evidence viewer (`/image-evidence`, `/image-evidence/:imageEvidenceId`)
- Goal action: Inspect a saved image-evidence bundle and decide whether its raw identity, derived outputs, and handoff metadata are trustworthy enough for downstream reuse.
- Primary persona: Operator reviewing microscopy or figure-adjacent image metadata before using it in notes, packs, or external viewer handoff.
- Current friction: Backend `image_evidence` registration exists, but there is no direct viewer for raw-vs-derived separation, checksum/missing-file warnings, view state, or handoff metadata.
- Success metric: Operator can open a saved image-evidence bundle, understand what the raw source is, see whether the bundle is warning-heavy, inspect derived-output lineage, and hand off to a note or external viewer without confusing metadata with validated claim truth.
- Constraints: Read-only v0 lane; no embedded image canvas, no external process launch, preserve `--pp-*` tokens and dark-first Lattice tone, keep the viewer framed as metadata QA rather than image interpretation.

## Quick Review (5 min)
- The first read needs to answer three questions quickly: what raw source this bundle points to, whether anything about it is warning-heavy, and whether derived outputs still preserve explicit lineage.
- The index should prioritize search and warning visibility over thumbnails or gallery layout.
- The detail page should keep source identity, warnings, and derived-output lineage in the main viewport, then put metadata, view state, and handoff targets in a supporting rail.

## Full Review
### P0
- Keep the viewer read-only and metadata-first. Rendering image pixels or editing overlays inside this surface would blur the raw/derived boundary that the backend contract is trying to protect.
- Surface warning state in the primary viewport. If checksum mismatch, missing local file, or representative-only notes are buried below the fold, users will over-trust the saved bundle.

### P1
- Show raw source identity, paper linkage, checksum, and content format together so the operator can orient without opening JSON files.
- Keep derived outputs grouped with their provenance fields: kind, tool, created-by, bundle path or external ref, and optional view-state linkage.
- If a paper note slug exists, provide direct handoff into `/papers/:slug` so the image-evidence lane stays connected to the current paper-note review loop.

### P2
- Put view state and handoff targets in a side rail rather than the hero position. They matter, but they are secondary to raw identity and warning status.
- Use copy that explicitly says this is a metadata review surface, not an image-analysis viewer.

### Full Review Coverage
- 6P storyboard context: Problem is that saved image metadata becomes opaque once registered; emotion is low trust in representative images without provenance; action is open an image-evidence bundle; struggle is separating raw identity from derived outputs and handoff metadata; attempt is inspect warning/source/lineage cards; happy ending is a bounded image bundle whose limits are obvious before reuse.
- BMAP: Motivation is high because image-backed artifacts are easy to over-trust; ability drops when raw source, derived outputs, and handoff metadata are split across files; prompt should bring warning state and raw-vs-derived separation into the first screen.
- B.I.A.S: Block comes from opaque metadata bundles and absent trust cues; interpret improves when source identity, warnings, and derived lineage are shown together; act improves with direct note handoff and clear external-viewer metadata; store improves when every bundle uses the same summary/detail rhythm.
- Peak-End: Peak should be immediate recognition of source kind and warning state; pit is a gallery-like surface that implies image truth; transition is from saved-bundle index to metadata-rich detail; end is a trust-boundary card that reminds the operator what this viewer does not validate.
- Ethics: The viewer must not imply that a registered image proves a claim, that representative crops are exhaustive evidence, or that external-viewer handoff means the current runtime has validated the underlying pixels.

## BMAP diagnosis
- Motivation: High. Image evidence is likely to be reused downstream, so trust calibration matters.
- Ability: Medium before this viewer. Reading `image_evidence.json` and adjacent files directly is possible but too indirect for routine review.
- Prompt: Weak before this viewer. There was no dedicated place to review bundle warnings and raw/derived separation before handoff.

## B.I.A.S diagnosis
- Block: No dedicated read surface for image-evidence QA.
- Interpret: Users need to see raw source, warning state, derived outputs, and handoff metadata together.
- Act: The next actions are usually open the note, inspect the handoff target, or decide not to reuse the bundle.
- Store: Repeated bundle-summary and derived-output cards make future inspection predictable.

## Peak-End design notes
- Peak: The first detail card should immediately show source kind, content format, and warning count.
- Pit: Avoid image-gallery styling that makes representative outputs feel like validated findings.
- Transition: Keep the index lightweight, then move into source-first detail.
- End: Finish with an explicit trust-boundary card so users leave with the correct mental model.

## Concrete changes
- Route level: add `/image-evidence` index and `/image-evidence/:imageEvidenceId` detail routes.
- Component level: render bundle summary, warning cards, derived-output cards, linked references, view-state rail, and handoff rail.
- Copy level: frame the viewer as saved metadata review, not image interpretation.
- Default-action level: primary action on index is `Open bundle`; primary detail handoff is `Open note` when a paper slug exists.
- Runtime contract: mock mode should keep the same index/detail interaction without inventing unsupported binary rendering.

## Ethics check results
- Regret: Low if warnings and trust-boundary copy stay visible.
- Black Mirror: Risk appears if the viewer looks like a microscopy tool and causes users to infer pixel-level validation. Countermeasure is a metadata-first layout and explicit non-goals copy.
- In Real-Life: A reviewer should be able to explain where the raw image lives, what derived outputs were produced, and whether this bundle has any warning state without touching the filesystem.

## Next PR-sized actions
- Add a mock-backed read-only viewer with search, warning-forward detail, and note handoff.
- If real usage justifies it, add a backend smoke that opens a registered image-evidence bundle and checks note-handoff consistency.
- Defer any visual image preview or viewer-launch behavior into a separate RFC lane.

# UI Reference Research: Evidence Reader

Status: Non-canonical research note
Date: 2026-05-10
Source tool: Lazyweb MCP, developer-local Codex config
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Related operating note: `docs/ui_references.md`

## Scope

Target PaperPipe surfaces:
- paper detail page
- evidence-linked reader
- figure/table viewer
- artifact review and approval flow

Research goal:
- find UI patterns that can help PaperPipe feel like a real research reading and verification workspace, not a generic SaaS dashboard.

Data boundary:
- no PaperPipe PDF, paper title, private note, lab context, screenshot, local path, or user data was sent.
- raw Lazyweb signed screenshot URLs are not stored in this report.
- this report is not a product requirement, biomedical evidence source, canonical state, or runtime dependency.

## Curation Metadata

Sanitized prompt stance:
- use only generic UI references
- do not use PaperPipe data, PDFs, paper titles, lab names, screenshots, user identifiers, or local paths
- output non-canonical patterns, anti-patterns, and PR-sized implications

Layer classification:
- Lazyweb output: review/support artifact
- proposed PaperPipe changes: must be classified separately before implementation
- no canonical structured state, biomedical source, raw memory, runtime dependency, or user-facing export is created by this report

Recommended disposition:
- paper detail / evidence-linked reader: partial adopt
- figure/table/image evidence viewer: partial adopt
- artifact review / approval flow: partial adopt with guardrails
- generic SaaS dashboard and marketing references: reject
- product runtime integration: reject

## Queries Run

```text
desktop evidence linked reading workspace left outline center document right claims evidence provenance panel scientific document review
```

```text
desktop document review annotation evidence citations side panel legal due diligence source provenance claims
```

```text
desktop data table figure viewer metadata warnings provenance derived outputs review before export scientific analytics QA
```

```text
desktop review approval workflow generated artifact draft reviewed state provenance export guarded actions
```

## Useful References

| Reference | Why it is useful | PaperPipe implication | Do not copy |
| --- | --- | --- | --- |
| Benchling BioResearch product preview | Shows scientist-oriented workspace with left navigation, central protocol/document surface, and surrounding registration/workbench context. | Supports PaperPipe's existing rail + document + artifact layout direction for Workbench. | Marketing hero framing, signup CTAs, broad lab-platform positioning. |
| Parley RFE/RFx dashboard | Shows document-response/review workflow with searchable request evidence surfaces. | Useful for review queues where documents, requests, and evidence status need to stay scannable. | Sales workflow language and client-response framing. |
| Grammarly Citation Finder / Citation Generator | Shows source/citation work close to writing, including a side panel for generated citations and copy actions. | Useful as a pattern for keeping citations near notes while separating generated assistance from accepted evidence. | Student-writing framing, one-click citation trust, promotional onboarding. |
| Lamin use-cases screenshots | Emphasizes data provenance, workflows, notebooks, and generated Python reports. | Useful vocabulary for provenance-first scientific workspaces and report generation lanes. | Treating generated reports as canonical without review. |
| Metaplane data CI/CD | Shows test reports and quality gates before merging data changes. | Strong analogy for PaperPipe quality gates, stale state, and guarded promotion/export. | CI/CD jargon as user-facing reading UI. |
| Metabase Data Studio | Dense analytics workspace with sidebar navigation, data/model concepts, and SQL/editor affordances. | Useful for table/figure artifact review density and tool navigation. | Generic BI dashboard structure as the paper reader default. |
| Zeplin workflow approvals | Shows approval request fields, assignee, due date, design attachment, and managed approvals. | Useful for explicit artifact review ownership and approval metadata. | Turning PaperPipe into a generic approval engine. |
| Dropbox Replay | Shows media review with timestamped comments, annotations, versions, and approval workflow. | Useful for figure/image evidence review: annotations should attach to viewport/version context. | Media-production visual language and external sharing emphasis. |
| GitHub code review | Provides mature patterns for diff-scoped review, comments, required checks, and protected merge. | Useful analogy for "generated artifact cannot promote until checks pass." | Developer-centric diff terminology in researcher-facing screens. |

## Low-Signal Or Rejected References

| Reference | Reason |
| --- | --- |
| Glean Canvas / Confluence AI / Asana creative production | Mostly marketing pages. Some review/export language exists, but little direct paper-reading value. |
| Scribd document category pages | Useful for library browsing and saved/bookmark affordances only. Not enough evidence/provenance workflow. |
| OpenAI research index pages | Useful for filtering and research feed layout, but not a document evidence workspace. |
| Causaly result | Query returned a dashboard-ish marketing surface, not enough claim/evidence UI detail. |
| Blank or unrelated screens from Churchome, CodeCrafters, Citizens Bank, MLB | Rejected as retrieval noise. |

## Patterns To Consider

1. Keep the current three-zone reader shape.
   - Left: outline, section navigator, search/filter context.
   - Center: markdown/PDF/reading body.
   - Right: saved state, claims, evidence, references, operator note.
   - This aligns with the current PaperPipe detail page and Workbench rather than arguing for a redesign.

2. Make generated versus reviewed state visible at the point of action.
   - Useful references: GitHub checks, Metaplane data tests, Zeplin approvals.
   - PaperPipe language should stay lane-specific: saved state, unresolved, grounded, stale, draft-like, reviewed.

3. Treat citation/source panels as nearby support, not as truth owners.
   - Useful reference: Grammarly citation side panel.
   - PaperPipe should keep citations and references close to the reader while routing truth through canonical structured state and upstream evidence.

4. Use provenance cards for figure/table artifacts.
   - Useful references: Lamin, Metabase, Dropbox Replay.
   - For PaperPipe, a figure/table viewer should foreground source ref, derived output, warning state, viewport/version context, and reuse boundary.

5. Avoid marketing-style UI imports.
   - Many Lazyweb results were landing pages.
   - PaperPipe should extract interaction structure only, not hero copy, conversion CTAs, gradients, or generic SaaS card galleries.

## Product Psychology Notes

### Quick Review

- Choice count: keep research actions fewer than six per panel.
- Benefit: first screen should answer "what evidence can I verify now?"
- Next action: prioritize "open review", "inspect evidence", "reopen source", or "save operator note" over broad dashboards.
- Feedback: every save, queue, sync, or review action needs immediate state feedback.
- Ethics: do not imply AI-generated claims or citations are reviewed evidence until the canonical state supports that.

### Full Review

P0:
- Do not send private research content to external UI search tools.
- Do not let Lazyweb output become canonical product requirements.
- Do not loosen artifact/state/provenance boundaries for prettier UI.

P1:
- Preserve the existing `--pp-*` visual system and dark-first Lattice tone.
- Reuse current paper detail and Workbench layout before adding new primitives.
- Make draft/reviewed/grounded/unresolved state more legible where operators act.

P2:
- Use references to tune density, panel hierarchy, labels, and empty/error states.
- Keep screenshots and visual inspiration local or curated; do not commit raw dumps.

6P storyboard context:
- Problem: researcher must read a paper and decide whether a claim is actually supported.
- Emotion: wary, time-constrained, and allergic to unsupported summaries.
- Action: opens paper detail or Workbench.
- Struggle: evidence, generated notes, references, and artifacts are split or too easy to over-trust.
- Attempt: reader surfaces canonical state, claim/evidence links, provenance, and guarded actions together.
- Happy ending: researcher can say "I know what supports this claim, what is unresolved, and what can be reused."

BMAP:
- Motivation: high when the paper matters to an active project or meeting.
- Ability: improves when claims, evidence, sections, and references sit near the reading surface.
- Prompt: right prompts are review-state badges and explicit next actions near the artifact, not generic CTA banners.

B.I.A.S:
- Block: avoid dense undifferentiated panels; group by read, verify, reuse.
- Interpret: use state language tied to evidence confidence and provenance.
- Act: make the smallest safe next action obvious.
- Store: record review/save/sync feedback so trust accumulates through visible state.

Peak-End:
- Peak: finding a claim's source and status without losing reading context.
- Pit: ambiguous generated artifact that looks final.
- Transition: reading -> review -> reuse/export should show state changes.
- End: close the loop with saved state or explicit unresolved status.

Ethics:
- Regret: unsafe if external research leaks paper/lab content.
- Black Mirror: unsafe if polished generated artifacts obscure uncertainty.
- In Real-Life: the UI should behave like a careful research assistant, not a salesperson.

## PR-Sized Next Actions

1. Paper detail page: tune panel hierarchy so saved state, claim/evidence review, references, and operator notes read as one evidence workflow without changing contracts.
2. Image/figure evidence viewer: add or refine provenance-first grouping for source, warnings, derived outputs, and reuse boundary.
3. Artifact review surfaces: audit labels for draft-like/generated/reviewed/stale state and ensure guarded actions remain explicit.

## Final Recommendation

Continue using Lazyweb only as a developer-local reference research tool. The first pilot produced a few useful analogies, especially from Benchling, Lamin, Metaplane, Zeplin, Dropbox Replay, GitHub review, and citation side panels, but the retrieval set also contained many marketing or unrelated pages.

The valuable pattern is not a new UI style. It is a confirmation that PaperPipe should keep moving toward evidence-first, provenance-visible, review-state-aware workspace screens using the existing Lattice architecture.

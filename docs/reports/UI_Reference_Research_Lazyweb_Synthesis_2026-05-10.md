# UI Reference Research: Lazyweb Synthesis

Status: Non-canonical research synthesis
Date: 2026-05-10
Source tool: Lazyweb MCP, developer-local Codex config
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Operating note: `docs/ui_references.md`
Related pilot: `docs/reports/UI_Reference_Research_evidence_reader_2026-05-10.md`

## Executive Summary

Recommendation: partial adopt.

Lazyweb is useful as a developer-only UI reference research tool for PaperPipe, especially for evidence-linked readers, provenance-heavy artifact viewers, review-state rails, and approval-flow anti-patterns.

It should not be installed as a PaperPipe runtime dependency, FastAPI integration, frontend package, backend service, or product skill. It should stay in local Codex/Cursor MCP config only, with tokens and raw output outside git.

## Capability Summary

Observed useful capability:
- generic web UI reference discovery
- screenshot-backed pattern comparison
- retrieval of real product analogies for dense review surfaces
- quick collection of approval, provenance, annotation, dashboard, and reader patterns

Observed limits:
- many results are marketing pages or generic SaaS surfaces
- references require PaperPipe translation before use
- raw screenshot URLs and generated reports are not durable product artifacts
- output can inspire UI hierarchy but cannot supply biomedical evidence, canonical state, or product requirements

## Disposition Matrix

| Area | Disposition | PaperPipe decision |
| --- | --- | --- |
| Paper detail / evidence-linked reader | Partial adopt | Use references to tune panel order and evidence workflow, not to redesign the reader. |
| Figure / image evidence viewer | Partial adopt | Put trust boundary and provenance before reuse/handoff controls. |
| Claim/evidence graph | Defer | Useful future research area, but no graph UI change should happen without a concrete route/component and state contract. |
| Research workspace dashboard | Defer | Keep Home paper-first. Avoid project-management dashboards until there is a runtime-backed project model. |
| Notes / star / sticker / annotation | Partial adopt with guardrails | Keep compact paper-level markers. Defer passage/figure annotation until a first-class anchor model exists. |
| Artifact review / approval flow | Partial adopt with guardrails | Use state-first review patterns. Do not add approved/promoted states without schema/API ownership. |
| Product runtime integration | Reject | No runtime dependency, service integration, committed MCP config, or product skill. |

## Security And Config Decision

Developer-only:
- local Codex or Cursor MCP config outside the repository
- local token storage such as `~/.lazyweb/lazyweb_mcp_token` or `LAZYWEB_MCP_TOKEN`
- ignored raw research output under `.lazyweb/`

Repository-safe:
- curated non-canonical summaries in `docs/reports/`
- operating guidance in `docs/ui_references.md`
- UX review checkpoints that restate reference findings in PaperPipe terms

Not allowed:
- committed MCP config
- bearer tokens or install tokens
- raw Lazyweb screenshot dumps
- PaperPipe paper PDFs, paper titles, private notes, lab context, local paths, or user identifiers in external queries
- direct promotion of Lazyweb findings into product requirements

## Prompt And Artifact Contract

All future Lazyweb prompts must be sanitized and must state:
- use only generic UI references
- do not use PaperPipe data, PDFs, paper titles, lab names, screenshots, user identifiers, or local paths
- output a non-canonical report
- include useful patterns, anti-patterns, and PR-sized implications

Curated output must include:
- target PaperPipe route or flow
- source tool and date
- sanitized prompt used
- reference source labels
- useful pattern
- what not to copy
- evidence/provenance/state impact
- layer classification for any proposed PaperPipe change
- disposition: adopt, partial adopt, defer, or reject

## Product Psychology Review

### Quick Review

- Choice count: keep reference-derived actions sparse and evidence-scoped.
- Benefit: every adopted pattern must help the user read, verify, recover, or safely reuse paper-linked evidence.
- Next action: prioritize open review, inspect evidence, reopen source, save marker, or guarded export over generic dashboard CTAs.
- Feedback: state changes need visible confirmation and should not imply scientific validation without upstream support.
- Ethics: do not leak private research content or overstate generated artifact readiness.

### Full Review

P0:
- Keep Lazyweb developer-only and non-runtime.
- Keep private research content out of external UI searches.
- Keep canonical structured state and evidence provenance as the product truth.
- Do not add approval, promotion, or annotation states without a PaperPipe schema/API contract.

P1:
- Use Lazyweb only to compare layout hierarchy, state wording, dense review patterns, and anti-patterns.
- Store decisions in `docs/ui_references.md`, dated reports, or matching UX review reports.
- Translate every reference into PaperPipe route/component/layer language before implementation.

P2:
- Prefer docs-only fit checks when the current UI already matches the evidence workflow.
- Keep raw research output ignored and avoid committing raw screenshot dumps.

### Full Review Coverage

6P storyboard context:
- Problem: PaperPipe UI can drift toward generic SaaS polish if references are copied directly.
- Emotion: researchers need confidence that source, evidence, and generated artifacts remain distinct.
- Action: developer researches UI references before a PR.
- Struggle: useful UI patterns are mixed with marketing pages and unrelated dashboards.
- Attempt: use sanitized prompts, curated summaries, and UX checkpoints.
- Happy Ending: the UI improves only where it strengthens evidence workflow and provenance.

BMAP:
- Motivation is high because PaperPipe needs real UI references for dense research workflows.
- Ability improves when the allowed prompts, output artifacts, and adoption rules are explicit.
- Prompt is `docs/ui_references.md` plus the matching UX review report before any UI change.

B.I.A.S:
- Block: reject generic SaaS dashboards and decorative sticker systems.
- Interpret: restate every pattern as paper detail, evidence review, marker recovery, or artifact handoff.
- Act: implement only PR-sized changes with tests when a concrete UI issue exists.
- Store: keep non-canonical research notes separate from canonical product specs and runtime state.

Peak-End:
- Peak: a reference confirms a better state/provenance hierarchy without forcing a redesign.
- Pit: a polished external UI pattern becomes a fake product requirement.
- Transition: Lazyweb search -> curated report -> UX checkpoint -> scoped PR.
- End: PaperPipe keeps local-first evidence ownership while improving its research workflow UI.

Ethics:
- Regret: lower when private data never leaves the local workspace.
- Black Mirror: lower when generated artifacts cannot appear approved through styling alone.
- In Real-Life: the tool behaves like a careful design researcher, not a product authority.

## Linked Decisions

- `docs/ui_references.md`: developer-only policy, safe prompts, expected artifacts, security rules, adoption rule.
- `docs/PaperPipe_UI_Redesign_Document_Map.md`: reading order, document ownership, current decisions, open gaps, and implementation gate.
- `docs/PaperPipe_Page_Architecture.md`: page family boundaries, route intent, action hierarchy, Settings/Local Secrets, and assistant placement.
- `docs/PaperPipe_Extracted_Data_Workflow_Map.md`: extracted-data reuse, duplicate-use rules, relationship summaries, and stale-impact guardrails.
- `docs/UX_REVIEW_REPORT_paper-notes-viewer.md`: paper detail hierarchy and marker-scope decisions.
- `docs/UX_REVIEW_REPORT_image-evidence-viewer.md`: trust boundary before reuse/handoff context.
- `docs/UX_REVIEW_REPORT_meeting-pack-trace.md`: review state before draft maintenance or sharing.
- `docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`: review state before version history navigation.
- `docs/UX_REVIEW_REPORT_triage-dashboard.md`: research dashboard references deferred in favor of paper-first home.
- `docs/UX_REVIEW_REPORT_paper-annotation-marking.md`: sticker/annotation references constrained to paper-level marker semantics.
- `docs/UX_REVIEW_REPORT_artifact-family.md`: approval-flow references constrained by artifact-family review state and schema ownership.

## Final Recommendation

Keep Lazyweb in local MCP config only. Use it to collect generic UI references, then preserve only curated, non-canonical summaries in docs.

Do not add Lazyweb to PaperPipe runtime, CI, API routes, package dependencies, source skills, or product workflows.

The strongest adopted pattern is not visual style. It is the discipline of putting evidence state, provenance, trust boundary, and guarded next actions before polished downstream reuse.

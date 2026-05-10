# UI Reference Research

Status: Active operating note
Date: 2026-05-10
Owner: Frontend/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose

PaperPipe may use external UI reference tools, including Lazyweb, to study how real products arrange complex reading, review, annotation, and approval surfaces.

These references are design research inputs only. They are not product requirements, biomedical evidence, canonical state, runtime dependencies, or approval artifacts.

## Boundary

Lazyweb and similar tools are allowed only as developer-local research tools. They are not runtime infrastructure.

Allowed:
- local Codex, Cursor, or other developer MCP configuration outside this repository
- generic UI pattern searches that do not include private paper, lab, user, PDF, or note content
- ignored local research output under `.lazyweb/`
- curated summaries promoted into `docs/reports/` or this note when they are clearly labeled non-canonical

Not allowed:
- PaperPipe runtime dependency
- FastAPI, frontend package, backend service, or `src/skills/` integration
- committed MCP config, bearer tokens, generated Lazyweb reports, or raw screenshot dumps
- external queries containing user PDFs, paper note bodies, unpublished lab material, secret keys, private file paths, or identifiable research context
- promoting a reference result directly into a product requirement without a separate PaperPipe review decision

## Layer Classification

Lazyweb research output is a review/support artifact.

It is not:
- raw source
- raw memory
- compiled biomedical knowledge
- canonical structured state
- user-facing export

If a UI proposal derived from references changes evidence handling, provenance, artifact review, or response shape, classify the actual PaperPipe change separately before implementation.

## Safe Research Targets

Use external references for visual and interaction patterns around:
- paper detail pages
- evidence-linked readers
- claim or evidence graphs
- figure and table viewers
- research workspace dashboards
- notes, star, sticker, and annotation flows
- artifact review and approval flows

Prefer patterns that improve evidence workflow:
- claim-to-source traceability
- provenance visibility
- draft versus reviewed state separation
- low cognitive load in dense review screens
- reversible and explicit operator actions
- clear handoff between reading, review, and export lanes

Avoid patterns that only add visual polish, marketing flavor, or generic SaaS dashboard density.

## Prompt Templates

Use sanitized prompts. Do not paste PaperPipe paper content, screenshots containing private notes, PDFs, lab names, user identifiers, or local file paths.

### Evidence-Linked Reader

```text
Use Lazyweb only for generic UI references. Do not use PaperPipe data, PDFs, paper titles, lab names, or screenshots containing user content.

Find desktop references for evidence-linked reading workspaces: left outline/navigation, center document/read pane, right claim/evidence/provenance panel. Focus on reviewability, source trace, and low cognitive load. Output a non-canonical report with patterns, anti-patterns, and screenshot provenance.
```

### Figure/Table Evidence Viewer

```text
Use Lazyweb only for generic UI references. Do not use PaperPipe data, PDFs, paper titles, lab names, or screenshots containing user content.

Find references for figure/table evidence viewers where the user must inspect metadata, warnings, derived outputs, and source lineage before reuse. Prefer scientific, analytics, data-review, document-review, or QA tools over marketing dashboards. Output a non-canonical report with pattern groups and risks.
```

### Artifact Review Flow

```text
Use Lazyweb only for generic UI references. Do not use PaperPipe data, PDFs, paper titles, lab names, or screenshots containing user content.

Find references for artifact approval or review flows that separate draft/generated output from reviewed/promoted state. Focus on explicit state labels, provenance, reversible actions, and guarded export. Output a non-canonical report with PR-sized design implications.
```

## Expected Artifacts

Raw local research output should stay ignored:

```text
.lazyweb/{skill}/{topic-date}/
├── report.md
├── report.html
└── references/
```

Curated summaries may be promoted to:
- `docs/reports/UI_Reference_Research_<flow>_<date>.md`
- this note, if the pattern becomes durable workflow guidance

Curated summaries should include:
- target PaperPipe screen or flow
- source tool and date
- reference source labels
- what pattern is useful
- what should not be copied
- evidence/provenance/state impact
- whether the finding is recommendation, open question, or rejected pattern

## Security Rules

Keep tokens and MCP config out of git.

Recommended local token locations:
- `~/.lazyweb/lazyweb_mcp_token`
- environment variable `LAZYWEB_MCP_TOKEN`

Repository ignore coverage should include:
- `.lazyweb/`
- `*.mcp.json`
- `.mcp.json`
- `mcp.json`
- `.lazyweb_mcp_token`
- `lazyweb_mcp_token`

When using visual search, do not upload screenshots from PaperPipe if they contain user paper content, private note text, lab context, local paths, or identifiers. Prefer generic text searches over image comparison for PaperPipe surfaces.

## Adoption Rule

Lazyweb can inform a UI change only after the change is restated in PaperPipe terms:
- which existing route/component changes
- which `--pp-*` tokens and existing primitives are reused
- which canonical state or artifact layer remains unchanged
- which UX review artifact covers the change
- which frontend verification will run

Reference research is useful context. It is not the decision.

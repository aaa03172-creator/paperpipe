# Skills Recommendations

Status: Active recommendation note  
Date: 2026-03-09  
Owner: Skills maintainers  
Canonical: `docs/SKILLS_RECOMMENDATIONS.md`  
Canonical parent: `docs/SKILLS_AUDIT.md`

Date: 2026-03-09

## Comparison Baseline

Current PaperPipe already covers core paper processing through:

- PDF -> text/tables via [src/agents/ingest_agent.py](/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py)
- retrieval/indexing via [src/agents/indexer_agent.py](/Users/jangseongjin/paperpipe/src/agents/indexer_agent.py)
- ClaimSet generation via [src/agents/reader_agent.py](/Users/jangseongjin/paperpipe/src/agents/reader_agent.py)
- stats verification via [src/agents/stats_agent.py](/Users/jangseongjin/paperpipe/src/agents/stats_agent.py)
- Obsidian note updates via [backend/routers/obsidian.py](/Users/jangseongjin/paperpipe/backend/routers/obsidian.py) and [src/services/deepread_note_writer.py](/Users/jangseongjin/paperpipe/src/services/deepread_note_writer.py)
- paper notes web viewer via [backend/routers/paper_notes.py](/Users/jangseongjin/paperpipe/backend/routers/paper_notes.py) and [frontend/src/app/pages/PaperNoteDetailPage.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx)
- existing sandbox policy via [src/sandbox/docker_runner.py](/Users/jangseongjin/paperpipe/src/sandbox/docker_runner.py)

The scientific-skills repository adds curated docs, runnable patterns, and safer operator-facing entry points, but it should not replace stable PaperPipe internals unless reliability or UX materially improves.

## Adopt Now (core-safe)

### `markitdown`
- Replaces/Augments: augments our PDF/text extraction entrypoint for lightweight markdown conversion; fallback remains our own ingest path.
- Why now: MIT, local-first, immediate ROI for note-side extraction previews without forcing a full deepread job.
- Minimal integration: `POST /skills/run` -> `extract_markdown`; right-panel button in `/papers/:slug`; writes run summary to `.pp/<slug>/state.json`.
- License + network + secret requirements: MIT, no network, no secrets.

### `citation-management`
- Replaces/Augments: augments note references validation, DOI normalization, and citation counting; keep our own OpenAlex/PubMed clients for actual fetching.
- Why now: MIT, strong documentation value, immediate ROI for frontmatter `pp.signals.citation_count` and reference QA.
- Minimal integration: `POST /skills/run` -> `validate_citations`; no arbitrary web crawling, only DOI/OpenAlex allowlist.
- License + network + secret requirements: MIT, allowlisted network only (`api.openalex.org`, `doi.org`), no secrets.

### `pyzotero`
- Replaces/Augments: augments Zotero-aware reference handling; keep our own note viewer and Obsidian export paths.
- Why now: MIT, directly aligned with existing Zotero-heavy note metadata.
- Minimal integration: companion skill for `validate_citations`; future route can enrich library lookups when explicit credentials are available.
- License + network + secret requirements: MIT, local/read-only mode safe; API mode requires `ZOTERO_LIBRARY_ID`, `ZOTERO_API_KEY`.

### `peer-review`
- Replaces/Augments: augments appraisal/reporting pattern on top of our existing ClaimSet + stats artifacts.
- Why now: MIT, immediate UX win for structured appraisal cards without replacing our reader/stat verifier.
- Minimal integration: `POST /skills/run` -> `critical_appraisal`; sidecar-backed cards in note detail.
- License + network + secret requirements: MIT, no network, no secrets, Docker sandbox preferred.

## Optional (needs license audit)

### `literature-review`
- Replaces/Augments: would augment evidence-synthesis reports, but overlaps with our paper indexing, fetching, and note workflows.
- Keep ours unless: we need a dedicated literature synthesis route with report templates.
- Concerns: MIT skill wrapper, but default workflow pushes Google Scholar/manual scraping paths and large report generation.
- Minimal integration plan: separate endpoint or cron-only report flow, not core note detail button.
- License + network + secret requirements: MIT, network-heavy, no secret required by default.

### `research-lookup`
- Replaces/Augments: could augment fresh web research or paper discovery, but PaperPipe should remain local-first for core note actions.
- Keep ours unless: user explicitly requests live research lookup.
- Concerns: API-heavy and requires third-party keys.
- Minimal integration plan: separate non-core research endpoint, never automatic in note viewer.
- License + network + secret requirements: MIT, external API heavy, requires `PARALLEL_API_KEY` and/or `OPENROUTER_API_KEY`.

### `openalex-database`
- Replaces/Augments: duplicates [src/fetch/openalex.py](/Users/jangseongjin/paperpipe/src/fetch/openalex.py).
- Recommendation: keep ours for runtime; borrow query patterns/docs only.
- Concerns: skill metadata says `Unknown` license even though OpenAlex itself is open.
- Minimal integration plan: none for now beyond our existing OpenAlex client.
- License + network + secret requirements: metadata `Unknown`, allowlisted network, no secret.

### `pubmed-database`
- Replaces/Augments: duplicates [src/fetch/pubmed.py](/Users/jangseongjin/paperpipe/src/fetch/pubmed.py).
- Recommendation: keep ours for runtime; use skill docs only for advanced query patterns if needed.
- Concerns: metadata `Unknown`; network-heavy.
- Minimal integration plan: none for core notes path.
- License + network + secret requirements: metadata `Unknown`, network required, optional NCBI API key.

## Do Not Adopt (core)

### `bioservices`
- Reason: GPLv3. Duplicates some multi-database access, but incompatible for core embedding in this repo without a deliberate licensing decision.
- What it would augment: cross-database lookup workflows.
- Why not core: license gate.

### `cobrapy`
- Reason: GPL-2.0 and unrelated to current core paper note workflow.
- What it would augment: metabolic modeling.
- Why not core: license gate and low immediate ROI.

### `denario`
- Reason: GPL-3.0, multi-agent orchestration overlaps conceptually with PaperPipe agents but would increase complexity and licensing risk.
- Why not core: keep PaperPipe’s own agent chain.

### `docx`
- Reason: proprietary terms in skill metadata.
- What it would augment: report generation.
- Why not core: unsafe licensing posture for default adoption.

### `paper-2-web`
- Reason: metadata `Unknown`, external API keys, GPU-heavy, and outside current paper notes viewer scope.
- What it would augment: promotional website/poster/video generation.
- Why not core: high infra cost and not aligned with note viewer or ClaimSet workflow.

## Selected Integration Plan

1. Pin `rules/scientific-skills` as a submodule and copy only approved project-scoped skills into `.codex/skills/`.
2. Gate every runtime action through [config/skills_policy.yaml](/Users/jangseongjin/paperpipe/config/skills_policy.yaml) for license, network, sandbox, and secrets.
3. Expose only three safe note-level actions first:
   - `extract_markdown`
   - `validate_citations`
   - `critical_appraisal`
4. Store outputs canonically in `vault/.pp/<slug>/state.json` plus per-run files under `vault/.pp/<slug>/runs/`.
5. Use note frontmatter only for summary signals (`pp.*`) and render runs/claimset from structured JSON in the web viewer.

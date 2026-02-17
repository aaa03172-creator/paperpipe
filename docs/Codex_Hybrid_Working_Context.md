# Codex Hybrid Working Context (PaperPipe)
Last updated: 2026-02-17
Source docs:
- `/Users/jangseongjin/Downloads/Codex_Brief_PaperPipe.md`
- `/Users/jangseongjin/Downloads/Codex_Hybrid_Integration_Rules.md`

## Mission
Keep PaperPipe maintainable and stable while developing in parallel with Antigravity.

## Non-negotiable rules
- Ship via PR workflow only: branch -> PR -> merge.
- Keep changes small and integrate frequently (per ticket, at least daily).
- Do not change business thresholds/policies without SSOT + tests + rationale.
- No file deletions by default.
- OA-only policy stays (no paywalled scraping).
- No Zotero DB writes (RIS export only).

## Ownership boundaries
- Antigravity: runtime/ops behavior (`processor.py`, fetchers/downloader, watch-folder behavior, production state handling).
- Codex: quality layer (`src/gates.py`, tests, CI/pre-commit, regression harness, quality docs).

## Shared contract rule
If touching contracts below, merge quickly and include docs/tests/migration note:
- SSOT/spec docs
- config schema and loader contract
- gate output contract (`decision`, `reason_code`, schema)
- `paper_id`/dedupe/state DB contract
- Obsidian note and CSV index schema
- watch-folder matching rules

## Immediate Codex priorities
1. Gate engine extraction: add/normalize `src/gates.py` with stable contract.
2. Idempotency regression: rerun same paper, assert duplicate-free outputs.
3. JSON repair harness for FAILED outputs with fixture tests.

## Ask-before-act triggers
- SSOT ambiguity/conflict.
- Threshold/slot-rule changes.
- Broad semantic/runtime impact.
- Large PR scope (about 15+ files).

## Current local context
- Active branch target: `codex/*` prefix.
- Existing uncommitted runtime-side changes exist in `/Users/jangseongjin/paperpipe/src/processor.py`.
- To reduce conflict risk, prefer quality-layer changes first (`src/gates.py`, `tests/`, docs).

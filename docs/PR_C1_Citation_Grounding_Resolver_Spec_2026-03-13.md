# PR-C1 Citation Grounding Resolver

Status: implemented additive resolver  
Date: 2026-03-13

## Scope

This PR adds a runtime resolver that verifies claim evidence against indexed chunk text and writes a resolved artifact.

Added pieces:

- `/Users/jangseongjin/paperpipe/src/services/citation_grounding.py`
- optional `grounded` / `resolution` fields on legacy `EvidenceSpan`
- `claimset.resolved.json` write in the read step

## Resolution rules

1. prefer the provided `chunk_id` if it points to a real indexed chunk
2. verify `quote` or `raw_text` against chunk text
3. if direct substring fails, retry with normalized text matching
4. if exactly one chunk matches, resolve page/chunk/source span
5. if multiple chunks match, mark `AMBIGUOUS_MATCH`
6. if no chunk matches, mark `FAILED_MATCH`

## Output effects

Resolved spans now add:

- `grounded: true|false`
- `resolution: OK | NORMALIZED_MATCH | AMBIGUOUS_MATCH | FAILED_MATCH`
- `page`, `chunk_id`, `char_start`, `char_end`, `source_span` when resolution succeeds

## Adoption

- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py` now writes both:
  - `claimset.json`
  - `claimset.resolved.json`
- deepread note upsert uses the resolved claimset
- `/Users/jangseongjin/paperpipe/src/exporter.py` now prefers `claimset.resolved.json` over legacy `claimset.json`

## Non-goals

- no bbox/highlight coordinate synthesis
- no reader prompt hard lock to `chunk_id + quote` yet
- no cross-document contradiction logic

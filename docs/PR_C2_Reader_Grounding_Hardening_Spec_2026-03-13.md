# PR-C2 Reader Grounding Hardening

Status: implemented  
Date: 2026-03-13

## Scope

This PR hardens `ReaderAgent` so it stops manufacturing placeholder chunk ids when the source text can be mapped to deterministic local chunks.

## Changes

- `/Users/jangseongjin/paperpipe/src/agents/reader_agent.py`
  - builds local deterministic chunk views from section text using the same `pXX_cYY` / `sXX_cYY` contract
  - prompts with chunk-aware snippet headers instead of section-only headers
  - tells the model to reuse visible chunk ids and not invent placeholder ids
  - normalizes evidence spans by matching `quote/raw_text` back into local chunks
  - replaces placeholder chunk ids with matched deterministic chunk ids when possible
  - heuristic fallback now emits deterministic chunk ids and real `source_span` offsets

- `/Users/jangseongjin/paperpipe/src/services/citation_grounding.py`
  - exports `find_text_location(...)` so reader/runtime/teacher-review can reuse the same matching logic

- `/Users/jangseongjin/paperpipe/src/quality/teacher_review.py`
  - now delegates text-location matching to the shared grounding utility

## Non-goals

- no hard requirement that the LLM always returns `chunk_id`
- no removal of legacy `page` hints
- no bbox synthesis

## Result

The pipeline now has three aligned layers:

1. deterministic chunk ids from indexing
2. reader-side local chunk inference during claim normalization
3. runtime resolver writing `claimset.resolved.json`

That reduces the amount of synthetic `ev_*` / `heuristic_*` evidence identifiers that reach runtime artifacts.

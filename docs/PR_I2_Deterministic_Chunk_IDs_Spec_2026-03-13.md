# PR-I2 Deterministic Chunk IDs

Status: Implemented  
Date: 2026-03-13  
Parent roadmap: `/Users/jangseongjin/paperpipe/docs/Audit_Driven_Roadmap_2026-03-13.md`

## Goal

Replace the active `uuid4()` chunk-id strategy in the deepread indexing lane with a deterministic contract that is stable for the same document and the same chunking behavior.

## Implemented scope

Updated files:

- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/src/contracts/artifact_views.py`
- `/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py`
- `/Users/jangseongjin/paperpipe/src/agents/indexer_agent.py`
- `/Users/jangseongjin/paperpipe/tests/test_indexer_agent_chunk_ids.py`

## Contract

### 1. Chunk ID format

- page-backed chunks: `p{page:02d}_c{chunk:02d}`
- page-unknown fallback: `s{section:02d}_c{chunk:02d}`

Examples:

- `p01_c01`
- `p03_c07`
- `s02_c04`

### 2. Determinism rule

Chunk ids are deterministic for:

- the same document text sections
- the same section ordering
- the same page hints
- the same fixed chunking settings

This PR does **not** promise stability across future parser/chunker behavior changes.

### 3. Page semantics

- `page_hint` in indexed chunks is 1-indexed
- this matches existing `page_1`, `page_2`, ... section naming in the current runtime
- `EvidenceSpan.page` remains a separate field with current downstream semantics

### 4. Added chunk metadata

`DocumentChunk` now carries additive metadata:

- `page_hint`
- `section_ordinal`
- `chunk_ordinal`
- `chunk_id_version`

Current `chunk_id_version` value:

- `det-v1`

## Implementation notes

### 1. Shared helper

`/Users/jangseongjin/paperpipe/src/services/identity.py`

- added `make_chunk_id()`

### 2. Text section view now preserves page/ordering hints

`/Users/jangseongjin/paperpipe/src/contracts/artifact_views.py`

- `TextSectionView` now includes:
  - `page_hint`
  - `ordinal`

Current behavior:

- `DocumentArtifact` sections use `page_start` when available
- `DocumentArtifactV2` page text views expose `page.page_index + 1`

### 3. Indexer uses deterministic IDs

`/Users/jangseongjin/paperpipe/src/agents/indexer_agent.py`

- removed `uuid4()` chunk ids from the active indexing lane
- page-aware chunk ids increment in traversal order per page
- page-unknown sections fall back to section-based ids

## Verification

Targeted tests:

- `/Users/jangseongjin/paperpipe/tests/test_indexer_agent_chunk_ids.py`
- `/Users/jangseongjin/paperpipe/tests/test_artifact_bridge.py`
- `/Users/jangseongjin/paperpipe/tests/test_reader_agent_reliability.py`
- `/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py`

Result:

- `12 passed`

Full suite:

- `540 passed, 1 skipped`

## Non-goals in this PR

- no evidence resolver yet
- no `grounded/resolution` claim contract yet
- no `paper_key` migration
- no reader prompt migration to strict `chunk_id + quote`
- no promise of cross-version chunk stability across parser/chunker changes

## Next step

The next structurally correct follow-up is:

- additive execution event log (`PR-E1`)
or
- output contract bridge + citation resolver groundwork if event logging is intentionally deferred

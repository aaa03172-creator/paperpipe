# Output Contract Audit

Status: Working infrastructure audit  
Date: 2026-03-13  
Scope: ingest artifacts, index/claim artifacts, resolved claimset handling, paper notes structured state, and contract drift across runtime surfaces

## 0. Executive Summary

The repository does not have one single output contract.

It currently operates with three overlapping contract layers:

1. `DocumentArtifactV2` for newer ingest/parser output
2. legacy `agent_artifacts` for index, claimset, stats, exporter, and most runtime integrations
3. `StructuredPaperState` for paper-note/skills/chat-hook state under `.pp/<slug>/state.json`

Current judgment:

- there is meaningful progress toward structured contracts
- the runtime backbone is still the legacy `agent_artifacts` schema
- newer contracts exist, but they are not yet the singular downstream source of truth
- memory-ready and citation-grounding requirements are only partially satisfied because the active claim/evidence contract is still permissive

## 1. Current Contract Layers

### 1.1 Legacy runtime backbone: `src/schemas/agent_artifacts.py`

This file is still the main active contract for:

- `DocumentArtifact`
- `IndexArtifact`
- `ClaimSet`
- `EvidenceSpan`
- `StatsReport`

Primary consumers still include:

- `/Users/jangseongjin/paperpipe/src/agents/reader_agent.py`
- `/Users/jangseongjin/paperpipe/backend/routers/obsidian.py`
- `/Users/jangseongjin/paperpipe/src/services/deepread_note_writer.py`
- `/Users/jangseongjin/paperpipe/src/exporter.py`
- `/Users/jangseongjin/paperpipe/src/services/stats_repair.py`

Assessment:

- this is still the contract that most of the pipeline actually speaks
- any claim/evidence hardening work has to account for this schema first

### 1.2 New ingest contract: `DocumentArtifactV2`

`/Users/jangseongjin/paperpipe/src/contracts/document_artifact_v2.py` defines a newer ingest representation.

Key traits:

- page-aware geometry
- stable block/span ids
- explicit `bbox_pdf` validation against page bounds
- `schema_version = "2.0"`

Tests confirm:

- stable ids across repeated ingest runs
- bbox validation against page bounds
- round-trip contract stability

Primary evidence:

- `/Users/jangseongjin/paperpipe/tests/test_document_artifact_v2.py`

Assessment:

- ingest has a more disciplined contract than the downstream claimset path
- this is a real improvement, but it is not yet the end-to-end artifact backbone

### 1.3 Paper-note/skills contract: `StructuredPaperState`

`/Users/jangseongjin/paperpipe/src/schemas/skills.py` defines a separate state contract used under `.pp/<slug>/state.json`.

Key traits:

- `schema_version = "2026-03-09.chat-hooks.v1"`
- stable `claim_*` and `evidence_*` ids via content hashing
- explicit `locator` object with page/section/chunk/span/bbox/table fields
- per-run records in `runs[]`
- signals such as `claim_count`, `evidence_count`, `last_run_id`

Primary consumers:

- `/Users/jangseongjin/paperpipe/backend/routers/paper_notes.py`
- `/Users/jangseongjin/paperpipe/src/skills/storage.py`
- `/Users/jangseongjin/paperpipe/src/skills/runner.py`

Assessment:

- this is the most memory-ready structured state currently in the repository
- but it is not the primary deepread artifact contract
- it behaves like a parallel product-layer contract, not the canonical research pipeline output contract

## 2. What The Runtime Actually Uses

### 2.1 Ingest path

The ingest layer can produce `DocumentArtifactV2` with stable geometry-aware ids.

But downstream compatibility is maintained through `/Users/jangseongjin/paperpipe/src/contracts/artifact_bridge.py`, which converts v2 documents into legacy `DocumentArtifact` page sections.

Assessment:

- the bridge preserves basic text/table structure
- it does not preserve the full geometry-aware v2 contract as the default downstream interface

### 2.2 Reader path

`/Users/jangseongjin/paperpipe/src/agents/reader_agent.py` still imports and emits legacy `ClaimSet`, `ScientificClaim`, and `EvidenceSpan`.

Important prompt behavior:

- system prompt requires `evidence_spans`
- each evidence item needs `quote/raw_text` and a location hint
- location hint can be `page` or `source_span`
- example claim still uses `chunk_id="chunk_12"`

Assessment:

- the reader is not yet locked to a deterministic `chunk_id + quote` contract
- it still treats page/source-span hints as acceptable grounding

### 2.3 Obsidian/artifact API path

`/Users/jangseongjin/paperpipe/backend/routers/obsidian.py` prefers `claimset.resolved.json` over `claimset.json`.

But what "resolved" means in code today is limited:

- the router chooses that filename first if present
- mirror rendering parses it as legacy `ClaimSet`
- formatting uses only the first evidence span's `quote/raw_text` and `page`

Assessment:

- `claimset.resolved.json` is a preferred file name, not evidence that a formal resolver layer exists
- the API surface still assumes legacy claim/evidence shape

### 2.4 Paper Notes path

`/Users/jangseongjin/paperpipe/backend/routers/paper_notes.py` relies on `.pp/<slug>/state.json`, not on `claimset.resolved.json`, for the structured note state used by the viewer.

Assessment:

- the paper notes viewer already runs on a different contract family than the deepread artifact bundle
- this is why note-state can look more memory-ready than the artifact layer beneath it

## 3. Claim/Evidence Contract Quality

### 3.1 What `EvidenceSpan` currently enforces

Legacy `EvidenceSpan` in `/Users/jangseongjin/paperpipe/src/schemas/agent_artifacts.py` supports:

- `page`
- `chunk_id`
- `char_start` / `char_end`
- `raw_text`
- `quote`
- `rationale`
- optional bbox and table/cell metadata
- optional back-compat `section` and `source_span`

Current validation guarantees:

- evidence must have either text payload or table cell link
- bbox formats must be structurally valid
- table/cell link must be paired

What it does not guarantee:

- deterministic `chunk_id`
- exact `quote` presence
- `quote in chunk_text`
- `grounded` / `resolution`
- a single canonical location strategy

Assessment:

- this is a permissive evidence container, not a verified evidence contract

### 3.2 Active `chunk_id` remains weak downstream

`IndexArtifact` defines chunks, but the active claim path does not enforce a stable chunk contract.

Current reality:

- `EvidenceSpan.chunk_id` defaults to `"unknown"`
- reader example uses synthetic ids like `chunk_12`
- other paths tolerate missing or placeholder chunk ids

Assessment:

- chunk-aware evidence exists in schema shape
- it is not enforced strongly enough to support trustworthy citation grounding on its own

### 3.3 Page hints still dominate UX surfaces

Current consumer behavior still privileges page hints and first evidence span summaries.

Examples:

- Obsidian markdown formatter emits `Page {page}`
- mirror payload exposes `evidence_page`
- exporter builds Zotero page links from `EvidenceSpan.page`

Assessment:

- the product already leans on page-based evidence UX
- that matches current implementation reality more than the desired chunk-verified grounding model

## 4. Contract Drift Across Subsystems

### 4.1 Deepread artifacts vs Paper Notes structured state

Deepread artifact claimsets use:

- `statement`
- `evidence_spans`
- optional `page`, `chunk_id`, `quote`

Paper Notes structured state uses:

- `claim`
- `evidence[]`
- stable `evidence_ids`
- nested `locator`

Assessment:

- these are related but not identical contracts
- there is no single declared bridge module that says this state is the canonical successor of deepread claimsets

### 4.2 Skills runner performs ad hoc normalization

`/Users/jangseongjin/paperpipe/src/skills/runner.py` reads raw claim payloads and converts them into `SkillClaimCard` / `SkillClaimEvidence`.

Normalization currently handles:

- `statement` or `claim`
- `evidence_spans` or `evidence`
- optional `page`, `section`, `chunk_id`, `bbox`, table ids
- stable hashed evidence ids

Assessment:

- normalization exists, which is useful
- but it is implemented as an adapter, not as a single project-wide output contract

### 4.3 `claimset.resolved.json` has no strong schema identity

Tests and runtime code frequently treat `claimset.resolved.json` as a file-name preference, not a formal schema version boundary.

Examples:

- artifact listing APIs can surface arbitrary JSON without validating it as a claimset
- mirror/viewer layers only validate when they need structured fields

Assessment:

- the file naming convention is stronger than the schema identity behind it

## 5. What Is Strong Today

### 5.1 Ingest geometry contract is meaningfully improved

`DocumentArtifactV2` is a real upgrade:

- stable ids
- page geometry
- bbox bounds checking
- cleaner parser-facing contract

### 5.2 Skills/state layer already has stable ids

`StructuredPaperState` and `SkillEvidenceLocator` already support:

- stable claim ids
- stable evidence ids
- locator-rich evidence
- per-run structured state

This is the closest existing implementation to the future memory-ready hook concept.

### 5.3 Artifact preference rules are explicit

The repository consistently prefers:

- `claimset.resolved.json` over `claimset.json`

This gives a clean upgrade slot, even if the underlying schema is still legacy-shaped.

## 6. Main Gaps

### 6.1 No single source-of-truth output contract

There is no one schema family that fully owns:

- ingest
- reader output
- evidence validation
- note viewer state
- memory-ready recall state

Priority: P1

### 6.2 No verified evidence resolver in the active deepread path

The runtime does not currently implement a formal `grounded/resolution` layer on top of claim evidence.

Priority: P1

### 6.3 Contract upgrade is happening via bridges and adapters, not via replacement

`DocumentArtifactV2` and `StructuredPaperState` both improve on legacy shapes, but the core pipeline still depends on `agent_artifacts`.

Priority: P1

### 6.4 `claimset.resolved.json` is not enough by itself

A resolved filename without a resolver contract can mislead downstream assumptions.

Priority: P2

## 7. Recommended Next Sequence

### Step 1. Declare the active contract layers explicitly

Short-term documentation should state:

- ingest canonical contract: `DocumentArtifactV2`
- deepread runtime contract: legacy `agent_artifacts` claimset/stats for now
- product/viewer structured state: `StructuredPaperState`

### Step 2. Add a formal bridge from deepread claimset to structured state

Instead of multiple ad hoc normalizers, add one project-owned bridge that converts deepread claimsets into a memory-ready structured state contract.

### Step 3. Harden evidence semantics before more UX promises

Minimum additions needed in the active deepread contract:

- deterministic `chunk_id`
- strict quote expectation
- resolver status such as `grounded` and `resolution`
- documented page-index semantics

### Step 4. Treat `claimset.resolved.json` as a schema step, not only a filename

Add an explicit schema/version marker so downstream consumers can know what kind of claimset they are reading.

## 8. Final Judgment

The repository has real structured-output progress, but not a unified structured-output backbone.

The most accurate description of the current state is:

- ingest has a stronger v2 contract
- deepread runtime still speaks legacy `agent_artifacts`
- paper notes and skills already speak a more memory-ready state contract
- bridges between these layers exist, but they are partial and not yet the single official path

This means the next output-contract PR should focus on convergence, not on inventing yet another schema family.

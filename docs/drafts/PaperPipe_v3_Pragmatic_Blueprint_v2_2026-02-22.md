# PaperPipe v3 Pragmatic Blueprint v2 (2026-02-22)

## 0. Purpose
- This document defines the implementation blueprint for memory-ready hooks while preserving current research-agent velocity.
- Scope is fixed to three foundational PRs:
  - `PR-H0`: Stable IDs + Artifact Registry
  - `PR-H1`: SQLite Event Log (Runs/Jobs/Events/User Actions)
  - `PR-H2`: Output Schema Contract (ChunkSet/ClaimSet/Evidence Resolver)
- This is an execution spec, not a concept memo.

## 1. Hard Rules (Must)
- API-First: core logic must be callable from FastAPI paths, not CLI-only branches.
- Pydantic Contracts: all artifact I/O must use typed models in `src/schemas/` or `src/contracts/`.
- Idempotency: markdown rendering must upsert/replace target sections, never blind append.
- Evidence Verifiability: evidence must be machine-checkable (`chunk_id + quote`) before UX confidence labels are shown.
- Conservative Parsing: bbox/span highlighting is out of MVP scope.

## 2. Non-Goals (Locked)
- No bbox/coordinate highlight implementation.
- No full table structure parsing.
- No scite-grade support/contrast judgment.
- No multi-document synthesis or conflict adjudication yet.

## 3. PR-H0 v2: Stable IDs + Safe Artifact Keys

### 3.1 Goals
- Ensure every output and log shares stable references across pipeline stages.
- Prevent filesystem breakage caused by reserved characters in `paper_id`.
- Enable future memory lookup to reference exact artifacts deterministically.

### 3.2 Canonical Identity Model
- `paper_id` (logical ID, immutable once issued)
  - Priority on first creation:
    - `zotero:<key>` if Zotero key exists
    - `doi:<normalized_doi>` if DOI exists
    - `pdfsha256:<hash>` fallback
- `paper_key` (filesystem-safe key, deterministic from paper_id)
  - Recommended: `base32(sha256(paper_id))[:16]`
  - Used in file paths only
- `run_id`, `job_id`, `event_id`, `action_id`
  - ULID preferred (UUIDv7 acceptable)
- `chunk_id`
  - `p{page:02d}_c{chunk:02d}` deterministic by parser/chunker config
- `claim_id`
  - runtime-local ID allowed
- `claim_fingerprint`
  - required for dedupe/merge (`sha` of normalized claim text)

### 3.3 Required Modules
- `src/core/ids.py`
  - `normalize_doi(doi: str) -> str`
  - `sha256_file(path: str | Path) -> str`
  - `make_paper_id(zotero_key: str | None, doi: str | None, pdf_path: str | Path | None) -> str`
  - `make_paper_key(paper_id: str) -> str`
  - `new_ulid() -> str`
  - `chunk_id(page: int, idx: int) -> str`
  - `fingerprint(text: str) -> str`
- `src/core/artifact_paths.py`
  - `artifact_root(paper_key: str, run_id: str) -> Path`
  - `ingest_chunks_json_path(paper_key: str, run_id: str) -> Path`
  - `claimset_json_path(paper_key: str, run_id: str) -> Path`
  - `stats_report_path(paper_key: str, run_id: str) -> Path`

### 3.4 Database Contract Additions
- Add/ensure `papers` mapping columns:
  - `paper_id TEXT PRIMARY KEY`
  - `paper_key TEXT NOT NULL UNIQUE`
  - `doi TEXT`
  - `zotero_key TEXT`
  - `pdf_sha256 TEXT`
  - `created_at TEXT NOT NULL`
- All artifact references in runtime should carry both `paper_id` and `paper_key` when needed.

### 3.5 Determinism Definition
- Deterministic chunk IDs are guaranteed only when all below match:
  - same parser/version
  - same chunker/version
  - same chunk config hash
  - same source document content

### 3.6 H0 Acceptance Criteria
- Same DOI input always yields same `paper_id`.
- Same PDF always yields same `pdfsha256`.
- Same `paper_id` always yields same `paper_key`.
- Same parser/chunker/config produces same `chunk_id` sequence.
- `fingerprint()` returns same value across case/whitespace-only differences.

## 4. PR-H1 v2: Runs/Jobs/Events/User Actions (SQLite)

### 4.1 Goals
- Persist intent -> execution -> outcome timeline for debug, retry, and future memory extraction.
- Support replayability by reconstructing run state from DB rows.

### 4.2 Schema (Recommended)
- `runs` (execution-level record)
- `jobs` (step-level work units)
- `job_events` (high-volume timeline)
- `user_actions` (explicit user intent signals)

```sql
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  paper_id TEXT,
  trigger_source TEXT,        -- chat|ui|cron|watcher
  pipeline_profile TEXT,      -- fast_ingest|grounded_read|deep_verify
  status TEXT NOT NULL,       -- running|succeeded|failed|cancelled
  created_at TEXT NOT NULL,
  finished_at TEXT,
  params_json TEXT,
  metrics_json TEXT,
  FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
);

CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  paper_id TEXT,
  job_type TEXT NOT NULL,     -- ingest|read|discover|stats|export
  status TEXT NOT NULL,       -- queued|running|succeeded|failed|cancelled
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  params_json TEXT,
  result_ref TEXT,
  error_code TEXT,
  error_taxonomy_code TEXT,
  error_detail TEXT,
  metrics_json TEXT,
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS job_events (
  event_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,        -- debug|info|warn|error
  event_type TEXT NOT NULL,   -- step_start|step_end|llm_call|io|exception...
  message TEXT,
  payload_json TEXT,
  FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS user_actions (
  action_id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  paper_id TEXT,
  action_type TEXT NOT NULL,  -- important|pin|remember|tag_add|...
  source TEXT NOT NULL,       -- chat|ui|obsidian
  payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_paper ON runs(paper_id);
CREATE INDEX IF NOT EXISTS idx_jobs_run ON jobs(run_id);
CREATE INDEX IF NOT EXISTS idx_jobs_paper ON jobs(paper_id);
CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_actions_paper ON user_actions(paper_id);
```

### 4.3 Runtime Requirements
- SQLite pragmas at connection bootstrap:
  - `PRAGMA foreign_keys = ON;`
  - `PRAGMA journal_mode = WAL;`
  - `PRAGMA synchronous = NORMAL;`
- Event logging is buffered:
  - in-memory queue
  - batch insert by writer thread/task
  - short transaction windows

### 4.4 Integration Requirement (Important)
- This repository currently uses bootstrap functions, not a migration runner.
- Implement schema ensures in `src/db_bootstrap.py` (or equivalent ensure layer), and invoke from `src/db_utils.init_db()`.
- Do not rely on SQL files alone unless a migration executor is introduced in the same PR.

### 4.5 Required Module
- `src/db/event_log.py`
  - `create_run(paper_id, trigger_source, pipeline_profile, params) -> run_id`
  - `finish_run(run_id, status, metrics=None)`
  - `create_job(run_id, paper_id, job_type, params=None) -> job_id`
  - `update_job_status(job_id, status, result_ref=None, error_code=None, error_detail=None, error_taxonomy_code=None, metrics=None)`
  - `log_event(job_id, level, event_type, message=None, payload=None) -> event_id`
  - `log_user_action(paper_id, action_type, source, payload=None) -> action_id`

### 4.6 Minimum Instrumentation Points
- Job lifecycle transitions:
  - `queued -> running -> succeeded|failed|cancelled`
- Step boundaries:
  - `step_start` and `step_end` for ingest/index/read/verify/export/discover
- Exception capture:
  - `event_type="exception"` with structured payload
- User intent:
  - e.g., `#important` -> `user_actions(action_type="important")`

### 4.7 H1 Acceptance Criteria
- A run can be reconstructed from `runs -> jobs -> job_events` without raw logs.
- Failure path records `status=failed` plus error fields.
- High-frequency events do not stall batch processing due to DB lock contention.
- User intent actions are persisted and queryable per `paper_id`.

## 5. PR-H2 v2: Output Schema Contract (ChunkSet/ClaimSet/Evidence)

### 5.1 Goals
- Treat markdown as a view layer and JSON contracts as canonical research assets.
- Make Citation Jump, future synthesis, and memory features consume the same JSON artifacts.

### 5.2 Schema Files
- `src/contracts/chunks.py`
- `src/contracts/claims.py`

### 5.3 ChunkSet Contract
- `paper_id: str`
- `run_id: str`
- `parser: str`
- `parser_version: str`
- `chunker: str`
- `chunker_version: str`
- `config_hash: str`
- `created_at: datetime`
- `chunks: list[Chunk]`

`Chunk` fields:
- `chunk_id: str` (`p03_c07`)
- `page: int` (1-based)
- `text_raw: str`
- `text_norm: str | None` (optional if normalized on read)
- `section_hint: str | None`

### 5.4 ClaimSet Contract
- `paper_id: str`
- `run_id: str`
- `model: str`
- `created_at: datetime`
- `claims: list[Claim]`

`Claim` fields:
- `claim_id: str`
- `claim_fingerprint: str`
- `text: str`
- `type: str | None`
- `evidence: list[EvidenceRef]`

`EvidenceRef` fields:
- `chunk_id: str`
- `quote: str`
- `grounded: bool | None`
- `resolution: str | None` (`OK|NORMALIZED_MATCH|FAILED_MATCH|AMBIGUOUS`)

### 5.5 Evidence Resolver (Mandatory)
- `src/core/text_normalize.py`
  - `normalize_text(s: str) -> str`
  - normalize whitespace, line-break hyphenation, ligatures, quote variants
- `src/core/evidence_resolver.py`
  - `resolve_evidence(claimset: ClaimSet, chunkset: ChunkSet) -> ClaimSet`
- Resolution logic:
  1. exact raw match: `quote in chunk.text_raw` -> `OK`
  2. normalized match: `normalize(quote) in normalize(chunk.text_raw)` -> `NORMALIZED_MATCH`
  3. else -> `FAILED_MATCH`

### 5.6 Artifact Persistence Contract
- Ingest stage writes:
  - `artifacts/{paper_key}/{run_id}/chunks.json`
- Read stage writes:
  - `artifacts/{paper_key}/{run_id}/claimset.raw.json`
  - `artifacts/{paper_key}/{run_id}/claimset.resolved.json`
- Stats stage writes:
  - `artifacts/{paper_key}/{run_id}/stats_report.json`

### 5.7 Compatibility Requirement
- Existing consumers reference `src/schemas/agent_artifacts.py`.
- Add bridge adapters to avoid breaking current runtime in one shot:
  - legacy -> new contract
  - new contract -> legacy renderer payload (temporary)

### 5.8 H2 Acceptance Criteria
- Evidence resolver marks grounded status deterministically.
- Claim fingerprint is stable against case/whitespace-only changes.
- Citation Jump can be rendered from resolved ClaimSet JSON without markdown parsing.
- UX can display certainty bands based on `grounded/resolution` state.

## 6. Recommended PR Order
1. `PR-H0 v2` (IDs + paper_key + artifact paths)
2. `PR-H1 v2` (runs/jobs/events/actions + WAL + buffered writer)
3. `PR-H2 v2` (output contracts + resolver + bridge)
4. Then continue product roadmap:
   - Discover & Queue
   - Citation Jump MVP
   - Stats Trigger

## 7. Test Plan (Required)

### 7.1 Unit Tests
- `tests/test_ids.py`
  - DOI normalization stability
  - paper_id/paper_key determinism
  - file hash stability
  - fingerprint normalization stability
- `tests/test_chunk_id_determinism.py`
  - deterministic sequence with fixed parser/chunker/config
- `tests/test_event_log.py`
  - run/job/event insert and status transitions
  - failed job records error fields
  - user action persistence
- `tests/test_evidence_resolver.py`
  - exact match -> `OK`
  - normalized match -> `NORMALIZED_MATCH`
  - missing match -> `FAILED_MATCH`

### 7.2 Integration Tests
- ingest -> read -> resolve -> render flow with persisted artifact references
- run reconstruction from DB (`runs/jobs/events`)
- lock-resilience smoke test under burst event logging

## 8. Operational Guardrails
- Keep DB writes short and batched where possible.
- Never emit unresolved artifacts without `run_id` and `paper_id`.
- Log both system error and taxonomy code when available.
- Keep markdown rendering as a pure consumer of resolved JSON artifacts.

---

Document version: `blueprint.pragmatic.2026-02-22.v2`  
Owner: PaperPipe Core  
Execution baseline: `H0 -> H1 -> H2` before higher-order product features

# PR-I1 Identity And Pathing Spec

Status: Implemented  
Date: 2026-03-13  
Parent roadmap: `/Users/jangseongjin/paperpipe/docs/Audit_Driven_Roadmap_2026-03-13.md`

## Implementation status

Implemented in:

- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`
- `/Users/jangseongjin/paperpipe/src/jobs/queue.py`
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/backend/routers/obsidian.py`
- `/Users/jangseongjin/paperpipe/src/exporter.py`
- `/Users/jangseongjin/paperpipe/src/services/paper_ops_summary.py`
- `/Users/jangseongjin/paperpipe/tests/test_identity_helpers.py`

Verification:

- targeted regression: `41 passed`
- secondary touched-surface regression: `20 passed`
- full suite: `537 passed, 1 skipped`

## 0. Goal

`PR-I1` introduces one project-owned helper layer for runtime identity and artifact pathing.

This PR does **not** attempt to solve every future identity problem. Its job is to remove ad hoc ID/path generation from active runtime paths so later work can build on one stable abstraction.

## 1. What This PR Solves

### 1.1 Current problems

Verified from the current audits and code:

- `paper_id` is used as both logical identity and filesystem path segment
- `doc_id` and `paper_id` coexist without a formal bridge
- `job_id` and `run_id` are created in multiple places by multiple rules
- artifact directories are still assembled ad hoc in several runtime paths
- future `paper_key` migration would currently require touching many call sites

### 1.2 Scope of the fix

This PR will:

- centralize runtime identity generation
- centralize artifact path assembly
- add a `doc_id -> paper_id` bridge helper
- keep current observable behavior as stable as possible

This PR will **not**:

- change on-disk artifact layout yet
- switch to ULID/UUIDv7 yet
- make chunk ids deterministic yet
- add DB migrations
- add event-log tables
- add citation resolver semantics

## 2. Design Principle

Stabilize the call sites first, then change the underlying identity policy later.

That means:

- wrap current behavior in helpers now
- preserve current public/runtime-compatible formats where possible
- move future changes like `paper_key` or run-id format behind those helpers later

## 3. Proposed Files

## 3.1 New file

### `/Users/jangseongjin/paperpipe/src/services/identity.py`

Reason:

- this keeps the helper layer close to `runtime_paths.py`
- avoids introducing a new package convention during the same PR
- minimizes churn relative to the current codebase

Proposed functions:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def normalize_doi(value: str) -> str: ...


def bridge_doc_id_to_paper_id(doc_id: str) -> str: ...


def make_runtime_paper_id(
    *,
    paper_id: str | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    zotero_key: str | None = None,
    file_path: str | Path | None = None,
) -> str: ...


def new_job_id() -> str: ...


def new_run_id(now: datetime | None = None) -> str: ...


def artifact_paper_segment(paper_id: str) -> str: ...
```

Function semantics:

- `normalize_doi()`
  - lowercases
  - strips `https://doi.org/` and `doi:` prefixes
  - trims whitespace
- `bridge_doc_id_to_paper_id()`
  - preserves prefixed ids like `doi:...`, `pmid:...`, `zotero:...`
  - converts `file:...` into a stable runtime-safe fallback string without pretending it is canonical
- `make_runtime_paper_id()`
  - central factory for future callers
  - priority order for now:
    1. explicit `paper_id`
    2. `zotero:<key>`
    3. `doi:<normalized>`
    4. `pmid:<value>`
    5. bridged `file:` fallback
- `new_job_id()`
  - returns current `uuid4()` string for compatibility
- `new_run_id()`
  - returns current `run_YYYYMMDD_HHMMSS` format for compatibility
  - uses UTC explicitly inside the helper
- `artifact_paper_segment()`
  - returns the current path segment for a paper
  - in `PR-I1` this will still be the raw `paper_id`
  - later `paper_key` migration will replace the implementation, not the callers

## 3.2 Existing files to update

### `/Users/jangseongjin/paperpipe/src/jobs/queue.py`

Replace inline generation:

- `job_id = str(uuid.uuid4())`
- `run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"`

with helper calls:

- `job_id = new_job_id()`
- `run_id = new_run_id()`

### `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`

Replace fallback `run_id = str(uuid.uuid4())` with:

- `run_id = new_run_id()`

Replace raw artifact path assembly with:

- `artifact_dir = artifact_run_dir(paper_id, run_id)`

Also use `bridge_doc_id_to_paper_id()` only where a doc/runtime identity bridge is actually needed.

### `/Users/jangseongjin/paperpipe/backend/main.py`

Remove local raw assembly logic and delegate to helpers:

- `_artifact_run_dir()` should call `artifact_run_dir(paper_id, run_id)`
- any direct `artifacts_root() / paper_id` should become helper-based

### `/Users/jangseongjin/paperpipe/backend/routers/obsidian.py`

Replace:

- `artifacts_root() / paper_id / run_id / filename`

with:

- `artifact_run_dir(paper_id, run_id) / filename`

### `/Users/jangseongjin/paperpipe/src/services/paper_ops_summary.py`

Replace:

- `paper_dir = artifacts_path / paper_id`

with helper-backed paper-dir lookup.

### `/Users/jangseongjin/paperpipe/src/exporter.py`

Any artifact lookup path that currently depends on raw `paper_id` concatenation should use the same helper-backed directory contract.

### `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`

Do not redesign this file in `PR-I1`.

Only keep or expose the path helpers needed by the new identity layer:

- `artifact_paper_dir()`
- `artifact_run_dir()`

If needed, implementation can change to route through `artifact_paper_segment()`.

## 4. Behavior Preservation Rules

### 4.1 Keep current `run_id` format

Even though a future ULID/v7 move may be desirable, `PR-I1` should keep the public/runtime-observed run-id shape stable.

Reason:

- current tests and artifact expectations already assume `run_YYYYMMDD_HHMMSS`
- the problem right now is fragmentation, not lack of entropy

### 4.2 Keep current artifact layout

Do not change:

- `storage/artifacts/{paper_id}/{run_id}`

in `PR-I1`.

Reason:

- the purpose of this PR is to centralize the assembly points first
- actual `paper_key` migration should happen only after helper adoption is complete

### 4.3 Do not unify `doc_id` and `paper_id` by force

`PR-I1` should introduce a bridge helper, not pretend these are already the same identity.

Reason:

- current code really does use them for different layers
- forcing equivalence now would hide real edge cases

## 5. Exact Implementation Tasks

1. add `/Users/jangseongjin/paperpipe/src/services/identity.py`
2. replace inline runtime id generation in `/Users/jangseongjin/paperpipe/src/jobs/queue.py`
3. replace fallback run-id generation in `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
4. replace ad hoc artifact path assembly in:
   - `/Users/jangseongjin/paperpipe/backend/main.py`
   - `/Users/jangseongjin/paperpipe/backend/routers/obsidian.py`
   - `/Users/jangseongjin/paperpipe/src/services/paper_ops_summary.py`
   - `/Users/jangseongjin/paperpipe/src/exporter.py`
5. add narrow doc-to-runtime bridge helpers where currently needed
6. update tests or add new tests for helper behavior

## 6. Test Plan

## 6.1 New tests

### `/Users/jangseongjin/paperpipe/tests/test_identity_helpers.py`

Recommended test names:

- `test_normalize_doi_strips_prefixes_and_lowercases`
- `test_make_runtime_paper_id_prefers_zotero_then_doi_then_pmid`
- `test_bridge_doc_id_to_paper_id_preserves_prefixed_ids`
- `test_new_job_id_returns_uuid_string`
- `test_new_run_id_matches_current_format`
- `test_artifact_paper_segment_is_identity_in_v1`

## 6.2 Updated/affected existing tests

Re-run at minimum:

- `/Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py`
- `/Users/jangseongjin/paperpipe/tests/test_artifacts_runs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_obsidian_artifacts_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_db_get_paper_by_id.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_events_persistence.py`

Optional but useful:

- `/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py`

## 7. Acceptance Criteria

`PR-I1` is done only if all are true:

1. runtime id generation is no longer duplicated across queue/runner call sites
2. artifact path assembly is no longer duplicated across major runtime/API call sites
3. helper behavior preserves current observable runtime behavior
4. no artifact layout migration is required for the PR to pass
5. the helper layer makes later `paper_key` and resolver work a local change instead of a repo-wide search-and-replace

## 8. Explicit Non-goals

- no `paper_key` storage migration in this PR
- no `execution_runs` / `job_events` / `user_actions` tables in this PR
- no deterministic chunk ids in this PR
- no `grounded` / `resolution` claim fields in this PR
- no Meeting Pack adoption or frontend work in this PR

## 9. Follow-up Dependency

The next PR after `PR-I1` should be:

- `/Users/jangseongjin/paperpipe/docs/Audit_Driven_Roadmap_2026-03-13.md` -> `PR-I2 Deterministic Chunk IDs`

Reason:

- once call sites are centralized, deterministic chunk-id migration becomes a contained refactor instead of a repository-wide breakage risk

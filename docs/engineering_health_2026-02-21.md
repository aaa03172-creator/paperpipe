# Engineering Health Check - 2026-02-22

## Snapshot
- Runtime Python lines (`src` + `backend`): `13,002`
- Test Python lines (`tests`): `7,014`
- Test-to-runtime line ratio: `53.9%`
- Current test status: `210 passed, 1 skipped, 8 warnings`

## 1) Modularization Status
Large files (`>500` lines): none at this checkpoint.

Largest runtime modules (current top):
- `backend/services/job_runner.py` (`463`)
- `src/processor.py` (`253`)
- `src/downloader/router.py` (`244`)
- `src/db.py` (`244`, deprecated compatibility layer)

Risk:
- Primary blast radius moved to `backend/services/job_runner.py`.
- Contract stability across `backend/main.py` ↔ `src/jobs/*` is now the main review focus.

Action (recommended order):
1. Keep `backend/services/job_runner.py` below `500` lines by extracting stage-specific helpers before adding new Phase 3.x logic.
2. Maintain `src/db_utils` as canonical runtime DB API and keep `src/db.py` wrapper-only.
3. Require API/queue contract tests whenever `src/jobs/schemas.py` changes.

## 2) Duplicate Logic / Drift Risk
Observed:
- Legacy DB dual-path (`src/db.py` and `src/db_utils.py`) still exists.
- LLM provider adapters intentionally share small repeated blocks (accepted duplicate for provider isolation).
- Fetch modules (`src/fetchers.py`, `src/fetch/pubmed.py`, `src/fetch/arxiv.py`) retain repeated constants/import scaffolding.

Action:
1. Keep `src/db.py` deprecated and wrapper-only.
2. Reject new imports from `src.db` in runtime paths.
3. Add CI check to fail on new `from src.db import ...` usage outside approved legacy list.

## 3) Test Coverage Posture
Strength:
- Full suite remains green after queue/API hardening.
- New queue claim tests now protect ordering + single-running constraints.

Gaps to watch:
- `backend/services/job_runner.py` still has multiple exception branches best covered by failure-path tests.
- SSE stream behavior (`/jobs/{id}/events`) has light direct coverage relative to operational importance.

Action:
1. Maintain command-level smoke tests for `read/done/deepread`.
2. Add direct API tests for job cancel/done SSE sequence.
3. Add regression tests before moving legacy wrappers or schema-related logic.

## 4) Governance Rules (Immediate)
1. Any file crossing `700` lines requires either:
   - split plan in same PR, or
   - issue/ticket with explicit deadline.
2. Runtime DB access must use `src/db_utils`.
3. Any schema-touching PR must include:
   - migration safety test
   - duplicate/open-row safety test where relevant

Enforcement note:
- Runtime size guard is now automated by `tests/test_runtime_module_size_guard.py` (threshold `700` lines).

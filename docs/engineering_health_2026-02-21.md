# Engineering Health Check - 2026-02-21

## Snapshot
- `src` Python lines: `10,566`
- `tests` Python lines: `5,969`
- Test-to-source line ratio: `56.5%`
- `src` Python files: `76`
- `tests` Python files: `63`
- Current test status: `156 passed, 7 warnings`

## 1) Modularization Status
Large files (`>500` lines) currently include:
- `src/cli.py` (`1079`)
- `src/llm_provider.py` (`833`)
- `src/exporter.py` (`616`)
- `src/obsidian.py` (`564`)
- `src/db_utils.py` (`516`)

Risk:
- Change blast radius is high in these files.
- Review/ownership boundaries are unclear.

Action (recommended order):
1. Split `src/cli.py` into command modules by domain (`ops`, `profile`, `deepread`, `maintenance`).
2. Split `src/llm_provider.py` into provider adapters + JSON handling + retry policy.
3. Keep `db_utils` as canonical DB API and move remaining legacy access behind compatibility wrappers only.

## 2) Duplicate Logic / Drift Risk
Observed:
- Historical DB dual-path (`src/db.py` and `src/db_utils.py`) created behavioral drift.
- Runtime callers are now being migrated to `src/db_utils`, but compatibility code still exists for legacy flows/tests.

Action:
1. Keep `src/db.py` deprecated and wrapper-only.
2. Reject new imports from `src.db` in runtime paths.
3. Add CI check to fail on new `from src.db import ...` usage outside approved legacy list.

## 3) Test Coverage Posture
Strength:
- Absolute test volume is healthy for current size.
- Recent refactors were validated against full suite.

Gaps to watch:
- High-line modules can still hide untested branches.
- CLI command matrix is large; smoke tests should expand gradually by command group.

Action:
1. Maintain command-level smoke tests for `read/done/deepread`.
2. Add per-module risk tests when touching `cli.py`, `llm_provider.py`, `exporter.py`.
3. Add regression tests before moving legacy wrappers or schema-related logic.

## 4) Governance Rules (Immediate)
1. Any file crossing `700` lines requires either:
   - split plan in same PR, or
   - issue/ticket with explicit deadline.
2. Runtime DB access must use `src/db_utils`.
3. Any schema-touching PR must include:
   - migration safety test
   - duplicate/open-row safety test where relevant


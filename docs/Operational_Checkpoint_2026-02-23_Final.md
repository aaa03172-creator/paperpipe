# Operational Checkpoint (2026-02-23)

## Final State
- Branch: `codex/mainline-sync-20260223-r3`
- QA (default operational mode):
  - `Total Active Papers (APPROVED/INDEXED): 52`
  - `Missing Summary: 0`
  - `Missing/Invalid ClaimSet (Operational): 0`
  - `Missing Markdown Files: 0`
  - `FAILED Papers (papers table): 0`
- Jobs table:
  - `completed: 57`
  - `failed: 0`
  - `running: 0`
  - `queued: 0`
- Archived failures:
  - table: `job_failures_archive`
  - rows: `12`
  - reasons:
    - `pdf_not_found_recovered`: 10
    - `test_fixture_failed_legacy`: 2

## Notes
- `qa_report` default mode excludes fixture records (`local--`, `integration_test_*`, `/tests/` paths).
- ClaimSet backlog is fully drained (`0`) as of this checkpoint.
- A backup DB snapshot was created before failed-job archive apply:
  - `storage/backups/state_before_failed_archive_20260223_214423.db`

## Repro Commands
```bash
python3 scripts/qa_report.py
python3 - <<'PY'
import sqlite3
conn=sqlite3.connect('storage/state.db')
cur=conn.cursor()
print(dict(cur.execute("select status,count(*) from jobs group by status").fetchall()))
print(cur.execute("select count(*) from job_failures_archive").fetchone()[0])
conn.close()
PY
```

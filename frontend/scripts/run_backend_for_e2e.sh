#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="$(command -v python3 || command -v python)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

"${PYTHON_BIN}" - <<'PY'
import sqlite3
from pathlib import Path

root = Path.cwd()
db_path = root / "storage" / "state.db"
db_path.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db_path)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS papers (
        paper_id TEXT PRIMARY KEY,
        title TEXT,
        pdf_path TEXT,
        updated_at TEXT
    )
    """
)
pdf = root / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-001",
        "E2E Seed Paper",
        str(pdf.resolve()),
    ),
)
conn.commit()
conn.close()
PY

"${PYTHON_BIN}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

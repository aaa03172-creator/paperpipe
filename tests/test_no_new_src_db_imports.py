from pathlib import Path
import re


IMPORT_PATTERNS = [
    re.compile(r"^\s*from\s+src\.db\s+import\s+", re.MULTILINE),
    re.compile(r"^\s*import\s+src\.db(?:\s+as\s+\w+)?\s*$", re.MULTILINE),
]

# Legacy compatibility tests are allowed to import src.db directly.
ALLOWED = {
    "tests/test_db_path_alignment.py",
    "tests/test_db_get_paper_by_id.py",
    "tests/test_db_schema_compat.py",
}


def test_no_new_direct_src_db_imports_outside_allowlist():
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if rel == "src/db.py" or rel in ALLOWED:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in IMPORT_PATTERNS):
            offenders.append(rel)

    assert not offenders, f"Direct src.db imports are disallowed. Offenders: {offenders}"

from pathlib import Path


MAX_RUNTIME_MODULE_LINES = 700


def test_runtime_modules_stay_under_size_guardrail():
    root = Path(__file__).resolve().parents[1]
    runtime_dirs = [root / "src", root / "backend"]
    offenders: list[tuple[str, int]] = []

    for base in runtime_dirs:
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            rel = py.relative_to(root).as_posix()
            line_count = sum(1 for _ in py.open("r", encoding="utf-8", errors="ignore"))
            if line_count > MAX_RUNTIME_MODULE_LINES:
                offenders.append((rel, line_count))

    assert not offenders, (
        f"Runtime module size guard failed (> {MAX_RUNTIME_MODULE_LINES} lines): "
        + ", ".join(f"{path} ({count})" for path, count in offenders)
    )

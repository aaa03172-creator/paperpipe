from pathlib import Path
import re


BUNDLE_ROUTE_PATTERNS = (
    re.compile(r"/paper-syntheses/\{synthesis_id\}(?!/)"),
    re.compile(r"/paper-syntheses/\$\{[^}]+\}(?!/)"),
    re.compile(r"/paper-syntheses/papersynth_[A-Za-z0-9._-]+(?!/)"),
    re.compile(r"/paper-syntheses/papersynth_missing(?!/)"),
)

# Allowed remaining surfaces:
# - backend compatibility route owner
# - bounded docs that explain the compatibility route
# - explicit backward-compat tests
ALLOWED = {
    "backend/routers/paper_syntheses.py",
    "docs/PAPER_SYNTHESIS.md",
    "docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md",
    "scripts/check_paper_synthesis_bundle_route_usage.py",
    "scripts/check_paper_synthesis_bundle_route_removal_readiness.py",
    "tests/test_bounded_artifact_handoff_bridge.py",
    "tests/test_paper_syntheses_api.py",
    "tests/test_paper_synthesis_bundle_route_scripts.py",
    "tests/test_no_new_paper_synthesis_bundle_route_usage.py",
}

SKIP_PREFIXES = (
    ".codex/",
    "build/",
    "dist/",
    "docs/reports/",
    "storage/",
    "frontend/.e2e-backend-runtime/",
    "tests/fixtures/",
)

TEXT_SUFFIXES = {".py", ".md", ".ts", ".tsx", ".yaml", ".yml"}


def test_no_new_paper_synthesis_bundle_route_usage_outside_allowlist() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in ALLOWED or any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in BUNDLE_ROUTE_PATTERNS):
            offenders.append(rel)

    assert not offenders, (
        "Paper synthesis compatibility bundle route should not spread outside allowlist. "
        f"Offenders: {offenders}"
    )

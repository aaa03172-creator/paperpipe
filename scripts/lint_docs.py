#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

RETIRED_STUB_TARGETS = {
    "docs/Lattice_v3_UIUX_MASTER.md": "docs/Lattice_v3_Master_Spec.md",
    "docs/PaperPipe_v3_Master_Spec.md": "docs/Lattice_v3_Master_Spec.md",
    "docs/PaperPipe_v3_Master_Spec_Final_Blueprint_v1_2.md": "docs/Lattice_v3_Master_Spec.md",
    "docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md": (
        "docs/PaperPipe_Minimum_Operating_Principles.md"
    ),
}

COMMON_ALLOWED_RETIRED_STUB_REFERENCERS = {
    "scripts/lint_docs.py",
    "tests/test_lint_docs.py",
}

MASTER_SPEC_STUBS = {
    "docs/Lattice_v3_UIUX_MASTER.md",
    "docs/PaperPipe_v3_Master_Spec.md",
    "docs/PaperPipe_v3_Master_Spec_Final_Blueprint_v1_2.md",
}

ALLOWED_RETIRED_STUB_REFERENCERS_BY_STUB = {
    "docs/Lattice_v3_UIUX_MASTER.md": {
        "docs/README.md",
        "docs/Lattice_v3_Master_Spec.md",
        "docs/UIUX_Adoption_Filter_2026-02-25.md",
        *COMMON_ALLOWED_RETIRED_STUB_REFERENCERS,
        *MASTER_SPEC_STUBS,
    },
    "docs/PaperPipe_v3_Master_Spec.md": {
        "docs/README.md",
        "docs/Lattice_v3_Master_Spec.md",
        *COMMON_ALLOWED_RETIRED_STUB_REFERENCERS,
        *MASTER_SPEC_STUBS,
    },
    "docs/PaperPipe_v3_Master_Spec_Final_Blueprint_v1_2.md": {
        "docs/README.md",
        "docs/Lattice_v3_Master_Spec.md",
        *COMMON_ALLOWED_RETIRED_STUB_REFERENCERS,
        *MASTER_SPEC_STUBS,
    },
    "docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md": {
        "docs/README.md",
        "docs/reports/README.md",
        "docs/reports/External_Harness_Discipline_Fit_Review_2026-04-03.md",
        "docs/reports/Lightweight_Contracts_Followup_Review_2026-04-03.md",
        *COMMON_ALLOWED_RETIRED_STUB_REFERENCERS,
        "docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md",
    },
}

ROOT_REPORT_PREFIXES = (
    "Local_Batch_Validation_",
    "Local_Reader_Audit_",
    "tmp_",
    "release_notes_",
)

SKIP_DIRS = {
    ".git",
    "node_modules",
    "build",
    "dist",
    ".vite",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".e2e-backend-runtime",
    ".codex",
    "tmp",
    "storage",
}

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".tsx",
    ".ts",
    ".js",
}

HEADER_SCAN_LIMIT = 20
HEADER_METADATA_PREFIXES = (
    "Status:",
    "Date:",
    "Owner:",
    "Canonical:",
    "Canonical parent:",
    "Purpose:",
)


def iter_repo_files() -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if path.suffix and path.suffix not in TEXT_SUFFIXES:
                continue
            files.append(path)
    return files


def has_status_metadata(text: str) -> bool:
    if text.startswith("---") and text.count("---") >= 2:
        frontmatter = text.split("---", 2)[1]
        return any(line.strip().startswith("status:") for line in frontmatter.splitlines())

    lines = text.splitlines()[:HEADER_SCAN_LIMIT]
    index = 0

    while index < len(lines) and not lines[index].strip():
        index += 1

    if index < len(lines) and lines[index].strip().startswith("#"):
        index += 1

        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                break
            if any(stripped.startswith(prefix) for prefix in HEADER_METADATA_PREFIXES):
                break
            if stripped.startswith("#"):
                break
            index += 1

        while index < len(lines) and not lines[index].strip():
            index += 1

    saw_metadata_block = False
    saw_status = False

    for line in lines[index:]:
        stripped = line.strip()

        if not stripped:
            if saw_metadata_block:
                break
            continue

        if stripped.startswith("#") and not saw_metadata_block:
            continue

        if any(stripped.startswith(prefix) for prefix in HEADER_METADATA_PREFIXES):
            saw_metadata_block = True
            if stripped.startswith("Status:"):
                saw_status = True
            continue

        break

    return saw_status


def lint_root_doc_metadata(issues: list[str]) -> None:
    for path in sorted(DOCS.glob("*.md")):
        text = path.read_text(errors="ignore")
        if not has_status_metadata(text):
            issues.append(f"missing metadata header: {path.relative_to(ROOT)}")

    for path in (DOCS / "reports" / "README.md", DOCS / "archive" / "README.md"):
        if not path.exists():
            issues.append(f"missing index doc: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(errors="ignore")
        if not has_status_metadata(text):
            issues.append(f"missing metadata header: {path.relative_to(ROOT)}")


def lint_root_report_leaks(issues: list[str]) -> None:
    for path in sorted(DOCS.glob("*")):
        if not path.is_file():
            continue
        if any(path.name.startswith(prefix) for prefix in ROOT_REPORT_PREFIXES):
            issues.append(f"root docs report leak: {path.relative_to(ROOT)}")


def lint_retired_stubs(issues: list[str]) -> None:
    for rel, target in sorted(RETIRED_STUB_TARGETS.items()):
        path = ROOT / rel
        if not path.exists():
            issues.append(f"missing retired stub: {rel}")
            continue
        text = path.read_text(errors="ignore")
        if "Status: Retired compatibility stub" not in text:
            issues.append(f"retired stub missing status banner: {rel}")
        if f"Canonical target: `{target}`" not in text:
            issues.append(f"retired stub missing canonical target: {rel}")


def find_unexpected_retired_stub_references(rel: str, text: str) -> list[str]:
    issues: list[str] = []
    for stub in sorted(RETIRED_STUB_TARGETS):
        if stub not in text:
            continue
        allowed_referrers = ALLOWED_RETIRED_STUB_REFERENCERS_BY_STUB.get(
            stub, COMMON_ALLOWED_RETIRED_STUB_REFERENCERS
        )
        if rel in allowed_referrers:
            continue
        issues.append(
            f"unexpected retired compatibility stub reference in {rel}: {stub}"
        )
    return issues


def lint_retired_stub_references(issues: list[str]) -> None:
    repo_files = iter_repo_files()
    for path in repo_files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(errors="ignore")
        issues.extend(find_unexpected_retired_stub_references(rel, text))


def main() -> int:
    issues: list[str] = []
    lint_root_doc_metadata(issues)
    lint_root_report_leaks(issues)
    lint_retired_stubs(issues)
    lint_retired_stub_references(issues)

    if issues:
        print("docs lint failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("docs lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

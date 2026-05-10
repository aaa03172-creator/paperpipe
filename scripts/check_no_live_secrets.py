from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


SECRET_ASSIGNMENT_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<name>(?:OPENAI|ANTHROPIC|LATTICE|PAPERPIPE)_[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD))\s*=\s*(?P<value>.+?)\s*$"
)
OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9][A-Za-z0-9_-]{12,}\b")
ANTHROPIC_KEY_RE = re.compile(r"\bsk-ant-[A-Za-z0-9_-]{12,}\b")

ALLOWED_VALUES = {
    "",
    '""',
    "''",
    "<redacted>",
    "<api_key>",
    "<your-api-key>",
    "change-me",
    "placeholder",
    "test-key",
    "secret-key",
    "legacy-key",
}

DEFAULT_EXTRA_FILES = (".env",)
SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv314",
    "node_modules",
    "dist",
    "build",
    "tests",
}


def _git_tracked_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [root / line for line in result.stdout.splitlines() if line.strip()]


def _is_example_path(path: Path) -> bool:
    lowered = path.name.lower()
    return lowered.endswith(".example") or ".example." in lowered or "fixtures" in path.parts


def _is_skipped(path: Path) -> bool:
    return any(part in SKIPPED_DIRS for part in path.parts)


def _normalize_assignment_value(value: str) -> str:
    text = value.strip()
    if "#" in text:
        text = text.split("#", 1)[0].strip()
    return text.strip().strip('"').strip("'").strip()


def _looks_allowed_assignment(value: str) -> bool:
    normalized = _normalize_assignment_value(value)
    lowered = normalized.lower()
    if lowered in ALLOWED_VALUES:
        return True
    if lowered.startswith("${") and lowered.endswith("}"):
        return True
    if lowered.startswith("$"):
        return True
    return False


def _scan_file(path: Path, root: Path) -> list[str]:
    if _is_skipped(path) or _is_example_path(path) or not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except OSError as exc:
        return [f"{path.relative_to(root)}: unable to read file: {exc}"]

    findings: list[str] = []
    rel = path.relative_to(root)
    for index, line in enumerate(text.splitlines(), start=1):
        assignment = SECRET_ASSIGNMENT_RE.match(line)
        if assignment and not _looks_allowed_assignment(assignment.group("value")):
            findings.append(f"{rel}:{index}: live-looking secret assignment for {assignment.group('name')}")
            continue
        if OPENAI_KEY_RE.search(line) or ANTHROPIC_KEY_RE.search(line):
            findings.append(f"{rel}:{index}: live-looking provider API key")
    return findings


def scan(root: Path, *, extra_files: tuple[str, ...] = DEFAULT_EXTRA_FILES) -> list[str]:
    root = root.resolve()
    paths = _git_tracked_files(root)
    for extra in extra_files:
        path = root / extra
        if path.exists() and path not in paths:
            paths.append(path)
    findings: list[str] = []
    for path in sorted(set(paths)):
        findings.extend(_scan_file(path.resolve(), root))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail if live-looking provider secrets are present in repo files.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to scan.")
    parser.add_argument(
        "--extra-file",
        action="append",
        dest="extra_files",
        default=None,
        help="Additional untracked local file to scan. Repeatable. Defaults to .env.",
    )
    args = parser.parse_args(argv)

    findings = scan(args.root, extra_files=tuple(args.extra_files or DEFAULT_EXTRA_FILES))
    if findings:
        print("Live-looking secrets found:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("No live-looking provider secrets found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

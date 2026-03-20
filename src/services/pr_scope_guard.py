from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

DEFAULT_ALLOWED_DOCS_WITH_CODE = {
    "docs/API_CHAT_CONTRACT.md",
    "docs/Current_Code_Baseline_Audit_2026-03-13.md",
    "docs/MEETING_PACK.md",
    "docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md",
    "docs/Pending_PR_Queue.md",
    "docs/Repository_Baseline_Adoption_2026-03-13.md",
    "docs/archive/PR_M0_Staged_Candidate_Validation_2026-03-17.md",
    "docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md",
    "docs/reports/Backend_API_PR_Packaging_2026-03-18.md",
    "docs/reports/Committed_Backend_API_Stack_Summary_2026-03-18.md",
    "docs/reports/Current_Baseline_Recheck_2026-03-18.md",
}


@dataclass(frozen=True)
class ScopeReport:
    doc_files: list[str]
    code_files: list[str]
    allowed_doc_files: list[str]
    blocked_doc_files: list[str]

    @property
    def has_mixed_scope(self) -> bool:
        return bool(self.doc_files and self.code_files)

    @property
    def is_allowed(self) -> bool:
        if not self.has_mixed_scope:
            return True
        return not self.blocked_doc_files


@dataclass(frozen=True)
class TitleScopeReport:
    policy: str
    violating_files: list[str]
    message: str

    @property
    def is_allowed(self) -> bool:
        return not self.violating_files


def normalize_paths(paths: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw in paths:
        value = (raw or "").strip()
        if not value:
            continue
        normalized.append(value.replace("\\", "/"))
    return normalized


def is_doc_file(path: str) -> bool:
    p = path.strip().replace("\\", "/")
    if p.startswith("docs/"):
        return True
    # Root-level markdown is treated as docs scope.
    return "/" not in p and p.lower().endswith(".md")


def classify_scope(files: Sequence[str], allowed_docs_with_code: set[str] | None = None) -> ScopeReport:
    normalized = normalize_paths(files)
    allowed_docs = set(allowed_docs_with_code or DEFAULT_ALLOWED_DOCS_WITH_CODE)

    doc_files: list[str] = []
    code_files: list[str] = []
    allowed_doc_files: list[str] = []
    blocked_doc_files: list[str] = []

    for path in normalized:
        if is_doc_file(path):
            doc_files.append(path)
        else:
            code_files.append(path)

    for path in doc_files:
        if path in allowed_docs:
            allowed_doc_files.append(path)
        else:
            blocked_doc_files.append(path)

    return ScopeReport(
        doc_files=sorted(doc_files),
        code_files=sorted(code_files),
        allowed_doc_files=sorted(allowed_doc_files),
        blocked_doc_files=sorted(blocked_doc_files),
    )


def infer_title_policy(title: str | None) -> str:
    raw = (title or "").strip().lower()
    if raw.startswith("docs(") or raw.startswith("docs:") or raw.startswith("docs "):
        return "docs"
    if raw.startswith("test(") or raw.startswith("test:") or raw.startswith("test "):
        return "test"
    return "none"


def classify_title_scope(
    title: str | None,
    files: Sequence[str],
    *,
    allowed_docs_with_code: set[str] | None = None,
) -> TitleScopeReport:
    policy = infer_title_policy(title)
    normalized = normalize_paths(files)
    allowed_docs = set(allowed_docs_with_code or DEFAULT_ALLOWED_DOCS_WITH_CODE)

    if policy == "none":
        return TitleScopeReport(policy=policy, violating_files=[], message="no title policy")

    if policy == "docs":
        violations = sorted([path for path in normalized if not is_doc_file(path)])
        msg = "docs-title PR must contain docs files only"
        return TitleScopeReport(policy=policy, violating_files=violations, message=msg)

    # policy == "test"
    violations = sorted(
        [path for path in normalized if not (path.startswith("tests/") or path in allowed_docs)]
    )
    msg = "test-title PR must contain tests/* files only (plus allowlisted queue doc)"
    return TitleScopeReport(policy=policy, violating_files=violations, message=msg)

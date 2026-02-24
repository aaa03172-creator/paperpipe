from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

DEFAULT_ALLOWED_DOCS_WITH_CODE = {"docs/Pending_PR_Queue.md"}


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

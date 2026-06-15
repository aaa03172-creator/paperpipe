from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from src.config import load_config
from src.db_utils import get_all_papers, init_db, mark_as_retracted
from src.retraction import check_retraction

logger = logging.getLogger(__name__)

RetractionChecker = Callable[[str, str | None], dict[str, Any]]
RetractionMarker = Callable[[str], bool]


@dataclass(frozen=True)
class RetractionAuditPaperResult:
    doi: str | None
    title: str | None
    status: str
    is_retracted: bool = False
    retraction_details: str | None = None
    marked: bool = False
    error: str | None = None


@dataclass(frozen=True)
class RetractionAuditSummary:
    total_papers: int
    checked_count: int
    skipped_known_retracted: int
    skipped_missing_identifier: int
    retracted_count: int
    marked_count: int
    error_count: int
    apply: bool
    results: list[RetractionAuditPaperResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_papers": self.total_papers,
            "checked_count": self.checked_count,
            "skipped_known_retracted": self.skipped_known_retracted,
            "skipped_missing_identifier": self.skipped_missing_identifier,
            "retracted_count": self.retracted_count,
            "marked_count": self.marked_count,
            "error_count": self.error_count,
            "apply": self.apply,
            "results": [item.__dict__ for item in self.results],
        }


def run_retraction_audit(
    *,
    apply: bool = False,
    limit: int | None = None,
    sleep_seconds: float = 0.5,
    email: str | None = None,
    papers: list[dict[str, Any]] | None = None,
    checker: RetractionChecker = check_retraction,
    marker: RetractionMarker = mark_as_retracted,
) -> RetractionAuditSummary:
    """Run an explicit ops-only retraction audit.

    By default this is a dry run: external retraction checks are performed, but
    the runtime DB is not modified unless ``apply=True``.
    """
    init_db()
    if papers is None:
        papers = get_all_papers()
    selected_papers = papers[: max(limit, 0)] if limit is not None else list(papers)
    if email is None:
        email = _configured_unpaywall_email()

    results: list[RetractionAuditPaperResult] = []
    checked_count = 0
    skipped_known_retracted = 0
    skipped_missing_identifier = 0
    retracted_count = 0
    marked_count = 0
    error_count = 0

    for paper in selected_papers:
        doi = _clean_optional_text(paper.get("doi"))
        title = _clean_optional_text(paper.get("title"))
        if paper.get("is_retracted"):
            skipped_known_retracted += 1
            results.append(RetractionAuditPaperResult(doi=doi, title=title, status="skipped_known_retracted"))
            continue
        if not doi:
            skipped_missing_identifier += 1
            results.append(RetractionAuditPaperResult(doi=doi, title=title, status="skipped_missing_identifier"))
            continue

        checked_count += 1
        try:
            check_result = checker(doi, email)
            is_retracted = bool(check_result.get("is_retracted"))
            details = _clean_optional_text(check_result.get("retraction_details"))
            marked = False
            status = "clean"
            if is_retracted:
                retracted_count += 1
                status = "retracted_found"
                if apply:
                    marked = marker(doi)
                    if marked:
                        marked_count += 1
                    status = "marked_retracted" if marked else "mark_failed"
            results.append(
                RetractionAuditPaperResult(
                    doi=doi,
                    title=title,
                    status=status,
                    is_retracted=is_retracted,
                    retraction_details=details,
                    marked=marked,
                )
            )
        except Exception as exc:
            error_count += 1
            logger.warning("Retraction audit failed for %s: %s", doi, exc)
            results.append(
                RetractionAuditPaperResult(
                    doi=doi,
                    title=title,
                    status="error",
                    error=str(exc),
                )
            )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return RetractionAuditSummary(
        total_papers=len(selected_papers),
        checked_count=checked_count,
        skipped_known_retracted=skipped_known_retracted,
        skipped_missing_identifier=skipped_missing_identifier,
        retracted_count=retracted_count,
        marked_count=marked_count,
        error_count=error_count,
        apply=apply,
        results=results,
    )


def _configured_unpaywall_email() -> str | None:
    try:
        return load_config().system.unpaywall_email
    except Exception:
        return None


def _clean_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None

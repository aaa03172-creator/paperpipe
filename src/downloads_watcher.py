from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src import downloads_watcher_core as watcher_core
from src import downloads_watcher_store as watcher_store

logger = logging.getLogger(__name__)

REVIEW_NEEDS_PDF_MATCH = "NEEDS_PDF_MATCH"
UNMATCHED_SENTINEL_PAPER_ID = "__UNMATCHED__"
DOI_RE = watcher_core.DOI_RE


@dataclass
class DownloadWatchResult:
    status: str
    destination: Optional[Path]
    matched_paper_id: Optional[str]
    note: str = ""


def _normalize_doi(value: str | None) -> str:
    return watcher_core.normalize_doi(value)


def _sanitize_text(value: str) -> str:
    return watcher_core.sanitize_text(value)


def _extract_doi_from_filename(path: Path) -> str:
    return watcher_core.extract_doi_from_filename(path)


def _extract_doi_candidates_from_pdf_content(path: Path) -> list[tuple[str, str]]:
    return watcher_core.extract_doi_candidates_from_pdf_content(path)


def _tokenize_text_for_score(value: str) -> set[str]:
    return watcher_core.tokenize_text_for_score(value)


def _is_confident_content_doi_match(file_stem: str, row: dict[str, Any], source: str) -> bool:
    return watcher_core.is_confident_content_doi_match(file_stem, row, source)


def _load_manual_required_candidates() -> list[dict[str, Any]]:
    return watcher_store.load_manual_required_candidates()


def _enqueue_pdf_match_review(paper_id: str, reason: str, allow_multiple_open: bool = False) -> bool:
    return watcher_store.enqueue_pdf_match_review(
        paper_id=paper_id,
        reason=reason,
        decision=REVIEW_NEEDS_PDF_MATCH,
        allow_multiple_open=allow_multiple_open,
    )


def _update_downloaded_path(paper_id: str, destination: Path) -> None:
    watcher_store.update_downloaded_path(paper_id=paper_id, destination=destination)


def _best_title_candidates(filename_stem: str, rows: list[dict[str, Any]], threshold: float) -> list[tuple[float, dict[str, Any]]]:
    return watcher_core.best_title_candidates(filename_stem, rows, threshold)


def _resolve_destination(storage_dir: Path, paper_id: str, suffix: str = ".pdf") -> Path:
    return watcher_core.resolve_destination(storage_dir, paper_id, suffix)


def process_downloaded_pdf(
    file_path: Path,
    downloads_watch_dir: Path | None = None,
    pdf_storage_dir: Path | None = None,
    title_threshold: float = 0.90,
) -> DownloadWatchResult:
    source = Path(file_path)
    if not source.exists():
        return DownloadWatchResult(status="missing_file", destination=None, matched_paper_id=None, note="source_not_found")

    storage_dir = Path(pdf_storage_dir or Path("storage/pdfs")).expanduser()
    unmatched_dir = storage_dir / "_unmatched"
    candidates = _load_manual_required_candidates()

    doi_candidates: list[tuple[str, str]] = []
    filename_doi = _extract_doi_from_filename(source)
    if filename_doi:
        doi_candidates.append((filename_doi, "filename"))

    for doi, source_type in _extract_doi_candidates_from_pdf_content(source):
        if not any(existing == doi for existing, _ in doi_candidates):
            doi_candidates.append((doi, source_type))

    for doi, source_type in doi_candidates:
        doi_hits = [r for r in candidates if _normalize_doi(str(r.get("doi") or "")) == doi]
        if not doi_hits:
            continue

        if len(doi_hits) == 1:
            row = doi_hits[0]
            if source_type != "filename" and not _is_confident_content_doi_match(source.stem, row, source_type):
                continue

            paper_id = str(row["paper_id"])
            dest = _resolve_destination(storage_dir, paper_id, source.suffix.lower() or ".pdf")
            shutil.move(str(source), str(dest))
            _update_downloaded_path(paper_id, dest)
            return DownloadWatchResult(status="matched_doi", destination=dest, matched_paper_id=paper_id, note=f"{doi}:{source_type}")

        if len(doi_hits) > 1:
            unmatched_dir.mkdir(parents=True, exist_ok=True)
            dest = _resolve_destination(unmatched_dir, source.stem, source.suffix.lower() or ".pdf")
            shutil.move(str(source), str(dest))
            for row in doi_hits:
                _enqueue_pdf_match_review(str(row["paper_id"]), f"Ambiguous DOI match for file={source.name}, doi={doi} (source={source_type})")
            return DownloadWatchResult(status="ambiguous_doi", destination=dest, matched_paper_id=None, note=doi)

    # No confident DOI match found.
    title_hits = _best_title_candidates(source.stem, candidates, title_threshold)
    if len(title_hits) == 1:
        row = title_hits[0][1]
        unmatched_dir.mkdir(parents=True, exist_ok=True)
        paper_id = str(row["paper_id"])
        dest = _resolve_destination(storage_dir, paper_id, source.suffix.lower() or ".pdf")
        shutil.move(str(source), str(dest))
        _update_downloaded_path(paper_id, dest)
        return DownloadWatchResult(status="matched_title", destination=dest, matched_paper_id=paper_id)

    unmatched_dir.mkdir(parents=True, exist_ok=True)
    dest = _resolve_destination(unmatched_dir, source.stem, source.suffix.lower() or ".pdf")
    shutil.move(str(source), str(dest))

    # Queue follow-up for likely candidates when we have ambiguous title hits.
    if title_hits:
        for score, row in title_hits[:3]:
            _enqueue_pdf_match_review(
                str(row["paper_id"]),
                f"Ambiguous title match for file={source.name}, score={score:.3f}",
            )
        return DownloadWatchResult(status="ambiguous_title", destination=dest, matched_paper_id=None)

    # Unmatched: queue at least one review record for operational triage.
    if candidates:
        all_scored = _best_title_candidates(source.stem, candidates, threshold=0.0)
        if all_scored:
            best_score, best_row = all_scored[0]
            _enqueue_pdf_match_review(
                str(best_row["paper_id"]),
                f"Unmatched PDF file={source.name}; best_title_score={best_score:.3f}",
            )
        else:
            _enqueue_pdf_match_review(
                UNMATCHED_SENTINEL_PAPER_ID,
                f"Unmatched PDF file={source.name}; no title candidates",
            )
    else:
        _enqueue_pdf_match_review(
            UNMATCHED_SENTINEL_PAPER_ID,
            f"Unmatched PDF file={source.name}; manual_required queue empty",
        )
    return DownloadWatchResult(status="unmatched", destination=dest, matched_paper_id=None)


class DownloadsFileHandler(FileSystemEventHandler):
    def __init__(self, pdf_storage_dir: Path, title_threshold: float = 0.90):
        self.pdf_storage_dir = pdf_storage_dir
        self.title_threshold = title_threshold

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".pdf":
            return
        time.sleep(1)
        try:
            result = process_downloaded_pdf(path, pdf_storage_dir=self.pdf_storage_dir, title_threshold=self.title_threshold)
            logger.info("Downloads watcher processed %s -> %s (%s)", path.name, result.status, result.destination)
        except Exception as exc:
            logger.error("Downloads watcher failed for %s: %s", path.name, exc)


class DownloadsWatcherService:
    def __init__(self, downloads_watch_dir: Path, pdf_storage_dir: Path, title_threshold: float = 0.90):
        self.downloads_watch_dir = downloads_watch_dir.expanduser()
        self.pdf_storage_dir = pdf_storage_dir.expanduser()
        self.title_threshold = title_threshold
        self.observer = Observer()

    def start(self):
        self.downloads_watch_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_storage_dir.mkdir(parents=True, exist_ok=True)
        handler = DownloadsFileHandler(pdf_storage_dir=self.pdf_storage_dir, title_threshold=self.title_threshold)
        self.observer.schedule(handler, str(self.downloads_watch_dir), recursive=False)
        self.observer.start()
        logger.info("Watching downloads dir: %s", self.downloads_watch_dir)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

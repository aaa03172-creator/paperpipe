from __future__ import annotations

import logging
import re
import shutil
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.db_utils import get_db_connection
from src.services.runtime_paths import pdf_storage_root

logger = logging.getLogger(__name__)

REVIEW_NEEDS_PDF_MATCH = "NEEDS_PDF_MATCH"
UNMATCHED_SENTINEL_PAPER_ID = "__UNMATCHED__"
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)


@dataclass
class DownloadWatchResult:
    status: str
    destination: Optional[Path]
    matched_paper_id: Optional[str]
    note: str = ""


def _normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "DOI:"):
        if doi.startswith(prefix.lower()):
            doi = doi[len(prefix) :]
            break
    return doi.strip().rstrip(").,;]>\"'")


def _sanitize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _extract_doi_from_filename(path: Path) -> str:
    stem = path.stem
    # Tolerate common filename substitutions for slash.
    candidate = stem.replace("_", "/")
    match = DOI_RE.search(candidate)
    if match:
        return _normalize_doi(match.group(0))
    return ""


def _extract_doi_candidates_from_pdf_content(path: Path) -> list[tuple[str, str]]:
    # Returns tuples of (doi, source_type) with source_type used for confidence decisions.
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _record(value: str, source: str) -> None:
        doi = _normalize_doi(value)
        if not doi or doi in seen:
            return
        candidates.append((doi, source))
        seen.add(doi)

    # Try structured extraction first when a PDF parser is available.
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        meta = reader.metadata or {}
        for value in meta.values():
            if not value:
                continue
            for match in DOI_RE.finditer(str(value)):
                _record(match.group(0), "metadata")
        for page in reader.pages[:3]:
            text = page.extract_text() or ""
            for match in DOI_RE.finditer(text):
                _record(match.group(0), "text")
    except Exception:
        pass

    # Fallback: scan raw bytes for DOI-like token to support lightweight fixtures.
    try:
        raw = path.read_bytes()
        text = raw.decode("latin-1", errors="ignore")
        for match in DOI_RE.finditer(text):
            _record(match.group(0), "raw")
    except Exception:
        pass
    return candidates


def _tokenize_text_for_score(value: str) -> set[str]:
    return {token for token in _sanitize_text(value).split() if len(token) >= 3}


def _is_confident_content_doi_match(file_stem: str, row: dict[str, Any], source: str) -> bool:
    if source == "metadata":
        return True
    stem_tokens = _tokenize_text_for_score(file_stem)
    if not stem_tokens:
        return False

    title = str(row.get("title") or "")
    title_tokens = _tokenize_text_for_score(title)
    if stem_tokens.intersection(title_tokens):
        return True

    paper_id = str(row.get("paper_id") or "").lower()
    if paper_id and paper_id in file_stem.lower():
        return True

    return SequenceMatcher(None, _sanitize_text(file_stem), _sanitize_text(title)).ratio() >= 0.35


def _load_manual_required_candidates() -> list[dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT paper_id, doi, title
            FROM papers
            WHERE lower(coalesce(pdf_status, '')) = 'manual_required'
            """
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _enqueue_pdf_match_review(paper_id: str, reason: str, allow_multiple_open: bool = False) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if not allow_multiple_open:
            cur.execute(
                """
                SELECT 1 FROM review_queue
                WHERE paper_id = ? AND decision = ? AND resolved_at IS NULL
                LIMIT 1
                """,
                (paper_id, REVIEW_NEEDS_PDF_MATCH),
            )
            if cur.fetchone():
                return False
        cur.execute(
            """
            INSERT INTO review_queue (paper_id, decision, reason)
            VALUES (?, ?, ?)
            """,
            (paper_id, REVIEW_NEEDS_PDF_MATCH, reason),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to enqueue NEEDS_PDF_MATCH for %s: %s", paper_id, exc)
        return False
    finally:
        conn.close()


def _update_downloaded_path(paper_id: str, destination: Path) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE papers
            SET pdf_status = 'downloaded',
                pdf_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE paper_id = ?
            """,
            (str(destination), paper_id),
        )
        conn.commit()
    finally:
        conn.close()


def _best_title_candidates(filename_stem: str, rows: list[dict[str, Any]], threshold: float) -> list[tuple[float, dict[str, Any]]]:
    key = _sanitize_text(filename_stem)
    scored: list[tuple[float, dict[str, Any]]] = []
    if not key:
        return scored
    for row in rows:
        title = _sanitize_text(str(row.get("title") or ""))
        if not title:
            continue
        score = SequenceMatcher(None, key, title).ratio()
        if score >= threshold:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _resolve_destination(storage_dir: Path, paper_id: str, suffix: str = ".pdf") -> Path:
    storage_dir.mkdir(parents=True, exist_ok=True)
    target = storage_dir / f"{paper_id}{suffix}"
    if not target.exists():
        return target
    ts = int(time.time())
    return storage_dir / f"{paper_id}_{ts}{suffix}"


def process_downloaded_pdf(
    file_path: Path,
    downloads_watch_dir: Path | None = None,
    pdf_storage_dir: Path | None = None,
    title_threshold: float = 0.90,
) -> DownloadWatchResult:
    source = Path(file_path)
    if not source.exists():
        return DownloadWatchResult(status="missing_file", destination=None, matched_paper_id=None, note="source_not_found")

    storage_dir = Path(pdf_storage_dir).expanduser() if pdf_storage_dir is not None else pdf_storage_root()
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

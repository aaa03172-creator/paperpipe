
import time
import logging
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from src.config import AppConfig
from src.fetchers import fetch_pubmed
from src.llm_provider import get_llm_provider
from src.processor import (
    derive_saved_issues_state,
    process_local_pdf as processor_process_local_pdf,
)
from src.services.intake_override_log import build_intake_override_log, merge_feedback_json_with_intake_override
from src.obsidian import save_paper_to_obsidian
from src.zotero import export_to_ris
from src.schemas import PaperStatus
from src.db_utils import save_paper_state

# Setup logger for this module
logger = logging.getLogger("src.watcher")
logger.setLevel(logging.INFO)

class PaperFileHandler(FileSystemEventHandler):
    """
    Handles file system events for the watch folder.
    """
    def __init__(self, processor):
        self.processor = processor

    def on_created(self, event):
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Only process PDFs
        if path.suffix.lower() == ".pdf":
            # Wait briefly to ensure file handle is released
            time.sleep(1)
            logger.info(f"👀 Detected new PDF: {path.name}")
            try:
                self.processor.process_local_pdf(path)
            except Exception as e:
                logger.error(f"❌ Error processing local PDF {path.name}: {e}")

class WatcherService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.watch_folder = config.paths.watch_folder
        self.observer = Observer()

    def start(self, processor):
        """
        Starts the directory observer.
        """
        if not self.watch_folder:
            logger.error("❌ Watch folder not configured in config.yaml.")
            return

        # Ensure directory exists
        if not self.watch_folder.exists():
            logger.info(f"📁 Creating watch folder: {self.watch_folder}")
            self.watch_folder.mkdir(parents=True, exist_ok=True)

        event_handler = PaperFileHandler(processor)
        self.observer.schedule(event_handler, str(self.watch_folder), recursive=False)
        self.observer.start()
        
        logger.info(f"🔭 Watching for PDFs in: {self.watch_folder}")
        logger.info("   (Press Ctrl+C to stop)")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
            logger.info("🛑 Watcher stopped.")
        
        self.observer.join()


def extract_doi_from_pdf(_path: Path) -> str | None:
    """Legacy shim retained for tests that patch this symbol."""
    return None


def process_local_pdf(file_path: Path, config: AppConfig | None = None):
    """Compatibility entrypoint used by legacy tests/scripts."""
    if config is None:
        return processor_process_local_pdf(file_path, config=None)

    doi = extract_doi_from_pdf(file_path)
    fetched = fetch_pubmed([doi], max_results=1) if doi else []
    paper = fetched[0] if fetched else None
    if paper is None:
        return processor_process_local_pdf(file_path, config=config)

    llm = get_llm_provider(config.llm, getattr(config, "entity_aliases", {}))
    analysis_available = bool(llm)
    tags: list[str] = []
    confidence = 0.0
    slot = "test"
    if llm:
        tag_payload = llm.tag_paper({"title": paper.title, "summary": paper.summary}) or {}
        tags = tag_payload.get("soft_tags", []) or []
        confidence = float(tag_payload.get("confidence", 0.0) or 0.0)
        try:
            slot = llm.classify_slot({"title": paper.title, "summary": paper.summary}, slot) or slot
        except Exception:
            pass

    processing_status = PaperStatus.APPROVED if confidence >= 0.8 else PaperStatus.PENDING_REVIEW
    issues_state = derive_saved_issues_state(
        processing_status,
        analysis_available=analysis_available,
    )
    intake_override_log = build_intake_override_log(
        producer="watcher_local_pdf",
        analysis_available=analysis_available,
        llm_tagging_used=analysis_available,
        llm_slot_classification_used=analysis_available,
        input_slot="test",
        stored_slot=slot,
        input_tags=tags,
        stored_tags=tags,
        processing_status=processing_status.value,
        issues_state=issues_state,
        confidence=confidence,
    )

    row = {
        "id": paper.id,
        "paper_id": paper.id,
        "doi": paper.doi or paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "published": paper.published,
        "source": paper.source,
        "summary": paper.summary,
        "link": paper.link,
        "slot": slot,
        "tags": tags,
        "processing_status": processing_status,
        "pdf_path": str(file_path),
        "local_pdf_path": str(file_path),
    }
    row["feedback_json"] = merge_feedback_json_with_intake_override(None, intake_override_log)

    save_paper_to_obsidian(row, config)
    export_to_ris(row, Path(config.paths.export_dir))
    save_paper_state(
        row["doi"],
        row["title"],
        row["source"],
        time.strftime("%Y-%m-%d"),
        local_pdf_path=row["pdf_path"],
        feedback_json=row["feedback_json"],
        status=processing_status.value,
        issues_state=issues_state,
    )
    if config.paths.upload_dir:
        upload_dir = Path(config.paths.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, upload_dir / file_path.name)
    return row

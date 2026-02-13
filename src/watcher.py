
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from src.config import AppConfig

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

import logging
import sys
from pathlib import Path
from rich.logging import RichHandler
from src.services.runtime_paths import logs_root

def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """
    Sets up a centralized logger with:
    1. RichHandler for beautiful console output.
    2. FileHandler for persistent logging.
    """

    resolved_log_file = Path(log_file).expanduser().resolve() if log_file else (logs_root() / "paperpipe.log").resolve()

    # Create logs directory if it doesn't exist
    log_path = Path(resolved_log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Root Logger Configuration
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(rich_tracebacks=True, show_path=False),
            logging.FileHandler(log_path, encoding='utf-8')
        ]
    )

    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger("paperpipe")
    logger.info(f"Logging initialized at level {log_level}")
    return logger

import logging
import sys
from pathlib import Path
from rich.logging import RichHandler

def setup_logging(log_level: str = "INFO", log_file: str = "logs/paperpipe.log") -> logging.Logger:
    """
    Sets up a centralized logger with:
    1. RichHandler for beautiful console output.
    2. FileHandler for persistent logging.
    """
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Root Logger Configuration
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(rich_tracebacks=True, show_path=False),
            logging.FileHandler(log_file, encoding='utf-8')
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

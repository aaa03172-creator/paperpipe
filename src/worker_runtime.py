import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


EventSink = Callable[[dict[str, Any]], None]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_processor_factory() -> Any:
    # Lazy import to avoid importing heavy runtime dependencies at module import time.
    from src.processor import PaperProcessor

    return PaperProcessor()


def run_processor_batch(
    batch_size: int = 5,
    processor_factory: Callable[[], Any] = _default_processor_factory,
    emit: EventSink | None = None,
) -> dict[str, Any]:
    """
    Worker-friendly wrapper around PaperProcessor.run().

    This keeps the existing CLI processor flow intact while exposing
    a single callable unit for API job workers.
    """

    def _emit(stage: str, message: str, status: str, level: str = "INFO") -> None:
        if not emit:
            return
        emit(
            {
                "stage": stage,
                "status": status,
                "level": level,
                "message": message,
                "timestamp": _utc_now_iso(),
            }
        )

    _emit("processor", f"Starting processor batch (batch_size={batch_size})", "running")

    try:
        processor = processor_factory()
        processor.run(batch_size=batch_size)

        result = {
            "status": "succeeded",
            "batch_size": batch_size,
            "message": "Processor batch completed",
        }
        _emit("processor", result["message"], "succeeded")
        return result
    except Exception as exc:
        logger.exception("Processor worker failed")
        result = {
            "status": "failed",
            "batch_size": batch_size,
            "message": str(exc),
        }
        _emit("processor", f"Processor batch failed: {exc}", "failed", level="ERROR")
        return result

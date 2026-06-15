from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable


@dataclass
class StageTimer:
    stage: str
    monotonic_fn: Callable[[], float] = perf_counter
    started_at: float | None = None
    finished_at: float | None = None

    def __enter__(self) -> StageTimer:
        self.started_at = float(self.monotonic_fn())
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.finish()

    def finish(self) -> None:
        if self.finished_at is None:
            self.finished_at = float(self.monotonic_fn())

    def to_meta(self) -> dict[str, Any]:
        elapsed = None
        if self.started_at is not None and self.finished_at is not None:
            elapsed = round(max(0.0, self.finished_at - self.started_at), 3)
        return {"stage": self.stage, "wall_seconds": elapsed}


def summarize_stage_timings(stages: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0.0
    counted = 0
    for stage in stages:
        value = stage.get("wall_seconds")
        if isinstance(value, int | float):
            total += float(value)
            counted += 1
    return {
        "stage_count": len(stages),
        "timed_stage_count": counted,
        "total_observed_wall_seconds": round(total, 3),
    }

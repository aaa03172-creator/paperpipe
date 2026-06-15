from src.services.performance_profile import StageTimer, summarize_stage_timings


class FakeMonotonic:
    def __init__(self, values: list[float]):
        self.values = list(values)

    def __call__(self) -> float:
        return self.values.pop(0)


def test_stage_timer_records_elapsed_seconds():
    timer = StageTimer("ingest", monotonic_fn=FakeMonotonic([10.0, 12.5]))

    with timer:
        pass

    assert timer.to_meta()["stage"] == "ingest"
    assert timer.to_meta()["wall_seconds"] == 2.5


def test_summarize_stage_timings_keeps_numeric_total():
    summary = summarize_stage_timings(
        [
            {"stage": "ingest", "wall_seconds": 1.25},
            {"stage": "reader", "wall_seconds": 10.0},
            {"stage": "pending", "wall_seconds": None},
        ]
    )

    assert summary["total_observed_wall_seconds"] == 11.25
    assert summary["stage_count"] == 3
    assert summary["timed_stage_count"] == 2

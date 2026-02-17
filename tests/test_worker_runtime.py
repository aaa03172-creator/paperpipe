from src.worker_runtime import run_processor_batch


class _ProcessorOK:
    def __init__(self):
        self.calls = []

    def run(self, batch_size: int = 5):
        self.calls.append(batch_size)


class _ProcessorFail:
    def run(self, batch_size: int = 5):
        raise RuntimeError("boom")


def test_run_processor_batch_success_emits_start_and_complete():
    events = []
    holder = {}

    def factory():
        proc = _ProcessorOK()
        holder["proc"] = proc
        return proc

    result = run_processor_batch(batch_size=7, processor_factory=factory, emit=events.append)

    assert result["status"] == "succeeded"
    assert result["batch_size"] == 7
    assert holder["proc"].calls == [7]

    assert len(events) == 2
    assert events[0]["status"] == "running"
    assert events[1]["status"] == "succeeded"


def test_run_processor_batch_failure_emits_error_and_returns_failed():
    events = []

    result = run_processor_batch(batch_size=3, processor_factory=_ProcessorFail, emit=events.append)

    assert result["status"] == "failed"
    assert result["batch_size"] == 3
    assert "boom" in result["message"]

    assert len(events) == 2
    assert events[0]["status"] == "running"
    assert events[1]["status"] == "failed"
    assert events[1]["level"] == "ERROR"

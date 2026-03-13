from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import signal
from typing import Any, Iterator

try:
    import fitz  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    fitz = None


@dataclass(frozen=True)
class BatchTimeoutPolicy:
    strategy: str = "adaptive"  # "adaptive" | "fixed"
    base_timeout_sec: int = 180
    min_timeout_sec: int = 120
    max_timeout_sec: int = 600
    size_weight_sec_per_mib: float = 35.0
    size_floor_mib: float = 0.5
    page_weight_sec_per_page: float = 10.0


def estimate_pdf_page_count(pdf_path: Path) -> int | None:
    if fitz is None:
        return None
    try:
        with fitz.open(str(pdf_path)) as doc:
            return int(doc.page_count)
    except Exception:
        return None


class StepTimeoutError(TimeoutError):
    """Raised when a guarded step exceeds timeout budget."""


def is_timeout_exception(exc: BaseException) -> bool:
    if isinstance(exc, (StepTimeoutError, TimeoutError)):
        return True
    timeout_type_names = {
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
        "WriteTimeout",
        "PoolTimeout",
    }
    for cls in type(exc).__mro__:
        if cls.__name__ in timeout_type_names:
            return True
    return False


@contextmanager
def time_limit(seconds: int) -> Iterator[None]:
    """
    Apply a SIGALRM-based timeout guard.
    On non-POSIX environments without SIGALRM, this becomes a no-op.
    """
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    def _raise_timeout(_signum: int, _frame: Any) -> None:
        raise StepTimeoutError(f"step_timeout:{seconds}s")

    previous_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(int(seconds))
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def estimate_doc_timeout_seconds(pdf_path: Path, policy: BatchTimeoutPolicy) -> int:
    base = max(1, int(policy.base_timeout_sec))
    if str(policy.strategy).strip().lower() == "fixed":
        return base

    try:
        size_mib = pdf_path.stat().st_size / (1024.0 * 1024.0)
    except OSError:
        size_mib = float(policy.size_floor_mib)

    size_mib = max(float(policy.size_floor_mib), float(size_mib))
    page_count = estimate_pdf_page_count(pdf_path)
    page_bonus = 0.0
    if page_count is not None:
        page_bonus = max(0, int(page_count)) * float(policy.page_weight_sec_per_page)

    adaptive = int(round(base + (size_mib * float(policy.size_weight_sec_per_mib)) + page_bonus))
    adaptive = max(int(policy.min_timeout_sec), adaptive)
    adaptive = min(int(policy.max_timeout_sec), adaptive)
    return max(1, adaptive)


def default_reader_timeout_base_seconds(llm_timeout_seconds: int) -> int:
    base = max(1, int(llm_timeout_seconds))
    return max(60, base * 6)


def default_stats_timeout_base_seconds(llm_timeout_seconds: int) -> int:
    base = max(1, int(llm_timeout_seconds))
    return max(90, base * 8)


def next_retry_timeout_seconds(
    current_timeout_sec: int,
    *,
    retry_factor: float = 1.75,
    min_bump_sec: int = 60,
    hard_cap_sec: int = 900,
) -> int:
    current = max(1, int(current_timeout_sec))
    factor = max(1.05, float(retry_factor))
    bump = max(1, int(min_bump_sec))
    cap = max(current + 1, int(hard_cap_sec))

    proposed = int(round(current * factor))
    proposed = max(current + bump, proposed)
    proposed = min(cap, proposed)
    return max(current + 1, proposed)


def estimate_reader_timeout_seconds(
    base_timeout_sec: int,
    *,
    page_count: int,
    table_count: int,
    adaptive: bool = True,
    doc_timeout_sec: int | None = None,
    remaining_doc_budget_sec: int | None = None,
) -> int:
    base = max(1, int(base_timeout_sec))
    if not adaptive:
        return base
    pages = max(0, int(page_count))
    tables = max(0, int(table_count))
    bonus = min(pages, 120) * 3 + min(tables, 30) * 4
    estimated = max(base, base + bonus)

    if doc_timeout_sec is not None and int(doc_timeout_sec) > 0:
        doc_floor = min(240, max(base, int(int(doc_timeout_sec) * 0.45)))
        estimated = max(estimated, doc_floor)

    if remaining_doc_budget_sec is not None:
        estimated = min(estimated, max(base, int(remaining_doc_budget_sec)))

    return min(360, max(base, estimated))


def estimate_stats_timeout_seconds(
    base_timeout_sec: int,
    *,
    page_count: int,
    table_count: int,
    claim_count: int,
    adaptive: bool = True,
    doc_timeout_sec: int | None = None,
    remaining_doc_budget_sec: int | None = None,
) -> int:
    base = max(1, int(base_timeout_sec))
    if not adaptive:
        return base
    pages = max(0, int(page_count))
    tables = max(0, int(table_count))
    claims = max(0, int(claim_count))
    bonus = min(pages, 120) * 2 + min(tables, 40) * 8 + min(claims, 20) * 12
    estimated = max(base, base + bonus)

    if doc_timeout_sec is not None and int(doc_timeout_sec) > 0:
        doc_floor = min(420, max(base, int(int(doc_timeout_sec) * 0.75)))
        estimated = max(estimated, doc_floor)

    if remaining_doc_budget_sec is not None:
        estimated = min(estimated, max(base, int(remaining_doc_budget_sec)))

    return min(540, max(base, estimated))

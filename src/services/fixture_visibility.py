from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Callable, TypeVar

T = TypeVar("T")


def prefer_non_fixture_items(items: Iterable[T], is_fixture: Callable[[T], bool]) -> list[T]:
    materialized = list(items)
    visible = [item for item in materialized if not is_fixture(item)]
    return visible or materialized


def is_test_fixture_paper_record(record: Mapping[str, object]) -> bool:
    paper_id = str(record.get("paper_id") or "").strip().lower()
    title = str(record.get("title") or "").strip().lower()
    pdf_path = str(record.get("pdf_path") or "").replace("\\", "/").lower()

    if paper_id.startswith("paper-e2e-"):
        return True
    if paper_id.startswith("local--"):
        return True
    if "_test_" in paper_id or paper_id.startswith("integration_test_") or paper_id == "phase0_test":
        return True
    if "/tests/" in pdf_path:
        return True
    if title.startswith("e2e ") or " fixture" in title or title.endswith("fixture"):
        return True
    return False

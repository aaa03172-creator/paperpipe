from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Callable, TypeVar

from src.schemas.meeting_pack import MeetingPack

T = TypeVar("T")


def _include_test_fixtures_enabled() -> bool:
    raw = (
        os.getenv("LATTICE_INCLUDE_TEST_FIXTURES")
        or os.getenv("PAPERPIPE_INCLUDE_TEST_FIXTURES")
        or ""
    ).strip()
    return raw.lower() in {"1", "true", "yes", "on"}


def prefer_non_fixture_items(items: Iterable[T], is_fixture: Callable[[T], bool]) -> list[T]:
    materialized = list(items)
    if _include_test_fixtures_enabled():
        return materialized
    visible = [item for item in materialized if not is_fixture(item)]
    return visible or materialized


def _looks_like_fixture_title(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        normalized.startswith("e2e ")
        or normalized.startswith("backend visual ")
        or normalized.endswith(" fixture")
        or normalized.endswith("-fixture")
        or normalized.endswith("_fixture")
    )


def _looks_like_fixture_ref(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        normalized.startswith("paper-e2e-")
        or normalized.startswith("zoteroe2e")
        or normalized.startswith("e2e_")
        or normalized.startswith("e2e-")
        or normalized.endswith("_fixture")
        or normalized.endswith("-fixture")
    )


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
    if _looks_like_fixture_title(title):
        return True
    return False


def is_test_fixture_meeting_pack(pack: MeetingPack) -> bool:
    title = pack.title.strip().lower()
    request_title = (pack.generation_request.title if pack.generation_request else "") or ""
    request_title = request_title.strip().lower()

    if _looks_like_fixture_title(title):
        return True
    if _looks_like_fixture_title(request_title):
        return True

    for source in pack.source_items:
        ref = source.ref.strip().lower()
        source_title = source.title.strip().lower()
        if _looks_like_fixture_ref(ref):
            return True
        if _looks_like_fixture_title(source_title):
            return True

    return False

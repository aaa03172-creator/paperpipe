from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Callable, TypeVar

from src.schemas.meeting_pack import MeetingPack
from src.schemas.skills import StructuredPaperState

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


def is_test_fixture_meeting_pack(pack: MeetingPack) -> bool:
    title = pack.title.strip().lower()
    request_title = (pack.generation_request.title if pack.generation_request else "") or ""
    request_title = request_title.strip().lower()

    if title.startswith("e2e ") or "fixture" in title or title.startswith("backend visual "):
        return True
    if request_title.startswith("e2e ") or "fixture" in request_title or request_title.startswith("backend visual "):
        return True

    for source in pack.source_items:
        ref = source.ref.strip().lower()
        source_title = source.title.strip().lower()
        if "e2e" in ref or "fixture" in ref:
            return True
        if source_title.startswith("e2e ") or "fixture" in source_title:
            return True

    return False


def fixture_structured_state_allowed(vault_path: Path | None = None) -> bool:
    if _include_test_fixtures_enabled():
        return True
    if vault_path is None:
        return False
    try:
        resolved = Path(vault_path).expanduser().resolve()
    except Exception:
        resolved = Path(vault_path).expanduser()
    return ".e2e-backend-runtime" in resolved.parts


def is_test_fixture_structured_state(state: StructuredPaperState) -> bool:
    for run in state.runs:
        run_id = str(run.id or "").strip().lower()
        if run_id.startswith("run_e2e_fixture") or run_id.startswith("job-e2e-fixture"):
            return True

    for claim in state.claimset:
        claim_id = str(claim.id or "").strip().lower()
        source_claim_id = str(getattr(claim, "source_claim_id", "") or "").strip().lower()
        if claim_id.startswith("claim_c0ffee") or source_claim_id.startswith("e2e-claim-"):
            return True
        for evidence in claim.evidence:
            evidence_id = str(evidence.id or "").strip().lower()
            if evidence_id.startswith("evidence_deadbeef"):
                return True
            locator = evidence.locator if isinstance(evidence.locator, dict) else {}
            chunk_id = str(locator.get("chunk_id") or "").strip().lower()
            if chunk_id.startswith("chunk-e2e-"):
                return True
    return False

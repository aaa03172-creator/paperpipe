from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Callable, TypeVar

from src.schemas.meeting_pack import MeetingPack
from src.schemas.skills import StructuredPaperState

T = TypeVar("T")


@dataclass(frozen=True)
class StructuredStateQuarantineMove:
    source_path: Path
    destination_path: Path


def _include_test_fixtures_enabled() -> bool:
    raw = (
        os.getenv("LATTICE_INCLUDE_TEST_FIXTURES")
        or os.getenv("PAPERPIPE_INCLUDE_TEST_FIXTURES")
        or ""
    ).strip()
    return raw.lower() in {"1", "true", "yes", "on"}


def include_test_fixtures_enabled() -> bool:
    return _include_test_fixtures_enabled()


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


def classify_test_fixture_paper_record(record: Mapping[str, object]) -> tuple[bool, str | None]:
    if is_test_fixture_paper_record(record):
        return True, "fixture_visibility_rule"

    paper_id = str(record.get("paper_id") or "").strip().lower()
    title = str(record.get("title") or "").strip().lower()
    pdf_path = str(record.get("pdf_path") or "").replace("\\", "/").strip().lower()
    pdf_name = Path(pdf_path).name

    if paper_id.startswith("test_"):
        return True, "paper_id_test_prefix"
    if title.startswith("test local "):
        return True, "title_test_local_prefix"
    if pdf_name in {"test_paper.pdf", "dummy.pdf"} or pdf_name.startswith("test_"):
        return True, "pdf_name_test_fixture"
    return False, None


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


def is_test_fixture_meeting_pack_request(
    *,
    title: str | None,
    source_refs: Iterable[str],
) -> bool:
    normalized_title = str(title or "").strip().lower()
    if normalized_title.startswith("backend visual ") or normalized_title.startswith("e2e "):
        return True

    for raw_ref in source_refs:
        ref = str(raw_ref or "").strip().lower()
        if not ref:
            continue
        if ref.startswith("paper-e2e-") or ref.startswith("zoteroe2e"):
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


def visible_structured_state(
    state: StructuredPaperState | None,
    *,
    vault_path: Path | None = None,
) -> StructuredPaperState | None:
    if state is None:
        return None
    if is_test_fixture_structured_state(state) and not fixture_structured_state_allowed(vault_path):
        return None
    return state


def hidden_fixture_structured_state_paths(vault_path: Path) -> list[Path]:
    resolved_vault = Path(vault_path).expanduser().resolve(strict=False)
    if fixture_structured_state_allowed(resolved_vault):
        return []

    state_root = resolved_vault / ".pp"
    if not state_root.exists():
        return []

    hidden_paths: list[Path] = []
    for state_path in sorted(state_root.glob("*/state.json")):
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            state = StructuredPaperState.model_validate(payload)
        except Exception:
            continue
        if is_test_fixture_structured_state(state):
            hidden_paths.append(state_path)
    return hidden_paths


def quarantine_hidden_fixture_structured_states(
    vault_path: Path,
    *,
    apply: bool,
    now: datetime | None = None,
) -> list[StructuredStateQuarantineMove]:
    resolved_vault = Path(vault_path).expanduser().resolve(strict=False)
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    quarantine_root = resolved_vault / ".pp" / "_quarantine" / "fixture_states" / timestamp

    moves: list[StructuredStateQuarantineMove] = []
    for source_path in hidden_fixture_structured_state_paths(resolved_vault):
        slug = source_path.parent.name
        destination_path = quarantine_root / slug / source_path.name
        moves.append(
            StructuredStateQuarantineMove(
                source_path=source_path,
                destination_path=destination_path,
            )
        )

    if apply:
        for move in moves:
            move.destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source_path), str(move.destination_path))

    return moves

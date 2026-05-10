from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.schemas.artifact_generation_outcome import ArtifactGenerationOutcome
from src.services.event_log import sanitize_event_payload_for_log, sanitize_event_text_for_log
from src.services.runtime_paths import artifact_generation_outcome_log_path


def _sanitize_artifact_generation_outcome(outcome: ArtifactGenerationOutcome) -> ArtifactGenerationOutcome:
    updates = {}
    for field_name in (
        "outcome_id",
        "artifact_id",
        "paper_id",
        "run_id",
        "dna_id",
        "review_feedback_id",
        "actor_id",
        "note",
    ):
        value = getattr(outcome, field_name)
        sanitized = sanitize_event_text_for_log(value)
        if sanitized != value:
            updates[field_name] = sanitized

    sanitized_metadata = sanitize_event_payload_for_log(outcome.metadata)
    if sanitized_metadata != outcome.metadata:
        updates["metadata"] = sanitized_metadata

    if not updates:
        return outcome
    return outcome.model_copy(update=updates)


def append_artifact_generation_outcome(
    outcome: ArtifactGenerationOutcome,
    *,
    log_path: Path | None = None,
) -> ArtifactGenerationOutcome:
    if not outcome.timestamp:
        outcome.timestamp = datetime.now(timezone.utc).isoformat()
    outcome = _sanitize_artifact_generation_outcome(outcome)

    path = log_path or artifact_generation_outcome_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(outcome.model_dump_json())
        handle.write("\n")
    return outcome


def load_artifact_generation_outcomes(*, log_path: Path | None = None) -> list[ArtifactGenerationOutcome]:
    path = log_path or artifact_generation_outcome_log_path()
    if not path.exists():
        return []

    outcomes: list[ArtifactGenerationOutcome] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            outcomes.append(
                _sanitize_artifact_generation_outcome(ArtifactGenerationOutcome.model_validate_json(line))
            )
        except Exception:
            continue
    return outcomes

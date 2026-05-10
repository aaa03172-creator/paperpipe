from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.schemas.artifact_review_feedback import ArtifactReviewFeedbackCase
from src.services.event_log import sanitize_event_payload_for_log, sanitize_event_text_for_log
from src.services.runtime_paths import artifact_review_feedback_log_path


def _sanitize_artifact_review_feedback(feedback: ArtifactReviewFeedbackCase) -> ArtifactReviewFeedbackCase:
    updates = {}
    for field_name in (
        "feedback_id",
        "artifact_id",
        "paper_id",
        "run_id",
        "dna_id",
        "reason_code",
        "actor_id",
        "note",
    ):
        value = getattr(feedback, field_name)
        sanitized = sanitize_event_text_for_log(value)
        if sanitized != value:
            updates[field_name] = sanitized

    sanitized_metadata = sanitize_event_payload_for_log(feedback.metadata)
    if sanitized_metadata != feedback.metadata:
        updates["metadata"] = sanitized_metadata

    if not updates:
        return feedback
    return feedback.model_copy(update=updates)


def append_artifact_review_feedback(
    feedback: ArtifactReviewFeedbackCase,
    *,
    log_path: Path | None = None,
) -> ArtifactReviewFeedbackCase:
    if not feedback.timestamp:
        feedback.timestamp = datetime.now(timezone.utc).isoformat()
    feedback = _sanitize_artifact_review_feedback(feedback)

    path = log_path or artifact_review_feedback_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(feedback.model_dump_json())
        handle.write("\n")
    return feedback


def load_artifact_review_feedback(*, log_path: Path | None = None) -> list[ArtifactReviewFeedbackCase]:
    path = log_path or artifact_review_feedback_log_path()
    if not path.exists():
        return []

    feedback_rows: list[ArtifactReviewFeedbackCase] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            feedback_rows.append(
                _sanitize_artifact_review_feedback(ArtifactReviewFeedbackCase.model_validate_json(line))
            )
        except Exception:
            continue
    return feedback_rows

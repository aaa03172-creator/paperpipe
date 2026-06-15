from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.schemas.claim_evidence_correction import ClaimEvidenceCorrectionCase, ClaimEvidenceCorrectionLocator
from src.schemas.ml_training_examples import (
    CorrectionIssueLabel,
    CorrectionReviewExample,
    MLTrainingRecord,
    PayloadClass,
    TrainingSourceSpan,
)


def _correction_issue_label(reason_codes: list[object]) -> CorrectionIssueLabel:
    normalized = " ".join(str(code).lower() for code in reason_codes)
    if "numeric" in normalized or "number" in normalized or "value" in normalized:
        return "numeric_mismatch"
    if "uncertainty" in normalized or "limitation" in normalized:
        return "uncertainty_missing"
    if "location" in normalized or "locator" in normalized or "missing_location" in normalized:
        return "location_missing"
    if "unsupported" in normalized:
        return "unsupported"
    if "weak" in normalized:
        return "weak"
    if "over" in normalized or "overstatement" in normalized:
        return "overclaim"
    return "overclaim"


def _locator_source_ref(locator: ClaimEvidenceCorrectionLocator) -> str:
    parts: list[str] = ["document_artifact.json"]
    fragments: list[str] = []
    if locator.page is not None:
        fragments.append(f"page={locator.page}")
    if locator.chunk_id:
        fragments.append(f"chunk_id={locator.chunk_id}")
    if locator.section:
        fragments.append(f"section={locator.section}")
    if locator.figure_id:
        fragments.append(f"figure_id={locator.figure_id}")
    if locator.table_id:
        fragments.append(f"table_id={locator.table_id}")
    if locator.cell_id:
        fragments.append(f"cell_id={locator.cell_id}")
    if fragments:
        parts.append("#" + "&".join(fragments))
    return "".join(parts)


def _locator_to_source_span(
    locator: ClaimEvidenceCorrectionLocator,
    *,
    correction_id: str,
    index: int,
) -> TrainingSourceSpan:
    return TrainingSourceSpan(
        span_id=f"{correction_id}:evidence:{index}",
        source_ref=_locator_source_ref(locator),
        page_index=locator.page,
        block_id=locator.chunk_id,
        char_start=locator.char_start,
        char_end=locator.char_end,
    )


def build_correction_review_example_from_case(
    correction: ClaimEvidenceCorrectionCase,
    *,
    payload_class: PayloadClass = "local_only",
    observed_issue: CorrectionIssueLabel | None = None,
    expected_label: CorrectionIssueLabel | None = None,
) -> CorrectionReviewExample:
    evidence_refs = correction.after_evidence_refs or correction.before_evidence_refs
    if not evidence_refs:
        raise ValueError("correction requires at least one evidence ref to build a training example")
    label = expected_label or observed_issue or _correction_issue_label(list(correction.reason_codes))
    source_spans = [
        _locator_to_source_span(locator, correction_id=correction.correction_id, index=index)
        for index, locator in enumerate(evidence_refs, start=1)
    ]
    created_at = correction.created_at or datetime.now(timezone.utc)
    return CorrectionReviewExample(
        example_id=f"correction_review:{correction.correction_id}",
        paper_id=correction.paper_id,
        run_id=correction.run_id,
        claim_id=correction.claim_id,
        claim_text=correction.before_claim_text,
        evidence_text_ref=source_spans[0].source_ref,
        payload_class=payload_class,
        observed_issue=observed_issue or label,
        expected_label=label,
        minimal_correction=correction.after_claim_text,
        must_preserve_terms=[],
        must_not_infer=["unsupported causal effect", "unreported subgroup effect"],
        source_spans=source_spans,
        review_status="accepted" if correction.accepted_for_eval else "reviewed",
        created_at=created_at,
    )


def write_ml_training_examples_jsonl(
    examples: list[MLTrainingRecord],
    out: Path,
) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [example.model_dump_json() for example in examples]
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out


def write_run_ml_training_examples_sidecar(
    artifact_dir: Path,
    examples: list[MLTrainingRecord],
    *,
    filename: str = "ml_training_examples.jsonl",
) -> Path:
    if Path(filename).name != filename or not filename.endswith(".jsonl"):
        raise ValueError("filename must be a simple .jsonl sidecar name")
    return write_ml_training_examples_jsonl(examples, Path(artifact_dir) / filename)

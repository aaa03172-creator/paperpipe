from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim
from src.schemas.core import BiomedicalClinicalExtraction
from src.schemas.evidence_extraction import (
    EvidenceExtractionBundle,
    EvidenceExtractionLocator,
    EvidenceExtractionMetrics,
    EvidenceExtractionRecord,
    EvidenceExtractionRef,
)
from src.skills.storage import atomic_write_text

_SKIP_CLINICAL_TOP_LEVEL_FIELDS = {"paper_id", "citation"}


def build_evidence_extraction_bundle(
    *,
    paper_id: str,
    run_id: str,
    resolved_claimset: ClaimSet,
    clinical_extraction: BiomedicalClinicalExtraction | None = None,
) -> EvidenceExtractionBundle:
    records: list[EvidenceExtractionRecord] = []
    source_artifacts = ["claimset.resolved.json"]
    warnings: list[str] = []

    for claim in resolved_claimset.claims:
        record = _build_claim_record(claim)
        records.append(record)

    if clinical_extraction is not None:
        source_artifacts.append("clinical_extraction.json")
        records.extend(_build_clinical_records(clinical_extraction))
    else:
        warnings.append("clinical_extraction_missing")

    metrics = EvidenceExtractionMetrics(
        record_count=len(records),
        claim_record_count=sum(1 for record in records if record.record_type == "claim"),
        clinical_field_record_count=sum(1 for record in records if record.record_type == "clinical_field"),
        entity_record_count=sum(1 for record in records if record.record_type == "entity"),
        relation_record_count=sum(1 for record in records if record.record_type == "relation"),
        evidence_backed_record_count=sum(1 for record in records if record.status == "evidence_backed"),
        artifact_backed_record_count=sum(1 for record in records if record.status == "artifact_backed"),
        derived_record_count=sum(1 for record in records if record.status == "derived"),
        evidence_ref_count=sum(len(record.evidence_refs) for record in records),
        grounded_evidence_ref_count=sum(
            1 for record in records for ref in record.evidence_refs if ref.grounded is True
        ),
    )
    return EvidenceExtractionBundle(
        generated_at=datetime.now(timezone.utc),
        paper_id=paper_id,
        doc_id=resolved_claimset.doc_id,
        run_id=run_id,
        source_artifacts=source_artifacts,
        records=records,
        metrics=metrics,
        warnings=warnings,
    )


def write_evidence_extraction_bundle(bundle: EvidenceExtractionBundle, artifact_dir: Path) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "evidence_extraction_bundle.json"
    atomic_write_text(path, bundle.model_dump_json(indent=2))
    return path


def _build_claim_record(claim: ScientificClaim) -> EvidenceExtractionRecord:
    evidence_refs = [_build_evidence_ref(claim.claim_id, span) for span in claim.evidence_spans]
    return EvidenceExtractionRecord(
        record_id=f"claim:{claim.claim_id}",
        record_type="claim",
        label=claim.type.replace("_", " ").strip() or "claim",
        value=claim.statement.strip(),
        source_artifact="claimset.resolved.json",
        claim_id=claim.claim_id,
        confidence=claim.confidence,
        status="evidence_backed" if evidence_refs else "derived",
        tags=[claim.type],
        evidence_refs=evidence_refs,
        metadata={
            "unknown": bool(claim.unknown),
            "unknown_reason": claim.unknown_reason,
            "limitations": list(claim.limitations or []),
        },
    )


def _build_evidence_ref(claim_id: str, span: EvidenceSpan) -> EvidenceExtractionRef:
    locator = EvidenceExtractionLocator(
        page=span.page,
        chunk_id=span.chunk_id,
        char_start=span.char_start,
        char_end=span.char_end,
        section=span.section,
        table_id=span.table_id,
        cell_id=span.cell_id,
        bbox_pdf=list(span.bbox_pdf) if span.bbox_pdf else None,
        bbox_pct=dict(span.bbox_pct) if span.bbox_pct else None,
    )
    return EvidenceExtractionRef(
        claim_id=claim_id,
        quote=span.quote,
        rationale=span.rationale,
        grounded=span.grounded,
        resolution=span.resolution,
        locator=locator,
    )


def _build_clinical_records(clinical_extraction: BiomedicalClinicalExtraction) -> list[EvidenceExtractionRecord]:
    payload = clinical_extraction.model_dump(mode="json", exclude_none=True)
    records: list[EvidenceExtractionRecord] = []
    for key, value in payload.items():
        if key in _SKIP_CLINICAL_TOP_LEVEL_FIELDS:
            continue
        records.extend(_flatten_clinical_value(key, value))
    return records


def _flatten_clinical_value(field_path: str, value: Any) -> list[EvidenceExtractionRecord]:
    if isinstance(value, BaseModel):
        return _flatten_clinical_value(field_path, value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, dict):
        records: list[EvidenceExtractionRecord] = []
        for key, nested in value.items():
            records.extend(_flatten_clinical_value(f"{field_path}.{key}", nested))
        return records
    if isinstance(value, list):
        records: list[EvidenceExtractionRecord] = []
        for idx, nested in enumerate(value):
            records.extend(_flatten_clinical_value(f"{field_path}[{idx}]", nested))
        return records
    if _should_skip_scalar(value):
        return []

    normalized_value: str | int | float | None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        normalized_value = value
    else:
        normalized_value = None

    return [
        EvidenceExtractionRecord(
            record_id=f"clinical:{field_path}",
            record_type="clinical_field",
            label=_format_field_label(field_path),
            value=str(value),
            normalized_value=normalized_value,
            source_artifact="clinical_extraction.json",
            field_path=field_path,
            status="artifact_backed",
            tags=[field_path.split(".", 1)[0].split("[", 1)[0]],
        )
    ]


def _should_skip_scalar(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, bool):
        return value is False
    if isinstance(value, (int, float)):
        return value == 0
    return False


def _format_field_label(field_path: str) -> str:
    label = field_path.replace("[", " ").replace("]", "").replace(".", " / ").replace("_", " ")
    return " ".join(part for part in label.split() if part).strip()

from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.bc5cdr_eval import BC5CDRDocument
from src.schemas.evidence_extraction import (
    EvidenceExtractionBundle,
    EvidenceExtractionMetrics,
    EvidenceExtractionRecord,
)


def project_bc5cdr_to_evidence_extraction_bundle(
    document: BC5CDRDocument,
    *,
    paper_id: str | None = None,
    run_id: str = "bc5cdr_adapter",
    source_artifact: str = "bc5cdr_document.json",
) -> EvidenceExtractionBundle:
    records: list[EvidenceExtractionRecord] = []

    mention_record_ids: dict[str, str] = {}
    for mention in document.mentions:
        record_id = f"entity:{mention.mention_id}"
        mention_record_ids[mention.mention_id] = record_id
        records.append(
            EvidenceExtractionRecord(
                record_id=record_id,
                record_type="entity",
                label=mention.entity_type.title(),
                value=mention.text,
                normalized_value=mention.normalized_id,
                source_artifact=source_artifact,
                status="artifact_backed",
                tags=[mention.entity_type],
                metadata={
                    "entity_type": mention.entity_type,
                    "mention_text": mention.text,
                    "char_start": mention.char_start,
                    "char_end": mention.char_end,
                    "normalized_id": mention.normalized_id,
                    "source_mention_id": mention.mention_id,
                },
            )
        )

    for relation in document.relations:
        records.append(
            EvidenceExtractionRecord(
                record_id=f"relation:{relation.relation_id}",
                record_type="relation",
                label=relation.relation_type.replace("_", " ").title(),
                value=(
                    f"{mention_record_ids.get(relation.chemical_mention_id, relation.chemical_mention_id)}"
                    f" -> {mention_record_ids.get(relation.disease_mention_id, relation.disease_mention_id)}"
                ),
                source_artifact=source_artifact,
                status="artifact_backed",
                tags=[relation.relation_type],
                metadata={
                    "relation_type": relation.relation_type,
                    "chemical_record_id": mention_record_ids.get(
                        relation.chemical_mention_id, relation.chemical_mention_id
                    ),
                    "disease_record_id": mention_record_ids.get(
                        relation.disease_mention_id, relation.disease_mention_id
                    ),
                    "source_relation_id": relation.relation_id,
                },
            )
        )

    metrics = EvidenceExtractionMetrics(
        record_count=len(records),
        entity_record_count=sum(1 for record in records if record.record_type == "entity"),
        relation_record_count=sum(1 for record in records if record.record_type == "relation"),
        artifact_backed_record_count=len(records),
    )
    return EvidenceExtractionBundle(
        generated_at=datetime.now(timezone.utc),
        paper_id=paper_id or document.doc_id,
        doc_id=document.doc_id,
        run_id=run_id,
        source_artifacts=[source_artifact],
        records=records,
        metrics=metrics,
        warnings=[],
    )

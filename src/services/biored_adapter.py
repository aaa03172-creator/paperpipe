from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.biored_eval import BioREDDocument
from src.schemas.evidence_extraction import (
    EvidenceExtractionBundle,
    EvidenceExtractionMetrics,
    EvidenceExtractionRecord,
)


def project_biored_to_evidence_extraction_bundle(
    document: BioREDDocument,
    *,
    paper_id: str | None = None,
    run_id: str = "biored_adapter",
    source_artifact: str = "biored_document.json",
) -> EvidenceExtractionBundle:
    records: list[EvidenceExtractionRecord] = []
    mention_record_ids: dict[str, str] = {}

    for mention in document.mentions:
        record_id = f"entity:{mention.mention_id}"
        mention_record_ids[mention.mention_id] = record_id
        normalized_value = mention.normalized_ids[0] if len(mention.normalized_ids) == 1 else None
        records.append(
            EvidenceExtractionRecord(
                record_id=record_id,
                record_type="entity",
                label=mention.entity_type,
                value=mention.text,
                normalized_value=normalized_value,
                source_artifact=source_artifact,
                status="artifact_backed",
                tags=[mention.entity_type],
                metadata={
                    "entity_type": mention.entity_type,
                    "mention_text": mention.text,
                    "char_start": mention.char_start,
                    "char_end": mention.char_end,
                    "normalized_ids": list(mention.normalized_ids),
                    "entity_id": mention.entity_id,
                    "source_mention_id": mention.mention_id,
                },
            )
        )

    for relation in document.relations:
        head_record_id = mention_record_ids.get(relation.head_mention_id, relation.head_mention_id)
        tail_record_id = mention_record_ids.get(relation.tail_mention_id, relation.tail_mention_id)
        tags = [relation.relation_type]
        if relation.novelty != "unknown":
            tags.append(f"novelty:{relation.novelty}")
        records.append(
            EvidenceExtractionRecord(
                record_id=f"relation:{relation.relation_id}",
                record_type="relation",
                label=relation.relation_type.replace("_", " ").strip() or "relation",
                value=f"{head_record_id} -> {tail_record_id}",
                source_artifact=source_artifact,
                status="artifact_backed",
                tags=tags,
                metadata={
                    "relation_type": relation.relation_type,
                    "head_record_id": head_record_id,
                    "tail_record_id": tail_record_id,
                    "novelty": relation.novelty,
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

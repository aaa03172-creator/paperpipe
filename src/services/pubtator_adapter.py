from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.schemas.evidence_extraction import (
    EvidenceExtractionBundle,
    EvidenceExtractionMetrics,
    EvidenceExtractionRecord,
)
from src.schemas.pubtator_silver import (
    PubTatorAnnotation,
    PubTatorDocument,
    PubTatorLocation,
    PubTatorPassage,
    PubTatorRelation,
    PubTatorRelationNode,
)

_ENTITY_TYPE_MAP = {
    "gene": "GeneOrGeneProduct",
    "geneorgeneproduct": "GeneOrGeneProduct",
    "protein": "GeneOrGeneProduct",
    "chemical": "ChemicalEntity",
    "chemicalentity": "ChemicalEntity",
    "drug": "ChemicalEntity",
    "compound": "ChemicalEntity",
    "disease": "DiseaseOrPhenotypicFeature",
    "diseaseorphenotypicfeature": "DiseaseOrPhenotypicFeature",
    "phenotype": "DiseaseOrPhenotypicFeature",
    "sequencevariant": "SequenceVariant",
    "sequence_variant": "SequenceVariant",
    "variant": "SequenceVariant",
    "species": "OrganismTaxon",
    "organism": "OrganismTaxon",
    "organismtaxon": "OrganismTaxon",
    "cellline": "CellLine",
    "cell_line": "CellLine",
}


def load_pubtator_document(path: Path) -> PubTatorDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalized = _normalize_pubtator_payload(payload)
    return PubTatorDocument.model_validate(normalized)


def project_pubtator_to_evidence_extraction_bundle(
    document: PubTatorDocument,
    *,
    paper_id: str | None = None,
    run_id: str = "pubtator_adapter",
    source_artifact: str = "pubtator_document.json",
) -> EvidenceExtractionBundle:
    records: list[EvidenceExtractionRecord] = []
    annotation_record_ids: dict[str, str] = {}
    relation_count = 0

    for passage in document.passages:
        passage_type = _infons_get(passage.infons, "type", "section_type") or "unknown"
        for annotation in passage.annotations:
            entity_type = _normalize_entity_type(_infons_get(annotation.infons, "type"))
            if entity_type is None:
                continue
            char_start, char_end = _annotation_span(annotation.locations)
            if char_start is None or char_end is None:
                continue
            normalized_ids = _split_identifier_list(_infons_get(annotation.infons, "identifier", "identifier_id"))
            record_id = f"entity:{annotation.annotation_id}"
            annotation_record_ids[annotation.annotation_id] = record_id
            records.append(
                EvidenceExtractionRecord(
                    record_id=record_id,
                    record_type="entity",
                    label=entity_type,
                    value=annotation.text,
                    normalized_value=normalized_ids[0] if len(normalized_ids) == 1 else None,
                    source_artifact=source_artifact,
                    status="artifact_backed",
                    tags=[entity_type, "bootstrap:silver", "annotation_source:pubtator_central"],
                    metadata={
                        "entity_type": entity_type,
                        "mention_text": annotation.text,
                        "char_start": char_start,
                        "char_end": char_end,
                        "normalized_ids": normalized_ids,
                        "source_annotation_id": annotation.annotation_id,
                        "annotation_source": "pubtator_central",
                        "bootstrap_tier": "silver",
                        "passage_type": passage_type,
                        "location_count": len(annotation.locations),
                    },
                )
            )

        for relation in passage.relations:
            ref_ids = [node.refid for node in relation.nodes if node.refid.strip()]
            if len(ref_ids) < 2:
                continue
            head_record_id = annotation_record_ids.get(ref_ids[0])
            tail_record_id = annotation_record_ids.get(ref_ids[1])
            if not head_record_id or not tail_record_id:
                continue
            relation_type = _infons_get(relation.infons, "type", "relation_type") or "related_to"
            relation_count += 1
            records.append(
                EvidenceExtractionRecord(
                    record_id=f"relation:{relation.relation_id}",
                    record_type="relation",
                    label=relation_type.replace("_", " ").strip() or "relation",
                    value=f"{head_record_id} -> {tail_record_id}",
                    source_artifact=source_artifact,
                    status="artifact_backed",
                    tags=[relation_type, "bootstrap:silver", "annotation_source:pubtator_central"],
                    metadata={
                        "relation_type": relation_type,
                        "head_record_id": head_record_id,
                        "tail_record_id": tail_record_id,
                        "node_roles": [node.role for node in relation.nodes],
                        "source_relation_id": relation.relation_id,
                        "annotation_source": "pubtator_central",
                        "bootstrap_tier": "silver",
                        "passage_type": passage_type,
                        "novelty": _infons_get(relation.infons, "novelty"),
                    },
                )
            )

    metrics = EvidenceExtractionMetrics(
        record_count=len(records),
        entity_record_count=sum(1 for record in records if record.record_type == "entity"),
        relation_record_count=relation_count,
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
        warnings=["silver_bootstrap:pubtator_central"],
    )


def _normalize_pubtator_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("documents"), list):
        documents = [item for item in payload.get("documents") or [] if isinstance(item, dict)]
        if len(documents) != 1:
            raise ValueError("PubTator collection payload must contain exactly one document")
        payload = documents[0]

    if not isinstance(payload, dict):
        raise ValueError("PubTator payload must be a JSON object")

    doc_id = str(payload.get("doc_id") or payload.get("id") or "").strip()
    if not doc_id:
        raise ValueError("PubTator payload missing document id")

    passages_payload = payload.get("passages")
    passages = passages_payload if isinstance(passages_payload, list) else []

    normalized_passages: list[dict[str, Any]] = []
    for passage in passages:
        if not isinstance(passage, dict):
            continue
        annotations_payload = passage.get("annotations")
        relations_payload = passage.get("relations")
        annotations = annotations_payload if isinstance(annotations_payload, list) else []
        relations = relations_payload if isinstance(relations_payload, list) else []
        normalized_annotations: list[dict[str, Any]] = []
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            locations_payload = annotation.get("locations")
            locations = locations_payload if isinstance(locations_payload, list) else []
            normalized_annotations.append(
                {
                    "annotation_id": str(annotation.get("annotation_id") or annotation.get("id") or "").strip(),
                    "text": str(annotation.get("text") or "").strip(),
                    "infons": _normalize_infons(annotation.get("infons")),
                    "locations": [
                        {
                            "offset": int(location.get("offset")),
                            "length": int(location.get("length")),
                        }
                        for location in locations
                        if isinstance(location, dict) and location.get("offset") is not None and location.get("length") is not None
                    ],
                }
            )
        normalized_relations: list[dict[str, Any]] = []
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            nodes_payload = relation.get("nodes")
            nodes = nodes_payload if isinstance(nodes_payload, list) else []
            normalized_relations.append(
                {
                    "relation_id": str(relation.get("relation_id") or relation.get("id") or "").strip() or "relation",
                    "infons": _normalize_infons(relation.get("infons")),
                    "nodes": [
                        {
                            "refid": str(node.get("refid") or "").strip(),
                            "role": str(node.get("role") or "").strip() or None,
                        }
                        for node in nodes
                        if isinstance(node, dict) and str(node.get("refid") or "").strip()
                    ],
                }
            )
        normalized_passages.append(
            {
                "offset": int(passage.get("offset") or 0),
                "text": str(passage.get("text") or "").strip() or None,
                "infons": _normalize_infons(passage.get("infons")),
                "annotations": normalized_annotations,
                "relations": normalized_relations,
            }
        )

    return {
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "doc_id": doc_id,
        "passages": normalized_passages,
    }


def _normalize_infons(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, raw in value.items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        raw_text = str(raw or "").strip()
        if raw_text:
            normalized[key_text] = raw_text
    return normalized


def _infons_get(infons: dict[str, str], *keys: str) -> str | None:
    lowered = {str(key).strip().lower(): value for key, value in infons.items()}
    for key in keys:
        candidate = lowered.get(str(key).strip().lower())
        if candidate:
            return candidate
    return None


def _normalize_entity_type(value: str | None) -> str | None:
    token = re.sub(r"[^a-z0-9]+", "", str(value or "").lower())
    return _ENTITY_TYPE_MAP.get(token)


def _split_identifier_list(value: str | None) -> list[str]:
    if not value:
        return []
    pieces = re.split(r"[|,;]", value)
    result: list[str] = []
    for piece in pieces:
        candidate = piece.strip()
        if candidate and candidate not in result:
            result.append(candidate)
    return result


def _annotation_span(locations: list[PubTatorLocation]) -> tuple[int | None, int | None]:
    if not locations:
        return None, None
    start = min(location.offset for location in locations)
    end = max(location.offset + location.length for location in locations)
    if end <= start:
        return None, None
    return start, end

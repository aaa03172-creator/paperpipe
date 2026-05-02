from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.bc5cdr_eval import (
    BC5CDRDocument,
    BC5CDREvalReport,
    BC5CDRMention,
    BC5CDRRelation,
    BC5CDRScore,
)
from src.schemas.evidence_extraction import EvidenceExtractionBundle, EvidenceExtractionRecord
from src.skills.storage import atomic_write_text

_SUPPORTED_ENTITY_TYPES = {"chemical", "disease"}
_SUPPORTED_RELATION_TYPES = {"chemical_induced_disease"}


def load_bc5cdr_document(path: Path) -> BC5CDRDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"BC5CDR document payload must be a JSON object: {path}")
    return BC5CDRDocument.model_validate(payload)


def load_evidence_extraction_bundle(path: Path) -> EvidenceExtractionBundle:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Evidence extraction bundle payload must be a JSON object: {path}")
    return EvidenceExtractionBundle.model_validate(payload)


def project_bundle_to_bc5cdr_document(bundle: EvidenceExtractionBundle) -> tuple[BC5CDRDocument, list[str]]:
    mentions: list[BC5CDRMention] = []
    relations: list[BC5CDRRelation] = []
    warnings: list[str] = []
    mention_lookup: dict[str, BC5CDRMention] = {}

    for record in bundle.records:
        if record.record_type == "entity":
            mention = _project_entity_record(record, warnings)
            if mention is None:
                continue
            mentions.append(mention)
            mention_lookup[record.record_id] = mention

    for record in bundle.records:
        if record.record_type == "relation":
            relation = _project_relation_record(record, mention_lookup, warnings)
            if relation is None:
                continue
            relations.append(relation)

    return (
        BC5CDRDocument(
            doc_id=bundle.doc_id,
            mentions=mentions,
            relations=relations,
        ),
        warnings,
    )


def evaluate_bc5cdr_bundle(
    *,
    gold_document: BC5CDRDocument,
    bundle: EvidenceExtractionBundle,
) -> BC5CDREvalReport:
    prediction_document, projection_warnings = project_bundle_to_bc5cdr_document(bundle)
    return evaluate_bc5cdr_prediction(
        gold_document=gold_document,
        prediction_document=prediction_document,
        warnings=projection_warnings,
    )


def evaluate_bc5cdr_prediction(
    *,
    gold_document: BC5CDRDocument,
    prediction_document: BC5CDRDocument,
    warnings: list[str] | None = None,
) -> BC5CDREvalReport:
    gold_mentions_exact = {_mention_exact_key(mention) for mention in gold_document.mentions}
    pred_mentions_exact = {_mention_exact_key(mention) for mention in prediction_document.mentions}
    gold_mentions_normalized = {_mention_normalized_key(mention) for mention in gold_document.mentions}
    pred_mentions_normalized = {_mention_normalized_key(mention) for mention in prediction_document.mentions}
    gold_relations = _relation_keys(gold_document)
    pred_relations = _relation_keys(prediction_document)

    return BC5CDREvalReport(
        evaluated_at=datetime.now(timezone.utc),
        gold_doc_id=gold_document.doc_id,
        prediction_doc_id=prediction_document.doc_id,
        doc_id_match=gold_document.doc_id == prediction_document.doc_id,
        mention_exact=_score(gold_mentions_exact, pred_mentions_exact),
        mention_normalized=_score(gold_mentions_normalized, pred_mentions_normalized),
        relation=_score(gold_relations, pred_relations),
        warnings=list(warnings or []),
    )


def write_bc5cdr_eval_report(report: BC5CDREvalReport, path: Path) -> Path:
    atomic_write_text(path, report.model_dump_json(indent=2))
    return path


def _project_entity_record(record: EvidenceExtractionRecord, warnings: list[str]) -> BC5CDRMention | None:
    entity_type = str(record.metadata.get("entity_type") or "").strip().lower()
    if entity_type not in _SUPPORTED_ENTITY_TYPES:
        warnings.append(f"unsupported_entity_type:{record.record_id}")
        return None

    char_start = _safe_int(record.metadata.get("char_start"))
    char_end = _safe_int(record.metadata.get("char_end"))
    if char_start is None or char_end is None or char_end <= char_start:
        warnings.append(f"entity_missing_offsets:{record.record_id}")
        return None

    mention_text = str(record.metadata.get("mention_text") or record.value or "").strip()
    if not mention_text:
        warnings.append(f"entity_missing_text:{record.record_id}")
        return None

    normalized_id = record.normalized_value if isinstance(record.normalized_value, str) else None
    if normalized_id is None:
        candidate = str(record.metadata.get("normalized_id") or "").strip()
        normalized_id = candidate or None

    return BC5CDRMention(
        mention_id=record.record_id,
        entity_type=entity_type,  # type: ignore[arg-type]
        text=mention_text,
        char_start=char_start,
        char_end=char_end,
        normalized_id=normalized_id,
    )


def _project_relation_record(
    record: EvidenceExtractionRecord,
    mention_lookup: dict[str, BC5CDRMention],
    warnings: list[str],
) -> BC5CDRRelation | None:
    relation_type = str(record.metadata.get("relation_type") or "chemical_induced_disease").strip().lower()
    if relation_type not in _SUPPORTED_RELATION_TYPES:
        warnings.append(f"unsupported_relation_type:{record.record_id}")
        return None

    chemical_id = str(
        record.metadata.get("chemical_record_id")
        or record.metadata.get("chemical_mention_id")
        or ""
    ).strip()
    disease_id = str(
        record.metadata.get("disease_record_id")
        or record.metadata.get("disease_mention_id")
        or ""
    ).strip()
    if not chemical_id or not disease_id:
        warnings.append(f"relation_missing_endpoints:{record.record_id}")
        return None
    if chemical_id not in mention_lookup or disease_id not in mention_lookup:
        warnings.append(f"relation_unknown_endpoint:{record.record_id}")
        return None

    chemical = mention_lookup[chemical_id]
    disease = mention_lookup[disease_id]
    if chemical.entity_type != "chemical" or disease.entity_type != "disease":
        warnings.append(f"relation_endpoint_type_mismatch:{record.record_id}")
        return None

    return BC5CDRRelation(
        relation_id=record.record_id,
        relation_type=relation_type,  # type: ignore[arg-type]
        chemical_mention_id=chemical_id,
        disease_mention_id=disease_id,
    )


def _mention_exact_key(mention: BC5CDRMention) -> tuple[str, int, int]:
    return (mention.entity_type, mention.char_start, mention.char_end)


def _mention_normalized_key(mention: BC5CDRMention) -> tuple[str, int, int, str | None]:
    normalized = str(mention.normalized_id or "").strip() or None
    return (mention.entity_type, mention.char_start, mention.char_end, normalized)


def _relation_keys(
    document: BC5CDRDocument,
) -> set[tuple[tuple[str, int, int], tuple[str, int, int], str]]:
    mention_lookup = {mention.mention_id: mention for mention in document.mentions}
    keys: set[tuple[tuple[str, int, int], tuple[str, int, int], str]] = set()
    for relation in document.relations:
        chemical = mention_lookup.get(relation.chemical_mention_id)
        disease = mention_lookup.get(relation.disease_mention_id)
        if chemical is None or disease is None:
            continue
        chemical_key = _mention_exact_key(chemical)
        disease_key = _mention_exact_key(disease)
        keys.add((chemical_key, disease_key, relation.relation_type))
    return keys


def _score(gold: set[tuple], predicted: set[tuple]) -> BC5CDRScore:
    hit_count = len(gold & predicted)
    predicted_count = len(predicted)
    gold_count = len(gold)
    precision = hit_count / predicted_count if predicted_count else 0.0
    recall = hit_count / gold_count if gold_count else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else 0.0
    return BC5CDRScore(
        predicted_count=predicted_count,
        gold_count=gold_count,
        hit_count=hit_count,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def _safe_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

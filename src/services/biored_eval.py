from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.biored_eval import (
    BioREDDocument,
    BioREDEvalReport,
    BioREDMention,
    BioREDRelation,
    BioREDScore,
)
from src.schemas.evidence_extraction import EvidenceExtractionBundle, EvidenceExtractionRecord
from src.skills.storage import atomic_write_text


def load_biored_document(path: Path) -> BioREDDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"BioRED document payload must be a JSON object: {path}")
    return BioREDDocument.model_validate(payload)


def project_bundle_to_biored_document(bundle: EvidenceExtractionBundle) -> tuple[BioREDDocument, list[str]]:
    mentions: list[BioREDMention] = []
    relations: list[BioREDRelation] = []
    warnings: list[str] = []
    mention_lookup: dict[str, BioREDMention] = {}

    for record in bundle.records:
        if record.record_type != "entity":
            continue
        mention = _project_entity_record(record, warnings)
        if mention is None:
            continue
        mentions.append(mention)
        mention_lookup[record.record_id] = mention

    for record in bundle.records:
        if record.record_type != "relation":
            continue
        relation = _project_relation_record(record, mention_lookup, warnings)
        if relation is None:
            continue
        relations.append(relation)

    return (
        BioREDDocument(
            doc_id=bundle.doc_id,
            mentions=mentions,
            relations=relations,
        ),
        warnings,
    )


def evaluate_biored_bundle(
    *,
    gold_document: BioREDDocument,
    bundle: EvidenceExtractionBundle,
) -> BioREDEvalReport:
    prediction_document, projection_warnings = project_bundle_to_biored_document(bundle)
    return evaluate_biored_prediction(
        gold_document=gold_document,
        prediction_document=prediction_document,
        warnings=projection_warnings,
    )


def evaluate_biored_prediction(
    *,
    gold_document: BioREDDocument,
    prediction_document: BioREDDocument,
    warnings: list[str] | None = None,
) -> BioREDEvalReport:
    gold_mentions_exact = {_mention_exact_key(mention) for mention in gold_document.mentions}
    pred_mentions_exact = {_mention_exact_key(mention) for mention in prediction_document.mentions}
    gold_mentions_normalized = {_mention_normalized_key(mention) for mention in gold_document.mentions}
    pred_mentions_normalized = {_mention_normalized_key(mention) for mention in prediction_document.mentions}
    gold_relations = _relation_keys(gold_document)
    pred_relations = _relation_keys(prediction_document)
    gold_relations_with_novelty = _relation_keys(gold_document, include_novelty=True)
    pred_relations_with_novelty = _relation_keys(prediction_document, include_novelty=True)

    return BioREDEvalReport(
        evaluated_at=datetime.now(timezone.utc),
        gold_doc_id=gold_document.doc_id,
        prediction_doc_id=prediction_document.doc_id,
        doc_id_match=gold_document.doc_id == prediction_document.doc_id,
        mention_exact=_score(gold_mentions_exact, pred_mentions_exact),
        mention_normalized=_score(gold_mentions_normalized, pred_mentions_normalized),
        relation=_score(gold_relations, pred_relations),
        relation_novelty=_score(gold_relations_with_novelty, pred_relations_with_novelty),
        warnings=list(warnings or []),
    )


def write_biored_eval_report(report: BioREDEvalReport, path: Path) -> Path:
    atomic_write_text(path, report.model_dump_json(indent=2))
    return path


def _project_entity_record(record: EvidenceExtractionRecord, warnings: list[str]) -> BioREDMention | None:
    entity_type = str(record.metadata.get("entity_type") or "").strip()
    if not entity_type:
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

    normalized_ids = _normalized_ids_from_record(record)
    entity_id = str(record.metadata.get("entity_id") or "").strip() or None

    return BioREDMention(
        mention_id=record.record_id,
        entity_type=entity_type,
        text=mention_text,
        char_start=char_start,
        char_end=char_end,
        normalized_ids=normalized_ids,
        entity_id=entity_id,
    )


def _project_relation_record(
    record: EvidenceExtractionRecord,
    mention_lookup: dict[str, BioREDMention],
    warnings: list[str],
) -> BioREDRelation | None:
    relation_type = str(record.metadata.get("relation_type") or "").strip()
    if not relation_type:
        warnings.append(f"unsupported_relation_type:{record.record_id}")
        return None

    head_id = str(
        record.metadata.get("head_record_id")
        or record.metadata.get("chemical_record_id")
        or record.metadata.get("source_record_id")
        or ""
    ).strip()
    tail_id = str(
        record.metadata.get("tail_record_id")
        or record.metadata.get("disease_record_id")
        or record.metadata.get("target_record_id")
        or ""
    ).strip()
    if not head_id or not tail_id:
        warnings.append(f"relation_missing_endpoints:{record.record_id}")
        return None
    if head_id not in mention_lookup or tail_id not in mention_lookup:
        warnings.append(f"relation_unknown_endpoint:{record.record_id}")
        return None

    novelty = _normalize_novelty(record.metadata.get("novelty"))
    return BioREDRelation(
        relation_id=record.record_id,
        relation_type=relation_type,
        head_mention_id=head_id,
        tail_mention_id=tail_id,
        novelty=novelty,
    )


def _mention_exact_key(mention: BioREDMention) -> tuple[str, int, int]:
    return (mention.entity_type, mention.char_start, mention.char_end)


def _mention_normalized_key(mention: BioREDMention) -> tuple[str, int, int, tuple[str, ...]]:
    return (mention.entity_type, mention.char_start, mention.char_end, tuple(sorted(mention.normalized_ids)))


def _relation_keys(
    document: BioREDDocument,
    *,
    include_novelty: bool = False,
) -> set[tuple]:
    mention_lookup = {mention.mention_id: mention for mention in document.mentions}
    keys: set[tuple] = set()
    for relation in document.relations:
        head = mention_lookup.get(relation.head_mention_id)
        tail = mention_lookup.get(relation.tail_mention_id)
        if head is None or tail is None:
            continue
        base = (_mention_exact_key(head), _mention_exact_key(tail), relation.relation_type)
        if include_novelty:
            keys.add(base + (relation.novelty,))
        else:
            keys.add(base)
    return keys


def _score(gold: set[tuple], predicted: set[tuple]) -> BioREDScore:
    hit_count = len(gold & predicted)
    predicted_count = len(predicted)
    gold_count = len(gold)
    precision = hit_count / predicted_count if predicted_count else 0.0
    recall = hit_count / gold_count if gold_count else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else 0.0
    return BioREDScore(
        predicted_count=predicted_count,
        gold_count=gold_count,
        hit_count=hit_count,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def _normalized_ids_from_record(record: EvidenceExtractionRecord) -> list[str]:
    values = record.metadata.get("normalized_ids")
    if isinstance(values, list):
        normalized = [str(value).strip() for value in values if str(value).strip()]
        if normalized:
            return normalized
    if isinstance(record.normalized_value, str) and record.normalized_value.strip():
        return [record.normalized_value.strip()]
    candidate = str(record.metadata.get("normalized_id") or "").strip()
    return [candidate] if candidate else []


def _normalize_novelty(value: object) -> str:
    token = str(value or "").strip().lower()
    if token in {"novel", "new"}:
        return "novel"
    if token in {"background", "known", "existing", "previously_known"}:
        return "background"
    return "unknown"


def _safe_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.llm_provider import get_llm_provider
from src.services.slot_classification_audit import (
    classify_slot_classification_input_richness,
    load_slot_classification_goldset_csv,
)

_FENCED_TEXT_RE = re.compile(r"```(?:text|prompt)?\s*\n(?P<body>.*?)\n```", re.DOTALL)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def load_candidate_prompt_template(prompt_path: Path) -> str:
    text = prompt_path.read_text(encoding="utf-8").strip()
    match = _FENCED_TEXT_RE.search(text)
    template = (match.group("body") if match else text).strip()
    if "{evidence_bundle}" not in template:
        raise ValueError(f"candidate_prompt_missing_evidence_bundle_placeholder={prompt_path}")
    return template


def _normalize_slot(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"clinical", "mechanism", "methods"}:
        return normalized
    return None


def _normalize_current_slot(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"clinical", "mechanism", "methods", "unknown"}:
        return normalized
    return None


def _title_case_current_slot(value: str) -> str:
    return {
        "clinical": "Clinical",
        "mechanism": "Mechanism",
        "methods": "Methods",
        "unknown": "Unknown",
    }[value]


def _coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _build_provider_payload(row: dict) -> dict[str, Any]:
    payload: dict[str, Any] = {"title": row.get("title") or ""}
    if row.get("summary"):
        payload["summary"] = row["summary"]
    if row.get("full_text"):
        payload["full_text"] = row["full_text"]
    return payload


def _extract_json(provider: Any, response_content: str | None) -> dict[str, Any] | None:
    if not response_content:
        return None
    extractor = getattr(provider, "_extract_json", None)
    if callable(extractor):
        extracted = extractor(response_content)
        return extracted if isinstance(extracted, dict) else None
    try:
        parsed = json.loads(response_content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_provider_slot(provider: Any, value: Any) -> str | None:
    normalizer = getattr(provider, "_normalize_slot_prediction", None)
    if callable(normalizer):
        normalized = normalizer(value)
        return _normalize_slot(normalized)
    return _normalize_slot(value)


def _build_evidence_bundle(provider: Any, paper: dict[str, Any], current_slot: str) -> str:
    builder = getattr(provider, "_paper_evidence_bundle", None)
    if callable(builder):
        return str(
            builder(
                paper,
                current_slot=_title_case_current_slot(current_slot),
                max_chars=4500,
                per_section_chars=900,
            )
        )
    parts = [
        f"Title: {paper.get('title', 'N/A')}",
        f"Abstract: {paper.get('summary', 'N/A')}",
        f"Current Slot: {_title_case_current_slot(current_slot)}",
    ]
    if paper.get("full_text"):
        parts.extend(["Full Text Excerpt:", str(paper.get("full_text"))[:4500]])
    return "\n".join(parts)


def _classify_with_candidate_prompt(
    *,
    provider: Any,
    paper: dict[str, Any],
    current_slot: str,
    prompt_template: str,
) -> dict[str, Any]:
    evidence_bundle = _build_evidence_bundle(provider, paper, current_slot)
    prompt = prompt_template.replace("{evidence_bundle}", evidence_bundle)
    requester = getattr(provider, "_make_request", None)
    if not callable(requester):
        return {
            "predicted_slot": None,
            "prediction_status": "provider_missing_make_request",
            "first_pass_predicted_slot": None,
            "final_source": None,
            "adjudication_triggered": None,
            "adjudication_reason": None,
            "confidence": None,
            "error": "Provider does not expose _make_request.",
        }

    response = requester("slot_classification", prompt, is_json=True)
    payload = _extract_json(provider, response)
    if not payload:
        return {
            "predicted_slot": None,
            "prediction_status": "invalid_response",
            "first_pass_predicted_slot": None,
            "final_source": None,
            "adjudication_triggered": None,
            "adjudication_reason": None,
            "confidence": None,
            "error": str(response or "").strip() or "No response content.",
        }

    predicted_slot = _normalize_provider_slot(provider, payload.get("predicted_slot"))
    if predicted_slot is None:
        return {
            "predicted_slot": None,
            "prediction_status": "invalid_prediction",
            "first_pass_predicted_slot": None,
            "final_source": None,
            "adjudication_triggered": _coerce_optional_bool(payload.get("needs_adjudication")),
            "adjudication_reason": str(payload.get("reasoning") or "").strip() or None,
            "confidence": _coerce_optional_float(payload.get("confidence")),
            "error": f"invalid_predicted_slot={payload.get('predicted_slot')}",
        }

    return {
        "predicted_slot": predicted_slot,
        "prediction_status": "ok",
        "first_pass_predicted_slot": predicted_slot,
        "final_source": "candidate_prompt_first_pass",
        "adjudication_triggered": _coerce_optional_bool(payload.get("needs_adjudication")),
        "adjudication_reason": str(payload.get("reasoning") or "").strip() or None,
        "confidence": _coerce_optional_float(payload.get("confidence")),
        "error": None,
    }


def run_candidate_generation(
    *,
    goldset_csv_path: Path,
    candidate_prompt_path: Path,
    out_dir: Path,
    run_id: str,
    candidate_id: str,
    provider: Any | None = None,
    fallback_current_slot: str | None = None,
) -> Path:
    rows = load_slot_classification_goldset_csv(goldset_csv_path)
    prompt_template = load_candidate_prompt_template(candidate_prompt_path)
    if provider is None:
        config = load_config()
        provider = get_llm_provider(config.llm, getattr(config, "entity_aliases", None))
    provider_available = bool(provider and provider.is_available())
    fallback_current_slot = _normalize_current_slot(fallback_current_slot)

    run_root = out_dir / run_id
    prediction_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    for row in rows:
        current_slot = _normalize_current_slot(row.get("current_slot")) or fallback_current_slot
        input_richness = classify_slot_classification_input_richness(
            title=row.get("title"),
            summary=row.get("summary"),
            full_text=row.get("full_text"),
        )
        record: dict[str, Any] = {
            "paper_id": row.get("paper_id"),
            "doi": row.get("doi"),
            "title": row.get("title"),
            "gold_slot": row.get("gold_slot"),
            "current_slot": current_slot,
            "input_richness": input_richness,
            "predicted_slot": None,
            "prediction_status": None,
            "prediction_source": "none",
            "candidate_id": candidate_id,
            "first_pass_predicted_slot": None,
            "final_source": None,
            "adjudication_triggered": None,
            "adjudication_reason": None,
            "confidence": None,
            "error": None,
        }
        if not provider_available:
            record["prediction_status"] = "provider_unavailable"
            detail_rows.append(record)
            continue
        if not current_slot:
            record["prediction_status"] = "missing_current_slot"
            detail_rows.append(record)
            continue

        try:
            result = _classify_with_candidate_prompt(
                provider=provider,
                paper=_build_provider_payload(row),
                current_slot=current_slot,
                prompt_template=prompt_template,
            )
            record.update(result)
            if record["prediction_status"] == "ok":
                record["prediction_source"] = "prompt_candidate"
        except Exception as exc:
            record["prediction_status"] = "provider_exception"
            record["error"] = str(exc)

        detail_rows.append(record)
        if record["prediction_status"] == "ok":
            prediction_rows.append(
                {
                    "paper_id": record["paper_id"],
                    "doi": record["doi"],
                    "title": record["title"],
                    "current_slot": record["current_slot"],
                    "input_richness": record["input_richness"],
                    "predicted_slot": record["predicted_slot"],
                    "prediction_status": record["prediction_status"],
                    "prediction_source": record["prediction_source"],
                    "candidate_id": record["candidate_id"],
                    "first_pass_predicted_slot": record["first_pass_predicted_slot"],
                    "final_source": record["final_source"],
                    "adjudication_triggered": record["adjudication_triggered"],
                    "adjudication_reason": record["adjudication_reason"],
                    "confidence": record["confidence"],
                }
            )

    status_counts = Counter(str(row.get("prediction_status") or "") for row in detail_rows)
    input_richness_counts = Counter(str(row.get("input_richness") or "") for row in detail_rows)
    summary = {
        "schema_version": "slot_classification_prompt_candidate_prediction_generation.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "inputs": {
            "goldset_csv_path": str(goldset_csv_path),
            "candidate_prompt_path": str(candidate_prompt_path),
            "fallback_current_slot": fallback_current_slot,
        },
        "provider_available": provider_available,
        "document_count": len(rows),
        "prediction_written_count": len(prediction_rows),
        "status_counts": {key: int(value) for key, value in sorted(status_counts.items())},
        "input_richness_counts": {key: int(value) for key, value in sorted(input_richness_counts.items())},
        "predictions_jsonl_path": str(run_root / "predictions.jsonl"),
    }
    details = {
        "schema_version": "slot_classification_prompt_candidate_prediction_generation_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "documents": detail_rows,
    }
    _write_jsonl(run_root / "predictions.jsonl", prediction_rows)
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", details)
    return run_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate slot-classification prediction JSONL with a non-runtime prompt candidate."
    )
    parser.add_argument(
        "--goldset-csv",
        default=str(ROOT / "tests" / "gold_set" / "gold_standard_template.csv"),
        help="Goldset CSV path with title, gold_slot, and optional summary/full_text/current_slot columns.",
    )
    parser.add_argument("--candidate-prompt", required=True, help="Prompt candidate markdown or text path.")
    parser.add_argument("--candidate-id", required=True, help="Prompt candidate identifier.")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "slot_classification_predictions"),
        help="Output directory for generated predictions and summary artifacts.",
    )
    parser.add_argument(
        "--fallback-current-slot",
        default=None,
        choices=["clinical", "mechanism", "methods", "unknown"],
        help="Optional fallback slot when the goldset row omits current_slot.",
    )
    parser.add_argument("--run-id", required=True, help="Generation run identifier.")
    args = parser.parse_args()

    run_root = run_candidate_generation(
        goldset_csv_path=Path(args.goldset_csv).expanduser(),
        candidate_prompt_path=Path(args.candidate_prompt).expanduser(),
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
        candidate_id=args.candidate_id,
        fallback_current_slot=args.fallback_current_slot,
    )
    payload = {
        "run_root": str(run_root),
        "predictions_jsonl_path": str(run_root / "predictions.jsonl"),
        "summary_path": str(run_root / "summary.json"),
        "details_path": str(run_root / "details.json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

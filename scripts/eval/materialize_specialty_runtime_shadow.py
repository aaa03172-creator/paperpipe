#!/usr/bin/env python3
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

from src.config import load_config, resolve_specialty_trial_extraction_feature
from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.llm_provider import get_llm_provider
from src.schemas.agent_artifacts import DocumentArtifact
from src.schemas.core import SpecialtyTrialExtraction


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = _load_json_object(path)
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise RuntimeError(f"manifest_missing_documents={path}")
    return [doc for doc in documents if isinstance(doc, dict)]


def _resolve_manifest_entry_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path or "").strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (manifest_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _candidate_run_dirs(*, manifest_path: Path, doc: dict[str, Any], artifacts_root: Path) -> list[Path]:
    paper_id = str(doc.get("paper_id") or "").strip()
    run_dirs: dict[str, Path] = {}

    if paper_id:
        canonical_root = artifacts_root / paper_id
        if canonical_root.exists():
            for run_dir in canonical_root.glob("run_*"):
                if run_dir.is_dir():
                    run_dirs[str(run_dir.resolve())] = run_dir.resolve()

    for source_path in doc.get("gold_source_paths") or []:
        resolved = _resolve_manifest_entry_path(manifest_path, str(source_path or ""))
        if resolved.exists():
            parent = resolved.parent.resolve()
            if parent.is_dir():
                run_dirs[str(parent)] = parent

    return sorted(run_dirs.values(), key=lambda item: item.name)


def _safe_name(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    token = re.sub(r"_+", "_", token).strip("_")
    return token or "artifact"


def _diagnostic_reason_codes(*, status: str | None, error_text: str | None) -> list[str]:
    if str(status or "").strip() != "schema_invalid":
        return []
    text = str(error_text or "").strip()
    if not text:
        return []

    reason_codes: list[str] = []
    current_field: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("ValidationError:") or line.startswith("For further information visit"):
            continue
        if not raw_line.startswith(" "):
            current_field = re.sub(r"[^a-zA-Z0-9_.]+", "", line)
            continue
        if not current_field:
            continue
        field_token = current_field.replace(".", "_")
        lowered = line.lower()
        if lowered.startswith("field required"):
            code = f"missing_{field_token}"
        else:
            code = f"invalid_{field_token}"
        if code not in reason_codes:
            reason_codes.append(code)
        current_field = None
    return reason_codes


def _slice_between(text: str, start_markers: list[str], end_markers: list[str]) -> str:
    lowered = text.lower()
    start_idx = -1
    for marker in start_markers:
        idx = lowered.find(marker.lower())
        if idx != -1:
            start_idx = idx
            break
    if start_idx == -1:
        return ""
    end_idx = len(text)
    for marker in end_markers:
        idx = lowered.find(marker.lower(), start_idx)
        if idx != -1:
            end_idx = min(end_idx, idx)
    return text[start_idx:end_idx].strip()


def _load_artifact(path: Path) -> DocumentArtifact | DocumentArtifactV2:
    payload = _load_json_object(path)
    try:
        return DocumentArtifactV2.model_validate(payload)
    except Exception:
        return DocumentArtifact.model_validate(payload)


def _is_specialty_shadow_eligible(extraction: SpecialtyTrialExtraction) -> bool:
    return bool(extraction.eligibility_flags.include_for_mci_mct_review and extraction.population.mci_only)


def _build_specialty_shadow_inputs(
    doc: DocumentArtifact | DocumentArtifactV2,
    *,
    paper_id: str,
    gold_extraction: SpecialtyTrialExtraction,
) -> tuple[dict[str, Any], str]:
    header = get_artifact_header(doc)
    sections = [section for section in iter_text_sections(doc) if (section.text or "").strip()]
    texts = [section.text.strip() for section in sections]
    page0 = texts[0] if texts else ""
    early_text = "\n\n".join(texts[:3])

    summary = _slice_between(
        page0,
        start_markers=[
            "importance",
            "background",
            "objective",
            "abstract",
            "results",
        ],
        end_markers=[
            "author affiliations:",
            "corresponding author:",
            "trial registration",
            "copyright",
            "methods",
        ],
    )
    if not summary:
        summary = "\n\n".join(texts[:2])[:3200]
    else:
        summary = summary[:3200]

    snippets: list[str] = []
    lowered_early = early_text.lower()
    for marker in (
        "design, setting, and participants",
        "participants",
        "interventions",
        "main outcomes and measures",
        "methods",
        "results",
    ):
        idx = lowered_early.find(marker)
        if idx != -1:
            snippets.append(early_text[max(0, idx - 120) : idx + 900])
    methods_snippet = "\n\n".join(snippets)[:3000] if snippets else early_text[:3000]

    citation = gold_extraction.citation
    title = str(citation.title or header.title or paper_id)
    authors = citation.authors_first or ", ".join(header.authors) or "Unknown"
    published = str(citation.year or "")
    source = citation.journal_or_server or "Unknown"
    doi = citation.doi if citation.doi else None
    paper_payload = {
        "paper_id": paper_id,
        "title": title,
        "summary": summary,
        "published": published,
        "source": source,
        "authors": authors,
        "link": paper_id,
        "doi": doi,
    }
    return paper_payload, methods_snippet


def _materialize_record(
    *,
    manifest_path: Path,
    doc: dict[str, Any],
    artifacts_root: Path,
    run_root: Path,
    provider: Any,
    provider_available: bool,
) -> dict[str, Any]:
    paper_id = str(doc.get("paper_id") or "").strip()
    gold_path = _resolve_manifest_entry_path(manifest_path, str(doc.get("gold_path") or ""))
    gold_extraction = SpecialtyTrialExtraction.model_validate(_load_json_object(gold_path))
    run_dirs = _candidate_run_dirs(manifest_path=manifest_path, doc=doc, artifacts_root=artifacts_root)

    record: dict[str, Any] = {
        "paper_id": paper_id,
        "gold_path": str(gold_path),
        "eligible_for_specialty_shadow": _is_specialty_shadow_eligible(gold_extraction),
        "candidate_run_dir_count": len(run_dirs),
        "latest_run_dir": str(run_dirs[-1]) if run_dirs else None,
        "document_artifact_path": None,
        "status": None,
        "prediction_path": None,
        "prediction_paper_id": None,
        "provider_diagnostic_status": None,
        "provider_diagnostic_error": None,
        "provider_diagnostic_reason_codes": [],
        "raw_response_path": None,
        "raw_response_chars": 0,
        "compare_ready": False,
    }

    if not record["eligible_for_specialty_shadow"]:
        record["status"] = "skipped_ineligible"
        return record
    if not run_dirs:
        record["status"] = "no_runtime_run"
        return record

    artifact_path = run_dirs[-1] / "document_artifact.json"
    if not artifact_path.exists():
        record["status"] = "missing_document_artifact"
        return record
    record["document_artifact_path"] = str(artifact_path)

    if not provider_available:
        record["status"] = "provider_unavailable"
        return record

    doc_artifact = _load_artifact(artifact_path)
    paper_payload, methods_snippet = _build_specialty_shadow_inputs(
        doc_artifact,
        paper_id=paper_id,
        gold_extraction=gold_extraction,
    )
    record["paper_payload_preview"] = {
        "title": paper_payload["title"],
        "summary_chars": len(str(paper_payload["summary"] or "")),
        "methods_chars": len(str(methods_snippet or "")),
    }

    try:
        prediction = provider.extract_specialty_trial_data(paper_payload, methods_snippet)
    except Exception as exc:
        record["status"] = "provider_exception"
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record

    diagnostic_getter = getattr(provider, "get_specialty_trial_extraction_diagnostic", None)
    if callable(diagnostic_getter):
        diagnostic = diagnostic_getter() or {}
        if isinstance(diagnostic, dict):
            record["provider_diagnostic_status"] = str(diagnostic.get("status") or "").strip() or None
            error_text = str(diagnostic.get("error") or "").strip()
            record["provider_diagnostic_error"] = error_text or None
            record["provider_diagnostic_reason_codes"] = _diagnostic_reason_codes(
                status=record["provider_diagnostic_status"],
                error_text=record["provider_diagnostic_error"],
            )

    raw_response_getter = getattr(provider, "get_specialty_trial_extraction_raw_response", None)
    if callable(raw_response_getter):
        raw_response = raw_response_getter()
        raw_text = str(raw_response).strip() if raw_response is not None else ""
        if raw_text:
            raw_response_path = run_root / "raw_responses" / f"{_safe_name(paper_id)}.txt"
            raw_response_path.parent.mkdir(parents=True, exist_ok=True)
            raw_response_path.write_text(raw_text + "\n", encoding="utf-8")
            record["raw_response_path"] = str(raw_response_path)
            record["raw_response_chars"] = len(raw_text)

    if not isinstance(prediction, SpecialtyTrialExtraction):
        if record.get("provider_diagnostic_status") == "schema_invalid":
            record["status"] = "prediction_schema_invalid"
            record["error"] = record.get("provider_diagnostic_error")
        else:
            record["status"] = "prediction_empty"
        return record

    prediction_paper_id = str(prediction.paper_id or "").strip()
    if prediction_paper_id != paper_id:
        record["status"] = "pairing_mismatch"
        record["prediction_paper_id"] = prediction_paper_id or None
        record["error"] = f"PAIRING_MISMATCH expected={paper_id} prediction={prediction_paper_id}"
        return record

    prediction_path = run_root / "predictions" / f"{_safe_name(paper_id)}.json"
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_text(prediction.model_dump_json(indent=2) + "\n", encoding="utf-8")
    record["status"] = "prediction_written"
    record["prediction_path"] = str(prediction_path)
    record["prediction_paper_id"] = prediction_paper_id
    record["compare_ready"] = True
    return record


def run_specialty_shadow_materializer(
    *,
    manifest_path: Path,
    artifacts_root: Path,
    out_dir: Path,
    run_id: str,
    provider: Any | None = None,
    feature_enabled: bool | None = None,
) -> Path:
    documents = _load_manifest(manifest_path)
    config = None
    if provider is None or feature_enabled is None:
        config = load_config()
    if provider is None:
        provider = get_llm_provider(config.llm, getattr(config, "entity_aliases", None))
    provider_available = bool(provider and provider.is_available())
    if feature_enabled is None:
        feature = resolve_specialty_trial_extraction_feature(getattr(config.llm, "features", None))
        feature_enabled = bool(getattr(feature, "enabled", False)) if feature is not None else False

    run_root = out_dir / run_id
    records = [
        _materialize_record(
            manifest_path=manifest_path,
            doc=doc,
            artifacts_root=artifacts_root,
            run_root=run_root,
            provider=provider,
            provider_available=provider_available,
        )
        for doc in documents
    ]
    records.sort(key=lambda item: str(item.get("paper_id") or ""))

    compare_docs = [
        {
            "paper_id": record["paper_id"],
            "gold_path": record["gold_path"],
            "prediction_path": record["prediction_path"],
        }
        for record in records
        if record.get("compare_ready") and record.get("prediction_path")
    ]
    generated_manifest = {
        "schema_version": "extraction_regression_manifest.v1",
        "generated_at": _utc_now_iso(),
        "source_manifest": str(manifest_path),
        "notes": [
            "Shadow materialization of specialty extraction artifacts using the current provider path.",
            "This is a bounded developer-sidecar lane and does not change product runtime behavior.",
        ],
        "documents": compare_docs,
    }
    _write_json(run_root / "generated_manifest.json", generated_manifest)

    status_counts = Counter(str(record.get("status") or "") for record in records)
    schema_invalid_reason_counts = Counter(
        code
        for record in records
        if str(record.get("status") or "") == "prediction_schema_invalid"
        for code in (record.get("provider_diagnostic_reason_codes") or [])
    )
    summary = {
        "schema_version": "specialty_runtime_shadow_materialization.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "manifest": str(manifest_path),
            "artifacts_root": str(artifacts_root),
        },
        "runtime_feature_enabled": bool(feature_enabled),
        "provider_available": provider_available,
        "document_count": len(records),
        "eligible_document_count": sum(1 for record in records if record.get("eligible_for_specialty_shadow")),
        "prediction_written_count": int(status_counts.get("prediction_written", 0)),
        "raw_response_written_count": sum(1 for record in records if record.get("raw_response_path")),
        "compare_ready_count": len(compare_docs),
        "status_counts": {
            "prediction_written": int(status_counts.get("prediction_written", 0)),
            "prediction_empty": int(status_counts.get("prediction_empty", 0)),
            "prediction_schema_invalid": int(status_counts.get("prediction_schema_invalid", 0)),
            "pairing_mismatch": int(status_counts.get("pairing_mismatch", 0)),
            "provider_exception": int(status_counts.get("provider_exception", 0)),
            "provider_unavailable": int(status_counts.get("provider_unavailable", 0)),
            "missing_document_artifact": int(status_counts.get("missing_document_artifact", 0)),
            "no_runtime_run": int(status_counts.get("no_runtime_run", 0)),
            "skipped_ineligible": int(status_counts.get("skipped_ineligible", 0)),
        },
        "schema_invalid_reason_counts": {
            code: int(count) for code, count in sorted(schema_invalid_reason_counts.items())
        },
        "generated_manifest_path": str(run_root / "generated_manifest.json"),
        "generated_manifest_document_count": len(compare_docs),
    }
    details = {
        "schema_version": "specialty_runtime_shadow_materialization_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "documents": records,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", details)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize specialty extraction artifacts for eligible runtime-shadow papers without changing runtime."
    )
    parser.add_argument("--manifest", required=True, help="Repo-grounded gold manifest to inspect.")
    parser.add_argument(
        "--artifacts-root",
        default=str(ROOT / "storage" / "artifacts"),
        help="Root folder containing runtime artifacts.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "extraction_runtime_shadow_materialized"),
        help="Output directory for materialized specialty shadow artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    run_root = run_specialty_shadow_materializer(
        manifest_path=Path(args.manifest).expanduser().resolve(),
        artifacts_root=Path(args.artifacts_root).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

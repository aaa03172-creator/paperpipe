#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import ollama

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.json_repair import repair_and_parse_json  # noqa: E402
from src.schemas.biored_eval import BioREDDocument  # noqa: E402
from src.services.biored_adapter import project_biored_to_evidence_extraction_bundle  # noqa: E402
from src.services.biored_eval import evaluate_biored_bundle, load_biored_document, write_biored_eval_report  # noqa: E402
from src.services.biored_prediction import (  # noqa: E402
    build_biored_prediction_inputs,
    build_biored_prediction_prompt,
    load_manifest,
    repair_biored_prediction_payload,
    resolve_manifest_entry_path,
    safe_file_stem,
)
from src.services.evidence_extraction_sidecar import write_evidence_extraction_bundle  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_predictions(
    *,
    manifest_path: Path,
    out_dir: Path,
    run_id: str,
    model: str,
    timeout_seconds: int,
    client: Any | None = None,
) -> Path:
    if client is None:
        config = load_config()
        host = config.llm.local.base_url if config.llm.local else "http://localhost:11434"
        client = ollama.Client(host=host, timeout=timeout_seconds)

    documents = load_manifest(manifest_path)
    run_root = out_dir / run_id
    predictions_root = run_root / "predictions"
    bundles_root = run_root / "bundles"
    eval_root = run_root / "eval"
    raw_root = run_root / "raw"
    errors_root = run_root / "errors"
    run_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    generated_docs: list[dict[str, Any]] = []
    schema_json = json.dumps(BioREDDocument.model_json_schema(), indent=2)

    for doc in documents:
        paper_id = str(doc.get("paper_id") or "").strip()
        gold_path = resolve_manifest_entry_path(manifest_path, str(doc.get("gold_path") or ""))
        gold_document = load_biored_document(gold_path)
        effective_paper_id = paper_id or gold_document.doc_id
        safe_id = safe_file_stem(effective_paper_id)

        source_path = None
        for candidate in doc.get("gold_source_paths") or []:
            resolved = resolve_manifest_entry_path(manifest_path, str(candidate or ""))
            if resolved.exists():
                source_path = resolved
                break
        if source_path is None:
            raise FileNotFoundError(f"document_artifact_missing_for={effective_paper_id}")

        paper = build_biored_prediction_inputs(source_path, paper_id=effective_paper_id)
        prompt = build_biored_prediction_prompt(paper=paper, schema_json=schema_json)

        raw_response: str | None = None
        status = "error"
        error_message: str | None = None
        prediction_path: str | None = None
        bundle_path: str | None = None
        eval_path: str | None = None
        eval_summary: dict[str, Any] | None = None

        try:
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.0, "num_predict": 3072},
            )
            raw_response = response["message"]["content"]
            parsed = repair_and_parse_json(raw_response)
            if not isinstance(parsed, dict):
                raise RuntimeError("parsed_payload_not_object")

            repaired = repair_biored_prediction_payload(
                parsed,
                paper_id=paper["doc_id"],
                abstract_text=paper["abstract"],
                default_title=paper["title"],
            )
            prediction_document = BioREDDocument.model_validate(repaired)

            prediction_file = predictions_root / f"{safe_id}.json"
            _write_json(prediction_file, prediction_document.model_dump(mode="json"))
            prediction_path = str(prediction_file)

            bundle = project_biored_to_evidence_extraction_bundle(
                prediction_document,
                paper_id=effective_paper_id,
                run_id=run_id,
                source_artifact="biored_prediction.json",
            )
            bundle_file = write_evidence_extraction_bundle(bundle, bundles_root / safe_id)
            bundle_path = str(bundle_file)

            report = evaluate_biored_bundle(gold_document=gold_document, bundle=bundle)
            report_file = write_biored_eval_report(report, eval_root / f"{safe_id}.json")
            eval_path = str(report_file)
            eval_summary = report.model_dump(mode="json")

            generated_docs.append(
                {
                    "paper_id": effective_paper_id,
                    "gold_path": str(gold_path),
                    "prediction_path": prediction_path,
                    "bundle_path": bundle_path,
                    "eval_path": eval_path,
                }
            )
            status = "ok"
        except httpx.ReadTimeout:
            error_message = f"ReadTimeout model={model} timeout_seconds={timeout_seconds}"
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"

        raw_file = raw_root / f"{safe_id}.txt"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_text((raw_response or "") + ("\n" if raw_response else ""), encoding="utf-8")
        if error_message:
            _write_json(
                errors_root / f"{safe_id}.json",
                {
                    "paper_id": effective_paper_id,
                    "status": status,
                    "error": error_message,
                    "model": model,
                    "timeout_seconds": timeout_seconds,
                    "source_path": str(source_path),
                    "gold_path": str(gold_path),
                },
            )

        rows.append(
            {
                "paper_id": effective_paper_id,
                "status": status,
                "error": error_message,
                "model": model,
                "prediction_path": prediction_path,
                "bundle_path": bundle_path,
                "eval_path": eval_path,
                "raw_path": str(raw_file),
                "mention_exact_f1": (eval_summary or {}).get("mention_exact", {}).get("f1"),
                "mention_normalized_f1": (eval_summary or {}).get("mention_normalized", {}).get("f1"),
                "relation_f1": (eval_summary or {}).get("relation", {}).get("f1"),
                "relation_novelty_f1": (eval_summary or {}).get("relation_novelty", {}).get("f1"),
            }
        )

    generated_manifest_path = run_root / "generated_manifest.json"
    _write_json(
        generated_manifest_path,
        {
            "schema_version": "biored_prediction_manifest.v1",
            "generated_at": _utc_now_iso(),
            "source_manifest": str(manifest_path),
            "model": model,
            "timeout_seconds": timeout_seconds,
            "documents": generated_docs,
        },
    )

    success_rows = [row for row in rows if row["status"] == "ok"]
    timeout_rows = [row for row in rows if "ReadTimeout" in str(row.get("error") or "")]
    metrics = {
        "schema_version": "biored_prediction_generation.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "source_manifest": str(manifest_path),
        "model": model,
        "timeout_seconds": timeout_seconds,
        "document_count": len(rows),
        "success_count": len(success_rows),
        "timeout_count": len(timeout_rows),
        "error_count": len([row for row in rows if row["status"] != "ok"]),
        "rows": rows,
        "generated_manifest_path": str(generated_manifest_path),
    }
    _write_json(run_root / "metrics.json", metrics)
    _write_json(
        run_root / "summary.json",
        {
            "run_id": run_id,
            "status": "ok",
            "model": model,
            "timeout_seconds": timeout_seconds,
            "document_count": len(rows),
            "success_count": len(success_rows),
            "timeout_count": len(timeout_rows),
            "generated_manifest_path": str(generated_manifest_path),
        },
    )
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate BioRED-style predictions from document artifacts, convert them into evidence bundles, and score them.",
    )
    parser.add_argument("--manifest", required=True, help="Manifest with BioRED gold_path plus gold_source_paths document artifacts.")
    parser.add_argument("--out-dir", default="snapshots/biored_prediction_generation", help="Output root directory.")
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument("--model", default="", help="Optional Ollama model override. Defaults to configured extractor model.")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="Per-request Ollama timeout seconds.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = load_config()
    default_model = config.llm.local.models.get("extractor", "llama3:latest") if config.llm.local else "llama3:latest"
    run_id = args.run_id or datetime.now(timezone.utc).strftime("biored_prediction_generation_%Y%m%d_%H%M%S")
    run_root = generate_predictions(
        manifest_path=Path(args.manifest).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        model=str(args.model or default_model),
        timeout_seconds=int(args.timeout_seconds),
    )
    print(f"[generate_biored_bundle_predictions] out={run_root}")
    print(f"[generate_biored_bundle_predictions] metrics={run_root / 'metrics.json'}")


if __name__ == "__main__":
    main()

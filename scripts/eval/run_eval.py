#!/usr/bin/env python3
import argparse
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.quality.gates import (
    EVIDENCE_LOCATION_MISSING,
    GateEngine,
    NO_EVIDENCE_SPAN,
    SCHEMA_INVALID,
)


def _now_tag() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_queries(path: Path) -> list[dict]:
    queries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            queries.append(json.loads(line))
    return queries


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


SUMMARY_FORBIDDEN = (
    "no summary available",
    "as an ai language model",
    "i cannot access",
)


def _summary_is_quality(summary: str | None) -> bool:
    text = str(summary or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if any(token in lowered for token in SUMMARY_FORBIDDEN):
        return False
    return True


def _manual_corrected_from_record(record: dict[str, Any]) -> bool:
    if bool(record.get("manual_corrected")):
        return True
    resolution = str(record.get("resolution") or "").upper()
    return resolution in {"MANUAL_FIX", "APPROVED_WITH_EDIT", "OVERRIDE", "REWRITE", "HUMAN_EDIT"}


def _manual_corrected_set(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    out: set[str] = set()
    for row in _load_jsonl(path):
        paper_id = str(row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        if _manual_corrected_from_record(row):
            out.add(paper_id)
    return out


def run_quality_eval(
    *,
    eval_jsonl: Path,
    pred_jsonl: Path,
    snapshots_dir: Path,
    run_id: str | None = None,
    manual_decisions_jsonl: Path | None = None,
) -> Path:
    eval_rows = _load_jsonl(eval_jsonl)
    pred_rows = _load_jsonl(pred_jsonl)

    pred_by_id: dict[str, dict[str, Any]] = {}
    for row in pred_rows:
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id:
            pred_by_id[paper_id] = row

    resolved_run_id = run_id or _now_tag()
    run_root = snapshots_dir / resolved_run_id
    run_root.mkdir(parents=True, exist_ok=True)

    manual_corrected_papers = _manual_corrected_set(manual_decisions_jsonl)
    gate_engine = GateEngine()

    total = len(eval_rows)
    schema_pass = 0
    evidence_pass = 0
    summary_pass = 0
    manual_corrected = 0
    missing_prediction = 0

    details_path = run_root / "detailed_results.jsonl"
    with details_path.open("w", encoding="utf-8") as f:
        for row in eval_rows:
            paper_id = str(row.get("paper_id") or "").strip()
            pred = pred_by_id.get(paper_id)
            reason_codes: list[str] = []

            if pred is None:
                missing_prediction += 1
                detail = {
                    "paper_id": paper_id,
                    "prediction_found": False,
                    "schema_valid": False,
                    "evidence_location_valid": False,
                    "summary_quality_valid": False,
                    "manual_corrected": paper_id in manual_corrected_papers,
                    "reason_codes": ["MISSING_PREDICTION"],
                }
                if detail["manual_corrected"]:
                    manual_corrected += 1
                f.write(json.dumps(detail, ensure_ascii=False) + "\n")
                continue

            pred_claimset = pred.get("claimset")
            if pred_claimset is None:
                pred_claimset = pred.get("teacher_output")
            if pred_claimset is None:
                pred_claimset = pred

            pred_summary = str(pred.get("summary") or "")
            if not pred_summary:
                prior = pred.get("prior_output")
                if isinstance(prior, dict):
                    pred_summary = str(prior.get("summary") or "")

            decision = gate_engine.evaluate(pred_claimset, summary_text=pred_summary)
            reason_codes = list(decision.reason_codes)

            schema_valid = SCHEMA_INVALID not in reason_codes
            evidence_valid = schema_valid and NO_EVIDENCE_SPAN not in reason_codes and EVIDENCE_LOCATION_MISSING not in reason_codes
            summary_valid = _summary_is_quality(pred_summary)
            manual_flag = (paper_id in manual_corrected_papers) or bool(row.get("manual_corrected"))

            if schema_valid:
                schema_pass += 1
            if evidence_valid:
                evidence_pass += 1
            if summary_valid:
                summary_pass += 1
            if manual_flag:
                manual_corrected += 1

            detail = {
                "paper_id": paper_id,
                "prediction_found": True,
                "schema_valid": schema_valid,
                "evidence_location_valid": evidence_valid,
                "summary_quality_valid": summary_valid,
                "manual_corrected": manual_flag,
                "reason_codes": reason_codes,
            }
            f.write(json.dumps(detail, ensure_ascii=False) + "\n")

    def _rate(value: int) -> float:
        return float(value) / float(total) if total else 0.0

    metrics = {
        "schema_version": "quality_eval.v1",
        "run_id": resolved_run_id,
        "mode": "quality",
        "total": total,
        "missing_prediction_count": missing_prediction,
        "schema_valid_count": schema_pass,
        "evidence_location_count": evidence_pass,
        "summary_quality_count": summary_pass,
        "manual_correction_count": manual_corrected,
        "schema_valid_rate": _rate(schema_pass),
        "evidence_location_rate": _rate(evidence_pass),
        "summary_artifact_rate": _rate(summary_pass),
        "manual_correction_rate": _rate(manual_corrected),
        "inputs": {
            "eval_jsonl": str(eval_jsonl),
            "pred_jsonl": str(pred_jsonl),
            "manual_decisions_jsonl": str(manual_decisions_jsonl) if manual_decisions_jsonl else None,
        },
    }
    _write_json(run_root / "metrics.json", metrics)
    _write_json(
        run_root / "summary.json",
        {
            "run_id": resolved_run_id,
            "status": "ok",
            "mode": "quality",
            "counts": {
                "eval_rows": total,
                "missing_prediction": missing_prediction,
            },
            "metrics_path": str(run_root / "metrics.json"),
            "details_path": str(details_path),
        },
    )
    return run_root


def _canonical_stage_payload(stage: str, document_id: str, local_path: str, file_hash: str) -> dict[str, Any]:
    # PR#1 baseline snapshot payload. Full pipeline outputs can be plugged in later.
    base = {
        "schema_version": "1.0",
        "stage": stage,
        "document_id": document_id,
        "source": {
            "local_path": local_path,
            "sha256": file_hash,
        },
        "status": "captured",
    }
    if stage == "ingest":
        base["output_keys"] = ["doc_id", "metadata", "sections", "tables"]
    elif stage == "reader":
        base["output_keys"] = ["doc_id", "claims"]
    elif stage == "index":
        base["output_keys"] = ["doc_id", "vector_store_id", "chunk_count", "chunks"]
    elif stage == "stats":
        base["output_keys"] = ["doc_id", "run_id", "checks", "schema_version"]
    return base


def run_eval(
    goldset_dir: Path,
    snapshots_dir: Path,
    run_id: str | None = None,
    allow_empty_docs: bool = False,
) -> Path:
    manifest_path = goldset_dir / "manifest.json"
    queries_path = goldset_dir / "queries.jsonl"

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest missing: {manifest_path}")
    if not queries_path.exists():
        raise FileNotFoundError(f"queries missing: {queries_path}")

    manifest = _load_manifest(manifest_path)
    queries = _load_queries(queries_path)
    documents = manifest.get("documents", [])

    if not allow_empty_docs and not documents:
        raise RuntimeError("manifest.documents is empty; fill local PDF entries or pass --allow-empty-docs")

    resolved_run_id = run_id or _now_tag()
    run_root = snapshots_dir / resolved_run_id
    ingest_dir = run_root / "ingest"
    reader_dir = run_root / "reader"
    index_dir = run_root / "index"
    stats_dir = run_root / "stats"
    query_dir = run_root / "queries"

    ingest_dir.mkdir(parents=True, exist_ok=True)
    reader_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    stats_dir.mkdir(parents=True, exist_ok=True)
    query_dir.mkdir(parents=True, exist_ok=True)

    missing_local_paths = []
    for doc in documents:
        local_path = doc.get("local_path")
        if local_path and not Path(local_path).exists():
            missing_local_paths.append({"document_id": doc.get("document_id"), "local_path": local_path})

    if missing_local_paths:
        _write_json(
            run_root / "summary.json",
            {
                "run_id": resolved_run_id,
                "status": "failed",
                "reason": "missing_local_paths",
                "missing_local_paths": missing_local_paths,
                "queries_count": len(queries),
            },
        )
        raise RuntimeError(f"missing local PDF paths: {len(missing_local_paths)}")

    stage_file_counts = {"ingest": 0, "reader": 0, "index": 0, "stats": 0}
    stage_output_keys = {}
    for doc in documents:
        document_id = str(doc.get("document_id") or "")
        local_path = str(doc.get("local_path") or "")
        if not document_id:
            raise RuntimeError("manifest document missing document_id")
        if not local_path:
            raise RuntimeError(f"manifest document {document_id} missing local_path")

        local_pdf = Path(local_path)
        source_sha256 = _sha256_file(local_pdf)
        file_basename = _safe_name(document_id)

        for stage, stage_dir in (
            ("ingest", ingest_dir),
            ("reader", reader_dir),
            ("index", index_dir),
            ("stats", stats_dir),
        ):
            payload = _canonical_stage_payload(stage, document_id, local_path, source_sha256)
            _write_json(stage_dir / f"{file_basename}.json", payload)
            stage_file_counts[stage] += 1
            stage_output_keys[stage] = payload.get("output_keys", [])

    for query in queries:
        query_id = str(query.get("query_id") or "")
        if not query_id:
            raise RuntimeError("queries.jsonl entry missing query_id")
        _write_json(
            query_dir / f"{_safe_name(query_id)}.json",
            {
                "query_id": query_id,
                "query": query.get("query"),
                "status": "captured",
                "schema_version": "1.0",
            },
        )

    _write_json(
        run_root / "summary.json",
        {
            "run_id": resolved_run_id,
            "status": "ok",
            "skeleton": False,
            "counts": {
                "queries": len(queries),
                "documents": len(documents),
                "ingest": stage_file_counts["ingest"],
                "reader": stage_file_counts["reader"],
                "index": stage_file_counts["index"],
                "stats": stage_file_counts["stats"],
            },
            "stage_output_keys": stage_output_keys,
        },
    )
    return run_root


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperPipe PR#1 eval harness snapshot runner")
    parser.add_argument(
        "--mode",
        default="snapshot",
        choices=["snapshot", "quality"],
        help="Evaluation mode. snapshot=existing harness, quality=metrics on eval/pred jsonl.",
    )
    parser.add_argument("--goldset-dir", default="goldset", help="Path to goldset directory")
    parser.add_argument("--snapshots-dir", default="snapshots", help="Path to snapshots root")
    parser.add_argument("--run-id", default=None, help="Optional fixed run id")
    parser.add_argument(
        "--allow-empty-docs",
        action="store_true",
        help="Allow empty document manifest for skeleton runs",
    )
    parser.add_argument("--eval-jsonl", default="", help="Quality mode: eval split JSONL path")
    parser.add_argument("--pred-jsonl", default="", help="Quality mode: prediction JSONL path")
    parser.add_argument(
        "--manual-decisions-jsonl",
        default="",
        help="Quality mode: optional human decision JSONL path for manual_correction_rate",
    )
    args = parser.parse_args()

    if args.mode == "quality":
        if not args.eval_jsonl or not args.pred_jsonl:
            raise SystemExit("--eval-jsonl and --pred-jsonl are required in --mode quality")
        manual_path = Path(args.manual_decisions_jsonl).expanduser() if args.manual_decisions_jsonl else None
        run_root = run_quality_eval(
            eval_jsonl=Path(args.eval_jsonl).expanduser(),
            pred_jsonl=Path(args.pred_jsonl).expanduser(),
            snapshots_dir=Path(args.snapshots_dir),
            run_id=args.run_id,
            manual_decisions_jsonl=manual_path,
        )
    else:
        run_root = run_eval(
            goldset_dir=Path(args.goldset_dir),
            snapshots_dir=Path(args.snapshots_dir),
            run_id=args.run_id,
            allow_empty_docs=args.allow_empty_docs,
        )
    print(f"[run_eval] snapshot created: {run_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

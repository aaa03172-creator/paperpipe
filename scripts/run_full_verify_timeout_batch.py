from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_summary(rows: List[Dict[str, Any]], timeout_sec: int) -> Dict[str, Any]:
    completed_like = [r for r in rows if r.get("status") in {"completed", "partial"}]
    pass_counter: Counter[str] = Counter()
    fail_tax_counter: Counter[str] = Counter()
    anchor_status_counter: Counter[str] = Counter()
    anchor_provider_counter: Counter[str] = Counter()
    reader_status_counter: Counter[str] = Counter()
    stats_status_counter: Counter[str] = Counter()

    total_checks = 0
    no_api_checks = 0
    no_table_data_checks = 0
    docid_doi_count = 0
    metadata_doi_count = 0

    for row in completed_like:
        pass_counter[str(row.get("table_pass") or "unknown")] += 1
        for code in row.get("table_failure_taxonomy") or []:
            fail_tax_counter[str(code)] += 1
        anchor_status_counter[str(row.get("anchor_api_status") or "unknown")] += 1
        anchor_provider_counter[str(row.get("anchor_api_provider") or "none")] += 1
        reader_status_counter[str(row.get("reader_status") or "unknown")] += 1
        stats_status_counter[str(row.get("stats_status") or "unknown")] += 1
        total_checks += int(row.get("checks") or 0)
        no_api_checks += int(row.get("no_api") or 0)
        no_table_data_checks += int(row.get("no_table_data_checks") or 0)
        if str(row.get("doc_id") or "").lower().startswith("doi:"):
            docid_doi_count += 1
        if row.get("metadata_doi"):
            metadata_doi_count += 1

    sample_size = len(rows)
    completed_count = len([r for r in rows if r.get("status") == "completed"])
    partial_count = len([r for r in rows if r.get("status") == "partial"])
    timeout_count = len([r for r in rows if r.get("status") == "timeout"])
    error_count = len([r for r in rows if r.get("status") == "error"])
    ingest_failed_count = len([r for r in rows if r.get("status") == "ingest_failed"])
    denominator = max(len(completed_like), 1)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": sample_size,
        "per_doc_timeout_sec": timeout_sec,
        "completed": completed_count,
        "partial": partial_count,
        "timeout": timeout_count,
        "error": error_count,
        "ingest_failed": ingest_failed_count,
        "pass_distribution": dict(pass_counter),
        "pass_ratio": {k: round(v / denominator, 4) for k, v in pass_counter.items()} if completed_like else {},
        "table_failure_taxonomy_counts": dict(fail_tax_counter),
        "reader_status_distribution": dict(reader_status_counter),
        "stats_status_distribution": dict(stats_status_counter),
        "total_checks": total_checks,
        "no_api_checks": no_api_checks,
        "no_api_ratio": round((no_api_checks / total_checks), 4) if total_checks else 0.0,
        "no_table_data_checks": no_table_data_checks,
        "no_table_data_ratio": round((no_table_data_checks / total_checks), 4) if total_checks else 0.0,
        "docid_doi_count": docid_doi_count,
        "docid_doi_ratio": round(docid_doi_count / denominator, 4) if completed_like else 0.0,
        "metadata_doi_count": metadata_doi_count,
        "metadata_doi_ratio": round(metadata_doi_count / denominator, 4) if completed_like else 0.0,
        "anchor_api_status_distribution": dict(anchor_status_counter),
        "anchor_api_provider_distribution": dict(anchor_provider_counter),
        "no_doi_docs": int(anchor_status_counter.get("no_doi", 0)),
        "no_doi_ratio": round(anchor_status_counter.get("no_doi", 0) / denominator, 4) if completed_like else 0.0,
    }


def _write_markdown(path: Path, summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    lines: List[str] = []
    lines.append("# Local Batch Validation Full (2026-03-06, sample=30)")
    lines.append("")
    lines.append("- Scope: ingest + reader + stats + anchor context (step-level timeout worker)")
    lines.append(f"- Sample size: {summary['sample_size']}")
    lines.append(f"- Per-doc timeout: {summary['per_doc_timeout_sec']}s")
    lines.append(f"- Completed: {summary['completed']}")
    lines.append(f"- Partial: {summary['partial']}")
    lines.append(f"- Timeout: {summary['timeout']}")
    lines.append(f"- Error: {summary['error']}")
    lines.append(f"- Ingest failed: {summary['ingest_failed']}")
    lines.append(f"- Total checks: {summary['total_checks']}")
    lines.append(f"- no_api ratio (completed+partial): {summary['no_api_ratio']:.2%}")
    lines.append(f"- no_table_data ratio (completed+partial): {summary['no_table_data_ratio']:.2%}")
    lines.append(f"- doc_id DOI ratio (completed+partial): {summary['docid_doi_ratio']:.2%}")
    lines.append(f"- anchor no_doi ratio (completed+partial): {summary['no_doi_ratio']:.2%}")
    lines.append("")
    lines.append("## Reader Status Distribution")
    for k, v in sorted(summary["reader_status_distribution"].items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Stats Status Distribution")
    for k, v in sorted(summary["stats_status_distribution"].items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Anchor API Status Distribution")
    for k, v in sorted(summary["anchor_api_status_distribution"].items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Table Failure Taxonomy Counts")
    for k, v in sorted(summary["table_failure_taxonomy_counts"].items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Per-Document")
    for row in rows:
        lines.append(
            "- {pdf}: status={status}, elapsed={elapsed_sec}s, reader={reader_status}, stats={stats_status}, checks={checks}, api={anchor_api_status}".format(
                pdf=row.get("pdf"),
                status=row.get("status"),
                elapsed_sec=row.get("elapsed_sec"),
                reader_status=row.get("reader_status"),
                stats_status=row.get("stats_status"),
                checks=row.get("checks"),
                anchor_api_status=row.get("anchor_api_status"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full verify batch with per-document subprocess timeout.")
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--per-doc-timeout-sec", type=int, default=80)
    parser.add_argument("--reader-timeout-sec", type=int, default=20)
    parser.add_argument("--stats-timeout-sec", type=int, default=25)
    parser.add_argument(
        "--output-json",
        default="docs/Local_Batch_Validation_2026-03-06_30_full_timeout.json",
    )
    parser.add_argument(
        "--output-md",
        default="docs/Local_Batch_Validation_2026-03-06_30_full_timeout.md",
    )
    args = parser.parse_args()

    config = load_config()
    pdfs = sorted(Path(config.paths.library_dir).glob("*.pdf"))[: int(args.sample_size)]
    rows: List[Dict[str, Any]] = []

    worker_script = Path("scripts/full_verify_worker.py").resolve()
    for idx, pdf in enumerate(pdfs, start=1):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            out_path = Path(tf.name)

        cmd = [
            "python3",
            str(worker_script),
            "--pdf",
            str(pdf.resolve()),
            "--output",
            str(out_path),
            "--reader-timeout-sec",
            str(int(args.reader_timeout_sec)),
            "--stats-timeout-sec",
            str(int(args.stats_timeout_sec)),
            "--skip-stats-when-no-claims",
        ]
        try:
            proc = subprocess.run(
                cmd,
                timeout=int(args.per_doc_timeout_sec),
                capture_output=True,
                text=True,
                check=False,
            )
            row = _safe_read_json(out_path)
            if not row:
                row = {
                    "pdf": pdf.name,
                    "status": "error",
                    "error": "worker_no_output",
                    "elapsed_sec": 0.0,
                }
            if proc.returncode != 0:
                row.setdefault("status", "error")
                row["status"] = "error"
                row["worker_returncode"] = proc.returncode
                stderr = (proc.stderr or "").strip()
                if stderr:
                    row["worker_stderr"] = stderr[-500:]
            rows.append(row)
            print(
                f"[{idx}/{len(pdfs)}] {pdf.name}: status={row.get('status')} "
                f"elapsed={row.get('elapsed_sec')}s reader={row.get('reader_status')} stats={row.get('stats_status')}"
            )
        except subprocess.TimeoutExpired:
            rows.append(
                {
                    "pdf": pdf.name,
                    "status": "timeout",
                    "elapsed_sec": int(args.per_doc_timeout_sec),
                }
            )
            print(f"[{idx}/{len(pdfs)}] {pdf.name}: timeout({args.per_doc_timeout_sec}s)")
        finally:
            try:
                out_path.unlink(missing_ok=True)
            except Exception:
                pass

    summary = _build_summary(rows, timeout_sec=int(args.per_doc_timeout_sec))
    payload = {"summary": summary, "rows": rows}
    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(out_md, summary=summary, rows=rows)
    print(f"WROTE_JSON {out_json}")
    print(f"WROTE_MD {out_md}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

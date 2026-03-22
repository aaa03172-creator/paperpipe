from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.timeout_policy import (
    BatchTimeoutPolicy,
    estimate_doc_timeout_seconds,
    next_retry_timeout_seconds,
)


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tail_text(path: Path, max_chars: int = 1000) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-max_chars:].strip()


def _terminate_process_group(proc: subprocess.Popen[str], grace_sec: int = 5) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=max(1, int(grace_sec)))
        return
    except subprocess.TimeoutExpired:
        pass

    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=max(1, int(grace_sec)))
    except subprocess.TimeoutExpired:
        pass


def _run_worker_with_timeout(cmd: List[str], timeout_sec: int) -> Tuple[int, bool, str]:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".log", delete=False) as lf:
        log_path = Path(lf.name)

    proc: subprocess.Popen[str] | None = None
    try:
        with log_path.open("a", encoding="utf-8") as log_fp:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fp,
                stderr=log_fp,
                start_new_session=True,
                text=True,
            )
            try:
                returncode = proc.wait(timeout=max(1, int(timeout_sec)))
                timed_out = False
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate_process_group(proc)
                returncode = int(proc.returncode if proc.returncode is not None else -9)
    finally:
        log_tail = _tail_text(log_path)
        try:
            log_path.unlink(missing_ok=True)
        except Exception:
            pass

    return int(returncode), bool(timed_out), log_tail


def _build_summary(rows: List[Dict[str, Any]], timeout_policy: BatchTimeoutPolicy, timeout_retry_limit: int) -> Dict[str, Any]:
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
    timeout_recovered_count = len([r for r in rows if bool(r.get("timeout_recovered"))])
    error_count = len([r for r in rows if r.get("status") == "error"])
    ingest_failed_count = len([r for r in rows if r.get("status") == "ingest_failed"])
    denominator = max(len(completed_like), 1)
    effective_doc_timeouts = [int(r.get("doc_timeout_sec") or timeout_policy.base_timeout_sec) for r in rows]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": sample_size,
        "per_doc_timeout_sec": int(timeout_policy.base_timeout_sec),
        "timeout_policy": {
            "strategy": str(timeout_policy.strategy),
            "base_timeout_sec": int(timeout_policy.base_timeout_sec),
            "min_timeout_sec": int(timeout_policy.min_timeout_sec),
            "max_timeout_sec": int(timeout_policy.max_timeout_sec),
            "size_weight_sec_per_mib": float(timeout_policy.size_weight_sec_per_mib),
            "size_floor_mib": float(timeout_policy.size_floor_mib),
            "page_weight_sec_per_page": float(timeout_policy.page_weight_sec_per_page),
        },
        "timeout_retry_limit": int(timeout_retry_limit),
        "completed": completed_count,
        "partial": partial_count,
        "timeout": timeout_count,
        "timeout_recovered": timeout_recovered_count,
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
        "effective_doc_timeout_min_sec": min(effective_doc_timeouts) if effective_doc_timeouts else int(timeout_policy.base_timeout_sec),
        "effective_doc_timeout_max_sec": max(effective_doc_timeouts) if effective_doc_timeouts else int(timeout_policy.base_timeout_sec),
    }


def _write_markdown(path: Path, summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    generated_at = str(summary.get("generated_at") or "")
    generated_date = generated_at.split("T")[0] if "T" in generated_at else (generated_at[:10] if generated_at else "unknown-date")
    lines: List[str] = []
    lines.append(f"# Local Batch Validation Full ({generated_date}, sample={summary['sample_size']})")
    lines.append("")
    lines.append("- Scope: ingest + reader + stats + anchor context (step-level timeout worker)")
    lines.append(f"- Sample size: {summary['sample_size']}")
    lines.append(f"- Per-doc timeout base: {summary['per_doc_timeout_sec']}s")
    timeout_policy = summary.get("timeout_policy") or {}
    lines.append(f"- Timeout policy: {timeout_policy.get('strategy', 'fixed')}")
    if "page_weight_sec_per_page" in timeout_policy:
        lines.append(f"- Timeout page weight: {timeout_policy.get('page_weight_sec_per_page')}s/page")
    lines.append(f"- Timeout retry limit: {summary.get('timeout_retry_limit', 0)}")
    lines.append(
        f"- Effective doc timeout range: {summary.get('effective_doc_timeout_min_sec', summary['per_doc_timeout_sec'])}"
        f"~{summary.get('effective_doc_timeout_max_sec', summary['per_doc_timeout_sec'])}s"
    )
    lines.append(f"- Completed: {summary['completed']}")
    lines.append(f"- Partial: {summary['partial']}")
    lines.append(f"- Timeout: {summary['timeout']}")
    lines.append(f"- Timeout recovered by retry: {summary.get('timeout_recovered', 0)}")
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
            "- {pdf}: status={status}, elapsed={elapsed_sec}s, doc_timeout={doc_timeout_sec}s, "
            "retries={timeout_retry_count}, reader={reader_status}, stats={stats_status}, checks={checks}, api={anchor_api_status}".format(
                pdf=row.get("pdf"),
                status=row.get("status"),
                elapsed_sec=row.get("elapsed_sec"),
                doc_timeout_sec=row.get("doc_timeout_sec"),
                timeout_retry_count=row.get("timeout_retry_count", 0),
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
    parser.add_argument("--timeout-policy", choices=("adaptive", "fixed"), default="adaptive")
    parser.add_argument("--per-doc-timeout-sec", type=int, default=180, help="Base timeout seconds (or fixed timeout in fixed mode)")
    parser.add_argument("--per-doc-timeout-min-sec", type=int, default=120, help="Adaptive mode minimum timeout seconds")
    parser.add_argument("--per-doc-timeout-max-sec", type=int, default=600, help="Adaptive mode maximum timeout seconds")
    parser.add_argument("--timeout-size-weight-sec-per-mib", type=float, default=35.0, help="Adaptive mode extra seconds per MiB")
    parser.add_argument("--timeout-size-floor-mib", type=float, default=0.5, help="Adaptive mode minimum size floor (MiB)")
    parser.add_argument("--timeout-page-weight-sec-per-page", type=float, default=10.0, help="Adaptive mode extra seconds per PDF page")
    parser.add_argument("--timeout-retry-limit", type=int, default=1, help="Retry count when subprocess timeout occurs")
    parser.add_argument("--timeout-retry-factor", type=float, default=1.75, help="Timeout multiplier for retry budget")
    parser.add_argument("--timeout-retry-min-bump-sec", type=int, default=60, help="Minimum timeout increase on retry")
    parser.add_argument("--reader-timeout-sec", type=int, default=30)
    parser.add_argument("--stats-timeout-sec", type=int, default=40)
    parser.add_argument("--adaptive-step-timeout", dest="adaptive_step_timeout", action="store_true")
    parser.add_argument("--no-adaptive-step-timeout", dest="adaptive_step_timeout", action="store_false")
    parser.set_defaults(adaptive_step_timeout=True)
    parser.add_argument(
        "--output-json",
        default="docs/reports/Local_Batch_Validation_2026-03-06_30_full_timeout.json",
    )
    parser.add_argument(
        "--output-md",
        default="docs/reports/Local_Batch_Validation_2026-03-06_30_full_timeout.md",
    )
    args = parser.parse_args()

    config = load_config()
    pdfs = sorted(Path(config.paths.library_dir).glob("*.pdf"))[: int(args.sample_size)]
    rows: List[Dict[str, Any]] = []
    timeout_min_sec = max(1, int(args.per_doc_timeout_min_sec))
    timeout_max_sec = max(timeout_min_sec, int(args.per_doc_timeout_max_sec))
    timeout_policy = BatchTimeoutPolicy(
        strategy=str(args.timeout_policy),
        base_timeout_sec=max(1, int(args.per_doc_timeout_sec)),
        min_timeout_sec=timeout_min_sec,
        max_timeout_sec=timeout_max_sec,
        size_weight_sec_per_mib=max(0.0, float(args.timeout_size_weight_sec_per_mib)),
        size_floor_mib=max(0.1, float(args.timeout_size_floor_mib)),
        page_weight_sec_per_page=max(0.0, float(args.timeout_page_weight_sec_per_page)),
    )
    timeout_retry_limit = max(0, int(args.timeout_retry_limit))

    worker_script = Path("scripts/full_verify_worker.py").resolve()
    for idx, pdf in enumerate(pdfs, start=1):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            out_path = Path(tf.name)

        doc_timeout_sec = estimate_doc_timeout_seconds(pdf.resolve(), timeout_policy)
        base_cmd = [
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
        if bool(args.adaptive_step_timeout):
            base_cmd.append("--adaptive-step-timeout")
        else:
            base_cmd.append("--no-adaptive-step-timeout")
        retry_count = 0
        row: Dict[str, Any]
        try:
            print(
                f"[{idx}/{len(pdfs)}] START {pdf.name}: timeout={doc_timeout_sec}s adaptive_step={bool(args.adaptive_step_timeout)}",
                flush=True,
            )
            while True:
                cmd = [*base_cmd, "--doc-timeout-sec", str(int(doc_timeout_sec))]
                worker_wait_timeout_sec = int(doc_timeout_sec) + 15
                returncode, timed_out, log_tail = _run_worker_with_timeout(cmd, worker_wait_timeout_sec)
                if timed_out:
                    if retry_count >= timeout_retry_limit:
                        row = {
                            "pdf": pdf.name,
                            "status": "timeout",
                            "elapsed_sec": int(doc_timeout_sec),
                            "doc_timeout_sec": int(doc_timeout_sec),
                            "timeout_retry_count": int(retry_count),
                            "timeout_recovered": False,
                        }
                        if log_tail:
                            row["worker_stderr"] = log_tail
                        print(
                            f"[{idx}/{len(pdfs)}] {pdf.name}: timeout({doc_timeout_sec}s) retries={retry_count}/{timeout_retry_limit}"
                        , flush=True)
                        break

                    next_timeout_sec = next_retry_timeout_seconds(
                        int(doc_timeout_sec),
                        retry_factor=float(args.timeout_retry_factor),
                        min_bump_sec=int(args.timeout_retry_min_bump_sec),
                        hard_cap_sec=timeout_max_sec,
                    )
                    retry_count += 1
                    print(
                        f"[{idx}/{len(pdfs)}] {pdf.name}: timeout({doc_timeout_sec}s) -> retry "
                        f"{retry_count}/{timeout_retry_limit} with {next_timeout_sec}s"
                    , flush=True)
                    doc_timeout_sec = next_timeout_sec
                    continue

                row = _safe_read_json(out_path)
                if not row:
                    row = {
                        "pdf": pdf.name,
                        "status": "error",
                        "error": "worker_no_output",
                        "elapsed_sec": 0.0,
                    }
                if returncode != 0:
                    row["worker_returncode"] = int(returncode)
                    if str(row.get("status") or "") != "timeout":
                        row.setdefault("status", "error")
                        row["status"] = "error"
                    if log_tail:
                        row["worker_stderr"] = log_tail

                row["doc_timeout_sec"] = int(doc_timeout_sec)
                row["timeout_retry_count"] = int(retry_count)
                row["timeout_recovered"] = bool(retry_count > 0 and row.get("status") in {"completed", "partial"})
                print(
                    f"[{idx}/{len(pdfs)}] {pdf.name}: status={row.get('status')} elapsed={row.get('elapsed_sec')}s "
                    f"timeout={doc_timeout_sec}s retries={retry_count} reader={row.get('reader_status')} stats={row.get('stats_status')}"
                , flush=True)
                break
            rows.append(row)
        finally:
            try:
                out_path.unlink(missing_ok=True)
            except Exception:
                pass

    summary = _build_summary(rows, timeout_policy=timeout_policy, timeout_retry_limit=timeout_retry_limit)
    payload = {"summary": summary, "rows": rows}
    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(out_md, summary=summary, rows=rows)
    print(f"WROTE_JSON {out_json}", flush=True)
    print(f"WROTE_MD {out_md}", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

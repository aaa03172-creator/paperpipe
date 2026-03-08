from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.ingest_agent import IngestAgent
from src.agents.reader_agent import ReaderAgent
from src.agents.stats_agent import StatsVerificationAgent
from src.config import load_config
from src.quality.claimset_policy import enforce_claimset_evidence_policy
from src.schemas.agent_artifacts import ClaimSet
from src.verify import resolve_anchor_api_context


class StepTimeoutError(TimeoutError):
    pass


@contextmanager
def _time_limit(seconds: int) -> Iterator[None]:
    if seconds <= 0:
        yield
        return

    def _raise_timeout(_signum: int, _frame: Any) -> None:
        raise StepTimeoutError(f"step_timeout:{seconds}s")

    prev_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)


def _row_base(pdf_path: Path) -> Dict[str, Any]:
    return {
        "pdf": pdf_path.name,
        "status": "completed",
        "elapsed_sec": 0.0,
        "doc_id": None,
        "metadata_doi": None,
        "resolved_doi": None,
        "table_count": 0,
        "table_pass": None,
        "table_failure_taxonomy": [],
        "fallback_pages": [],
        "checks": 0,
        "no_api": 0,
        "no_table_data_checks": 0,
        "anchor_api_provider": "none",
        "anchor_api_status": "not_run",
        "reader_status": "not_run",
        "stats_status": "not_run",
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full verify pipeline for one PDF with step-level timeouts.")
    parser.add_argument("--pdf", required=True, help="Absolute/relative PDF path")
    parser.add_argument("--output", required=True, help="Output JSON path for a single-row payload")
    parser.add_argument("--reader-timeout-sec", type=int, default=20)
    parser.add_argument("--stats-timeout-sec", type=int, default=25)
    parser.add_argument("--skip-stats-when-no-claims", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    pdf_path = Path(args.pdf)
    row = _row_base(pdf_path)
    try:
        config = load_config()
        ingest = IngestAgent(
            parser_backend=config.ingest.parser_backend,
            enable_ocr_fallback=config.ingest.enable_ocr_fallback,
            ocr_lang=config.ingest.ocr_lang,
            ocr_min_text_chars=config.ingest.ocr_min_text_chars,
            enable_table_pass2_ocr=config.ingest.enable_table_pass2_ocr,
            enable_cloud_table_fallback=config.ingest.enable_cloud_table_fallback,
            cloud_table_page_budget=config.ingest.cloud_table_page_budget,
            cloud_table_model=config.ingest.cloud_table_model,
            cloud_table_base_url=config.ingest.cloud_table_base_url,
            cloud_table_api_key=config.ingest.cloud_table_api_key,
            cloud_table_timeout_seconds=config.ingest.cloud_table_timeout_seconds,
        )
        reader = ReaderAgent(model_name=config.agents.main_model)
        stats = StatsVerificationAgent()

        doc = ingest.process_v2(str(pdf_path))
        if doc is None:
            row["status"] = "ingest_failed"
            row["elapsed_sec"] = round(time.perf_counter() - started, 3)
            _write_json(Path(args.output), row)
            return

        row["doc_id"] = doc.document_id
        row["metadata_doi"] = getattr(doc.meta, "doi", None)
        row["table_count"] = len(doc.tables)
        row["table_pass"] = str(ingest.last_table_extraction_meta.get("table_extraction_pass") or "")
        row["table_failure_taxonomy"] = list(ingest.last_table_extraction_meta.get("table_failure_taxonomy") or [])
        row["fallback_pages"] = list(ingest.last_table_extraction_meta.get("fallback_pages") or [])

        claim_set = ClaimSet(doc_id=doc.document_id, claims=[])
        try:
            with _time_limit(int(args.reader_timeout_sec)):
                analyzed = reader.analyze(doc)
                if analyzed is None:
                    analyzed = ClaimSet(doc_id=doc.document_id, claims=[])
                claim_set = enforce_claimset_evidence_policy(analyzed)
                row["reader_status"] = "ok"
        except StepTimeoutError as exc:
            row["reader_status"] = "timeout"
            row["reader_error"] = str(exc)
        except Exception as exc:
            row["reader_status"] = "error"
            row["reader_error"] = str(exc)

        report = None
        should_skip_stats = bool(args.skip_stats_when_no_claims and not claim_set.claims)
        if should_skip_stats:
            row["stats_status"] = "skipped_no_claims"
        else:
            try:
                with _time_limit(int(args.stats_timeout_sec)):
                    report = stats.run(job_id=f"worker-{pdf_path.stem}", doc=doc, claims=claim_set)
                row["stats_status"] = "ok"
            except StepTimeoutError as exc:
                row["stats_status"] = "timeout"
                row["stats_error"] = str(exc)
            except Exception as exc:
                row["stats_status"] = "error"
                row["stats_error"] = str(exc)

        if report is not None:
            checks = list(getattr(report, "checks", []) or [])
            row["checks"] = len(checks)
            row["no_api"] = sum(
                1
                for c in checks
                if str(getattr(getattr(c, "verdict", None), "value", getattr(c, "verdict", ""))).strip().lower()
                == "unverifiable"
            )
            row["no_table_data_checks"] = sum(1 for c in checks if str(getattr(c, "method", "") or "") == "no_table_data")
            anchor = resolve_anchor_api_context(
                getattr(report, "doc_id", None),
                doi_hint=getattr(doc.meta, "doi", None),
                source_ref=getattr(doc.meta, "source_ref", None),
                id_hint=f"file:{pdf_path.name}",
            )
        else:
            anchor = resolve_anchor_api_context(
                doc.document_id,
                doi_hint=getattr(doc.meta, "doi", None),
                source_ref=getattr(doc.meta, "source_ref", None),
                id_hint=f"file:{pdf_path.name}",
            )
            if row["stats_status"] in {"timeout", "error"}:
                row["status"] = "partial"

        row["anchor_api_provider"] = str(anchor.get("provider") or "none")
        row["anchor_api_status"] = str(anchor.get("status") or "unknown")
        row["resolved_doi"] = anchor.get("doi")
        row["elapsed_sec"] = round(time.perf_counter() - started, 3)
    except Exception as exc:
        row["status"] = "error"
        row["error"] = str(exc)
        row["elapsed_sec"] = round(time.perf_counter() - started, 3)

    _write_json(Path(args.output), row)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.services.runtime_paths import artifacts_root as default_artifacts_root
from src.services.runtime_paths import state_db_path as default_state_db_path


SUMMARY_FORBIDDEN_PHRASES = (
    "no summary available",
    "as an ai language model",
    "i cannot access",
    "i apologize, but",
)


@dataclass
class Candidate:
    paper_id: str
    paper_row: dict[str, Any]
    reason_codes: set[str] = field(default_factory=set)
    reason_details: list[str] = field(default_factory=list)

    def add_reason(self, code: str, detail: str | None = None) -> None:
        self.reason_codes.add(code)
        if detail:
            self.reason_details.append(detail)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "paper"


def _git_commit() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
        )
    except Exception:
        return "unknown"


def _is_test_fixture_record(paper_id: str, pdf_path: str | None) -> bool:
    pid = str(paper_id or "")
    path = str(pdf_path or "").replace("\\", "/")
    return (
        "_test_" in pid
        or pid.startswith("integration_test_")
        or pid == "phase0_test"
        or "/tests/" in path
    )


def _parse_json_like(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None
    return None


def _has_valid_claimset(feedback_json: Any) -> bool:
    parsed = _parse_json_like(feedback_json)
    if not isinstance(parsed, dict):
        return False
    claims = parsed.get("claims")
    if isinstance(claims, list):
        return True
    nested = parsed.get("ClaimSet")
    if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
        return True
    nested = parsed.get("claimset")
    if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
        return True
    return False


def _summary_has_artifact(summary: str | None) -> bool:
    value = str(summary or "").strip().lower()
    if not value:
        return True
    return any(token in value for token in SUMMARY_FORBIDDEN_PHRASES)


def _latest_artifact_run_dir(artifacts_root: Path, paper_id: str) -> Path | None:
    paper_dir = artifacts_root / paper_id
    if not paper_dir.exists() or not paper_dir.is_dir():
        return None
    run_dirs = [p for p in paper_dir.iterdir() if p.is_dir()]
    if not run_dirs:
        return None
    run_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return run_dirs[0]


def _load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_input_chunks(run_dir: Path | None) -> list[dict[str, Any]]:
    if not run_dir:
        return []
    index_path = run_dir / "index_artifact.json"
    index_payload = _load_json_file(index_path) if index_path.exists() else None
    if isinstance(index_payload, dict) and isinstance(index_payload.get("chunks"), list):
        chunks: list[dict[str, Any]] = []
        for idx, chunk in enumerate(index_payload["chunks"]):
            if not isinstance(chunk, dict):
                continue
            chunks.append(
                {
                    "chunk_id": chunk.get("chunk_id") or f"chunk-{idx}",
                    "text": chunk.get("text") or "",
                    "section_name": chunk.get("section_name") or "unknown",
                }
            )
        if chunks:
            return chunks

    doc_path = run_dir / "document_artifact.json"
    doc_payload = _load_json_file(doc_path) if doc_path.exists() else None
    if not isinstance(doc_payload, dict):
        return []

    sections = doc_payload.get("sections")
    if isinstance(sections, list):
        chunks = []
        for idx, sec in enumerate(sections):
            if not isinstance(sec, dict):
                continue
            chunks.append(
                {
                    "chunk_id": f"section-{idx}",
                    "text": sec.get("text") or "",
                    "section_name": sec.get("name") or "unknown",
                }
            )
        if chunks:
            return chunks

    pages = doc_payload.get("pages")
    if isinstance(pages, list):
        chunks = []
        for pidx, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            page_index = page.get("page_index", pidx)
            blocks = page.get("blocks")
            if not isinstance(blocks, list):
                continue
            for bidx, block in enumerate(blocks):
                if not isinstance(block, dict):
                    continue
                lines = block.get("lines")
                if not isinstance(lines, list):
                    continue
                texts: list[str] = []
                for line in lines:
                    if isinstance(line, dict):
                        t = str(line.get("text") or "").strip()
                        if t:
                            texts.append(t)
                if not texts:
                    continue
                chunks.append(
                    {
                        "chunk_id": f"p{page_index}-b{bidx}",
                        "text": " ".join(texts),
                        "section_name": f"page_{page_index}",
                    }
                )
        return chunks
    return []


def _load_tables(run_dir: Path | None) -> list[dict[str, Any]]:
    if not run_dir:
        return []
    doc_path = run_dir / "document_artifact.json"
    doc_payload = _load_json_file(doc_path) if doc_path.exists() else None
    if not isinstance(doc_payload, dict):
        return []
    tables = doc_payload.get("tables")
    if isinstance(tables, list):
        return [t for t in tables if isinstance(t, dict)]
    return []


def _load_prior_output(paper_row: dict[str, Any], run_dir: Path | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "summary": paper_row.get("summary"),
        "confidence": paper_row.get("confidence"),
        "status": paper_row.get("status"),
        "feedback_json": _parse_json_like(paper_row.get("feedback_json")) or paper_row.get("feedback_json"),
    }
    if run_dir:
        claimset_path = run_dir / "claimset.json"
        stats_path = run_dir / "stats_report.json"
        if claimset_path.exists():
            payload["claimset_json"] = _load_json_file(claimset_path)
        if stats_path.exists():
            payload["stats_report_json"] = _load_json_file(stats_path)
    return payload


def discover_candidates(
    conn: sqlite3.Connection,
    *,
    artifacts_root: Path,
    low_confidence_threshold: float,
    include_test_fixtures: bool,
    limit: int,
    paper_id_filter: set[str] | None = None,
) -> list[Candidate]:
    conn.row_factory = sqlite3.Row
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    if "paper_id" not in cols:
        raise RuntimeError("papers table missing required column: paper_id")

    select_cols = ["paper_id"]
    for col in ("status", "confidence", "summary", "feedback_json", "prompt_version", "updated_at", "pdf_path"):
        if col in cols:
            select_cols.append(col)
    if "model_used" in cols:
        select_cols.append("model_used")
    elif "agent_version" in cols:
        select_cols.append("agent_version")
    if "created_at" in cols:
        select_cols.append("created_at")
    if "updated_at" in cols and "created_at" in cols:
        order_by = "COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) ASC"
    elif "updated_at" in cols:
        order_by = "updated_at ASC"
    elif "created_at" in cols:
        order_by = "created_at ASC"
    else:
        order_by = "paper_id ASC"
    papers = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT {", ".join(select_cols)}
            FROM papers
            ORDER BY {order_by}
            """
        ).fetchall()
    ]

    cands: dict[str, Candidate] = {}

    def ensure(pid: str, row: dict[str, Any] | None = None) -> Candidate:
        if pid in cands:
            return cands[pid]
        paper_row = row or {"paper_id": pid}
        cands[pid] = Candidate(paper_id=pid, paper_row=paper_row)
        return cands[pid]

    for row in papers:
        pid = str(row.get("paper_id") or "").strip()
        if not pid:
            continue
        if paper_id_filter is not None and pid not in paper_id_filter:
            continue
        if not include_test_fixtures and _is_test_fixture_record(pid, row.get("pdf_path")):
            continue
        candidate = ensure(pid, row=row)

        confidence = row.get("confidence")
        try:
            conf_val = float(confidence) if confidence is not None else None
        except Exception:
            conf_val = None
        if conf_val is not None and conf_val < low_confidence_threshold:
            candidate.add_reason("LOW_CONFIDENCE", f"confidence={conf_val}")

        if _summary_has_artifact(row.get("summary")):
            candidate.add_reason("SUMMARY_ARTIFACT", "summary has placeholder/artifact pattern")

        if not _has_valid_claimset(row.get("feedback_json")):
            run_dir = _latest_artifact_run_dir(artifacts_root, pid)
            claimset_artifact_ok = False
            if run_dir:
                claimset_payload = _load_json_file(run_dir / "claimset.json")
                claimset_artifact_ok = isinstance(claimset_payload, dict) and isinstance(claimset_payload.get("claims"), list)
            if not claimset_artifact_ok:
                candidate.add_reason("CLAIMSET_MISSING_OR_INVALID", "feedback_json/artifacts missing valid claimset")

    # review_queue unresolved
    try:
        rows = conn.execute(
            """
            SELECT paper_id, decision, reason
            FROM review_queue
            WHERE resolved_at IS NULL
            """
        ).fetchall()
        for row in rows:
            pid = str(row[0] or "").strip()
            if not pid:
                continue
            if paper_id_filter is not None and pid not in paper_id_filter:
                continue
            candidate = ensure(pid)
            candidate.add_reason("REVIEW_QUEUE_OPEN", f"decision={row[1]} reason={row[2]}")
    except sqlite3.OperationalError:
        pass

    # failed jobs
    try:
        rows = conn.execute(
            """
            SELECT paper_id, COUNT(*) AS failed_count
            FROM jobs
            WHERE status = 'failed'
            GROUP BY paper_id
            """
        ).fetchall()
        for row in rows:
            pid = str(row[0] or "").strip()
            if not pid:
                continue
            if paper_id_filter is not None and pid not in paper_id_filter:
                continue
            candidate = ensure(pid)
            candidate.add_reason("JOB_FAILED", f"failed_count={row[1]}")
    except sqlite3.OperationalError:
        pass

    out = [c for c in cands.values() if c.reason_codes]
    out.sort(key=lambda c: (-len(c.reason_codes), c.paper_id))
    if limit > 0:
        out = out[:limit]
    return out


def extract_teacher_candidates(
    *,
    db_path: Path,
    artifacts_root: Path,
    extraction_run_id: str,
    low_confidence_threshold: float = 0.7,
    include_test_fixtures: bool = False,
    limit: int = 100,
    paper_id_filter: set[str] | None = None,
) -> list[Path]:
    if not db_path.exists():
        raise FileNotFoundError(f"db_not_found={db_path}")
    artifacts_root.mkdir(parents=True, exist_ok=True)

    try:
        cfg = load_config()
        model_name = str(getattr(getattr(cfg, "agents", None), "main_model", "unknown") or "unknown")
    except Exception:
        model_name = "unknown"
    git_commit = _git_commit()

    conn = sqlite3.connect(db_path)
    try:
        candidates = discover_candidates(
            conn,
            artifacts_root=artifacts_root,
            low_confidence_threshold=low_confidence_threshold,
            include_test_fixtures=include_test_fixtures,
            limit=limit,
            paper_id_filter=paper_id_filter,
        )
    finally:
        conn.close()

    output_roots: list[Path] = []
    teacher_root = artifacts_root / extraction_run_id / "teacher"

    for cand in candidates:
        pid = cand.paper_id
        safe_pid = _safe_name(pid)
        bundle_dir = teacher_root / safe_pid
        bundle_dir.mkdir(parents=True, exist_ok=True)

        run_dir = _latest_artifact_run_dir(artifacts_root, pid)
        chunks = _load_input_chunks(run_dir)
        tables = _load_tables(run_dir)
        prior_output = _load_prior_output(cand.paper_row, run_dir)

        chunks_path = bundle_dir / "input_chunks.jsonl"
        with chunks_path.open("w", encoding="utf-8") as f:
            for item in chunks:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        tables_path = bundle_dir / "tables.json"
        tables_path.write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")

        prior_path = bundle_dir / "prior_output.json"
        prior_path.write_text(json.dumps(prior_output, ensure_ascii=False, indent=2), encoding="utf-8")

        manifest = {
            "schema_version": "teacher_bundle.v1",
            "paper_id": pid,
            "bundle_id": f"{extraction_run_id}:{safe_pid}",
            "created_at": _utc_now_iso(),
            "git_commit": git_commit,
            "model": model_name,
            "prompt_version": cand.paper_row.get("prompt_version"),
            "candidate_reason_codes": sorted(cand.reason_codes),
            "candidate_reason_details": cand.reason_details,
            "source": {
                "db_path": str(db_path),
                "artifacts_root": str(artifacts_root),
                "latest_artifact_run_dir": str(run_dir) if run_dir else None,
            },
            "inputs": {
                "chunks_file": "input_chunks.jsonl",
                "chunks_count": len(chunks),
                "tables_file": "tables.json",
                "tables_count": len(tables),
                "prior_output_file": "prior_output.json",
            },
        }
        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        output_roots.append(bundle_dir)

    return output_roots


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract teacher-candidate bundles from PaperPipe runtime state.")
    parser.add_argument("--db", default=str(default_state_db_path()), help="Path to state.db")
    parser.add_argument("--artifacts-root", default=str(default_artifacts_root()), help="Artifacts root directory")
    parser.add_argument("--run-id", default="", help="Extraction run id (default: timestamp)")
    parser.add_argument("--limit", type=int, default=100, help="Max candidate papers to bundle")
    parser.add_argument("--low-confidence-threshold", type=float, default=0.7, help="Low confidence cutoff")
    parser.add_argument("--include-test-fixtures", action="store_true", help="Include test fixture records")
    parser.add_argument("--paper-id", action="append", dest="paper_ids", help="Optional target paper_id (repeatable)")
    args = parser.parse_args()

    run_id = args.run_id.strip() or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    paper_filter = {p.strip() for p in (args.paper_ids or []) if p.strip()} or None
    bundles = extract_teacher_candidates(
        db_path=Path(args.db).expanduser().resolve(),
        artifacts_root=Path(args.artifacts_root).expanduser().resolve(),
        extraction_run_id=run_id,
        low_confidence_threshold=args.low_confidence_threshold,
        include_test_fixtures=bool(args.include_test_fixtures),
        limit=max(0, args.limit),
        paper_id_filter=paper_filter,
    )
    print(f"[teacher-extract] run_id={run_id}")
    print(f"[teacher-extract] bundles={len(bundles)}")
    for path in bundles[:20]:
        print(f"  - {path}")
    if len(bundles) > 20:
        print(f"  ... and {len(bundles) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

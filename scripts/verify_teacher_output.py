from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.quality.gates import GateEngine
from src.quality.gates import TEACHER_REVIEW_FRAGMENTARY_CLAIM, TEACHER_REVIEW_MISALIGNED_QUOTE
from src.schemas.teacher_review_eval import TeacherReviewEvalSidecar
from src.services.runtime_paths import goldset_root as default_goldset_root


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "paper"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_prior_summary(bundle_dir: Path) -> str:
    prior_path = bundle_dir / "prior_output.json"
    if not prior_path.exists():
        return ""
    try:
        payload = json.loads(prior_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if isinstance(payload, dict):
        return str(payload.get("summary") or "")
    return ""


def _load_teacher_review_eval(bundle_dir: Path) -> tuple[Path | None, TeacherReviewEvalSidecar | None, str | None]:
    path = bundle_dir / "teacher_review_eval.json"
    if not path.exists():
        return None, None, None
    try:
        payload = _load_json(path)
        return path, TeacherReviewEvalSidecar.model_validate(payload), None
    except Exception as exc:
        return path, None, str(exc)


def _teacher_review_eval_guardrail(sidecar: TeacherReviewEvalSidecar) -> tuple[list[str], list[dict[str, str]], list[str]]:
    reason_codes: set[str] = set()
    findings: list[dict[str, str]] = []
    blocking_labels: list[str] = []

    for claim in sidecar.claims:
        if not claim.reviewed:
            continue
        if claim.anchor_quality_label == "FRAGMENTARY_CLAIM":
            reason_codes.add(TEACHER_REVIEW_FRAGMENTARY_CLAIM)
            blocking_labels.append("FRAGMENTARY_CLAIM")
            findings.append(
                {
                    "gate": "TeacherReviewEvalGate",
                    "reason_code": TEACHER_REVIEW_FRAGMENTARY_CLAIM,
                    "detail": f"claim_id={claim.claim_id} flagged as fragmentary by teacher_review_eval",
                }
            )
        elif claim.anchor_quality_label == "MISALIGNED_QUOTE":
            reason_codes.add(TEACHER_REVIEW_MISALIGNED_QUOTE)
            blocking_labels.append("MISALIGNED_QUOTE")
            findings.append(
                {
                    "gate": "TeacherReviewEvalGate",
                    "reason_code": TEACHER_REVIEW_MISALIGNED_QUOTE,
                    "detail": f"claim_id={claim.claim_id} flagged as misaligned quote by teacher_review_eval",
                }
            )

    return sorted(reason_codes), findings, sorted(set(blocking_labels))


def verify_and_route(
    *,
    bundle_dir: Path,
    teacher_output_path: Path,
    goldset_root: Path,
) -> tuple[Path, dict]:
    manifest = _load_json(bundle_dir / "manifest.json")
    teacher_output = _load_json(teacher_output_path)
    prior_summary = _load_prior_summary(bundle_dir)

    paper_id = str(manifest.get("paper_id") or "").strip()
    if not paper_id:
        raise RuntimeError(f"manifest missing paper_id: {bundle_dir / 'manifest.json'}")

    engine = GateEngine()
    decision = engine.evaluate(teacher_output, summary_text=prior_summary)
    reason_codes = set(decision.reason_codes)
    findings = [
        {"gate": f.gate, "reason_code": f.reason_code, "detail": f.detail}
        for f in decision.findings
    ]
    metrics = dict(decision.metrics)

    teacher_review_eval_path, teacher_review_eval, teacher_review_eval_error = _load_teacher_review_eval(bundle_dir)
    blocking_anchor_quality_labels: list[str] = []
    if teacher_review_eval is not None:
        extra_reason_codes, extra_findings, blocking_anchor_quality_labels = _teacher_review_eval_guardrail(
            teacher_review_eval
        )
        reason_codes.update(extra_reason_codes)
        findings.extend(extra_findings)
        metrics["teacher_review_eval_reviewed_claim_count"] = teacher_review_eval.metrics.reviewed_claim_count
        metrics["teacher_review_eval_blocking_label_count"] = len(blocking_anchor_quality_labels)

    accepted = len(reason_codes) == 0

    record = {
        "schema_version": "teacher_verification.v1",
        "paper_id": paper_id,
        "bundle_dir": str(bundle_dir),
        "teacher_output_path": str(teacher_output_path),
        "evaluated_at": _utc_now_iso(),
        "accepted": accepted,
        "reason_codes": sorted(reason_codes),
        "findings": findings,
        "metrics": metrics,
        "manifest": manifest,
        "teacher_output": teacher_output,
    }
    if teacher_review_eval_path is not None:
        record["teacher_review_eval_path"] = str(teacher_review_eval_path)
    if teacher_review_eval_error:
        record["teacher_review_eval_error"] = teacher_review_eval_error
    if teacher_review_eval is not None:
        record["teacher_review_eval_summary"] = {
            "bundle_outcome": teacher_review_eval.bundle_outcome,
            "issue_patterns": teacher_review_eval.issue_patterns,
            "blocking_anchor_quality_labels": blocking_anchor_quality_labels,
        }

    target_dir = goldset_root / ("accepted" if accepted else "quarantine")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{_safe_name(paper_id)}.json"
    target_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path, record


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify teacher output with quality gates and route to accepted/quarantine.")
    parser.add_argument("--bundle-dir", required=True, help="Path to one teacher bundle directory")
    parser.add_argument("--teacher-output", required=True, help="Path to teacher output JSON file")
    parser.add_argument(
        "--goldset-root",
        default=str(default_goldset_root()),
        help="Goldset root directory (default: $PAPERPIPE_GOLDSET_DIR or ./goldset)",
    )
    args = parser.parse_args()

    out_path, record = verify_and_route(
        bundle_dir=Path(args.bundle_dir).expanduser().resolve(),
        teacher_output_path=Path(args.teacher_output).expanduser().resolve(),
        goldset_root=Path(args.goldset_root).expanduser().resolve(),
    )
    print(f"[teacher-verify] accepted={record['accepted']}")
    print(f"[teacher-verify] reason_codes={record['reason_codes']}")
    print(f"[teacher-verify] output={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

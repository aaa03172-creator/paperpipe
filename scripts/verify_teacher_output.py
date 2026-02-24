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
    accepted = decision.passed

    record = {
        "schema_version": "teacher_verification.v1",
        "paper_id": paper_id,
        "bundle_dir": str(bundle_dir),
        "teacher_output_path": str(teacher_output_path),
        "evaluated_at": _utc_now_iso(),
        "accepted": accepted,
        "reason_codes": decision.reason_codes,
        "findings": [
            {"gate": f.gate, "reason_code": f.reason_code, "detail": f.detail}
            for f in decision.findings
        ],
        "metrics": decision.metrics,
        "manifest": manifest,
        "teacher_output": teacher_output,
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

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import load_config
from src.llm_provider import get_llm_provider


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "escalation_judge_case" / "cases.json"


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"Fixture missing cases list: {path}")
    out: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        paper = case.get("paper")
        if not isinstance(paper, dict):
            continue
        out.append(case)
    if not out:
        raise ValueError(f"Fixture has no usable cases: {path}")
    return out


def _result_model_name(provider: Any) -> str | None:
    getter = getattr(provider, "_get_model", None)
    if callable(getter):
        try:
            return str(getter("escalation"))
        except Exception:
            return None
    return None


def _evaluate_case(provider: Any, case: dict[str, Any]) -> dict[str, Any]:
    paper = dict(case["paper"])
    raw = provider.evaluate_escalation(paper)
    approved = raw.get("approved")
    reason = str(raw.get("reason") or "").strip()
    valid = isinstance(approved, bool) and bool(reason)
    expected = bool(case.get("expected_approved"))
    matched = bool(valid and approved == expected)
    return {
        "case_id": str(case.get("case_id") or ""),
        "expected_approved": expected,
        "approved": approved if isinstance(approved, bool) else None,
        "matched": matched,
        "valid_output": valid,
        "reason": reason,
    }


def _summarize(results: list[dict[str, Any]], *, model_name: str | None) -> dict[str, Any]:
    total = len(results)
    invalid = [item for item in results if not item.get("valid_output")]
    mismatches = [item for item in results if item.get("valid_output") and not item.get("matched")]
    approvals = [item for item in results if item.get("approved") is True]
    return {
        "schema_version": "escalation_judge_smoke_result.v1",
        "model": model_name,
        "total_cases": total,
        "valid_output_count": total - len(invalid),
        "invalid_output_count": len(invalid),
        "match_count": total - len(invalid) - len(mismatches),
        "mismatch_count": len(mismatches),
        "approved_count": len(approvals),
        "results": results,
    }


def run_smoke(*, config_path: Path, fixture_path: Path, max_mismatches: int) -> tuple[int, dict[str, Any]]:
    cfg = load_config(str(config_path))
    provider = get_llm_provider(cfg.llm, cfg.entity_aliases)
    if provider is None:
        raise RuntimeError("LLM provider could not be initialized from config")
    if not provider.is_available():
        raise RuntimeError("LLM provider is unavailable")

    cases = _load_fixture(fixture_path)
    results = [_evaluate_case(provider, case) for case in cases]
    summary = _summarize(results, model_name=_result_model_name(provider))
    failed = summary["invalid_output_count"] > 0 or summary["mismatch_count"] > max_mismatches
    return (1 if failed else 0), summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded smoke check for the escalation judge model.")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--max-mismatches", type=int, default=1)
    args = parser.parse_args()

    code, summary = run_smoke(
        config_path=args.config.expanduser().resolve(),
        fixture_path=args.fixture.expanduser().resolve(),
        max_mismatches=int(args.max_mismatches),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

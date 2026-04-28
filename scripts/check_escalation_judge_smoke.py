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


def _is_valid_judge_reason(reason: str) -> bool:
    text = str(reason or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith("judge error"):
        return False
    if "ai error" in lowered:
        return False
    return True


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
    in_scope_raw = raw.get("in_biomedical_scope")
    final_route = str(raw.get("final_route") or "").strip() or None
    raw_reason_codes = raw.get("reason_codes")
    if isinstance(raw_reason_codes, list):
        reason_codes = [str(code).strip() for code in raw_reason_codes if str(code).strip()]
    else:
        reason_codes = []
    valid = isinstance(approved, bool) and _is_valid_judge_reason(reason)
    expected = bool(case.get("expected_approved"))
    matched = bool(valid and approved == expected)
    return {
        "case_id": str(case.get("case_id") or ""),
        "expected_approved": expected,
        "approved": approved if isinstance(approved, bool) else None,
        "matched": matched,
        "valid_output": valid,
        "reason": reason,
        "in_biomedical_scope": in_scope_raw if isinstance(in_scope_raw, bool) else None,
        "final_route": final_route,
        "reason_codes": reason_codes,
    }


def _summarize(results: list[dict[str, Any]], *, model_name: str | None) -> dict[str, Any]:
    total = len(results)
    invalid = [item for item in results if not item.get("valid_output")]
    mismatches = [item for item in results if item.get("valid_output") and not item.get("matched")]
    approvals = [item for item in results if item.get("approved") is True]
    route_counts: dict[str, int] = {}
    reason_code_counts: dict[str, int] = {}
    in_scope_true = 0
    in_scope_false = 0

    for item in results:
        route = item.get("final_route")
        if isinstance(route, str) and route:
            route_counts[route] = route_counts.get(route, 0) + 1

        in_scope = item.get("in_biomedical_scope")
        if in_scope is True:
            in_scope_true += 1
        elif in_scope is False:
            in_scope_false += 1

        for code in item.get("reason_codes") or []:
            reason_code_counts[code] = reason_code_counts.get(code, 0) + 1

    top_reason_codes = [
        code for code, _ in sorted(reason_code_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    ]

    return {
        "schema_version": "escalation_judge_smoke_result.v1",
        "model": model_name,
        "total_cases": total,
        "valid_output_count": total - len(invalid),
        "invalid_output_count": len(invalid),
        "match_count": total - len(invalid) - len(mismatches),
        "mismatch_count": len(mismatches),
        "approved_count": len(approvals),
        "route_counts": route_counts,
        "biomedical_scope_counts": {
            "in_scope": in_scope_true,
            "out_of_scope": in_scope_false,
        },
        "top_reason_codes": top_reason_codes,
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

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.reader_agent import ReaderAgent
from src.contracts.artifact_views import get_artifact_header
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.quality.claimset_policy import enforce_claimset_evidence_policy
from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim

ARTIFACTS_ROOT = ROOT / "storage" / "artifacts"
ATTEMPT_LABELS = ["primary", "focused", "sentence_focus"]
POLICIES: dict[str, list[str]] = {
    "current": ["primary", "focused", "sentence_focus"],
    "focused_first": ["focused", "primary", "sentence_focus"],
}


@dataclass
class AttemptResult:
    label: str
    elapsed_seconds: float
    context_chars: int
    estimated_prompt_tokens: int | None
    estimated_response_tokens: int | None
    included_chunk_count: int | None
    unique_section_count: int | None
    sentence_focus_count: int | None
    parsed_claim_count: int
    status: str
    provider_status: str | None
    provider_request_wall_seconds: float | None
    provider_done_reason: str | None
    provider_prompt_eval_count: int | None
    provider_eval_count: int | None
    provider_total_duration_seconds: float | None
    provider_error_type: str | None


@dataclass
class PolicyResult:
    name: str
    attempts: list[AttemptResult]
    selected_attempt_label: str | None
    selected_claim_count: int
    total_elapsed_seconds: float
    total_prompt_tokens: int
    total_response_tokens: int
    repeat_index: int = 1
    warmup_prompt: str | None = None
    warmup_elapsed_seconds: float | None = None
    warmup_status: str | None = None
    warmup_request_wall_seconds: float | None = None
    warmup_eval_count: int | None = None
    warmup_error_type: str | None = None


def _find_run_root(run_id: str, paper_id: str | None = None) -> Path:
    if paper_id:
        candidate = ARTIFACTS_ROOT / paper_id / run_id
        if not candidate.exists():
            raise FileNotFoundError(f"run root not found for paper_id={paper_id} run_id={run_id}")
        return candidate

    matches = sorted(ARTIFACTS_ROOT.glob(f"*/{run_id}"))
    if not matches:
        raise FileNotFoundError(f"run root not found for {run_id}")
    if len(matches) > 1:
        joined = ", ".join(str(match.parent.name) for match in matches[:5])
        raise ValueError(
            f"run_id={run_id} is ambiguous across multiple paper ids; pass --paper-id. Matches include: {joined}"
        )
    return matches[0]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object payload in {path}")
    return payload


def _example_claimset_json() -> str:
    example_claim = ScientificClaim(
        claim_id="CLM-001",
        type="efficacy",
        statement="Caffeine increases coding speed by 20%.",
        evidence_spans=[
            EvidenceSpan(
                page=2,
                chunk_id="p03_c01",
                raw_text="Speed increased by 20% compared to placebo...",
                quote="Speed increased by 20%",
                rationale="The results section explicitly states the percentage increase derived from the t-test.",
                section="page_3",
                source_span=[0, 26],
            )
        ],
        limitations=[],
        confidence=0.9,
    )
    example_set = ClaimSet(doc_id="doi:10.1234/ex", claims=[example_claim])
    return example_set.model_dump_json(indent=2)


def _provider_meta(reader: ReaderAgent) -> dict[str, Any]:
    meta = getattr(reader.adapter, "last_request_meta", None)
    return dict(meta) if isinstance(meta, dict) else {}


def _selected_attempt(result: PolicyResult) -> AttemptResult | None:
    if result.selected_attempt_label:
        for attempt in result.attempts:
            if attempt.label == result.selected_attempt_label:
                return attempt
    return result.attempts[-1] if result.attempts else None


def _group_policy_results(results: list[PolicyResult]) -> dict[str, list[PolicyResult]]:
    grouped: dict[str, list[PolicyResult]] = {}
    for result in results:
        grouped.setdefault(result.name, []).append(result)
    for values in grouped.values():
        values.sort(key=lambda result: result.repeat_index)
    return grouped


def _run_warmup(*, reader: ReaderAgent, warmup_prompt: str | None) -> dict[str, Any]:
    prompt = str(warmup_prompt or "").strip()
    if not prompt:
        return {}

    started = time.perf_counter()
    error_type: str | None = None
    try:
        reader.adapter.generate(prompt)
    except Exception as exc:
        error_type = type(exc).__name__
    elapsed = round(time.perf_counter() - started, 3)
    meta = _provider_meta(reader)
    return {
        "prompt": prompt,
        "elapsed_seconds": elapsed,
        "status": str(meta.get("status") or "") or ("error" if error_type else None),
        "request_wall_seconds": round(float(meta["request_wall_seconds"]), 3) if meta.get("request_wall_seconds") is not None else None,
        "eval_count": int(meta["eval_count"]) if meta.get("eval_count") is not None else None,
        "error_type": str(meta.get("error_type") or "") or error_type,
    }


def _run_policy(
    *,
    reader: ReaderAgent,
    doc: DocumentArtifactV2,
    policy_name: str,
    warmup_prompt: str | None = None,
    repeat_index: int = 1,
) -> PolicyResult:
    order = POLICIES[policy_name]
    header = get_artifact_header(doc)
    sections = reader._collect_sections(doc)
    chunks = reader._collect_chunks(sections)
    table_context = reader._build_table_context(doc)
    contexts = {
        label: context
        for label, context in zip(ATTEMPT_LABELS, reader._build_attempt_contexts(sections=sections))
    }

    attempts: list[AttemptResult] = []
    selected_attempt_label: str | None = None
    selected_claim_count = 0
    warmup = _run_warmup(reader=reader, warmup_prompt=warmup_prompt)

    for label in order:
        context = str(contexts.get(label) or "")
        if not context.strip():
            continue
        attempt_idx = ATTEMPT_LABELS.index(label) + 1
        prompt = reader._build_extraction_prompt(
            doc_id=header.doc_id,
            title=header.title,
            authors=header.authors,
            paper_context=context,
            table_context=table_context,
            example_json=_example_claimset_json(),
            min_claims=reader.min_claims,
            attempt_idx=attempt_idx,
        )
        composition = reader._collect_context_composition_metrics(context)
        started = time.perf_counter()
        raw_text = ""
        status = "error"
        claim_count = 0
        response_tokens: int | None = None
        provider_meta: dict[str, Any] = {}
        try:
            result = reader.adapter.generate(prompt, format="json")
            provider_meta = _provider_meta(reader)
            raw_text = str(getattr(result, "text", "") or "")
            response_tokens = reader._estimate_token_count(raw_text)
            parsed = reader._parse_claimset_payload(raw_text, expected_doc_id=header.doc_id, chunks=chunks)
            if parsed is None:
                status = "parse_failed"
            else:
                parsed = enforce_claimset_evidence_policy(parsed)
                claim_count = len(parsed.claims)
                status = "parsed"
        except Exception as exc:  # benchmark-only path; keep going and report
            status = f"error:{type(exc).__name__}"
            provider_meta = _provider_meta(reader)
        elapsed = round(time.perf_counter() - started, 3)

        attempts.append(
            AttemptResult(
                label=label,
                elapsed_seconds=elapsed,
                context_chars=len(context),
                estimated_prompt_tokens=reader._estimate_token_count(prompt),
                estimated_response_tokens=response_tokens,
                included_chunk_count=int(composition.get("included_chunk_count") or 0) or None,
                unique_section_count=int(composition.get("unique_section_count") or 0) or None,
                sentence_focus_count=int(composition.get("sentence_focus_count") or 0),
                parsed_claim_count=claim_count,
                status=status,
                provider_status=str(provider_meta.get("status") or "") or None,
                provider_request_wall_seconds=round(float(provider_meta["request_wall_seconds"]), 3) if provider_meta.get("request_wall_seconds") is not None else None,
                provider_done_reason=str(provider_meta.get("done_reason") or "") or None,
                provider_prompt_eval_count=int(provider_meta["prompt_eval_count"]) if provider_meta.get("prompt_eval_count") is not None else None,
                provider_eval_count=int(provider_meta["eval_count"]) if provider_meta.get("eval_count") is not None else None,
                provider_total_duration_seconds=round(float(provider_meta["total_duration_seconds"]), 6) if provider_meta.get("total_duration_seconds") is not None else None,
                provider_error_type=str(provider_meta.get("error_type") or "") or None,
            )
        )
        if claim_count >= reader.min_claims:
            selected_attempt_label = label
            selected_claim_count = claim_count
            break

    return PolicyResult(
        name=policy_name,
        repeat_index=repeat_index,
        attempts=attempts,
        selected_attempt_label=selected_attempt_label,
        selected_claim_count=selected_claim_count,
        total_elapsed_seconds=round(sum(a.elapsed_seconds for a in attempts), 3),
        total_prompt_tokens=sum(int(a.estimated_prompt_tokens or 0) for a in attempts),
        total_response_tokens=sum(int(a.estimated_response_tokens or 0) for a in attempts),
        warmup_prompt=str(warmup.get("prompt") or "") or None,
        warmup_elapsed_seconds=float(warmup["elapsed_seconds"]) if warmup.get("elapsed_seconds") is not None else None,
        warmup_status=str(warmup.get("status") or "") or None,
        warmup_request_wall_seconds=float(warmup["request_wall_seconds"]) if warmup.get("request_wall_seconds") is not None else None,
        warmup_eval_count=int(warmup["eval_count"]) if warmup.get("eval_count") is not None else None,
        warmup_error_type=str(warmup.get("error_type") or "") or None,
    )


def _format_markdown(
    *,
    run_id: str,
    run_root: Path,
    model_name: str,
    results: list[PolicyResult],
    include_provider_metrics: bool = False,
    warmup_prompt: str | None = None,
    repeats: int = 1,
) -> str:
    show_repeat_column = repeats > 1
    lines: list[str] = []
    lines.append("# Reader Attempt Order Benchmark")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- run_root: `{run_root}`")
    lines.append(f"- model_name: `{model_name}`")
    lines.append(f"- repeats: `{repeats}`")
    lines.append(f"- include_provider_metrics: `{include_provider_metrics}`")
    lines.append(f"- warmup_prompt: `{str(warmup_prompt or '').strip() or None}`")
    lines.append("")
    if show_repeat_column:
        lines.append("| Policy | Runs | Selected attempts | Avg elapsed sec | Min elapsed sec | Max elapsed sec | Avg claims |")
        lines.append("| --- | ---: | --- | ---: | ---: | ---: | ---: |")
        for policy_name, grouped_results in _group_policy_results(results).items():
            elapsed_values = [result.total_elapsed_seconds for result in grouped_results]
            claim_values = [result.selected_claim_count for result in grouped_results]
            selected_attempts: list[str] = []
            for result in grouped_results:
                label = str(result.selected_attempt_label or "None")
                if label not in selected_attempts:
                    selected_attempts.append(label)
            lines.append(
                f"| `{policy_name}` | `{len(grouped_results)}` | "
                f"`{', '.join(selected_attempts)}` | "
                f"`{round(sum(elapsed_values) / len(elapsed_values), 3)}` | "
                f"`{round(min(elapsed_values), 3)}` | "
                f"`{round(max(elapsed_values), 3)}` | "
                f"`{round(sum(claim_values) / len(claim_values), 3)}` |"
            )
        lines.append("")
    if include_provider_metrics:
        if show_repeat_column:
            lines.append(
                "| Policy | Repeat | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | "
                "Total response tokens | Provider status | Provider req sec | Provider eval count | Provider done |"
            )
            lines.append("| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |")
        else:
            lines.append(
                "| Policy | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | "
                "Total response tokens | Provider status | Provider req sec | Provider eval count | Provider done |"
            )
            lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |")
    else:
        if show_repeat_column:
            lines.append("| Policy | Repeat | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | Total response tokens |")
            lines.append("| --- | ---: | --- | ---: | ---: | ---: | ---: |")
        else:
            lines.append("| Policy | Selected attempt | Selected claims | Total elapsed sec | Total prompt tokens | Total response tokens |")
            lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for result in results:
        selected = _selected_attempt(result)
        if include_provider_metrics:
            if show_repeat_column:
                lines.append(
                    f"| `{result.name}` | `{result.repeat_index}` | `{result.selected_attempt_label}` | `{result.selected_claim_count}` | "
                    f"`{result.total_elapsed_seconds}` | `{result.total_prompt_tokens}` | `{result.total_response_tokens}` | "
                    f"`{selected.provider_status if selected else None}` | "
                    f"`{selected.provider_request_wall_seconds if selected else None}` | "
                    f"`{selected.provider_eval_count if selected else None}` | "
                    f"`{selected.provider_done_reason if selected else None}` |"
                )
            else:
                lines.append(
                    f"| `{result.name}` | `{result.selected_attempt_label}` | `{result.selected_claim_count}` | "
                    f"`{result.total_elapsed_seconds}` | `{result.total_prompt_tokens}` | `{result.total_response_tokens}` | "
                    f"`{selected.provider_status if selected else None}` | "
                    f"`{selected.provider_request_wall_seconds if selected else None}` | "
                    f"`{selected.provider_eval_count if selected else None}` | "
                    f"`{selected.provider_done_reason if selected else None}` |"
                )
        else:
            if show_repeat_column:
                lines.append(
                    f"| `{result.name}` | `{result.repeat_index}` | `{result.selected_attempt_label}` | `{result.selected_claim_count}` | "
                    f"`{result.total_elapsed_seconds}` | `{result.total_prompt_tokens}` | `{result.total_response_tokens}` |"
                )
            else:
                lines.append(
                    f"| `{result.name}` | `{result.selected_attempt_label}` | `{result.selected_claim_count}` | "
                    f"`{result.total_elapsed_seconds}` | `{result.total_prompt_tokens}` | `{result.total_response_tokens}` |"
                )
    lines.append("")
    for result in results:
        heading = f"{result.name} (repeat {result.repeat_index})" if show_repeat_column else result.name
        lines.append(f"## {heading}")
        lines.append("")
        if result.warmup_prompt:
            lines.append(
                f"- warmup: prompt=`{result.warmup_prompt}` status=`{result.warmup_status}` "
                f"elapsed_sec=`{result.warmup_elapsed_seconds}` request_sec=`{result.warmup_request_wall_seconds}` "
                f"eval_count=`{result.warmup_eval_count}` error=`{result.warmup_error_type}`"
            )
            lines.append("")
        if include_provider_metrics:
            lines.append(
                "| Attempt | Status | Chunks | Sections | Sentence focus | Claims | Prompt tokens | "
                "Response tokens | Elapsed sec | Provider status | Provider req sec | Provider eval | Provider done | Provider error |"
            )
            lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- |")
        else:
            lines.append("| Attempt | Status | Chunks | Sections | Sentence focus | Claims | Prompt tokens | Response tokens | Elapsed sec |")
            lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for attempt in result.attempts:
            if include_provider_metrics:
                lines.append(
                    f"| `{attempt.label}` | `{attempt.status}` | `{attempt.included_chunk_count}` | "
                    f"`{attempt.unique_section_count}` | `{attempt.sentence_focus_count}` | "
                    f"`{attempt.parsed_claim_count}` | `{attempt.estimated_prompt_tokens}` | "
                    f"`{attempt.estimated_response_tokens}` | `{attempt.elapsed_seconds}` | "
                    f"`{attempt.provider_status}` | `{attempt.provider_request_wall_seconds}` | "
                    f"`{attempt.provider_eval_count}` | `{attempt.provider_done_reason}` | "
                    f"`{attempt.provider_error_type}` |"
                )
            else:
                lines.append(
                    f"| `{attempt.label}` | `{attempt.status}` | `{attempt.included_chunk_count}` | "
                    f"`{attempt.unique_section_count}` | `{attempt.sentence_focus_count}` | "
                    f"`{attempt.parsed_claim_count}` | `{attempt.estimated_prompt_tokens}` | "
                    f"`{attempt.estimated_response_tokens}` | `{attempt.elapsed_seconds}` |"
                )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark reader attempt order on a saved document artifact.")
    parser.add_argument("--run-id", required=True, help="Saved run id to benchmark against.")
    parser.add_argument("--paper-id", help="Optional paper id. Required when run ids are not globally unique.")
    parser.add_argument("--model-name", default="llama3:latest", help="Reader model name to use for the benchmark.")
    parser.add_argument("--policy", action="append", dest="policies", default=[], choices=sorted(POLICIES.keys()), help="Policy to run. Repeatable. Defaults to all policies.")
    parser.add_argument("--repeats", type=int, default=1, help="Number of times to rerun the selected policy set. Defaults to 1.")
    parser.add_argument("--include-provider-metrics", action="store_true", help="Include provider request metadata in the markdown summary.")
    parser.add_argument("--warmup-prompt", help="Optional untimed warm-up prompt to run once before each policy benchmark.")
    parser.add_argument("--out", type=Path, help="Optional output path for markdown summary.")
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")

    run_root = _find_run_root(str(args.run_id).strip(), str(args.paper_id).strip() if args.paper_id else None)
    doc_payload = _load_json(run_root / "document_artifact.json")
    doc = DocumentArtifactV2.model_validate(doc_payload)
    reader = ReaderAgent(model_name=args.model_name)
    policies = args.policies or list(POLICIES.keys())
    results = [
        _run_policy(
            reader=reader,
            doc=doc,
            policy_name=policy_name,
            warmup_prompt=args.warmup_prompt,
            repeat_index=repeat_index,
        )
        for repeat_index in range(1, args.repeats + 1)
        for policy_name in policies
    ]
    output = _format_markdown(
        run_id=args.run_id,
        run_root=run_root,
        model_name=args.model_name,
        results=results,
        include_provider_metrics=bool(args.include_provider_metrics),
        warmup_prompt=args.warmup_prompt,
        repeats=args.repeats,
    )
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

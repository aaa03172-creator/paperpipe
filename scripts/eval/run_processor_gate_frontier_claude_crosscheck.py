#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.processor_gate_replay_drift import (
    load_processor_gate_threshold_review_summary,
    render_processor_gate_threshold_review_markdown,
)


DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 1200
DEFAULT_TEMPERATURE = 0.0
DEFAULT_PACKET_FILENAME = "manual_review_frontier_crosscheck_packet.md"
DEFAULT_RESPONSE_MARKDOWN_FILENAME = "manual_review_frontier_claude_crosscheck.md"
DEFAULT_RESPONSE_JSON_FILENAME = "manual_review_frontier_claude_crosscheck.json"
SYSTEM_PROMPT = (
    "You are an independent biomedical review auditor. Review the provided frontier packet conservatively. "
    "Only recommend high-threshold boundary review when the packet contains concrete contradictory evidence. "
    "Follow the packet's requested response structure closely."
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_review_summary_path(path_or_dir: Path) -> Path:
    candidate = path_or_dir.expanduser().resolve(strict=False)
    return candidate / "summary.json" if candidate.is_dir() else candidate


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("processor gate threshold review summary must be a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _extract_text_from_message(message: Any) -> str:
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return str(content or "").strip()

    text_blocks: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if str(block.get("type") or "").strip() == "text":
                text = str(block.get("text") or "").strip()
                if text:
                    text_blocks.append(text)
            continue
        if str(getattr(block, "type", "") or "").strip() == "text":
            text = str(getattr(block, "text", "") or "").strip()
            if text:
                text_blocks.append(text)
    return "\n\n".join(text_blocks).strip()


def _usage_to_dict(usage: Any) -> dict[str, int | None]:
    if usage is None:
        return {"input_tokens": None, "output_tokens": None}
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def _anthropic_client(api_key: str):
    try:
        from anthropic import Anthropic
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The `anthropic` package is not available in this Python environment. "
            "Use the repo venv (for example `.venv/bin/python ...`) or install the project dependencies first."
        ) from exc

    return Anthropic(api_key=api_key)


def render_processor_gate_frontier_claude_crosscheck_markdown(
    *,
    run_id: str,
    packet_path: Path,
    model: str,
    response_text: str,
    stop_reason: str | None,
    usage: dict[str, int | None],
) -> str:
    lines = [
        f"# Processor Gate Frontier Claude Cross-Check: {run_id}",
        "",
        f"- Generated At: {_utc_now_iso()}",
        "- Provider: anthropic",
        f"- Model: {model}",
        f"- Packet: {packet_path}",
    ]
    if stop_reason:
        lines.append(f"- Stop Reason: {stop_reason}")
    if usage.get("input_tokens") is not None or usage.get("output_tokens") is not None:
        lines.append(
            "- Usage: "
            f"input={usage.get('input_tokens') if usage.get('input_tokens') is not None else '-'}, "
            f"output={usage.get('output_tokens') if usage.get('output_tokens') is not None else '-'}"
        )
    lines.extend(
        [
            "",
            "## Claude Response",
            response_text or "-",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_processor_gate_frontier_claude_crosscheck(
    *,
    review_run: Path,
    model: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    load_dotenv(ROOT / ".env")

    summary_path = _resolve_review_summary_path(review_run)
    if not summary_path.exists():
        raise FileNotFoundError(f"processor gate threshold review summary not found: {summary_path}")
    run_root = summary_path.parent
    packet_path = run_root / DEFAULT_PACKET_FILENAME
    if not packet_path.exists():
        raise FileNotFoundError(f"frontier crosscheck packet not found: {packet_path}")

    api_key = str(os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; load it in .env or the environment before running this script")

    packet_text = packet_path.read_text(encoding="utf-8").strip()
    if not packet_text:
        raise RuntimeError(f"frontier crosscheck packet is empty: {packet_path}")

    summary = load_processor_gate_threshold_review_summary(run_root)
    client = _anthropic_client(api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": packet_text}],
    )
    response_text = _extract_text_from_message(message)
    stop_reason = str(getattr(message, "stop_reason", "") or "").strip() or None
    usage = _usage_to_dict(getattr(message, "usage", None))

    response_markdown_path = run_root / DEFAULT_RESPONSE_MARKDOWN_FILENAME
    response_json_path = run_root / DEFAULT_RESPONSE_JSON_FILENAME
    run_id = str(summary.get("run_id") or run_root.name).strip() or run_root.name

    response_markdown_path.write_text(
        render_processor_gate_frontier_claude_crosscheck_markdown(
            run_id=run_id,
            packet_path=packet_path,
            model=model,
            response_text=response_text,
            stop_reason=stop_reason,
            usage=usage,
        ),
        encoding="utf-8",
    )
    _write_json(
        response_json_path,
        {
            "schema_version": "processor_gate_frontier_claude_crosscheck.v1",
            "generated_at": _utc_now_iso(),
            "run_id": run_id,
            "provider": "anthropic",
            "model": model,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "review_run_root": str(run_root),
            "review_summary_path": str(summary_path),
            "packet_path": str(packet_path),
            "response_markdown_path": str(response_markdown_path),
            "stop_reason": stop_reason,
            "usage": usage,
            "response_text": response_text,
        },
    )

    # Refresh audit.md so sibling-path discoverability stays current.
    (run_root / "audit.md").write_text(
        render_processor_gate_threshold_review_markdown(summary, run_root=run_root),
        encoding="utf-8",
    )

    return {
        "run_root": str(run_root),
        "summary_path": str(summary_path),
        "packet_path": str(packet_path),
        "response_markdown_path": str(response_markdown_path),
        "response_json_path": str(response_json_path),
        "provider": "anthropic",
        "model": model,
        "stop_reason": stop_reason,
        "usage": usage,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded Claude/Anthropic cross-check for the processor-gate threshold-review frontier packet."
        ),
        epilog=(
            "Reads manual_review_frontier_crosscheck_packet.md from an existing threshold-review run and writes "
            "manual_review_frontier_claude_crosscheck.{md,json} beside it."
        ),
    )
    parser.add_argument(
        "--review-run",
        required=True,
        help="Path to a processor gate threshold review run directory or summary.json file.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Anthropic model name to use for the frontier cross-check.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help="Maximum output tokens for the Anthropic response.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Sampling temperature for the Anthropic response.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    payload = run_processor_gate_frontier_claude_crosscheck(
        review_run=Path(args.review_run),
        model=str(args.model),
        max_tokens=max(int(args.max_tokens), 1),
        temperature=float(args.temperature),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

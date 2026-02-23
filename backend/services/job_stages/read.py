from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from src.contracts.output_contracts import build_claimset_contract


async def run_read_stage(
    *,
    run_id: str,
    paper_id: str,
    persona_id: str,
    config: Any,
    doc_artifact: Any,
    index_artifact: Any,
    artifact_dir: Path,
    bootstrap_meta: dict[str, Any],
    emit: Callable[[str, int, str, str], Awaitable[Any]],
    is_cancelled: Callable[[], Awaitable[bool]],
    write_artifact_model: Callable[[Path, str, Any], None],
    write_bootstrap_meta: Callable[[Path, dict[str, Any]], None],
    resolve_persona_hint: Callable[[str], Optional[str]],
    load_similar_feedback_top3: Callable[[str, int], list[dict[str, str]]],
    resolve_main_model: Callable[[Any], str],
    update_claimset_readiness: Callable[[dict[str, Any], str, int], None],
    resolve_claimset_evidence: Callable[[Any, Any], Any],
    reader_agent_cls: Any,
) -> tuple[Any, Any] | None:
    if await is_cancelled():
        return None
    await emit("read", 50, "Reader Agent analyzing...", "INFO")
    persona_hint = resolve_persona_hint(persona_id)

    feedback_query_text = persona_hint if persona_hint else paper_id
    similar_feedback = load_similar_feedback_top3(feedback_query_text, limit=3)
    if similar_feedback:
        fb_lines = ["Similar feedback examples (Top-3):"]
        for idx, item in enumerate(similar_feedback, 1):
            fb_lines.append(f"{idx}) paper_id={item['paper_id']} preview={item['preview']}")
        feedback_hint = "\n".join(fb_lines)
        persona_hint = f"{persona_hint}\n\n{feedback_hint}" if persona_hint else feedback_hint
        bootstrap_meta["similar_feedback_count"] = len(similar_feedback)
        bootstrap_meta["similar_feedback_paper_ids"] = [item["paper_id"] for item in similar_feedback]
        await emit("read", 53, f"Similar feedback injected: {len(similar_feedback)}", "INFO")

    if persona_hint:
        bootstrap_meta["persona_applied"] = True
        await emit("read", 52, f"Persona applied: {persona_id}", "INFO")

    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    main_model = resolve_main_model(config)
    bootstrap_meta["reader_model"] = main_model
    write_bootstrap_meta(artifact_dir, bootstrap_meta)

    try:
        reader_agent = reader_agent_cls(model_name=main_model, persona_hint=persona_hint)
    except TypeError:
        reader_agent = reader_agent_cls()

    raw_claim_set = reader_agent.analyze(doc_artifact)
    if not raw_claim_set:
        raise Exception("Reader Agent failed to produce claims")

    if hasattr(raw_claim_set, "model_copy"):
        raw_claim_set_copy = raw_claim_set.model_copy(deep=True)
    else:
        raw_claim_set_copy = raw_claim_set

    raw_contract = build_claimset_contract(
        paper_id=paper_id,
        run_id=run_id,
        claim_set=raw_claim_set_copy,
        stage="raw",
        model=main_model,
    )
    write_artifact_model(artifact_dir, "claimset.raw.json", raw_contract)
    bootstrap_meta["artifact_claimset_raw_written"] = True
    write_bootstrap_meta(artifact_dir, bootstrap_meta)

    claim_set = resolve_claimset_evidence(raw_claim_set, index_artifact)
    total_spans = 0
    grounded_spans = 0
    for claim in claim_set.claims:
        for span in claim.evidence_spans:
            total_spans += 1
            if getattr(span, "grounded", None) is True:
                grounded_spans += 1

    resolved_contract = build_claimset_contract(
        paper_id=paper_id,
        run_id=run_id,
        claim_set=claim_set,
        stage="resolved",
        model=main_model,
    )
    write_artifact_model(artifact_dir, "claimset.resolved.json", resolved_contract)
    write_artifact_model(artifact_dir, "claimset.json", claim_set)
    bootstrap_meta["artifact_claimset_written"] = True
    bootstrap_meta["artifact_claimset_resolved_written"] = True
    bootstrap_meta["evidence_spans_total"] = total_spans
    bootstrap_meta["evidence_spans_grounded"] = grounded_spans
    bootstrap_meta["evidence_grounded_ratio"] = (
        round(grounded_spans / total_spans, 4) if total_spans > 0 else None
    )
    update_claimset_readiness(bootstrap_meta, paper_id, len(claim_set.claims))
    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    await emit("read", 75, f"Extracted {len(claim_set.claims)} claims", "INFO")
    return claim_set, reader_agent

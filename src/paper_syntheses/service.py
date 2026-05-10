from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from src.contracts.output_bridge import (
    bind_claim_cards_to_run,
    claim_cards_from_claimset_payload,
    normalize_claimset_payload,
)
from src.paper_syntheses.renderer import render_paper_synthesis_markdown
from src.paper_syntheses.store import (
    list_paper_synthesis_ids,
    load_paper_synthesis,
    load_paper_synthesis_markdown,
    save_paper_synthesis_bundle,
)
from src.schemas.chat import ChatEvidenceRef, ChatLocator
from src.schemas.paper_synthesis import (
    PaperSynthesis,
    PaperSynthesisGenerateRequest,
    PaperSynthesisListItem,
    PaperSynthesisListResponse,
    PaperSynthesisResponse,
    PaperSynthesisSourceRef,
)
from src.schemas.skills import SkillClaimCard, SkillClaimEvidence, StructuredPaperState
from src.services.fixture_visibility import (
    fixture_structured_state_allowed,
    is_test_fixture_structured_state,
)
from src.services.listing_resilience import load_available_items
from src.services.runtime_paths import artifacts_root as default_artifacts_root
from src.services.runtime_paths import preferred_artifact_paper_dir
from src.skills.storage import (
    load_structured_state,
    paper_id_lookup_variants,
    resolve_note_path,
    safe_read_text,
    split_frontmatter,
    structured_state_path,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperSynthesisInputs:
    paper_slug: str
    state_path: Path
    state: StructuredPaperState
    run_id: str
    run_dir: Path
    run_meta_path: Path
    run_meta: dict[str, Any]
    claimset_path: Path
    claim_cards: list[SkillClaimCard]
    quality_gate_path: Path | None
    quality_gate: dict[str, Any] | None
    acceptance_contract_path: Path | None
    acceptance_contract: dict[str, Any] | None
    visual_evidence_ledger_path: Path | None
    visual_evidence_ledger: dict[str, Any] | None


@dataclass(frozen=True)
class PaperSynthesisBuildResult:
    synthesis: PaperSynthesis
    markdown: str
    inputs: PaperSynthesisInputs


@dataclass(frozen=True)
class PaperSynthesisResult:
    synthesis: PaperSynthesis
    markdown: str


def generate_paper_synthesis(
    *,
    request: PaperSynthesisGenerateRequest,
    vault_path: Path,
    root: Path | None = None,
    artifacts_root: Path | None = None,
    now: datetime | None = None,
) -> PaperSynthesisResult:
    result = materialize_paper_synthesis_for_slug(
        request.paper_slug,
        vault_path=vault_path,
        artifacts_root=artifacts_root,
        output_root=root,
        now=now,
    )
    return PaperSynthesisResult(synthesis=result.synthesis, markdown=result.markdown)


def load_paper_synthesis_inputs(
    paper_slug: str,
    *,
    vault_path: Path,
    artifacts_root: Path | None = None,
) -> PaperSynthesisInputs:
    state_path, state = _load_visible_structured_state(
        paper_slug,
        vault_path=vault_path,
    )

    artifacts_path = (artifacts_root or default_artifacts_root()).expanduser().resolve()
    run_dirs = _eligible_run_dirs(
        paper_slug,
        vault_path=vault_path,
        artifacts_root=artifacts_path,
    )
    if not run_dirs:
        raise FileNotFoundError(f"Artifacts directory not found for paper_slug={paper_slug}")

    for run_dir in run_dirs:
        run_meta_path = run_dir / "run_meta.json"
        claimset_path = run_dir / "claimset.resolved.json"
        quality_gate_path = run_dir / "quality_gate.json"
        acceptance_contract_path = run_dir / "acceptance_contract.json"
        visual_evidence_ledger_path = run_dir / "visual_evidence_ledger.json"
        run_meta = _load_json_dict(run_meta_path)
        claimset_payload = normalize_claimset_payload(_load_json_dict(claimset_path))
        quality_gate = _load_json_dict(quality_gate_path)
        acceptance_contract = _load_json_dict(acceptance_contract_path)
        visual_evidence_ledger = _load_json_dict(visual_evidence_ledger_path)
        if run_meta is None or claimset_payload is None:
            continue
        status = str(run_meta.get("status") or "").strip().lower()
        if status and status != "succeeded":
            continue

        raw_claims = [claim for claim in claimset_payload.get("claims") or [] if isinstance(claim, dict)]
        run_id = str(run_meta.get("run_id") or run_dir.name).strip() or run_dir.name
        claim_cards = bind_claim_cards_to_run(
            claim_cards_from_claimset_payload({"claims": raw_claims}),
            run_id,
        )
        return PaperSynthesisInputs(
            paper_slug=paper_slug,
            state_path=state_path,
            state=state,
            run_id=run_id,
            run_dir=run_dir,
            run_meta_path=run_meta_path,
            run_meta=run_meta,
            claimset_path=claimset_path,
            claim_cards=claim_cards,
            quality_gate_path=quality_gate_path if quality_gate is not None else None,
            quality_gate=quality_gate,
            acceptance_contract_path=acceptance_contract_path if acceptance_contract is not None else None,
            acceptance_contract=acceptance_contract,
            visual_evidence_ledger_path=visual_evidence_ledger_path if visual_evidence_ledger is not None else None,
            visual_evidence_ledger=visual_evidence_ledger,
        )

    raise FileNotFoundError(
        f"No eligible synthesis inputs found for paper_slug={paper_slug}; expected succeeded run with "
        "`run_meta.json` and `claimset.resolved.json`."
    )


def _load_visible_structured_state(
    paper_slug: str,
    *,
    vault_path: Path,
) -> tuple[Path, StructuredPaperState]:
    state_path = structured_state_path(vault_path, paper_slug)
    state = load_structured_state(vault_path, paper_slug, {})
    if state is None:
        raise FileNotFoundError(f"Canonical structured state not found for paper_slug={paper_slug}: {state_path}")
    if is_test_fixture_structured_state(state) and not fixture_structured_state_allowed(vault_path):
        raise FileNotFoundError(
            f"Canonical structured state for paper_slug={paper_slug} appears to be a test fixture and is hidden outside isolated E2E runtimes."
        )
    return state_path, state


def build_paper_synthesis_for_slug(
    paper_slug: str,
    *,
    vault_path: Path,
    artifacts_root: Path | None = None,
    now: datetime | None = None,
) -> PaperSynthesisBuildResult:
    inputs = load_paper_synthesis_inputs(
        paper_slug,
        vault_path=vault_path,
        artifacts_root=artifacts_root,
    )
    generated_at = now or datetime.now(timezone.utc)

    evidence_refs = _collect_claim_evidence_refs(inputs.claim_cards, paper_slug=paper_slug)
    warnings = _build_warnings(inputs)
    uncertainty_notes = _build_uncertainty_notes(inputs, evidence_refs=evidence_refs)
    readiness = _resolve_readiness(warnings=warnings, uncertainty_notes=uncertainty_notes, evidence_refs=evidence_refs)
    freshness = _resolve_freshness(inputs.state, run_id=inputs.run_id)

    synthesis = PaperSynthesis(
        synthesis_id=_build_synthesis_id(paper_slug, inputs.run_id),
        paper_slug=paper_slug,
        title=f"Paper synthesis: {paper_slug}",
        created_at=generated_at,
        updated_at=generated_at,
        readiness=readiness,
        freshness=freshness,
        summary=_build_summary_text(inputs),
        source_refs=[
            PaperSynthesisSourceRef(
                kind="structured_state",
                paper_slug=paper_slug,
                path=str(inputs.state_path),
                note="Canonical structured state.",
            ),
            PaperSynthesisSourceRef(
                kind="claimset_resolved",
                paper_slug=paper_slug,
                run_id=inputs.run_id,
                path=str(inputs.claimset_path),
                note="Resolved claim/evidence snapshot for synthesis.",
            ),
            PaperSynthesisSourceRef(
                kind="run_meta",
                paper_slug=paper_slug,
                run_id=inputs.run_id,
                path=str(inputs.run_meta_path),
                note="Run metadata for provenance and freshness.",
            ),
            *(
                [
                    PaperSynthesisSourceRef(
                        kind="quality_gate",
                        paper_slug=paper_slug,
                        run_id=inputs.run_id,
                        path=str(inputs.quality_gate_path),
                        note="Additive review gate artifact; not a canonical owner.",
                    )
                ]
                if inputs.quality_gate_path is not None
                else []
            ),
            *(
                [
                    PaperSynthesisSourceRef(
                        kind="acceptance_contract",
                        paper_slug=paper_slug,
                        run_id=inputs.run_id,
                        path=str(inputs.acceptance_contract_path),
                        note="Run acceptance snapshot used for bounded review handoff.",
                    )
                ]
                if inputs.acceptance_contract_path is not None
                else []
            ),
            *(
                [
                    PaperSynthesisSourceRef(
                        kind="visual_evidence_ledger",
                        paper_slug=paper_slug,
                        run_id=inputs.run_id,
                        path=str(inputs.visual_evidence_ledger_path),
                        note="Additive visual evidence replay artifact; not a canonical owner.",
                    )
                ]
                if inputs.visual_evidence_ledger_path is not None
                else []
            ),
        ],
        evidence_refs=evidence_refs,
        warnings=warnings,
        uncertainty_notes=uncertainty_notes,
    )
    markdown = render_paper_synthesis_markdown(
        synthesis,
        state=inputs.state,
        claim_cards=inputs.claim_cards,
        run_meta=inputs.run_meta,
        visual_evidence_ledger=inputs.visual_evidence_ledger,
    )
    return PaperSynthesisBuildResult(synthesis=synthesis, markdown=markdown, inputs=inputs)


def materialize_paper_synthesis_for_slug(
    paper_slug: str,
    *,
    vault_path: Path,
    artifacts_root: Path | None = None,
    output_root: Path | None = None,
    now: datetime | None = None,
) -> PaperSynthesisBuildResult:
    result = build_paper_synthesis_for_slug(
        paper_slug,
        vault_path=vault_path,
        artifacts_root=artifacts_root,
        now=now,
    )
    save_paper_synthesis_bundle(result.synthesis, result.markdown, root=output_root)
    return result


def get_paper_synthesis(synthesis_id: str, *, root: Path | None = None) -> PaperSynthesisResult:
    synthesis = load_paper_synthesis(synthesis_id, root)
    markdown = load_paper_synthesis_markdown(synthesis_id, root)
    return PaperSynthesisResult(synthesis=synthesis, markdown=markdown)


def list_paper_synthesis_summaries(
    *,
    root: Path | None = None,
    paper_slug: str | None = None,
) -> list[PaperSynthesis]:
    items = load_available_items(
        list_paper_synthesis_ids(root),
        lambda synthesis_id: load_paper_synthesis(synthesis_id, root),
        item_kind="paper synthesis",
        logger=logger,
    )
    normalized_slug = str(paper_slug or "").strip()
    if normalized_slug:
        items = [item for item in items if item.paper_slug == normalized_slug]
    return sorted(
        items,
        key=lambda item: (item.updated_at, item.synthesis_id),
        reverse=True,
    )


def paper_synthesis_response_payload(result: PaperSynthesisResult) -> PaperSynthesisResponse:
    return PaperSynthesisResponse(
        synthesis=result.synthesis,
        markdown=result.markdown,
    )


def paper_synthesis_list_response(
    *,
    root: Path | None = None,
    paper_slug: str | None = None,
) -> PaperSynthesisListResponse:
    items = [
        PaperSynthesisListItem(
            synthesis_id=synthesis.synthesis_id,
            paper_slug=synthesis.paper_slug,
            title=synthesis.title,
            updated_at=synthesis.updated_at,
            artifact_family=synthesis.artifact_family,
            template_kind=synthesis.template_kind,
            canonical_status=synthesis.canonical_status,
            readiness=synthesis.readiness,
            freshness=synthesis.freshness,
            warning_count=len(synthesis.warnings),
            source_ref_count=len(synthesis.source_refs),
            evidence_ref_count=len(synthesis.evidence_refs),
            lineage_summary=synthesis.lineage_summary,
        )
        for synthesis in list_paper_synthesis_summaries(root=root, paper_slug=paper_slug)
    ]
    return PaperSynthesisListResponse(items=items, total=len(items))


def _build_synthesis_id(paper_slug: str, run_id: str) -> str:
    digest = hashlib.sha1(f"{paper_slug}|{run_id}".encode("utf-8")).hexdigest()[:10]
    safe_slug = "".join(char if char.isalnum() or char in "._-" else "_" for char in paper_slug).strip("._") or "paper"
    return f"papersynth_{safe_slug}_{run_id}_{digest}"


def _build_summary_text(inputs: PaperSynthesisInputs) -> str:
    claim_count = len(inputs.claim_cards)
    evidence_count = sum(len(claim.evidence) for claim in inputs.claim_cards)
    canonical_claim_count = len(inputs.state.claimset)
    parser_backend = str(inputs.run_meta.get("parser_backend") or "").strip()
    parts = [
        "Derived from canonical structured state plus the selected `claimset.resolved.json` and `run_meta.json` only.",
        "Raw-memory helpers such as project memory, work traces, or conversation logs are intentionally excluded from this synthesis contract.",
        f"Selected run `{inputs.run_id}` contributes {claim_count} claim(s) and {evidence_count} evidence span(s).",
    ]
    if inputs.quality_gate is not None or inputs.acceptance_contract is not None or inputs.visual_evidence_ledger is not None:
        parts.append(
            "Additive review artifacts may be attached for this run, but they do not replace canonical state or resolved evidence."
        )
    if inputs.visual_evidence_ledger is not None:
        metrics = inputs.visual_evidence_ledger.get("metrics")
        metrics = metrics if isinstance(metrics, dict) else {}
        parts.append(
            "Visual evidence replay is attached as a review gate artifact "
            f"with {int(metrics.get('entry_count') or 0)} entrie(s)."
        )
    if canonical_claim_count:
        parts.append(f"Canonical structured state currently exposes {canonical_claim_count} claim(s).")
    if parser_backend:
        parts.append(f"Run metadata reports parser backend `{parser_backend}`.")
    return " ".join(parts)


def _build_warnings(inputs: PaperSynthesisInputs) -> list[str]:
    warnings: list[str] = []
    state_last_run_id = str(
        inputs.state.signals.get("last_run_id")
        or inputs.state.signals.get("state_source_run_id")
        or ""
    ).strip()
    if state_last_run_id and state_last_run_id != inputs.run_id:
        warnings.append(
            "Canonical structured state last_run_id differs from the selected synthesis run; keep this bundle review-only until reconciled."
        )
    if len(inputs.state.claimset) != len(inputs.claim_cards):
        warnings.append(
            "Canonical structured state claim count differs from the selected resolved claimset snapshot."
        )
    unresolved_evidence = sum(
        1
        for claim in inputs.claim_cards
        for evidence in claim.evidence
        if evidence.grounded is not True
    )
    if unresolved_evidence:
        warnings.append(
            "Some selected evidence entries are not explicitly grounded/resolved in the chosen claimset snapshot."
        )
    if not inputs.claim_cards:
        warnings.append("Selected `claimset.resolved.json` did not yield any structured claims.")
    quality_gate_status = str((inputs.quality_gate or {}).get("overall_status") or "").strip().lower()
    if quality_gate_status in {"warn", "fail"}:
        warnings.append(
            f"Selected run quality gate is `{quality_gate_status}`, so this synthesis should stay explicitly review-only."
        )
    visual_metrics = _visual_evidence_metrics(inputs)
    if visual_metrics and visual_metrics["unknown_count"] > 0:
        warnings.append(
            "Selected run visual evidence ledger contains unknown visual/table evidence; figure/table-backed claims must be replayed before reuse."
        )
    return _dedupe_non_empty_strings(warnings)


def _build_uncertainty_notes(
    inputs: PaperSynthesisInputs,
    *,
    evidence_refs: list[ChatEvidenceRef],
) -> list[str]:
    notes: list[str] = []
    unresolved_count = sum(
        1
        for claim in inputs.claim_cards
        for evidence in claim.evidence
        if evidence.grounded is not True
    )
    if unresolved_count:
        notes.append(f"{unresolved_count} evidence item(s) remain unresolved or only partially grounded.")
    if not evidence_refs:
        notes.append("No reusable evidence references were extracted from the selected claimset.")
    state_last_run_id = str(
        inputs.state.signals.get("last_run_id")
        or inputs.state.signals.get("state_source_run_id")
        or ""
    ).strip()
    if state_last_run_id and state_last_run_id != inputs.run_id:
        notes.append("Upstream canonical state and selected synthesis run are not aligned yet.")
    visual_metrics = _visual_evidence_metrics(inputs)
    if visual_metrics:
        notes.append(
            "Visual evidence replay summary: "
            f"{visual_metrics['entry_count']} entrie(s), "
            f"{visual_metrics['partially_observed_count']} partial, "
            f"{visual_metrics['unknown_count']} unknown."
        )
    return _dedupe_non_empty_strings(notes)


def _visual_evidence_metrics(inputs: PaperSynthesisInputs) -> dict[str, int] | None:
    ledger = inputs.visual_evidence_ledger
    if not isinstance(ledger, dict):
        return None
    metrics = ledger.get("metrics")
    if not isinstance(metrics, dict):
        return None
    return {
        "entry_count": int(metrics.get("entry_count") or 0),
        "observed_count": int(metrics.get("observed_count") or 0),
        "partially_observed_count": int(metrics.get("partially_observed_count") or 0),
        "unknown_count": int(metrics.get("unknown_count") or 0),
        "unsupported_count": int(metrics.get("unsupported_count") or 0),
    }


def _resolve_readiness(
    *,
    warnings: list[str],
    uncertainty_notes: list[str],
    evidence_refs: list[ChatEvidenceRef],
) -> str:
    if not evidence_refs:
        return "background_only"
    if warnings or uncertainty_notes:
        return "mixed"
    return "evidence_backed"


def _resolve_freshness(state: StructuredPaperState, *, run_id: str) -> str:
    state_last_run_id = str(
        state.signals.get("last_run_id")
        or state.signals.get("state_source_run_id")
        or ""
    ).strip()
    if not state_last_run_id:
        return "unknown"
    if state_last_run_id == run_id:
        return "current"
    return "stale"


def _collect_claim_evidence_refs(claim_cards: list[SkillClaimCard], *, paper_slug: str) -> list[ChatEvidenceRef]:
    refs: list[ChatEvidenceRef] = []
    for claim in claim_cards:
        for evidence in claim.evidence:
            refs.append(_evidence_ref(evidence, paper_slug=paper_slug, claim_id=claim.id))
    return _dedupe_evidence_refs(refs)


def _evidence_ref(
    evidence: SkillClaimEvidence,
    *,
    paper_slug: str,
    claim_id: str | None = None,
) -> ChatEvidenceRef:
    locator = evidence.locator
    return ChatEvidenceRef(
        paper_slug=paper_slug,
        claim_id=claim_id or evidence.claim_id,
        evidence_id=evidence.id,
        run_id=evidence.run_id,
        locator=(
            ChatLocator(
                page=locator.page,
                span=list(locator.span),
                section=locator.section,
                chunk_id=locator.chunk_id,
                char_start=locator.char_start,
                char_end=locator.char_end,
                bbox_pdf=list(locator.bbox_pdf) if locator.bbox_pdf else None,
                bbox_pct=dict(locator.bbox_pct) if locator.bbox_pct else None,
                table_id=locator.table_id,
                cell_id=locator.cell_id,
                source=locator.source,
            )
            if locator is not None
            else None
        ),
    )


def _dedupe_evidence_refs(refs: list[ChatEvidenceRef]) -> list[ChatEvidenceRef]:
    deduped: list[ChatEvidenceRef] = []
    seen: set[tuple[Any, ...]] = set()
    for ref in refs:
        locator = ref.locator
        key = (
            ref.paper_slug,
            ref.claim_id,
            ref.evidence_id,
            ref.run_id,
            getattr(locator, "page", None),
            tuple(getattr(locator, "span", []) or []),
            getattr(locator, "section", None),
            getattr(locator, "chunk_id", None),
            getattr(locator, "char_start", None),
            getattr(locator, "char_end", None),
            tuple(getattr(locator, "bbox_pdf", []) or []),
            tuple(sorted((getattr(locator, "bbox_pct", {}) or {}).items())),
            getattr(locator, "table_id", None),
            getattr(locator, "cell_id", None),
            getattr(locator, "source", None),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _dedupe_non_empty_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _artifact_candidate_ids(paper_slug: str, *, vault_path: Path) -> list[str]:
    candidates = [paper_slug]
    note_path = resolve_note_path(vault_path, paper_slug)
    if note_path is None:
        return candidates

    frontmatter, _body = split_frontmatter(safe_read_text(note_path))
    for key in ("id", "doi"):
        value = frontmatter.get(key)
        for candidate in paper_id_lookup_variants(value):
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _eligible_run_dirs(
    paper_slug: str,
    *,
    vault_path: Path,
    artifacts_root: Path,
) -> list[Path]:
    run_dirs: list[Path] = []
    seen: set[Path] = set()
    for candidate_id in _artifact_candidate_ids(paper_slug, vault_path=vault_path):
        paper_dir = preferred_artifact_paper_dir(candidate_id, root=artifacts_root)
        if not paper_dir.exists() or not paper_dir.is_dir():
            continue
        for path in paper_dir.iterdir():
            if not path.is_dir():
                continue
            if not (path / "run_meta.json").exists():
                continue
            if not (path / "claimset.resolved.json").exists():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            run_dirs.append(path)
    run_dirs.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    return run_dirs

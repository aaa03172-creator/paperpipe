from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import statistics
from typing import Any
from urllib.parse import unquote, urlparse

from src.agents.ingest_agent import IngestAgent
from src.config import load_config
from src.contracts.output_bridge import (
    bind_claim_cards_to_run,
    claim_cards_from_claimset_payload,
    normalize_claimset_payload,
)
from src.fetch.openalex import OpenAlexFetcher
from src.sandbox.docker_runner import DockerSandbox
from src.schemas.skills import (
    CriticalAppraisalCheck,
    CriticalAppraisalConcern,
    CriticalAppraisalQuestion,
    CriticalAppraisalReport,
    SkillClaimCard,
    SkillRunRecord,
    SkillRunRequest,
    SkillRunResponse,
)
from src.skills.policy import get_action_policy
from src.skills.storage import (
    atomic_write_text,
    compose_note,
    extract_markdown_links,
    extract_reference_block,
    load_structured_state,
    merge_state,
    resolve_note_path,
    safe_read_text,
    split_frontmatter,
    structured_relpath,
    structured_run_path,
    structured_state_path,
    update_frontmatter_pp,
    upsert_automation_results_section,
    write_structured_state,
)
from src.skills.types import NoteExecutionContext, SkillHandlerResult
from src.services.event_log import log_user_action
from src.services.fixture_visibility import visible_structured_state
from src.services.identity import make_runtime_paper_id
from src.services.runtime_paths import artifact_paper_dir, artifacts_root


logger = logging.getLogger(__name__)

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_stamp(ts: str) -> str:
    return (
        ts.replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("+00:00", "Z")
    )


def _best_effort_log_user_action(
    *,
    paper_id: str | None,
    action_type: str,
    source: str,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        log_user_action(paper_id=paper_id, action_type=action_type, source=source, payload=payload)
    except Exception:
        pass


def _paper_id_for_note_context(ctx: NoteExecutionContext) -> str | None:
    explicit_paper_id = str(ctx.frontmatter.get("paper_id") or ctx.frontmatter.get("id") or "").strip()
    doi = str(ctx.frontmatter.get("doi") or "").strip()
    zotero_key = str(ctx.frontmatter.get("zotero_key") or "").strip()
    try:
        if explicit_paper_id:
            return make_runtime_paper_id(paper_id=explicit_paper_id)
        if zotero_key:
            return make_runtime_paper_id(zotero_key=zotero_key)
        if doi:
            return make_runtime_paper_id(doi=doi)
    except Exception:
        return explicit_paper_id or doi or ctx.slug
    return ctx.slug


def _resolve_local_pdf_path(ctx: NoteExecutionContext) -> Path | None:
    candidates: list[Path] = []
    for key in ("pdf_path", "local_pdf_path"):
        raw = str(ctx.frontmatter.get(key) or "").strip()
        if raw:
            candidates.append(Path(raw).expanduser())

    pdf_url = str(ctx.frontmatter.get("pdf_url") or "").strip()
    if pdf_url.lower().startswith("file://"):
        local_path = unquote(urlparse(pdf_url).path or "")
        if local_path:
            candidates.append(Path(local_path).expanduser())

    for candidate in candidates:
        if candidate.exists():
            return candidate

    library_dir = Path(ctx.config.paths.library_dir).expanduser()
    if not library_dir.exists():
        return None

    tokens = [
        str(ctx.frontmatter.get("id") or "").strip(),
        str(ctx.frontmatter.get("doi") or "").strip(),
        ctx.slug,
    ]
    for token in tokens:
        if not token:
            continue
        normalized = {
            token,
            token.replace("/", "_"),
            token.replace(":", "_"),
            token.replace("/", ""),
        }
        for value in normalized:
            matches = sorted(library_dir.rglob(f"*{value}*.pdf"))
            if matches:
                return matches[0]
    return None


def _document_to_markdown(doc: Any) -> str:
    lines: list[str] = []
    metadata = getattr(doc, "metadata", None)
    title = str(getattr(metadata, "title", "") or "").strip()
    if title:
        lines.append(f"# {title}")
    sections = getattr(doc, "sections", None) or []
    for section in sections:
        heading = str(getattr(section, "name", "") or "section").strip().title()
        text = str(getattr(section, "text", "") or "").strip()
        if not text:
            continue
        lines.append(f"## {heading}")
        lines.append(text)
    tables = getattr(doc, "tables", None) or []
    if tables:
        lines.append("## Tables")
        for table in tables[:5]:
            caption = str(getattr(table, "caption", "") or "Table").strip()
            lines.append(f"- {caption}")
    return "\n\n".join(line for line in lines if line).strip()


def _handle_extract_markdown(ctx: NoteExecutionContext) -> SkillHandlerResult:
    pdf_path = _resolve_local_pdf_path(ctx)
    if pdf_path is None:
        return SkillHandlerResult(
            status="failed",
            summary="No local PDF source found for markdown extraction.",
            data={"reason": "pdf_missing"},
        )

    markdown_text = ""
    engine = "ingest_agent"
    if importlib.util.find_spec("markitdown") is not None:
        try:
            from markitdown import MarkItDown  # type: ignore

            markdown_text = str(MarkItDown().convert(str(pdf_path)).text_content or "").strip()
            engine = "markitdown"
        except Exception as exc:
            logger.info("MarkItDown unavailable for %s, falling back to IngestAgent: %s", ctx.slug, exc)

    if not markdown_text:
        ingest = IngestAgent(
            parser_backend=str(getattr(ctx.config.ingest, "parser_backend", "fitz_pdfplumber") or "fitz_pdfplumber"),
            enable_ocr_fallback=bool(getattr(ctx.config.ingest, "enable_ocr_fallback", False)),
            ocr_lang=str(getattr(ctx.config.ingest, "ocr_lang", "eng") or "eng"),
            ocr_min_text_chars=int(getattr(ctx.config.ingest, "ocr_min_text_chars", 200)),
            enable_table_pass2_ocr=bool(getattr(ctx.config.ingest, "enable_table_pass2_ocr", False)),
            enable_cloud_table_fallback=bool(getattr(ctx.config.ingest, "enable_cloud_table_fallback", False)),
            cloud_table_page_budget=int(getattr(ctx.config.ingest, "cloud_table_page_budget", 1)),
            cloud_table_model=str(getattr(ctx.config.ingest, "cloud_table_model", "gpt-4o-mini") or "gpt-4o-mini"),
            cloud_table_base_url=getattr(ctx.config.ingest, "cloud_table_base_url", None),
            cloud_table_api_key=getattr(ctx.config.ingest, "cloud_table_api_key", None),
            cloud_table_timeout_seconds=int(getattr(ctx.config.ingest, "cloud_table_timeout_seconds", 30)),
        )
        artifact = ingest.process(str(pdf_path))
        if artifact is None:
            return SkillHandlerResult(
                status="failed",
                summary="PDF ingest failed before markdown extraction.",
                data={"reason": "ingest_failed", "pdf_path": str(pdf_path)},
            )
        markdown_text = _document_to_markdown(artifact)
        section_count = len(getattr(artifact, "sections", []) or [])
        table_count = len(getattr(artifact, "tables", []) or [])
    else:
        section_count = markdown_text.count("\n## ")
        table_count = markdown_text.count("\n|")

    excerpt = markdown_text[:1600]
    summary = (
        f"Extracted markdown preview from {pdf_path.name} using {engine} "
        f"({max(section_count, 1)} sections, {table_count} tables/signals)."
    )
    return SkillHandlerResult(
        status="succeeded",
        summary=summary,
        artifacts={"pdf_path": str(pdf_path), "engine": engine},
        data={
            "section_count": max(section_count, 1),
            "table_count": max(table_count, 0),
            "markdown_excerpt": excerpt,
        },
    )


def _collect_reference_candidates(ctx: NoteExecutionContext) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _append(label: str, url: str, source: str) -> None:
        clean_label = label.strip()
        clean_url = url.strip()
        key = (clean_label, clean_url)
        if clean_label and clean_url and key not in seen:
            candidates.append({"label": clean_label, "url": clean_url, "source": source})
            seen.add(key)

    doi = str(ctx.frontmatter.get("doi") or "").strip()
    if doi:
        doi_url = doi if doi.lower().startswith("http") else f"https://doi.org/{doi}"
        _append("DOI", doi_url, "doi")

    zotero_link = str(
        ctx.frontmatter.get("zotero_link")
        or ctx.frontmatter.get("zotero_url")
        or ctx.frontmatter.get("zotero_uri")
        or ""
    ).strip()
    if zotero_link:
        _append("Zotero", zotero_link, "zotero")

    pdf_url = str(ctx.frontmatter.get("pdf_url") or "").strip()
    if pdf_url:
        _append("Open PDF", pdf_url, "pdf")

    for label, url in extract_markdown_links(extract_reference_block(ctx.body)):
        source = "external"
        if url.lower().startswith("zotero://"):
            source = "zotero"
        elif "doi.org/" in url.lower():
            source = "doi"
        elif url.lower().startswith("file://") or url.lower().endswith(".pdf"):
            source = "pdf"
        _append(label, url, source)

    return candidates


def _validate_reference(ref: dict[str, str], fetcher: OpenAlexFetcher | None) -> dict[str, Any]:
    label = ref["label"]
    url = ref["url"]
    source = ref["source"]
    result: dict[str, Any] = {"label": label, "url": url, "source": source, "status": "review"}
    if source == "zotero":
        result["status"] = "local"
        result["detail"] = "Local Zotero URI available."
        return result
    if source == "pdf":
        result["status"] = "local"
        result["detail"] = "Local or direct PDF link available."
        return result

    doi_match = DOI_PATTERN.search(url) or DOI_PATTERN.search(label)
    if doi_match:
        doi = doi_match.group(0)
        result["doi"] = doi
        if fetcher is None:
            result["status"] = "review"
            result["detail"] = "Network validation disabled by policy."
            return result
        metadata = fetcher.fetch_metadata(doi)
        if metadata:
            result["status"] = "verified"
            result["detail"] = (
                f"OpenAlex metadata found ({metadata.get('publication_year') or 'year n/a'}, "
                f"{metadata.get('citation_count', 0)} citations)."
            )
            result["metadata"] = metadata
            return result
        result["status"] = "review"
        result["detail"] = "DOI present but no metadata found in OpenAlex."
        return result

    if url.lower().startswith("http://") or url.lower().startswith("https://"):
        result["status"] = "review"
        result["detail"] = "External URL recorded; no arbitrary network probe executed."
        return result
    result["status"] = "review"
    result["detail"] = "Reference format requires manual review."
    return result


def _handle_validate_citations(ctx: NoteExecutionContext, network_enabled: bool) -> SkillHandlerResult:
    references = _collect_reference_candidates(ctx)
    fetcher = OpenAlexFetcher(email=getattr(ctx.config.system, "unpaywall_email", None)) if network_enabled else None
    checks = [_validate_reference(ref, fetcher) for ref in references]

    verified = sum(1 for item in checks if item["status"] == "verified")
    local = sum(1 for item in checks if item["status"] == "local")
    review = sum(1 for item in checks if item["status"] == "review")
    summary = f"Checked {len(checks)} references: {verified} verified, {local} local, {review} need review."
    return SkillHandlerResult(
        status="succeeded",
        summary=summary,
        data={"checks": checks, "reference_count": len(checks)},
        signals={"citation_count": len(checks)},
    )


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _candidate_paper_ids(ctx: NoteExecutionContext) -> list[str]:
    doi = str(ctx.frontmatter.get("doi") or "").strip()
    values = [
        str(ctx.frontmatter.get("id") or "").strip(),
        f"doi:{doi}" if doi else "",
        doi,
        ctx.slug,
    ]
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output


def _find_latest_artifact_paths(ctx: NoteExecutionContext) -> tuple[Path | None, Path | None]:
    root = artifacts_root()
    if not root.exists():
        return None, None

    candidates: list[tuple[float, Path, Path | None]] = []
    for paper_id in _candidate_paper_ids(ctx):
        paper_dir = artifact_paper_dir(paper_id)
        if not paper_dir.exists():
            continue
        for run_dir in paper_dir.iterdir():
            if not run_dir.is_dir():
                continue
            claimset_path = run_dir / "claimset.resolved.json"
            if not claimset_path.exists():
                claimset_path = run_dir / "claimset.json"
            if not claimset_path.exists():
                continue
            stats_path = run_dir / "stats_report.json"
            candidates.append(
                (
                    claimset_path.stat().st_mtime,
                    claimset_path,
                    stats_path if stats_path.exists() else None,
                )
            )
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def _load_claimset_payload(path: Path | None) -> dict[str, Any] | None:
    return normalize_claimset_payload(_load_json(path))


def _claim_cards_from_payload(payload: dict[str, Any]) -> list[SkillClaimCard]:
    return claim_cards_from_claimset_payload(payload)


def _bind_claim_cards_to_run(claim_cards: list[SkillClaimCard], run_id: str) -> list[SkillClaimCard]:
    return bind_claim_cards_to_run(claim_cards, run_id)


def _artifact_path_bundle(claimset_path: Path | None, stats_path: Path | None) -> dict[str, Path]:
    bundle: dict[str, Path] = {}
    if claimset_path is not None and claimset_path.exists():
        bundle["claimset"] = claimset_path
    if stats_path is not None and stats_path.exists():
        bundle["stats_report"] = stats_path
    artifact_dir = (
        claimset_path.parent
        if claimset_path is not None
        else stats_path.parent if stats_path is not None else None
    )
    if artifact_dir is None:
        return bundle
    for key, filename in {
        "reader_eval": "reader_eval.json",
        "quality_gate": "quality_gate.json",
    }.items():
        candidate = artifact_dir / filename
        if candidate.exists():
            bundle[key] = candidate
    return bundle


def _dedupe_ordered(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _evidence_locator_present(card: SkillClaimCard, evidence_index: int) -> bool:
    evidence = card.evidence[evidence_index]
    locator = evidence.locator
    if locator is None:
        return False
    return any(
        [
            isinstance(locator.page, int),
            bool(locator.section),
            bool(locator.chunk_id),
            bool(locator.span),
            locator.char_start is not None,
            locator.char_end is not None,
            locator.table_id is not None,
            locator.cell_id is not None,
            bool(locator.bbox_pdf),
            bool(locator.bbox_pct),
        ]
    )


def _quality_gate_check(quality_gate_payload: dict[str, Any] | None, check_name: str) -> dict[str, Any] | None:
    if not isinstance(quality_gate_payload, dict):
        return None
    checks = quality_gate_payload.get("checks")
    if not isinstance(checks, list):
        return None
    for item in checks:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip() == check_name:
            return item
    return None


def _normalize_appraisal_check_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"pass", "warn", "fail", "not_run"}:
        return normalized
    if normalized in {"ok", "verified", "completed", "ready", "success"}:
        return "pass"
    if normalized in {"warning", "mixed", "review"}:
        return "warn"
    if normalized in {"error", "failed", "missing"}:
        return "fail"
    return "not_run"


def _make_appraisal_check(*, code: str, label: str, status: str, detail: str) -> CriticalAppraisalCheck:
    return CriticalAppraisalCheck(
        code=code,
        label=label,
        status=_normalize_appraisal_check_status(status),
        detail=detail,
    )


def _build_appraisal_summary(
    *,
    label: str,
    claim_count: int,
    evidence_count: int,
    concern_count: int,
    stats_available: bool,
) -> str:
    if concern_count > 0:
        return (
            f"{label}: reviewed {claim_count} saved claims and {evidence_count} evidence anchors; "
            f"{concern_count} evidence-bounded concern{'s' if concern_count != 1 else ''} need follow-up."
        )
    if not stats_available:
        return (
            f"{label}: saved claims and evidence look internally reusable, "
            "but no stats report was available for this optional review lane."
        )
    return (
        f"{label}: saved claims, evidence anchors, and recorded checks look internally consistent "
        "for downstream reading review."
    )


def _build_critical_appraisal_report(
    claim_cards: list[SkillClaimCard],
    appraisal: dict[str, Any],
    *,
    stats_payload: dict[str, Any] | None,
    artifact_paths: dict[str, Path] | None = None,
    quality_gate_payload: dict[str, Any] | None = None,
    reader_eval_payload: dict[str, Any] | None = None,
) -> CriticalAppraisalReport:
    artifact_names = _dedupe_ordered(
        [path.name for path in (artifact_paths or {}).values() if isinstance(path, Path)]
    )
    stats_checks = stats_payload.get("checks") if isinstance(stats_payload, dict) else []
    if not isinstance(stats_checks, list):
        stats_checks = []

    unresolved_claim_ids: list[str] = []
    unresolved_evidence_ids: list[str] = []
    ambiguous_claim_ids: list[str] = []
    ambiguous_evidence_ids: list[str] = []
    approx_claim_ids: list[str] = []
    approx_evidence_ids: list[str] = []
    low_confidence_claim_ids: list[str] = []
    missing_locator_claim_ids: list[str] = []
    missing_locator_evidence_ids: list[str] = []
    grounded_evidence_count = 0

    for card in claim_cards:
        confidence = card.confidence if isinstance(card.confidence, (int, float)) else None
        if confidence is not None and confidence < 0.7:
            low_confidence_claim_ids.append(card.id)
        for index, evidence in enumerate(card.evidence):
            locator_source = str(
                (evidence.locator.source if evidence.locator is not None else None)
                or evidence.source
                or ""
            ).strip().lower()
            if evidence.grounded is True:
                grounded_evidence_count += 1
            if evidence.grounded is False and evidence.resolution == "AMBIGUOUS_MATCH":
                ambiguous_claim_ids.append(card.id)
                if evidence.id:
                    ambiguous_evidence_ids.append(evidence.id)
            elif evidence.grounded is False:
                unresolved_claim_ids.append(card.id)
                if evidence.id:
                    unresolved_evidence_ids.append(evidence.id)
            if locator_source == "approx":
                approx_claim_ids.append(card.id)
                if evidence.id:
                    approx_evidence_ids.append(evidence.id)
            if not _evidence_locator_present(card, index):
                missing_locator_claim_ids.append(card.id)
                if evidence.id:
                    missing_locator_evidence_ids.append(evidence.id)

    metrics = reader_eval_payload.get("metrics") if isinstance(reader_eval_payload, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}
    reader_eval_unresolved = int(metrics.get("unresolved_span_count") or 0)
    reader_eval_ambiguous = int(metrics.get("ambiguous_span_count") or 0)
    reader_eval_low_overlap = int(metrics.get("low_overlap_claim_count") or 0)
    verified_checks = int(appraisal.get("verified_checks") or 0)
    inconsistent_checks = int(appraisal.get("inconsistent_checks") or 0)
    claim_count = int(appraisal.get("claim_count") or len(claim_cards))
    evidence_count = int(appraisal.get("evidence_count") or sum(len(card.evidence) for card in claim_cards))
    stats_available = bool(isinstance(stats_payload, dict) and stats_payload)

    concerns: list[CriticalAppraisalConcern] = []
    if inconsistent_checks > 0:
        concerns.append(
            CriticalAppraisalConcern(
                code="stats_inconsistent",
                title="Saved stats checks disagree with at least one reported conclusion.",
                detail=(
                    f"{inconsistent_checks} of {len(stats_checks)} recorded checks are inconsistent. "
                    "Treat downstream critique as provisional until the saved verification lane is reconciled."
                ),
                severity="fail",
                source_artifacts=_dedupe_ordered(["stats_report.json", "quality_gate.json"]),
            )
        )
    if unresolved_evidence_ids:
        concerns.append(
            CriticalAppraisalConcern(
                code="unresolved_evidence",
                title="Some saved claims still rely on unresolved evidence anchors.",
                detail=(
                    f"{len(_dedupe_ordered(unresolved_claim_ids))} claims and {len(_dedupe_ordered(unresolved_evidence_ids))} "
                    "evidence anchors were marked unresolved."
                ),
                severity="fail",
                claim_ids=_dedupe_ordered(unresolved_claim_ids),
                evidence_ids=_dedupe_ordered(unresolved_evidence_ids),
                source_artifacts=_dedupe_ordered(["claimset.resolved.json", "reader_eval.json"]),
            )
        )
    if ambiguous_evidence_ids:
        concerns.append(
            CriticalAppraisalConcern(
                code="ambiguous_evidence",
                title="Some evidence anchors remain ambiguous rather than precisely grounded.",
                detail=(
                    f"{len(_dedupe_ordered(ambiguous_claim_ids))} claims still depend on ambiguous anchors. "
                    "These are better framed as follow-up questions than definitive critique."
                ),
                severity="warn",
                claim_ids=_dedupe_ordered(ambiguous_claim_ids),
                evidence_ids=_dedupe_ordered(ambiguous_evidence_ids),
                source_artifacts=_dedupe_ordered(["claimset.resolved.json", "reader_eval.json"]),
            )
        )
    if approx_evidence_ids:
        concerns.append(
            CriticalAppraisalConcern(
                code="approximate_locator",
                title="Some saved evidence uses approximate locator matches.",
                detail=(
                    f"{len(_dedupe_ordered(approx_evidence_ids))} evidence anchors came from approximate matching, "
                    "so precision-sensitive downstream notes should be checked before reuse."
                ),
                severity="warn",
                claim_ids=_dedupe_ordered(approx_claim_ids),
                evidence_ids=_dedupe_ordered(approx_evidence_ids),
                source_artifacts=_dedupe_ordered(["claimset.resolved.json", "reader_eval.json"]),
            )
        )
    if low_confidence_claim_ids:
        concerns.append(
            CriticalAppraisalConcern(
                code="low_confidence_claims",
                title="Some saved claims remain low-confidence.",
                detail=(
                    f"{len(_dedupe_ordered(low_confidence_claim_ids))} claims are below the 0.70 confidence threshold "
                    "used for this optional reviewer lane."
                ),
                severity="warn",
                claim_ids=_dedupe_ordered(low_confidence_claim_ids),
                source_artifacts=["claimset.resolved.json"],
            )
        )

    questions: list[CriticalAppraisalQuestion] = []
    if unresolved_evidence_ids or ambiguous_evidence_ids:
        questions.append(
            CriticalAppraisalQuestion(
                code="locator_follow_up",
                question="Which precise passage, table cell, or figure anchor should support the flagged claims?",
                rationale="The current appraisal found unresolved or ambiguous evidence links, so the next step is tighter grounding rather than free-form critique.",
                claim_ids=_dedupe_ordered(unresolved_claim_ids + ambiguous_claim_ids),
                evidence_ids=_dedupe_ordered(unresolved_evidence_ids + ambiguous_evidence_ids),
            )
        )
    if inconsistent_checks > 0:
        questions.append(
            CriticalAppraisalQuestion(
                code="stats_follow_up",
                question="Do the reported statistical conclusions still hold after the inconsistent saved checks are reconciled?",
                rationale="Stats disagreement should block strong downstream claims until the saved verification lane is aligned.",
            )
        )
    if low_confidence_claim_ids or reader_eval_low_overlap > 0:
        questions.append(
            CriticalAppraisalQuestion(
                code="scope_follow_up",
                question="Should the low-confidence or weak-overlap claims stay in the reusable note, or be downgraded to tentative context?",
                rationale="This keeps the default reading workspace focused on trustworthy claims instead of stretching the reviewer lane into product truth.",
                claim_ids=_dedupe_ordered(low_confidence_claim_ids),
            )
        )

    quality_gate_locator_check = _quality_gate_check(quality_gate_payload, "evidence_locator_quality")
    quality_gate_verification_check = _quality_gate_check(quality_gate_payload, "verification_completed")
    quality_gate_claimset_check = _quality_gate_check(quality_gate_payload, "claimset_ready")
    quality_gate_status = str((quality_gate_payload or {}).get("overall_status") or "").strip().lower()
    quality_gate_review_ready = (quality_gate_payload or {}).get("review_ready") is True

    locator_status = (
        _normalize_appraisal_check_status(quality_gate_locator_check.get("status"))
        if quality_gate_locator_check is not None
        else (
            "fail"
            if unresolved_evidence_ids
            else "warn"
            if ambiguous_evidence_ids or approx_evidence_ids or missing_locator_evidence_ids
            else "pass"
        )
    )
    locator_detail = (
        str(quality_gate_locator_check.get("detail") or "").strip()
        if quality_gate_locator_check is not None
        else (
            f"grounded={grounded_evidence_count}, ambiguous={len(_dedupe_ordered(ambiguous_evidence_ids))}, "
            f"unresolved={len(_dedupe_ordered(unresolved_evidence_ids))}, approx={len(_dedupe_ordered(approx_evidence_ids))}, "
            f"locator_missing={len(_dedupe_ordered(missing_locator_evidence_ids))}"
        )
    )

    stats_status = (
        "not_run"
        if not stats_available
        else "fail"
        if inconsistent_checks > 0
        else "warn"
        if len(stats_checks) == 0
        else "pass"
    )
    stats_detail = (
        "No saved stats report was available for this appraisal."
        if not stats_available
        else (
            f"{inconsistent_checks} inconsistent checks out of {len(stats_checks)} recorded checks."
            if inconsistent_checks > 0
            else (
                "Stats report exists but no saved checks were recorded."
                if len(stats_checks) == 0
                else f"{verified_checks} verified checks and 0 inconsistent checks."
            )
        )
    )

    verification_status = (
        _normalize_appraisal_check_status(quality_gate_verification_check.get("status"))
        if quality_gate_verification_check is not None
        else ("pass" if len(stats_checks) > 0 else "not_run")
    )
    verification_detail = (
        str(quality_gate_verification_check.get("detail") or "").strip()
        if quality_gate_verification_check is not None
        else (
            f"Recorded {len(stats_checks)} saved verification checks."
            if len(stats_checks) > 0
            else "No saved verification completion signal was available."
        )
    )

    review_ready_status = (
        "not_run"
        if quality_gate_payload is None
        else "pass"
        if quality_gate_review_ready and quality_gate_status == "pass"
        else "fail"
        if quality_gate_status == "fail"
        else "warn"
    )
    review_ready_detail = (
        "No saved quality gate was available for this optional review lane."
        if quality_gate_payload is None
        else f"quality_gate={quality_gate_status or 'unknown'}, review_ready={str(quality_gate_review_ready).lower()}"
    )

    checks = [
        _make_appraisal_check(
            code="claimset_ready",
            label="Saved claimset",
            status=(
                _normalize_appraisal_check_status(quality_gate_claimset_check.get("status"))
                if quality_gate_claimset_check is not None
                else ("pass" if claim_cards else "fail")
            ),
            detail=(
                str(quality_gate_claimset_check.get("detail") or "").strip()
                if quality_gate_claimset_check is not None
                else f"{claim_count} saved claims with {evidence_count} evidence anchors are available."
            ),
        ),
        _make_appraisal_check(
            code="evidence_locator_quality",
            label="Evidence locator quality",
            status=locator_status,
            detail=locator_detail,
        ),
        _make_appraisal_check(
            code="stats_consistency",
            label="Saved stats consistency",
            status=stats_status,
            detail=stats_detail,
        ),
        _make_appraisal_check(
            code="verification_completed",
            label="Verification completion",
            status=verification_status,
            detail=verification_detail,
        ),
        _make_appraisal_check(
            code="review_ready",
            label="Review-ready gate",
            status=review_ready_status,
            detail=review_ready_detail,
        ),
    ]

    warnings: list[str] = []
    if "reader_eval" not in (artifact_paths or {}):
        warnings.append("Reader eval sidecar was unavailable; locator quality was inferred from saved claim evidence.")
    elif reader_eval_unresolved > 0 or reader_eval_ambiguous > 0:
        warnings.append(
            f"Reader eval recorded unresolved={reader_eval_unresolved} and ambiguous={reader_eval_ambiguous} evidence spans."
        )
    if "quality_gate" not in (artifact_paths or {}):
        warnings.append("Quality gate artifact was unavailable; review-readiness stayed non-canonical and optional.")
    if missing_locator_evidence_ids:
        warnings.append(
            f"{len(_dedupe_ordered(missing_locator_evidence_ids))} evidence anchors were missing precise locator metadata."
        )

    summary = _build_appraisal_summary(
        label=str(appraisal.get("label") or "Needs review"),
        claim_count=claim_count,
        evidence_count=evidence_count,
        concern_count=len(concerns),
        stats_available=stats_available,
    )
    return CriticalAppraisalReport(
        label=str(appraisal.get("label") or "Needs review"),
        summary=summary,
        claim_count=claim_count,
        evidence_count=evidence_count,
        avg_confidence=float(appraisal.get("avg_confidence") or 0.0),
        verified_checks=verified_checks,
        inconsistent_checks=inconsistent_checks,
        checks=checks,
        concerns=concerns,
        questions=questions,
        warnings=warnings,
        source_artifacts=artifact_names,
    )


def _extract_taxonomy(ctx: NoteExecutionContext, cards: list[SkillClaimCard]) -> tuple[list[str], list[str], list[str]]:
    tags = ctx.frontmatter.get("tags")
    tag_list = [str(item).strip() for item in tags] if isinstance(tags, list) else []
    entities: list[str] = []
    mesh: list[str] = []
    outcomes: list[str] = []

    for tag in tag_list:
        if tag.startswith("Entity/"):
            entities.append(tag.split("/", 1)[1])
        elif tag.startswith("Mesh/"):
            mesh.append(tag.split("/", 1)[1])
        elif tag.startswith("Outcome/"):
            outcomes.append(tag.split("/", 1)[1])

    for card in cards:
        for tag in card.tags:
            if tag and tag not in outcomes:
                outcomes.append(tag)

    return entities, mesh, outcomes


def _build_appraisal_script(claimset_path: Path, stats_path: Path | None) -> str:
    stats_literal = f"Path({json.dumps(stats_path.name)})" if stats_path is not None else "None"
    return f"""
import json
from pathlib import Path

claimset = json.loads(Path({json.dumps(claimset_path.name)}).read_text())
stats_path = {stats_literal}
stats = json.loads(stats_path.read_text()) if stats_path and stats_path.exists() else {{}}
claims = claimset.get("claims", [])
confidences = [float(item.get("confidence", 0.0) or 0.0) for item in claims if isinstance(item, dict)]
evidence_count = 0
for item in claims:
    if isinstance(item, dict):
        evidence_count += len(item.get("evidence_spans") or item.get("evidence") or [])
checks = stats.get("checks") if isinstance(stats, dict) else []
if not isinstance(checks, list):
    checks = []
verified = sum(1 for item in checks if isinstance(item, dict) and item.get("verdict") == "verified")
inconsistent = sum(1 for item in checks if isinstance(item, dict) and item.get("verdict") == "inconsistent")
avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
if not claims:
    label = "Needs review"
elif inconsistent > 0 or avg_confidence < 0.55:
    label = "Needs review"
elif avg_confidence < 0.8:
    label = "Mixed"
else:
    label = "Strong"
print(json.dumps({{
    "label": label,
    "claim_count": len(claims),
    "evidence_count": evidence_count,
    "avg_confidence": round(avg_confidence, 4),
    "verified_checks": verified,
    "inconsistent_checks": inconsistent,
}}))
"""


def _run_critical_appraisal_in_sandbox(claimset_path: Path, stats_path: Path | None, timeout_seconds: int) -> tuple[dict[str, Any], str]:
    work_dir = claimset_path.parent / "_skills_sandbox"
    work_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(work_dir / claimset_path.name, claimset_path.read_text(encoding="utf-8"))
    if stats_path is not None and stats_path.exists():
        atomic_write_text(work_dir / stats_path.name, stats_path.read_text(encoding="utf-8"))
    sandbox = DockerSandbox(job_id=f"skills_{claimset_path.parent.name}", work_dir=str(work_dir))
    exit_code, stdout, stderr = sandbox.run_code(
        _build_appraisal_script(claimset_path=claimset_path, stats_path=stats_path),
        timeout_sec=timeout_seconds,
    )
    if exit_code != 0:
        raise RuntimeError(stderr or stdout or f"sandbox exit={exit_code}")
    payload = json.loads(stdout.strip().splitlines()[-1])
    if not isinstance(payload, dict):
        raise RuntimeError("sandbox returned non-object appraisal payload")
    return payload, "docker"


def _run_critical_appraisal_fallback(claim_cards: list[SkillClaimCard], stats_payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    confidences = [card.confidence for card in claim_cards if isinstance(card.confidence, (int, float))]
    avg_confidence = statistics.fmean(confidences) if confidences else 0.0
    evidence_count = sum(len(card.evidence) for card in claim_cards)
    checks = stats_payload.get("checks") if isinstance(stats_payload, dict) else []
    if not isinstance(checks, list):
        checks = []
    verified = sum(1 for item in checks if isinstance(item, dict) and item.get("verdict") == "verified")
    inconsistent = sum(1 for item in checks if isinstance(item, dict) and item.get("verdict") == "inconsistent")
    if not claim_cards:
        label = "Needs review"
    elif inconsistent > 0 or avg_confidence < 0.55:
        label = "Needs review"
    elif avg_confidence < 0.8:
        label = "Mixed"
    else:
        label = "Strong"
    return {
        "label": label,
        "claim_count": len(claim_cards),
        "evidence_count": evidence_count,
        "avg_confidence": round(avg_confidence, 4),
        "verified_checks": verified,
        "inconsistent_checks": inconsistent,
    }, "native-fallback"


def _handle_critical_appraisal(ctx: NoteExecutionContext, timeout_seconds: int) -> SkillHandlerResult:
    claimset_path, stats_path = _find_latest_artifact_paths(ctx)
    artifact_paths = _artifact_path_bundle(claimset_path, stats_path)
    claimset_payload = _load_claimset_payload(claimset_path)
    if not claimset_payload:
        state = visible_structured_state(
            load_structured_state(ctx.vault_path, ctx.slug, ctx.frontmatter),
            vault_path=ctx.vault_path,
        )
        if state and state.claimset:
            claim_cards = state.claimset
            stats_payload = _load_json(stats_path)
            review_artifact_paths = dict(artifact_paths)
            review_artifact_paths.setdefault("state", structured_state_path(ctx.vault_path, ctx.slug))
            appraisal, sandbox_mode = _run_critical_appraisal_fallback(claim_cards, stats_payload)
            appraisal_report = _build_critical_appraisal_report(
                claim_cards,
                appraisal,
                stats_payload=stats_payload,
                artifact_paths=review_artifact_paths,
                quality_gate_payload=_load_json(review_artifact_paths.get("quality_gate")),
                reader_eval_payload=_load_json(review_artifact_paths.get("reader_eval")),
            )
            summary = (
                f"{appraisal['label']}: reused stored ClaimSet with {appraisal['claim_count']} claims "
                f"and {appraisal['inconsistent_checks']} inconsistent checks."
            )
            return SkillHandlerResult(
                status="succeeded",
                summary=summary,
                artifacts={"claimset_source": "state.json", "sandbox": sandbox_mode},
                data={"appraisal": appraisal, "appraisal_report": appraisal_report.model_dump()},
                signals={"last_appraisal": appraisal["label"]},
            )
        return SkillHandlerResult(
            status="failed",
            summary="No ClaimSet artifact or structured ClaimSet available for appraisal.",
            data={"reason": "claimset_missing"},
        )

    claim_cards = _claim_cards_from_payload(claimset_payload)
    stats_payload = _load_json(stats_path)
    try:
        appraisal, sandbox_mode = _run_critical_appraisal_in_sandbox(
            claimset_path=claimset_path,
            stats_path=stats_path,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        logger.warning("Critical appraisal sandbox fallback for %s: %s", ctx.slug, exc)
        appraisal, sandbox_mode = _run_critical_appraisal_fallback(claim_cards, stats_payload)

    appraisal_report = _build_critical_appraisal_report(
        claim_cards,
        appraisal,
        stats_payload=stats_payload,
        artifact_paths=artifact_paths,
        quality_gate_payload=_load_json(artifact_paths.get("quality_gate")),
        reader_eval_payload=_load_json(artifact_paths.get("reader_eval")),
    )
    entities, mesh, outcomes = _extract_taxonomy(ctx, claim_cards)
    summary = (
        f"{appraisal['label']}: {appraisal['claim_count']} claims, "
        f"avg confidence {appraisal['avg_confidence']:.2f}, "
        f"{appraisal['inconsistent_checks']} inconsistent checks."
    )
    return SkillHandlerResult(
        status="succeeded",
        summary=summary,
        artifacts={
            "claimset_path": str(claimset_path) if claimset_path else None,
            "stats_report_path": str(stats_path) if stats_path else None,
            "sandbox": sandbox_mode,
        },
        data={"appraisal": appraisal, "appraisal_report": appraisal_report.model_dump()},
        claimset=[card.model_dump() for card in claim_cards],
        entities=entities,
        mesh=mesh,
        outcomes=outcomes,
        signals={"last_appraisal": appraisal["label"]},
    )


def _note_context(slug: str) -> NoteExecutionContext:
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    note_path = resolve_note_path(vault_path, slug)
    if note_path is None:
        raise FileNotFoundError(f"Paper note not found for slug={slug}")
    content = safe_read_text(note_path)
    frontmatter, body = split_frontmatter(content)
    return NoteExecutionContext(
        slug=slug,
        note_path=note_path,
        vault_path=vault_path,
        frontmatter=frontmatter,
        body=body,
        config=config,
    )


def run_skill_action(request: SkillRunRequest) -> SkillRunResponse:
    ctx = _note_context(request.slug)
    policy = get_action_policy(request.action)
    if not policy.enabled:
        raise PermissionError(f"Action disabled by policy: {request.action}")
    for secret in policy.secrets_required:
        if not secret:
            continue
        if not os.getenv(secret):
            raise PermissionError(f"Missing required secret for {request.action}: {secret}")

    if request.action == "extract_markdown":
        handler_result = _handle_extract_markdown(ctx)
    elif request.action == "validate_citations":
        handler_result = _handle_validate_citations(ctx, network_enabled=policy.network != "none")
    else:
        handler_result = _handle_critical_appraisal(ctx, timeout_seconds=policy.timeout_seconds)

    ts = _now_iso()
    run_id = f"skill-{_run_stamp(ts)}-{request.action}"
    run_artifacts = dict(handler_result.artifacts)
    run_artifacts["structured_path"] = structured_relpath(ctx.slug)
    run_artifacts["write_scope"] = {
        "structured_state": True,
        "frontmatter_pp": True,
        "markdown_summary": request.append_markdown_summary,
    }
    run_record = SkillRunRecord(
        id=run_id,
        action=request.action,
        ts=ts,
        status=handler_result.status,
        summary=handler_result.summary,
        artifacts=run_artifacts,
        data=handler_result.data,
    )
    claimset_cards = None
    if handler_result.claimset is not None:
        claimset_cards = [SkillClaimCard.model_validate(item) for item in handler_result.claimset]
        claimset_cards = _bind_claim_cards_to_run(claimset_cards, run_id)

    existing_state = visible_structured_state(
        load_structured_state(ctx.vault_path, ctx.slug, ctx.frontmatter),
        vault_path=ctx.vault_path,
    )
    reference_count = len(_collect_reference_candidates(ctx))
    signal_payload = {
        "citation_count": reference_count,
        **handler_result.signals,
    }
    merged_state = merge_state(
        ctx.slug,
        existing_state,
        run_record,
        claimset=claimset_cards,
        entities=handler_result.entities,
        mesh=handler_result.mesh,
        outcomes=handler_result.outcomes,
        signals=signal_payload,
    )

    run_stamp = _run_stamp(ts)
    run_output_path = structured_run_path(ctx.vault_path, ctx.slug, run_stamp, request.action)
    state_output_path = structured_state_path(ctx.vault_path, ctx.slug)
    raw_payload = {
        "paper_slug": ctx.slug,
        "note_path": str(ctx.note_path.relative_to(ctx.vault_path)),
        "run": run_record.model_dump(),
        "policy": {
            "license": policy.license,
            "sandbox": policy.sandbox,
            "network": policy.network,
            "network_allowlist": list(policy.network_allowlist),
            "secrets_required": list(policy.secrets_required),
            "timeout_seconds": policy.timeout_seconds,
        },
        "logs": handler_result.logs,
        "data": handler_result.data,
    }
    atomic_write_text(run_output_path, json.dumps(raw_payload, ensure_ascii=False, indent=2))
    write_structured_state(state_output_path, merged_state)

    updated_frontmatter = update_frontmatter_pp(
        ctx.frontmatter,
        merged_state,
        run_record,
        signals=signal_payload,
    )
    updated_body = ctx.body
    if request.append_markdown_summary:
        short_line = (
            f"- {ts} {request.action}: {handler_result.summary} "
            f"(structured: {updated_frontmatter['pp']['structured_path']})"
        )
        updated_body = upsert_automation_results_section(updated_body, short_line)
    atomic_write_text(ctx.note_path, compose_note(updated_frontmatter, updated_body))

    relative_note_path = str(ctx.note_path.relative_to(ctx.vault_path))
    _best_effort_log_user_action(
        paper_id=_paper_id_for_note_context(ctx),
        action_type="skill_run",
        source="ui",
        payload={
            "action": request.action,
            "slug": ctx.slug,
            "run_id": run_id,
            "status": handler_result.status,
            "append_markdown_summary": bool(request.append_markdown_summary),
            "structured_path": updated_frontmatter["pp"]["structured_path"],
            "note_path": relative_note_path,
        },
    )
    return SkillRunResponse(
        slug=ctx.slug,
        note_path=relative_note_path,
        structured_path=updated_frontmatter["pp"]["structured_path"],
        run=run_record,
        state=merged_state,
        frontmatter_pp=updated_frontmatter["pp"],
    )

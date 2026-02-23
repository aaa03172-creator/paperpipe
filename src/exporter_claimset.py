from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.artifact_paths import iter_paper_dir_candidates


def extract_claimset_claims(feedback: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(feedback, dict):
        return None
    if isinstance(feedback.get("claims"), list):
        return feedback["claims"]
    claimset = feedback.get("ClaimSet")
    if isinstance(claimset, dict) and isinstance(claimset.get("claims"), list):
        return claimset["claims"]
    claimset = feedback.get("claimset")
    if isinstance(claimset, dict) and isinstance(claimset.get("claims"), list):
        return claimset["claims"]
    return None


def claimset_artifacts_root() -> Path:
    env_root = os.getenv("PAPERPIPE_ARTIFACTS_DIR")
    if env_root:
        return Path(env_root).expanduser()
    return Path(__file__).resolve().parents[1] / "storage" / "artifacts"


def is_test_fixture_paper(paper: Dict[str, Any]) -> bool:
    paper_id = str(paper.get("paper_id") or "")
    pdf_path = str(paper.get("pdf_path") or "")
    return (
        paper_id.startswith("local--")
        or "_test_" in paper_id
        or paper_id.startswith("integration_test_")
        or paper_id == "phase0_test"
        or "/tests/" in pdf_path.replace("\\", "/")
    )


def extract_claimset_claims_from_file(path: Path) -> Optional[List[Dict[str, Any]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    claims = data.get("claims")
    if isinstance(claims, list):
        if claims and isinstance(claims[0], dict) and "statement" in claims[0]:
            return claims

        # Contract bridge: claimset.resolved.json stores {"text", "evidence"}.
        bridged: List[Dict[str, Any]] = []
        for item in claims:
            if not isinstance(item, dict):
                continue
            text = item.get("statement") or item.get("text")
            if not text:
                continue
            evidence_spans: List[Dict[str, Any]] = []
            evidence = item.get("evidence")
            if isinstance(evidence, list):
                for ev in evidence:
                    if not isinstance(ev, dict):
                        continue
                    evidence_spans.append(
                        {
                            "chunk_id": ev.get("chunk_id"),
                            "quote": ev.get("quote"),
                            "page": ev.get("page"),
                            "grounded": ev.get("grounded"),
                            "resolution": ev.get("resolution"),
                        }
                    )
            bridged.append(
                {
                    "claim_id": item.get("claim_id") or "unknown",
                    "type": item.get("type") or "unknown",
                    "statement": text,
                    "evidence_spans": evidence_spans,
                }
            )
        if bridged:
            return bridged
        return claims
    return None


def extract_claimset_claims_from_artifacts(
    paper_id: str,
    paper_key: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    for paper_dir in iter_paper_dir_candidates(paper_id=paper_id, paper_key=paper_key):
        if not paper_dir.exists():
            continue
        candidates = []
        candidates.extend(paper_dir.glob("*/claimset.resolved.json"))
        candidates.extend(paper_dir.glob("*/claimset.json"))
        candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
        for candidate in candidates:
            claims = extract_claimset_claims_from_file(candidate)
            if claims is not None:
                return claims
    return None


def resolve_claimset_claims(paper: Dict[str, Any], feedback: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    claims = extract_claimset_claims(feedback)
    if claims is not None:
        return claims
    paper_id = paper.get("paper_id")
    if not paper_id:
        return None
    return extract_claimset_claims_from_artifacts(
        paper_id=str(paper_id),
        paper_key=str(paper.get("paper_key") or "").strip() or None,
    )


def resolve_evidence_link(paper: Dict[str, Any], page_num: Optional[int]) -> Optional[str]:
    zotero_key = (paper.get("zotero_key") or "").strip()
    if not zotero_key or page_num is None:
        return None
    try:
        page = int(page_num)
    except (TypeError, ValueError):
        return None
    if page < 0:
        return None
    return f"zotero://open-pdf/library/items/{zotero_key}?page={page + 1}"


def format_claimset_section(paper: Dict[str, Any], claims: Optional[List[Dict[str, Any]]]) -> str:
    if not claims:
        return "## Critical Review (ClaimSet)\nClaimSet: unavailable\n"

    lines = ["## Critical Review (ClaimSet)"]
    for idx, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            continue
        statement = claim.get("statement") or "N/A"
        limitations = claim.get("limitations")
        confidence = claim.get("confidence", "N/A")
        evidence_spans = claim.get("evidence_spans")
        evidence_line = "Evidence: unavailable"

        if isinstance(evidence_spans, list) and evidence_spans:
            span = evidence_spans[0] if isinstance(evidence_spans[0], dict) else {}
            quote = span.get("quote") or span.get("raw_text") or "N/A"
            page_num = span.get("page")
            page_hint = "N/A"
            if isinstance(page_num, int):
                page_hint = str(page_num)
            link = resolve_evidence_link(paper, page_num if isinstance(page_num, int) else None)
            evidence_parts = [f'quote="{quote}"', f"page_num={page_hint}"]
            if link:
                evidence_parts.append(f"link={link}")
            evidence_line = "Evidence: " + ", ".join(evidence_parts)

        if isinstance(limitations, list):
            limitations_text = "; ".join([str(x) for x in limitations if str(x).strip()]) or "N/A"
        else:
            limitations_text = "N/A"

        lines.extend(
            [
                f"### Claim {idx}",
                f"- Claim: {statement}",
                f"- {evidence_line}",
                f"- Limitations: {limitations_text}",
                f"- Confidence: {confidence}",
            ]
        )

    if len(lines) == 1:
        lines.append("ClaimSet: unavailable")
    return "\n".join(lines) + "\n"


def span_missing_location(span: Any) -> bool:
    if not isinstance(span, dict):
        return True
    page = span.get("page")
    has_page = isinstance(page, int) and page >= 0
    has_source_span = isinstance(span.get("source_span"), list) and len(span.get("source_span")) >= 2
    has_char = span.get("char_start") is not None and span.get("char_end") is not None
    return not (has_page or has_source_span or has_char)


def feedback_needs_stats_check(feedback: Dict[str, Any]) -> bool:
    targets = {"unverifiable", "inconsistent"}

    def _walk(node: Any) -> bool:
        if isinstance(node, dict):
            verdict = node.get("verdict")
            if isinstance(verdict, str) and verdict.lower() in targets:
                return True
            for value in node.values():
                if _walk(value):
                    return True
        elif isinstance(node, list):
            for item in node:
                if _walk(item):
                    return True
        return False

    return _walk(feedback)

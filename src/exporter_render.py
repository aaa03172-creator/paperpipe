from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.exporter_claimset import format_claimset_section, resolve_claimset_claims
from src.exporter_helpers import (
    build_institutional_download_block,
    build_pdf_links,
    build_zotero_links,
    sanitize_frontmatter_tag,
)


def load_feedback_dict(feedback_json: str | None) -> dict[str, Any]:
    try:
        feedback = json.loads(feedback_json or "{}")
    except Exception:
        feedback = {}
    if not isinstance(feedback, dict):
        feedback = {}
    return feedback


def build_obsidian_tags(hard_tags: dict[str, Any], soft_tags: list[Any]) -> list[str]:
    obsidian_tags = []

    study_type = hard_tags.get("study_type")
    if study_type:
        safe_type = str(study_type).replace(" ", "_")
        obsidian_tags.append(f"Type/{safe_type}")

    for tag in soft_tags:
        safe_tag = sanitize_frontmatter_tag(tag)
        if safe_tag:
            obsidian_tags.append(safe_tag)
    return obsidian_tags


def resolve_verdict(confidence: Any) -> str:
    verdict = "❓ Unknown"
    try:
        f_conf = float(confidence)
        if f_conf >= 0.9:
            verdict = "🌟 Strongly Approved"
        elif f_conf >= 0.7:
            verdict = "✅ Approved"
        else:
            verdict = "⚠️ Low Confidence"
    except (TypeError, ValueError):
        pass
    return verdict


def build_findings_list(feedback: dict[str, Any]) -> str:
    evidence = feedback.get("evidence_snippets", [])
    findings_list = ""
    if evidence:
        for ev in evidence:
            loc = ev.get("location", "Text")
            txt = ev.get("snippet", "")
            sup = ev.get("supports", "")
            findings_list += f"* **[{loc}]**: {txt} (Supports: *{sup}*)\n"
    elif feedback.get("evidence_span"):
        span = feedback.get("evidence_span")
        findings_list = f"* **[Abstract/Text]**: {span} (Primary Evidence)\n"
    else:
        findings_list = "* *No granular findings extracted.*"
    return findings_list


def should_write_markdown(target_file: Path, paper: dict[str, Any], overwrite: bool) -> bool:
    if overwrite:
        return True
    if not target_file.exists():
        return True
    try:
        file_mtime = target_file.stat().st_mtime
        db_updated_str = paper.get("updated_at")
        if db_updated_str:
            dt_db = datetime.fromisoformat(db_updated_str)
            ts_db = dt_db.timestamp()
            if ts_db > file_mtime:
                return True
    except Exception:
        pass
    return False


def build_markdown_content(paper: Dict[str, Any], vault_path: Path) -> str:
    pid = paper["paper_id"]
    title = paper["title"] or "Untitled"
    summary = paper["summary"] or "No summary available."
    feedback = load_feedback_dict(paper.get("feedback_json"))

    hard_tags = feedback.get("hard_tags", {})
    soft_tags = feedback.get("soft_tags", [])
    confidence = paper.get("confidence")
    if confidence is None:
        confidence = feedback.get("confidence", 0.0)

    obsidian_tags = build_obsidian_tags(hard_tags, soft_tags)
    verdict = resolve_verdict(confidence)
    design_tag = hard_tags.get("design", "Unknown")
    findings_list = build_findings_list(feedback)

    links: List[str] = []
    links.extend(build_zotero_links(paper))
    links.extend(build_pdf_links(paper, vault_path))
    references_block = "\n".join([f"* {link}" for link in links]) if links else "*No external links available.*"
    institutional_block = build_institutional_download_block(paper, feedback)
    claimset_claims = resolve_claimset_claims(paper, feedback)
    claimset_block = format_claimset_section(paper, claimset_claims)

    today = datetime.now().strftime("%Y-%m-%d")

    return f"""---
id: {pid}
aliases: [\"{title.replace('"', '')}\"]
tags:
{chr(10).join([f"  - {tag}" for tag in obsidian_tags])}
date_processed: {today}
confidence: {confidence}
status: {paper['status']}
---

# {title}

> **One-Line Summary**
> {summary}

## 📊 Critical Analysis
* **Study Design:** {design_tag}
* **Professor's Verdict:** {verdict} ({confidence})

### Key Findings & Evidence
{findings_list}

{claimset_block}

## 🔗 References
{references_block}

{institutional_block}
"""

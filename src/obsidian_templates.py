from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.schemas import PaperStatus, TrialExtraction


def get_status_callout(paper: Dict[str, Any]) -> str:
    """Action Gates 상태에 따른 Callout 생성"""
    if paper.get("is_retracted"):
        return (
            "\n> [!danger] ☠️ RETRACTED PAPER\n"
            f"> **Details**: {paper.get('retraction_details', 'No details provided.')}\n"
        )

    status_str = paper.get("processing_status")
    if status_str == PaperStatus.QUARANTINED:
        return (
            "\n> [!danger] Low Confidence - Quarantined\n"
            "> This paper has been flagged for low confidence and isolated.\n"
        )
    if status_str == PaperStatus.PENDING_REVIEW:
        return (
            "\n> [!warning] Requires Human Review\n"
            "> Confidence score is in the intermediate range.\n"
        )
    if status_str == PaperStatus.APPROVED:
        if paper.get("is_escalated"):
            reason = paper.get("escalation_reason", "Judge Approved")
            return (
                "\n> [!success] Auto-Approved (Escalated)\n"
                f"> **Judge Decision**: {reason}\n"
            )
        return ""
    return ""


def get_template_study(paper: Dict[str, Any]) -> str:
    """기전/방법론 연구용 노트 템플릿"""
    one_liner_section = ""
    if paper.get("ai_one_liner"):
        one_liner_section = f"## 🧠 One-Liner\n> {paper['ai_one_liner']}\n"

    ai_summary_section = ""
    if paper.get("ai_mode") != "one-liner":
        ai_summary_section = (
            f"## 🧠 AI Summary ({paper.get('ai_mode', 'simple')})\n"
            f"{paper.get('ai_summary', 'Not available.')}\n"
        )

    hybrid_tags = paper.get("hybrid_tags", {})
    evidence_block = ""
    if isinstance(hybrid_tags, dict) and (
        hybrid_tags.get("evidence_span") or hybrid_tags.get("confidence")
    ):
        conf_score = hybrid_tags.get("confidence", 0.0)
        evidence_block = f'''
> [!info] Evidence & Confidence
> **Confidence**: {conf_score:.2f}
> **Evidence**: "{hybrid_tags.get('evidence_span', "N/A")}"
'''

    relevance_block = ""
    relevance = paper.get("relevance_analysis")
    if relevance:
        relevance_block = f'''
## 🧠 Context-Aware Analysis
> **Gap**: {relevance.get('gap', 'N/A')}
> **Insight**: {relevance.get('insight', 'N/A')}
> **Limitation**: {relevance.get('limitation', 'N/A')}
'''

    tags_list = str(paper.get("tags", [])).replace("'", '"')

    return f"""---
type: paper
aliases: ["{paper['title']}"]
tags: {tags_list}
cssclasses: ["paper-note"]
status: {paper.get('reading_status', 'Inbox')}
created: {datetime.now().strftime('%Y-%m-%d')}
source: {paper['source']}
url: {paper['link']}
slot: {paper['slot']}
---

# {paper['title']}

{one_liner_section}
{evidence_block}
{relevance_block}
{ai_summary_section}

## 📝 Notes
- 
"""


def extract_intervention_string(td: Dict[str, Any]) -> str:
    """Trial data 딕셔너리에서 상세 Intervention 문자열 생성"""
    inter = td.get("intervention", {})
    flags = td.get("eligibility_flags", {})

    int_parts = []
    category = inter.get("category", "unknown")
    product_name = inter.get("product_name")

    if category != "unknown":
        cat_display = category.replace("_", " ").title()
        if product_name:
            cat_display += f" ({product_name})"
        int_parts.append(cat_display)
    elif product_name:
        int_parts.append(product_name)

    dose_value = inter.get("dose_value", 0.0)
    dose_unit = inter.get("dose_unit", "unknown")
    dose_schedule = inter.get("dose_schedule")

    if dose_value > 0:
        unit = dose_unit.replace("_per_day", "/d") if dose_unit != "unknown" else ""
        int_parts.append(f"{dose_value:.1f}{unit}")
    elif dose_schedule:
        int_parts.append(dose_schedule)

    duration_weeks = inter.get("duration_weeks", 0)
    if duration_weeks > 0:
        int_parts.append(f"{duration_weeks} weeks")

    intervention_str = ", ".join(int_parts)
    if not intervention_str:
        tag = flags.get("separate_analysis_tag", "unknown")
        if tag != "unknown":
            tag_clean = tag.replace("_", " ").title()
            intervention_str = f"{tag_clean} (Unspecified details)"
        else:
            intervention_str = "Not detailed"
    return intervention_str


def get_template_trial(paper: Dict[str, Any], extraction: Optional[TrialExtraction] = None) -> str:
    """임상 연구용 템플릿 (추출 데이터 반영)"""
    tags_list = str(paper.get("tags", [])).replace("'", '"')
    status = paper.get("reading_status", "Inbox")

    one_liner_section = ""
    if paper.get("ai_one_liner"):
        one_liner_section = f"## 🧠 One-Liner\n> {paper['ai_one_liner']}\n"

    hybrid_tags = paper.get("hybrid_tags", {})
    evidence_block = ""
    if isinstance(hybrid_tags, dict) and (
        hybrid_tags.get("evidence_span") or hybrid_tags.get("confidence")
    ):
        conf_score = hybrid_tags.get("confidence", 0.0)
        callout_type = "success" if conf_score >= 0.8 else "warning"
        evidence_block = f'''
> [!{callout_type}] Evidence & Confidence
> **Confidence**: {conf_score:.2f}
> **Evidence**: "{hybrid_tags.get('evidence_span', "N/A")}"
'''

    if extraction:
        summary_block = extraction.to_summary_block()
        data_block = (
            "## 📊 Extracted Data (JSON)\n```json\n"
            + extraction.model_dump_json(indent=2)
            + "\n```\n"
        )
    else:
        fail_content = paper.get("ai_summary", "No data available.")
        if paper.get("ai_mode") == "one-liner":
            fail_content = "See One-Liner above."
        summary_block = f"> [!warning] Extraction Failed\n> {fail_content}"
        data_block = """## 📊 Data Extraction
| Metric | Result | p-value |
|--------|--------|---------|
|        |        |         |
"""

    relevance_block = ""
    relevance = paper.get("relevance_analysis")
    if relevance:
        relevance_block = f'''
## 🧠 Context-Aware Analysis
> **Gap**: {relevance.get('gap', 'N/A')}
> **Insight**: {relevance.get('insight', 'N/A')}
> **Limitation**: {relevance.get('limitation', 'N/A')}
'''

    institutional_block = ""
    if not paper.get("local_pdf_path"):
        from src.institutional_access import extract_institutional_proxy_link

        proxy_url = extract_institutional_proxy_link(paper.get("feedback_json"))
        if proxy_url:
            institutional_block = f"""
> [!info] 🪪 Institutional Access Available
> PDF was not auto-downloaded. [Download via KNU Libproxy]({proxy_url})
"""

    return f"""---
type: clinical_trial
aliases: ["{paper['title']}"]
tags: {tags_list}
cssclasses: ["clinical-note"]
status: {status}
created: {datetime.now().strftime('%Y-%m-%d')}
url: {paper['link']}
slot: {paper['slot']}
doi: {paper['doi']}
---

# {paper['title']}
{institutional_block}
{one_liner_section}
## 🏥 Trial Quick Look
{summary_block}

{evidence_block}
{relevance_block}

{data_block}

## Abstract
{paper.get('summary', 'No abstract available.')}
"""

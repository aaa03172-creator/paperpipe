from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.obsidian_templates import extract_intervention_string


def index_headers(is_clinical: bool) -> list[str]:
    headers = [
        "Date",
        "Slot",
        "Paper_ID",
        "Title",
        "DOI",
        "Source",
        "URL",
        "Score",
        "Status",
        "Note_Path",
        "Tags",
        "Authors",
    ]
    if is_clinical:
        headers.extend(["Population", "Intervention", "Outcome_Cognition", "Outcome_ADL"])
    return headers


def build_note_path(
    paper: Dict[str, Any],
    *,
    today: str,
    relative_note_path: Optional[str],
) -> str:
    if relative_note_path:
        return relative_note_path
    safe_title = "".join(
        c for c in paper.get("title", "")[:50] if c.isalnum() or c in (" ", "-", "_")
    ).strip()
    return f"Inbox/{today}/{paper.get('slot', 'Paper')}_{safe_title}.md"


def clinical_fields_from_paper(paper: Dict[str, Any]) -> tuple[str, str, str, str]:
    if not paper.get("trial_data"):
        return "", "", "", ""

    td = paper["trial_data"]
    pop = td.get("population", {})
    pop_str = "MCI-only" if pop.get("mci_only") else "Mixed"
    if not pop.get("mci_only"):
        notes = pop.get("comorbidity_notes")
        if notes:
            pop_str += f" ({notes})"

    int_str = extract_intervention_string(td)
    cog_str = "Reported" if td.get("outcomes", {}).get("cognition") else ""
    adl_str = "Yes" if td.get("outcomes", {}).get("adl_function") else "No"
    return pop_str, int_str, cog_str, adl_str


def is_same_slot_row(
    row: Dict[str, Any],
    *,
    today: str,
    paper_slot: str,
    is_clinical: bool,
) -> bool:
    same_slot = (row.get("Date") == today) and (row.get("Slot", "").lower() == paper_slot.lower())
    if is_clinical and row.get("Date") == today:
        return True
    return same_slot


def merged_index_row(
    *,
    paper: Dict[str, Any],
    today: str,
    paper_id: str,
    note_path: str,
    tags_val: str,
    authors_val: str,
    is_clinical: bool,
) -> Dict[str, Any]:
    row = {
        "Date": today,
        "Slot": paper.get("slot", "N/A"),
        "Paper_ID": paper_id,
        "Title": paper.get("title", ""),
        "DOI": paper.get("doi", ""),
        "Source": paper.get("source", ""),
        "URL": paper.get("link", ""),
        "Score": "Top1",
        "Status": paper.get("reading_status", "Inbox"),
        "Note_Path": note_path,
        "Tags": tags_val,
        "Authors": authors_val,
    }
    if is_clinical:
        pop_str, int_str, cog_str, adl_str = clinical_fields_from_paper(paper)
        row["Population"] = pop_str
        row["Intervention"] = int_str
        row["Outcome_Cognition"] = cog_str
        row["Outcome_ADL"] = adl_str
    return row


def now_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

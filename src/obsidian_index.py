from __future__ import annotations

import csv
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.obsidian_templates import extract_intervention_string

logger = logging.getLogger(__name__)


def find_related_papers(current_paper: Dict[str, Any], config) -> str:
    """
    Smart Linking: Find related papers from the CSV index based on shared tags.
    Returns a markdown list of links.
    """
    index_path = config.paths.obsidian_vault / config.paths.index_all
    if not index_path.exists():
        return ""

    related_links = []
    current_tags = set(current_paper.get("tags", []))
    current_id = current_paper.get("doi") or current_paper.get("link")

    try:
        with open(index_path, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("Paper_ID") == current_id:
                    continue

                row_tags = set(row.get("Tags", "").split(";"))
                overlap = current_tags.intersection(row_tags)

                if len(overlap) >= 2 or (
                    row.get("Slot") == current_paper.get("slot") and len(overlap) >= 1
                ):
                    note_path = row.get("Note_Path", "")
                    if note_path:
                        filename = Path(note_path).name.replace(".md", "")
                        link = f"- [[{filename}]] (Shared: {', '.join(list(overlap)[:3])})"
                        related_links.append(link)

        if related_links:
            return "\n## 🔗 Related Papers\n" + "\n".join(related_links[:5]) + "\n"
    except Exception as exc:
        logger.warning(f"Failed to find related papers: {exc}")
    return ""


def update_csv_index(
    paper: Dict[str, Any],
    file_path: Path,
    is_clinical: bool = False,
    relative_note_path: Optional[str] = None,
):
    """
    Date+Slot 기준으로 중복 방지(upsert).
    """
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

    rows = []
    updated = False
    today = datetime.now().strftime("%Y-%m-%d")
    paper_id = paper.get("doi") or paper.get("link") or "unknown_id"

    if relative_note_path:
        note_path = relative_note_path
    else:
        safe_title = "".join(
            c for c in paper.get("title", "")[:50] if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        note_path = f"Inbox/{today}/{paper.get('slot', 'Paper')}_{safe_title}.md"

    tags_val = ";".join(paper.get("tags", []))
    authors_val = ";".join(paper.get("authors", []))

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                is_same_slot = (row.get("Date") == today) and (
                    row.get("Slot", "").lower() == paper.get("slot", "").lower()
                )
                if is_clinical and row.get("Date") == today:
                    is_same_slot = True

                if is_same_slot:
                    row["Paper_ID"] = paper_id
                    row["Date"] = today
                    row["Title"] = paper.get("title", "")
                    row["DOI"] = paper.get("doi", "")
                    row["Source"] = paper.get("source", "")
                    row["URL"] = paper.get("link", "")
                    row["Note_Path"] = note_path
                    row["Score"] = "Top1"
                    row["Tags"] = tags_val
                    row["Authors"] = authors_val

                    if is_clinical and paper.get("trial_data"):
                        td = paper["trial_data"]
                        pop = td.get("population", {})
                        pop_desc = "MCI-only" if pop.get("mci_only") else "Mixed"
                        if not pop.get("mci_only"):
                            notes = pop.get("comorbidity_notes")
                            if notes:
                                pop_desc += f" ({notes})"
                        row["Population"] = pop_desc
                        row["Intervention"] = extract_intervention_string(td)
                        row["Outcome_Cognition"] = (
                            "Reported" if td.get("outcomes", {}).get("cognition") else ""
                        )
                        row["Outcome_ADL"] = (
                            "Yes" if td.get("outcomes", {}).get("adl_function") else "No"
                        )

                    row["Status"] = paper.get("reading_status", "Inbox")
                    updated = True

                for header in headers:
                    row.setdefault(header, "")
                rows.append(row)

    if not updated:
        pop_str, int_str, cog_str, adl_str = "", "", "", ""
        if is_clinical and paper.get("trial_data"):
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

        new_row = {
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
            new_row["Population"] = pop_str
            new_row["Intervention"] = int_str
            new_row["Outcome_Cognition"] = cog_str
            new_row["Outcome_ADL"] = adl_str
        for header in headers:
            new_row.setdefault(header, "")
        rows.append(new_row)

    with open(file_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def set_reading_status(paper_id_or_doi: str, new_status: str, config) -> Optional[str]:
    """
    Updates reading status in CSV index and markdown frontmatter.
    Returns DOI if found, else None.
    """
    vault_path = config.paths.obsidian_vault
    potential_indexes = [
        config.paths.index_all,
        "00_Index/on_demand.csv",
        "00_Index/manual_collection.csv",
    ]

    target_doi = None
    target_note_path = None

    for relative_idx_path in potential_indexes:
        index_path = vault_path / relative_idx_path
        if not index_path.exists():
            continue

        updated_rows = []
        found_in_this_file = False
        headers = []

        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                headers = reader.fieldnames
                for row in reader:
                    pid = row.get("Paper_ID", "")
                    doi = row.get("DOI", "")
                    title = row.get("Title", "")

                    if paper_id_or_doi == pid or paper_id_or_doi == doi or paper_id_or_doi == title:
                        row["Status"] = new_status
                        target_doi = doi
                        note_rel = row.get("Note_Path")
                        if note_rel:
                            target_note_path = vault_path / note_rel
                        found_in_this_file = True

                    updated_rows.append(row)

            if found_in_this_file:
                with open(index_path, "w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(updated_rows)
                logger.info(f"Updated status in index: {relative_idx_path}")
                break
        except Exception as exc:
            logger.error(f"Failed to read/update index {relative_idx_path}: {exc}")

    if target_note_path and target_note_path.exists():
        try:
            content = target_note_path.read_text(encoding="utf-8")
            new_content = re.sub(
                r"^status:.*$",
                f"status: {new_status}",
                content,
                count=1,
                flags=re.MULTILINE,
            )
            target_note_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Updated status in note: {target_note_path}")
        except Exception as exc:
            logger.error(f"Failed to update markdown note: {exc}")

    return target_doi

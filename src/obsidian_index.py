from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from src.obsidian_index_csv import (
    build_note_path,
    index_headers,
    is_same_slot_row,
    merged_index_row,
    now_date_str,
)

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
    headers = index_headers(is_clinical)

    rows = []
    updated = False
    today = now_date_str()
    paper_id = paper.get("doi") or paper.get("link") or "unknown_id"

    note_path = build_note_path(paper, today=today, relative_note_path=relative_note_path)

    tags_val = ";".join(paper.get("tags", []))
    authors_val = ";".join(paper.get("authors", []))

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                same_slot = is_same_slot_row(
                    row,
                    today=today,
                    paper_slot=paper.get("slot", ""),
                    is_clinical=is_clinical,
                )

                if same_slot:
                    row.update(
                        merged_index_row(
                            paper=paper,
                            today=today,
                            paper_id=paper_id,
                            note_path=note_path,
                            tags_val=tags_val,
                            authors_val=authors_val,
                            is_clinical=is_clinical,
                        )
                    )
                    updated = True

                for header in headers:
                    row.setdefault(header, "")
                rows.append(row)

    if not updated:
        new_row = merged_index_row(
            paper=paper,
            today=today,
            paper_id=paper_id,
            note_path=note_path,
            tags_val=tags_val,
            authors_val=authors_val,
            is_clinical=is_clinical,
        )
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

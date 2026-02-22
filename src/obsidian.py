from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.obsidian_index import find_related_papers, set_reading_status, update_csv_index
from src.obsidian_templates import (
    extract_intervention_string,
    get_status_callout,
    get_template_study,
    get_template_trial,
)
from src.schemas import PaperStatus, TrialExtraction

logger = logging.getLogger(__name__)

# Backward-compatible aliases for existing imports/tests.
_get_status_callout = get_status_callout
_extract_intervention_string = extract_intervention_string


def save_paper_to_obsidian(
    paper: Dict[str, Any],
    config,
    extraction: Optional[TrialExtraction] = None,
    subfolder_override: Optional[str] = None,
    index_file_override: Optional[str] = None,
):
    """마크다운 노트 생성 + CSV 인덱스 기록"""
    vault_path = config.paths.obsidian_vault

    if subfolder_override:
        today_folder = vault_path / subfolder_override
    elif paper.get("processing_status") == PaperStatus.QUARANTINED:
        today_folder = vault_path / "Inbox" / "Quarantine"
    else:
        today_folder = vault_path / "Inbox" / datetime.now().strftime("%Y-%m-%d")

    today_folder.mkdir(parents=True, exist_ok=True)

    safe_title = "".join(
        c for c in paper.get("title", "")[:50] if c.isalnum() or c in (" ", "-", "_")
    ).strip()
    filename = f"{paper.get('slot', 'Paper')}_{safe_title}.md"
    file_path = today_folder / filename

    related_block = find_related_papers(paper, config)
    if paper.get("slot", "").lower() == "clinical":
        content = get_template_trial(paper, extraction)
    else:
        content = get_template_study(paper)

    if related_block:
        content += related_block

    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write(content)

    try:
        relative_path = file_path.relative_to(vault_path)
    except ValueError:
        relative_path = file_path.name

    if index_file_override:
        path_all = config.paths.obsidian_vault / index_file_override
    else:
        path_all = config.paths.obsidian_vault / config.paths.index_all

    path_all.parent.mkdir(parents=True, exist_ok=True)
    update_csv_index(paper, path_all, is_clinical=False, relative_note_path=str(relative_path))

    if not index_file_override and paper.get("slot", "").lower() == "clinical":
        path_clinical = config.paths.obsidian_vault / config.paths.index_clinical
        path_clinical.parent.mkdir(parents=True, exist_ok=True)
        update_csv_index(paper, path_clinical, is_clinical=True, relative_note_path=str(relative_path))

    return file_path

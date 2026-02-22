from __future__ import annotations

from src.db_paper_read_ops import (
    get_all_papers_with_connection,
    get_paper_by_id_with_connection,
    get_paper_columns,
    get_papers_by_status_with_connection,
    is_paper_processed_with_connection,
    paper_lookup_conditions,
)
from src.db_paper_write_ops import (
    mark_as_retracted_with_connection,
    save_paper_state_with_connection,
    sync_zotero_to_db_with_connection,
    update_paper_status_with_connection,
    update_reading_status_with_connection,
)

__all__ = [
    "get_paper_columns",
    "paper_lookup_conditions",
    "get_paper_by_id_with_connection",
    "is_paper_processed_with_connection",
    "get_all_papers_with_connection",
    "get_papers_by_status_with_connection",
    "save_paper_state_with_connection",
    "update_reading_status_with_connection",
    "mark_as_retracted_with_connection",
    "update_paper_status_with_connection",
    "sync_zotero_to_db_with_connection",
]

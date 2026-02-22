from __future__ import annotations

import sqlite3
import warnings
from pathlib import Path

from src.db_legacy_support import (
    ensure_legacy_tables,
    get_all_embeddings_with_connection,
    save_embedding_with_connection,
)
from src.db_paper_ops import (
    get_all_papers_with_connection,
    get_paper_by_id_with_connection,
    get_paper_columns,
    is_paper_processed_with_connection,
    mark_as_retracted_with_connection,
    paper_lookup_conditions,
    save_paper_state_with_connection,
    update_reading_status_with_connection,
)
from src.db_run_stats import (
    get_profile_stats as get_profile_stats_with_connection,
    init_run_stats_table as init_run_stats_table_with_connection,
    log_run_stat as log_run_stat_with_connection,
)
from src.db_utils import DB_PATH as CANONICAL_DB_PATH

DB_PATH = CANONICAL_DB_PATH
_DEPRECATION_WARNED = False


def _warn_deprecated_once() -> None:
    global _DEPRECATION_WARNED
    if _DEPRECATION_WARNED:
        return
    warnings.warn(
        "src.db is deprecated; use src.db_utils for new runtime DB access.",
        DeprecationWarning,
        stacklevel=2,
    )
    _DEPRECATION_WARNED = True


def _connect() -> sqlite3.Connection:
    _warn_deprecated_once()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def get_db_connection() -> sqlite3.Connection:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """레거시 초기화 진입점(정식 init은 scripts.init_db + src.db_utils)."""
    from scripts import init_db as init_core_module
    import src.db_utils as db_utils_module

    original_core_path = init_core_module.DB_PATH
    original_utils_path = db_utils_module.DB_PATH
    try:
        init_core_module.DB_PATH = DB_PATH
        db_utils_module.DB_PATH = DB_PATH
        init_core_module.init_db()
        db_utils_module.init_db()
    finally:
        init_core_module.DB_PATH = original_core_path
        db_utils_module.DB_PATH = original_utils_path

    conn = _connect()
    ensure_legacy_tables(conn)
    init_run_stats_table_with_connection(conn)
    conn.commit()
    conn.close()


def update_paper_status(identifier: str, status: str):
    """논문 읽기 상태 업데이트(Inbox -> Reading -> Done)."""
    conn = _connect()
    try:
        update_reading_status_with_connection(conn, identifier, status)
        conn.commit()
    finally:
        conn.close()


def get_paper_status(identifier: str) -> str:
    """논문의 현재 reading_status 조회."""
    conn = _connect()
    c = conn.cursor()
    try:
        columns = get_paper_columns(c)
        conditions = paper_lookup_conditions(columns)
        if not conditions:
            return "Inbox"
        params = [identifier] * len(conditions)
        c.execute(
            f"SELECT reading_status FROM papers WHERE {' OR '.join(conditions)} LIMIT 1",
            params,
        )
        row = c.fetchone()
        return row[0] if row else "Inbox"
    finally:
        conn.close()


def check_run_exists(target_date: str) -> bool:
    """특정 날짜에 이미 성공 실행했는지 확인."""
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT status FROM runs WHERE date = ? AND status = 'SUCCESS'", (target_date,))
    result = c.fetchone()
    conn.close()
    return result is not None


def is_paper_processed(identifier: str) -> bool:
    """이미 처리된 논문인지(중복) 확인."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        return is_paper_processed_with_connection(conn, identifier)
    finally:
        conn.close()


def get_all_papers() -> list:
    """DB에 저장된 모든 논문의 DOI/제목/철회여부 반환."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        return get_all_papers_with_connection(conn)
    finally:
        conn.close()


def mark_as_retracted(identifier: str):
    """논문을 철회된 것으로 표시."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        mark_as_retracted_with_connection(conn, identifier)
        conn.commit()
    finally:
        conn.close()


def save_paper_state(identifier: str, title: str, source: str, processed_date: str):
    """처리완료된 논문을 DB에 기록."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        save_paper_state_with_connection(conn, identifier, title, source, processed_date)
        conn.commit()
    finally:
        conn.close()


def save_embedding(doi: str, vector: list):
    """벡터 임베딩 저장."""
    if not doi or not vector:
        return
    conn = _connect()
    try:
        save_embedding_with_connection(conn, doi, vector)
        conn.commit()
    except Exception as exc:
        print(f"DB Embedding Error: {exc}")
    finally:
        conn.close()


def get_all_embeddings() -> dict:
    """모든 벡터 임베딩 로드 (Smart Linking용)."""
    conn = _connect()
    try:
        return get_all_embeddings_with_connection(conn)
    except Exception as exc:
        print(f"DB Load Embedding Error: {exc}")
        return {}
    finally:
        conn.close()


def init_run_stats_table():
    """Initialize run_stats table for performance auditing."""
    conn = _connect()
    init_run_stats_table_with_connection(conn)
    conn.commit()
    conn.close()


def log_run_stat(profile_id: str, items_fetched: int, limit_hit: bool):
    """Log a run statistic."""
    try:
        conn = _connect()
        log_run_stat_with_connection(conn, profile_id, items_fetched, limit_hit)
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"Failed to log run stat: {exc}")


def get_profile_stats(profile_id: str, days: int = 7):
    """Get stats for a profile over the last N days."""
    conn = get_db_connection()
    try:
        return get_profile_stats_with_connection(conn, profile_id, days=days)
    finally:
        conn.close()


def get_paper_by_id(identifier: str) -> dict:
    """Retrieve paper details by internal ID(paper_id/id) or DOI."""
    conn = get_db_connection()
    try:
        return get_paper_by_id_with_connection(conn, identifier)
    finally:
        conn.close()

import sqlite3
import json
import warnings
from datetime import datetime
from pathlib import Path

from src.db_utils import DB_PATH as CANONICAL_DB_PATH, get_db_path as get_canonical_db_path

DB_PATH = CANONICAL_DB_PATH
_IMPORTED_DB_PATH = Path(DB_PATH)
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
    db_path = _resolved_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def _resolved_db_path() -> Path:
    configured = Path(DB_PATH).expanduser().resolve()
    if configured != _IMPORTED_DB_PATH:
        return configured
    return get_canonical_db_path()


def _paper_columns(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute("PRAGMA table_info(papers)")
    return {row[1] for row in cursor.fetchall()}


def _paper_lookup_conditions(columns: set[str]) -> list[str]:
    conditions: list[str] = []
    if "paper_id" in columns:
        conditions.append("paper_id = ?")
    if "doi" in columns:
        conditions.append("doi = ?")
    return conditions

def init_db():
    """데이터베이스 및 테이블 초기화"""
    from scripts import init_db as init_core_module
    import src.db_utils as db_utils_module

    # Canonical bootstrap first (papers/review_queue/jobs).
    # Keep DB_PATH aligned for tests/custom DB targets.
    original_core_path = init_core_module.DB_PATH
    original_utils_path = db_utils_module.DB_PATH
    try:
        resolved_path = _resolved_db_path()
        init_core_module.DB_PATH = resolved_path
        db_utils_module.DB_PATH = resolved_path
        init_core_module.init_db()
        db_utils_module.init_db()
    finally:
        init_core_module.DB_PATH = original_core_path
        db_utils_module.DB_PATH = original_utils_path

    conn = _connect()
    c = conn.cursor()
    # 실행 기록 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            date TEXT PRIMARY KEY,
            status TEXT,
            processed_count INTEGER,
            last_run_at TIMESTAMP
        )
    ''')
    # [NEW] Vector Embeddings Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS embeddings (
            doi TEXT PRIMARY KEY,
            vector TEXT,
            updated_at TIMESTAMP
        )
    ''')
    
    
    # [Migration] Add is_retracted column if not exists (for existing DBs)
    try:
        c.execute("ALTER TABLE papers ADD COLUMN is_retracted BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column already exists

    # [Migration] Add reading_status column if not exists
    try:
        c.execute("ALTER TABLE papers ADD COLUMN reading_status TEXT DEFAULT 'Inbox'")
    except sqlite3.OperationalError:
        pass # Column already exists

    # [Migration] Add processed_date for legacy callers
    try:
        c.execute("ALTER TABLE papers ADD COLUMN processed_date TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    init_run_stats_table() # [Milestone 4.5]
    conn.commit()
    conn.close()

def update_paper_status(identifier: str, status: str):
    """논문 읽기 상태 업데이트 (Inbox -> Reading -> Done)"""
    conn = _connect()
    c = conn.cursor()
    try:
        columns = _paper_columns(c)
        conditions = _paper_lookup_conditions(columns)
        if not conditions:
            return
        params = [status] + [identifier] * len(conditions)
        c.execute(
            f"UPDATE papers SET reading_status = ? WHERE {' OR '.join(conditions)}",
            params,
        )
        conn.commit()
    except Exception as e:
        print(f"DB Status Update Error: {e}")
    finally:
        conn.close()

def get_paper_status(identifier: str) -> str:
    """논문의 현재 상태 조회"""
    conn = _connect()
    c = conn.cursor()
    try:
        columns = _paper_columns(c)
        conditions = _paper_lookup_conditions(columns)
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
    """특정 날짜에 이미 실행했는지 확인"""
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT status FROM runs WHERE date = ? AND status = 'SUCCESS'", (target_date,))
    result = c.fetchone()
    conn.close()
    return result is not None

def is_paper_processed(identifier: str) -> bool:
    """이미 처리된 논문인지(중복) 확인"""
    if not identifier:
        return False
    conn = _connect()
    c = conn.cursor()
    try:
        columns = _paper_columns(c)
        conditions = _paper_lookup_conditions(columns)
        if not conditions:
            return False
        params = [identifier] * len(conditions)
        c.execute(
            f"SELECT 1 FROM papers WHERE {' OR '.join(conditions)} LIMIT 1",
            params,
        )
        result = c.fetchone()
        return result is not None
    finally:
        conn.close()

def get_all_papers() -> list:
    """DB에 저장된 모든 논문의 DOI와 제목 반환"""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        columns = _paper_columns(c)
        doi_expr = "doi" if "doi" in columns else "NULL AS doi"
        title_expr = "title" if "title" in columns else "NULL AS title"
        retract_expr = "is_retracted" if "is_retracted" in columns else "0 AS is_retracted"
        c.execute(f"SELECT {doi_expr}, {title_expr}, {retract_expr} FROM papers")
        rows = c.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def mark_as_retracted(identifier: str):
    """논문을 철회된 것으로 표시"""
    conn = _connect()
    c = conn.cursor()
    try:
        columns = _paper_columns(c)
        if "is_retracted" not in columns:
            try:
                c.execute("ALTER TABLE papers ADD COLUMN is_retracted BOOLEAN DEFAULT 0")
                columns.add("is_retracted")
            except sqlite3.OperationalError:
                pass
        conditions = _paper_lookup_conditions(columns)
        if not conditions:
            return
        params = [identifier] * len(conditions)
        c.execute(
            f"UPDATE papers SET is_retracted = 1 WHERE {' OR '.join(conditions)}",
            params,
        )
        conn.commit()
    finally:
        conn.close()

def save_paper_state(identifier: str, title: str, source: str, processed_date: str):
    """처리완료된 논문을 DB에 기록"""
    conn = _connect()
    c = conn.cursor()
    try:
        columns = _paper_columns(c)
        if not columns:
            return

        insert_cols: list[str] = []
        insert_vals: list[object] = []
        update_set: list[str] = []

        if "paper_id" in columns:
            insert_cols.append("paper_id")
            insert_vals.append(identifier)
            update_set.append("paper_id=excluded.paper_id")
        if "doi" in columns:
            insert_cols.append("doi")
            insert_vals.append(identifier)
            update_set.append("doi=excluded.doi")
        if "title" in columns:
            insert_cols.append("title")
            insert_vals.append(title)
            update_set.append("title=excluded.title")
        if "source" in columns:
            insert_cols.append("source")
            insert_vals.append(source)
            update_set.append("source=excluded.source")
        if "processed_date" in columns:
            insert_cols.append("processed_date")
            insert_vals.append(processed_date)
            update_set.append("processed_date=excluded.processed_date")
        if "processed_at" in columns:
            insert_cols.append("processed_at")
            insert_vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            update_set.append("processed_at=excluded.processed_at")
        if "updated_at" in columns:
            insert_cols.append("updated_at")
            insert_vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            update_set.append("updated_at=excluded.updated_at")
        if "is_retracted" in columns:
            insert_cols.append("is_retracted")
            insert_vals.append(0)
            update_set.append("is_retracted=COALESCE(papers.is_retracted, 0)")

        if not insert_cols:
            return

        placeholders = ",".join("?" for _ in insert_cols)
        conflict_target = None
        if "paper_id" in columns:
            conflict_target = "paper_id"
        elif "doi" in columns:
            conflict_target = "doi"

        if conflict_target:
            sql = (
                f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT({conflict_target}) DO UPDATE SET {', '.join(update_set)}"
            )
            c.execute(sql, tuple(insert_vals))
        else:
            sql = f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders})"
            c.execute(sql, tuple(insert_vals))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()

def save_embedding(doi: str, vector: list):
    """벡터 임베딩 저장"""
    if not doi or not vector: return
    conn = _connect()
    c = conn.cursor()
    try:
        vector_json = json.dumps(vector)
        c.execute("""
            INSERT INTO embeddings (doi, vector, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(doi) DO UPDATE SET
                vector=excluded.vector,
                updated_at=excluded.updated_at
        """, (doi, vector_json, datetime.now()))
        conn.commit()
    except Exception as e:
        print(f"DB Embedding Error: {e}")
    finally:
        conn.close()

def get_all_embeddings() -> dict:
    """모든 벡터 임베딩 로드 (Smart Linking용)"""
    conn = _connect()
    c = conn.cursor()
    try:
        c.execute("SELECT doi, vector FROM embeddings")
        rows = c.fetchall()
        result = {}
        for r in rows:
            try:
                result[r[0]] = json.loads(r[1])
            except:
                pass
        return result
    except Exception as e:
        print(f"DB Load Embedding Error: {e}")
        return {}
    finally:
        conn.close()

def init_run_stats_table():
    """Initialize the run_stats table for performance auditing."""
    conn = _connect()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS run_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            profile_id TEXT NOT NULL,
            items_fetched INTEGER DEFAULT 0,
            limit_hit BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def log_run_stat(profile_id: str, items_fetched: int, limit_hit: bool):
    """Log a run statistic."""
    try:
        conn = _connect()
        c = conn.cursor()
        c.execute('''
            INSERT INTO run_stats (profile_id, items_fetched, limit_hit)
            VALUES (?, ?, ?)
        ''', (profile_id, items_fetched, int(limit_hit)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log run stat: {e}")

def get_profile_stats(profile_id: str, days: int = 7):
    """Get stats for a profile over the last N days."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Calculate date threshold
    import datetime
    threshold = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    c.execute('''
        SELECT * FROM run_stats 
        WHERE profile_id = ? AND timestamp >= ?
        ORDER BY timestamp DESC
    ''', (profile_id, threshold))
    
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_paper_by_id(identifier: str) -> dict:
    """
    Retrieve paper details by internal ID (timestamp_hash) or DOI.
    Useful for looking up local paths or metadata.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        c.execute("PRAGMA table_info(papers)")
        columns = {row[1] for row in c.fetchall()}

        lookup_order = []
        if "paper_id" in columns:
            lookup_order.append("paper_id")
        if "id" in columns:
            lookup_order.append("id")
        if "doi" in columns:
            lookup_order.append("doi")

        for col in lookup_order:
            c.execute(f"SELECT * FROM papers WHERE {col} = ?", (identifier,))
            row = c.fetchone()
            if row:
                return dict(row)
        return None
    finally:
        conn.close()


def get_db_connection() -> sqlite3.Connection:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    return conn

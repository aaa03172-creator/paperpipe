import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("storage/state.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    """데이터베이스 및 테이블 초기화"""
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
    # 논문 처리 기록 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS papers (
            doi TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            processed_date TEXT,
            is_retracted BOOLEAN DEFAULT 0
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
        
    init_run_stats_table() # [Milestone 4.5]
    conn.commit()
    conn.close()

def update_paper_status(doi: str, status: str):
    """논문 읽기 상태 업데이트 (Inbox -> Reading -> Done)"""
    conn = _connect()
    c = conn.cursor()
    try:
        c.execute("UPDATE papers SET reading_status = ? WHERE doi = ?", (status, doi))
        conn.commit()
    except Exception as e:
        print(f"DB Status Update Error: {e}")
    finally:
        conn.close()

def get_paper_status(doi: str) -> str:
    """논문의 현재 상태 조회"""
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT reading_status FROM papers WHERE doi = ?", (doi,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "Inbox"

def check_run_exists(target_date: str) -> bool:
    """특정 날짜에 이미 실행했는지 확인"""
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT status FROM runs WHERE date = ? AND status = 'SUCCESS'", (target_date,))
    result = c.fetchone()
    conn.close()
    return result is not None

def is_paper_processed(doi: str) -> bool:
    """이미 처리된 논문인지(중복) 확인"""
    if not doi:
        return False
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT doi FROM papers WHERE doi = ?", (doi,))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_all_papers() -> list:
    """DB에 저장된 모든 논문의 DOI와 제목 반환"""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT doi, title, is_retracted FROM papers")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def mark_as_retracted(doi: str):
    """논문을 철회된 것으로 표시"""
    conn = _connect()
    c = conn.cursor()
    c.execute("UPDATE papers SET is_retracted = 1 WHERE doi = ?", (doi,))
    conn.commit()
    conn.close()

def save_paper_state(doi: str, title: str, source: str, processed_date: str):
    """처리완료된 논문을 DB에 기록"""
    conn = _connect()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO papers (doi, title, source, processed_date, is_retracted) 
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(doi) DO UPDATE SET
                processed_date=excluded.processed_date,
                title=excluded.title
        """, (doi, title, source, processed_date))
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
    
    # Try ID first
    c.execute("SELECT * FROM papers WHERE id = ?", (identifier,))
    row = c.fetchone()
    
    if not row:
        # Try DOI
        c.execute("SELECT * FROM papers WHERE doi = ?", (identifier,))
        row = c.fetchone()
        
    conn.close()
    return dict(row) if row else None


def get_db_connection() -> sqlite3.Connection:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    return conn

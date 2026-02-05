import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = "state.db"

def init_db():
    """데이터베이스 및 테이블 초기화"""
    conn = sqlite3.connect(DB_PATH)
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
            processed_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def check_run_exists(target_date: str) -> bool:
    """특정 날짜에 이미 실행했는지 확인"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # This query was incorrect, it should be checking for the existence of the run.
    c.execute("SELECT status FROM runs WHERE date = ? AND status = 'SUCCESS'", (target_date,))
    result = c.fetchone()
    conn.close()
    return result is not None

def is_paper_processed(doi: str) -> bool:
    """이미 처리된 논문인지(중복) 확인"""
    if not doi:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT doi FROM papers WHERE doi = ?", (doi,))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_paper_state(doi: str, title: str, source: str, processed_date: str):
    """처리완료된 논문을 DB에 기록"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO papers (doi, title, source, processed_date) VALUES (?, ?, ?, ?)",
                  (doi, title, source, processed_date))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()

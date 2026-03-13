import sqlite3


def init_run_stats_table() -> None:
    conn = sqlite3.connect("state.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS run_stats (
            profile_id TEXT,
            items_fetched INTEGER,
            limit_hit INTEGER,
            timestamp TEXT
        )
        """
    )
    conn.commit()


def log_run_stat(profile_id: str, items_fetched: int, limit_hit: bool) -> None:
    conn = sqlite3.connect("state.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO run_stats (profile_id, items_fetched, limit_hit, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (profile_id, items_fetched, int(limit_hit)),
    )
    conn.commit()


def get_profile_stats(profile_id: str, days: int):
    _ = days
    conn = sqlite3.connect("state.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT profile_id, items_fetched, limit_hit, timestamp FROM run_stats WHERE profile_id = ?",
        (profile_id,),
    )
    return cursor.fetchall()

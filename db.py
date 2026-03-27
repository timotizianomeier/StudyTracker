"""SQLite persistence for Pomodoro sessions."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.pomodoro_tracker.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT    NOT NULL,
                duration   INTEGER NOT NULL,
                focus      INTEGER,
                topic      TEXT,
                distracted INTEGER NOT NULL DEFAULT 0,
                reason     TEXT
            )
        """)


def save_session(
    duration: int,
    focus: int | None,
    topic: str | None,
    distracted: bool,
    reason: str | None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sessions
               (timestamp, duration, focus, topic, distracted, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                duration,
                focus,
                topic or None,
                1 if distracted else 0,
                reason or None,
            ),
        )


def get_all_sessions() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions ORDER BY timestamp DESC"
        ).fetchall()


def get_stats_by_topic() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("""
            SELECT
                COALESCE(NULLIF(topic, ''), '(no topic)') AS topic,
                ROUND(AVG(focus), 1)                       AS avg_focus,
                COUNT(*)                                   AS sessions,
                SUM(duration)                              AS total_min
            FROM sessions
            WHERE focus IS NOT NULL
            GROUP BY COALESCE(NULLIF(topic, ''), '(no topic)')
            ORDER BY avg_focus DESC
        """).fetchall()


def get_stats_by_time_of_day() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("""
            SELECT
                CASE
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 5  AND 11
                        THEN '🌅 Morning (5–11)'
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 12 AND 16
                        THEN '☀️ Afternoon (12–16)'
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 17 AND 20
                        THEN '🌆 Evening (17–20)'
                    ELSE '🌙 Night (21–4)'
                END AS period,
                ROUND(AVG(focus), 1) AS avg_focus,
                COUNT(*)             AS sessions
            FROM sessions
            WHERE focus IS NOT NULL
            GROUP BY period
            ORDER BY
                CASE period
                    WHEN '🌅 Morning (5–11)'    THEN 1
                    WHEN '☀️ Afternoon (12–16)' THEN 2
                    WHEN '🌆 Evening (17–20)'   THEN 3
                    ELSE 4
                END
        """).fetchall()


def get_summary() -> dict:
    with _connect() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)          AS total_sessions,
                SUM(duration)     AS total_minutes,
                ROUND(AVG(focus), 1) AS avg_focus
            FROM sessions
        """).fetchone()
        return dict(row) if row else {}

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
                COALESCE(NULLIF(topic, ''), '(no topic)')            AS topic,
                ROUND(SUM(focus * duration) * 1.0 / SUM(duration), 1) AS avg_focus,
                COUNT(*)                                              AS sessions,
                SUM(duration)                                         AS total_min
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
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 7  AND 12
                        THEN '🌅 Morning (7–13)'
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 13 AND 16
                        THEN '☀️ Afternoon (13–17)'
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 17 AND 22
                        THEN '🌆 Evening (17–23)'
                    ELSE '🌙 Night (23–7)'
                END AS period,
                ROUND(SUM(focus * duration) * 1.0 / SUM(duration), 1) AS avg_focus,
                COUNT(*)                                              AS sessions
            FROM sessions
            WHERE focus IS NOT NULL
            GROUP BY period
            ORDER BY
                CASE period
                    WHEN '🌅 Morning (7–13)'    THEN 1
                    WHEN '☀️ Afternoon (13–17)' THEN 2
                    WHEN '🌆 Evening (17–23)'   THEN 3
                    ELSE 4
                END
        """).fetchall()


def get_daily_by_topic() -> list[sqlite3.Row]:
    """Returns (day, topic, total_min, avg_focus, sessions) rows sorted by day ascending."""
    with _connect() as conn:
        return conn.execute("""
            SELECT
                DATE(timestamp) AS day,
                COALESCE(NULLIF(topic, ''), '(no topic)') AS topic,
                SUM(duration)                                                                    AS total_min,
                ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                      NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 1)          AS avg_focus,
                COUNT(*)                                                                         AS sessions
            FROM sessions
            GROUP BY day, topic
            ORDER BY day ASC
        """).fetchall()


def get_summary() -> dict:
    with _connect() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)          AS total_sessions,
                SUM(duration)     AS total_minutes,
                ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                      NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 1) AS avg_focus
            FROM sessions
        """).fetchone()
        return dict(row) if row else {}

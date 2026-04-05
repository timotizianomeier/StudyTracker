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


def get_distraction_summary() -> dict:
    """Overall distraction stats: total sessions, distracted count, rate %."""
    with _connect() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)       AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
        """).fetchone()
    if row and row["total_sessions"]:
        total = row["total_sessions"]
        dist  = row["distracted_sessions"] or 0
        return {
            "total_sessions":     total,
            "distracted_sessions": dist,
            "distraction_rate":   round(dist / total * 100, 1),
        }
    return {"total_sessions": 0, "distracted_sessions": 0, "distraction_rate": 0.0}


def get_distraction_word_freq(top_n: int = 25) -> list[tuple[str, int]]:
    """Parse free-text reason fields and return top-N words with counts."""
    import re
    from collections import Counter

    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "i", "my", "me", "we", "our", "you", "your", "he",
        "she", "it", "its", "they", "their", "that", "this", "these", "those",
        "had", "have", "has", "got", "get", "getting", "did", "do", "does",
        "just", "so", "no", "not", "yes", "very", "too", "then", "than",
        "when", "while", "during", "some", "also", "up", "out", "about",
        "into", "if", "what", "which", "who", "how", "there", "here", "where",
        "again", "more", "much", "many", "few", "all", "any", "both",
        "each", "s", "re", "ve", "ll", "d", "t", "m", "kept", "kept",
        "because", "due", "after", "before", "came", "came", "something",
    }
    with _connect() as conn:
        rows = conn.execute(
            "SELECT reason FROM sessions "
            "WHERE distracted = 1 AND reason IS NOT NULL AND reason != ''"
        ).fetchall()

    counter: Counter[str] = Counter()
    for row in rows:
        words = re.findall(r"[a-zA-Z']+", row["reason"].lower())
        for word in words:
            word = word.strip("'")
            if len(word) >= 3 and word not in STOPWORDS:
                counter[word] += 1

    return counter.most_common(top_n)


def get_distraction_by_hour() -> list[sqlite3.Row]:
    """Distraction totals grouped by hour of day (0–23)."""
    with _connect() as conn:
        return conn.execute("""
            SELECT
                CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            GROUP BY hour
            ORDER BY hour
        """).fetchall()


def get_distraction_by_weekday() -> list[sqlite3.Row]:
    """Distraction totals grouped by weekday (0=Sun … 6=Sat, SQLite %w)."""
    with _connect() as conn:
        return conn.execute("""
            SELECT
                CAST(strftime('%w', timestamp) AS INTEGER) AS weekday,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            GROUP BY weekday
            ORDER BY weekday
        """).fetchall()


def get_daily_distraction_rate() -> list[sqlite3.Row]:
    """Distraction totals per calendar day (YYYY-MM-DD)."""
    with _connect() as conn:
        return conn.execute("""
            SELECT
                strftime('%Y-%m-%d', timestamp) AS day,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            GROUP BY day
            ORDER BY day
        """).fetchall()


def get_weekly_distraction_rate() -> list[sqlite3.Row]:
    """Distraction totals per ISO calendar week (YYYY-Www)."""
    with _connect() as conn:
        return conn.execute("""
            SELECT
                strftime('%Y-W%W', timestamp) AS week,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            GROUP BY week
            ORDER BY week
        """).fetchall()


def get_all_topics() -> list[str]:
    """Return distinct topics used in past sessions, ordered by most recently used."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT topic, MAX(timestamp) AS last_used "
            "FROM sessions "
            "WHERE topic IS NOT NULL AND topic != '' "
            "GROUP BY topic "
            "ORDER BY last_used DESC"
        ).fetchall()
    return [row["topic"] for row in rows]


def get_daily_focus_vs_time() -> list[sqlite3.Row]:
    """Returns (day, total_min, avg_focus) per day for days that have focus data."""
    with _connect() as conn:
        return conn.execute("""
            SELECT
                DATE(timestamp) AS day,
                SUM(duration) AS total_min,
                ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                      NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 2) AS avg_focus
            FROM sessions
            GROUP BY day
            HAVING avg_focus IS NOT NULL
            ORDER BY day ASC
        """).fetchall()


def get_focus_by_start_hour() -> list[sqlite3.Row]:
    """Returns avg_focus and day count grouped by when the first session of the day started."""
    with _connect() as conn:
        return conn.execute("""
            WITH day_stats AS (
                SELECT
                    DATE(timestamp) AS day,
                    MIN(CAST(strftime('%H', timestamp) AS INTEGER)) AS first_hour,
                    ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                          NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 2) AS avg_focus
                FROM sessions
                GROUP BY day
                HAVING avg_focus IS NOT NULL
            )
            SELECT
                CASE
                    WHEN first_hour < 9  THEN 'Before 9am'
                    WHEN first_hour < 10 THEN '9am \u2013 10am'
                    ELSE '10am or later'
                END AS start_group,
                ROUND(AVG(avg_focus), 2) AS avg_focus,
                COUNT(*) AS days
            FROM day_stats
            GROUP BY
                CASE
                    WHEN first_hour < 9  THEN 1
                    WHEN first_hour < 10 THEN 2
                    ELSE 3
                END
            ORDER BY
                CASE
                    WHEN first_hour < 9  THEN 1
                    WHEN first_hour < 10 THEN 2
                    ELSE 3
                END
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

"""SQLite persistence for Pomodoro sessions."""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.expanduser("~/.pomodoro_tracker.db")

# Sentinel passed to filter functions to show only sessions with no term set.
UNTAGGED = ""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _term_where(term: str | None) -> tuple[str, list]:
    """Return (extra_AND_clause, params) for optional term filtering."""
    if term is None:
        return "", []
    if term == UNTAGGED:
        return "AND (term IS NULL OR term = '')", []
    return "AND term = ?", [term]


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
                reason     TEXT,
                start_time TEXT,
                term       TEXT
            )
        """)


def save_session(
    duration: int,
    focus: int | None,
    topic: str | None,
    distracted: bool,
    reason: str | None,
    start_time: datetime | None = None,
    term: str | None = None,
) -> None:
    end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(minutes=duration)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sessions
               (timestamp, duration, focus, topic, distracted, reason, start_time, term)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                end_time.isoformat(),
                duration,
                focus,
                topic or None,
                1 if distracted else 0,
                reason or None,
                start_time.isoformat(),
                term or None,
            ),
        )


def get_all_terms() -> list[str]:
    """Return distinct terms used in past sessions, ordered by most recently used."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT term, MAX(timestamp) AS last_used "
            "FROM sessions "
            "WHERE term IS NOT NULL AND term != '' "
            "GROUP BY term "
            "ORDER BY last_used DESC"
        ).fetchall()
    return [row["term"] for row in rows]


def get_last_term() -> str | None:
    """Return the most recently used term, or None if none exist."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT term FROM sessions "
            "WHERE term IS NOT NULL AND term != '' "
            "ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return row["term"] if row else None


def has_untagged_sessions() -> bool:
    """Return True if any sessions have no term set."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE term IS NULL OR term = ''"
        ).fetchone()
    return bool(row["n"])


def get_all_sessions(term: str | None = None) -> list[sqlite3.Row]:
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(
            f"SELECT * FROM sessions WHERE 1=1 {tc} ORDER BY timestamp DESC",
            tp,
        ).fetchall()


def get_stats_by_topic(term: str | None = None) -> list[sqlite3.Row]:
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                COALESCE(NULLIF(topic, ''), '(no topic)')            AS topic,
                ROUND(SUM(focus * duration) * 1.0 / SUM(duration), 1) AS avg_focus,
                COUNT(*)                                              AS sessions,
                SUM(duration)                                         AS total_min
            FROM sessions
            WHERE focus IS NOT NULL {tc}
            GROUP BY COALESCE(NULLIF(topic, ''), '(no topic)')
            ORDER BY avg_focus DESC
        """, tp).fetchall()


def get_stats_by_time_of_day(term: str | None = None) -> list[sqlite3.Row]:
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                CASE
                    WHEN CAST(strftime('%H', start_time) AS INTEGER) BETWEEN 7  AND 12
                        THEN '🌅 Morning (7–13)'
                    WHEN CAST(strftime('%H', start_time) AS INTEGER) BETWEEN 13 AND 16
                        THEN '☀️ Afternoon (13–17)'
                    WHEN CAST(strftime('%H', start_time) AS INTEGER) BETWEEN 17 AND 22
                        THEN '🌆 Evening (17–23)'
                    ELSE '🌙 Night (23–7)'
                END AS period,
                ROUND(SUM(focus * duration) * 1.0 / SUM(duration), 1) AS avg_focus,
                COUNT(*)                                              AS sessions
            FROM sessions
            WHERE focus IS NOT NULL {tc}
            GROUP BY period
            ORDER BY
                CASE period
                    WHEN '🌅 Morning (7–13)'    THEN 1
                    WHEN '☀️ Afternoon (13–17)' THEN 2
                    WHEN '🌆 Evening (17–23)'   THEN 3
                    ELSE 4
                END
        """, tp).fetchall()


def get_daily_by_topic(term: str | None = None) -> list[sqlite3.Row]:
    """Returns (day, topic, total_min, avg_focus, sessions) rows sorted by day ascending."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                DATE(timestamp) AS day,
                COALESCE(NULLIF(topic, ''), '(no topic)') AS topic,
                SUM(duration)                                                                    AS total_min,
                ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                      NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 1)          AS avg_focus,
                COUNT(*)                                                                         AS sessions
            FROM sessions
            WHERE 1=1 {tc}
            GROUP BY day, topic
            ORDER BY day ASC
        """, tp).fetchall()


def get_distraction_summary(term: str | None = None) -> dict:
    """Overall distraction stats: total sessions, distracted count, rate %."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        row = conn.execute(f"""
            SELECT
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            WHERE 1=1 {tc}
        """, tp).fetchone()
    if row and row["total_sessions"]:
        total = row["total_sessions"]
        dist  = row["distracted_sessions"] or 0
        return {
            "total_sessions":      total,
            "distracted_sessions": dist,
            "distraction_rate":    round(dist / total * 100, 1),
        }
    return {"total_sessions": 0, "distracted_sessions": 0, "distraction_rate": 0.0}


def get_distraction_word_freq(
    top_n: int | None = None, term: str | None = None
) -> list[tuple[str, int]]:
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
    tc, tp = _term_where(term)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT reason FROM sessions "
            f"WHERE distracted = 1 AND reason IS NOT NULL AND reason != '' {tc}",
            tp,
        ).fetchall()

    counter: Counter[str] = Counter()
    for row in rows:
        words = re.findall(r"[a-zA-Z']+", row["reason"].lower())
        for word in words:
            word = word.strip("'")
            if len(word) >= 3 and word not in STOPWORDS:
                counter[word] += 1

    return counter.most_common(top_n)


def get_distraction_by_hour(term: str | None = None) -> list[sqlite3.Row]:
    """Distraction totals grouped by hour of day (0–23)."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                CAST(strftime('%H', start_time) AS INTEGER) AS hour,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            WHERE 1=1 {tc}
            GROUP BY hour
            ORDER BY hour
        """, tp).fetchall()


def get_distraction_by_weekday(term: str | None = None) -> list[sqlite3.Row]:
    """Distraction totals grouped by weekday (0=Sun … 6=Sat, SQLite %w)."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                CAST(strftime('%w', timestamp) AS INTEGER) AS weekday,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            WHERE 1=1 {tc}
            GROUP BY weekday
            ORDER BY weekday
        """, tp).fetchall()


def get_daily_distraction_rate(term: str | None = None) -> list[sqlite3.Row]:
    """Distraction totals per calendar day (YYYY-MM-DD)."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                strftime('%Y-%m-%d', timestamp) AS day,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            WHERE 1=1 {tc}
            GROUP BY day
            ORDER BY day
        """, tp).fetchall()


def get_weekly_distraction_rate(term: str | None = None) -> list[sqlite3.Row]:
    """Distraction totals per ISO calendar week (YYYY-Www)."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                strftime('%Y-W%W', timestamp) AS week,
                COUNT(*)        AS total_sessions,
                SUM(distracted) AS distracted_sessions
            FROM sessions
            WHERE 1=1 {tc}
            GROUP BY week
            ORDER BY week
        """, tp).fetchall()


def get_all_topics(term: str | None = None) -> list[str]:
    """Return distinct topics used in past sessions, ordered by most recently used."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT topic, MAX(timestamp) AS last_used "
            f"FROM sessions "
            f"WHERE topic IS NOT NULL AND topic != '' {tc} "
            f"GROUP BY topic "
            f"ORDER BY last_used DESC",
            tp,
        ).fetchall()
    return [row["topic"] for row in rows]


def get_daily_focus_vs_time(term: str | None = None) -> list[sqlite3.Row]:
    """Returns (day, total_min, avg_focus) per day for days that have focus data."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT
                DATE(timestamp) AS day,
                SUM(duration) AS total_min,
                ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                      NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 2) AS avg_focus
            FROM sessions
            WHERE 1=1 {tc}
            GROUP BY day
            HAVING avg_focus IS NOT NULL
            ORDER BY day ASC
        """, tp).fetchall()


def get_focus_by_start_hour(term: str | None = None) -> list[sqlite3.Row]:
    """Returns avg_focus and day count grouped by when the first session of the day started."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            WITH day_stats AS (
                SELECT
                    DATE(start_time) AS day,
                    MIN(CAST(strftime('%H', start_time) AS INTEGER)) AS first_hour,
                    ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                          NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 2) AS avg_focus
                FROM sessions
                WHERE 1=1 {tc}
                GROUP BY day
                HAVING avg_focus IS NOT NULL
            )
            SELECT
                CASE
                    WHEN first_hour < 9  THEN 'Before 9am'
                    WHEN first_hour < 10 THEN '9am – 10am'
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
        """, tp).fetchall()


def get_focus_vs_start_time(term: str | None = None) -> list[sqlite3.Row]:
    """Returns (start_time, focus) for every session that has both values."""
    tc, tp = _term_where(term)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT start_time, focus
            FROM sessions
            WHERE focus IS NOT NULL AND start_time IS NOT NULL {tc}
            ORDER BY start_time ASC
        """, tp).fetchall()


def get_summary(term: str | None = None) -> dict:
    tc, tp = _term_where(term)
    with _connect() as conn:
        row = conn.execute(f"""
            SELECT
                COUNT(*)          AS total_sessions,
                SUM(duration)     AS total_minutes,
                ROUND(SUM(CASE WHEN focus IS NOT NULL THEN focus * duration END) * 1.0 /
                      NULLIF(SUM(CASE WHEN focus IS NOT NULL THEN duration END), 0), 1) AS avg_focus
            FROM sessions
            WHERE 1=1 {tc}
        """, tp).fetchone()
        return dict(row) if row else {}

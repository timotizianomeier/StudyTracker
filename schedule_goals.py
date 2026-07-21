"""Pure logic for the daily start/cutoff schedule goals.

Kept free of any UI so it can be unit-tested and reused: ``main.py`` calls
these to decide when to prompt for a late-work reason and what morning greeting
to show, then owns the actual windows.
"""

from datetime import date, datetime, time, timedelta

import config
import db


def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    h, m = hhmm.split(":")
    return int(h), int(m)


def late_cutoff_if_past(end_dt: datetime) -> str | None:
    """Return the cutoff ("HH:MM") if ``end_dt`` is past today's cutoff and no
    late-work reason has been logged yet for that day; otherwise ``None``.
    """
    end_by = config.get_end_by()
    eh, em = _parse_hhmm(end_by)
    threshold = end_dt.replace(hour=eh, minute=em, second=0, microsecond=0)
    if end_dt <= threshold:
        return None
    if db.has_over_cutoff_reason(end_dt.date().isoformat()):
        return None
    return end_by


def _day_met(row, start_by: str, end_by: str) -> bool:
    """True if the given day's first start was before ``start_by`` and its last
    session ended by ``end_by``."""
    first_start = datetime.fromisoformat(row["first_start"])
    last_end    = datetime.fromisoformat(row["last_end"])
    sh, sm = _parse_hhmm(start_by)
    eh, em = _parse_hhmm(end_by)
    day = date.fromisoformat(row["day"])

    started_early  = first_start.time() < time(sh, sm)
    finished_ontime = last_end <= datetime.combine(day, time(eh, em))
    return started_early and finished_ontime


def _describe_day(day: date, today: date) -> str:
    """Human phrase for a past study day relative to today."""
    if day == today - timedelta(days=1):
        return "yesterday"
    return f"on {day.strftime('%A')}"


def evaluate_previous_day(today: date | None = None) -> dict | None:
    """Compose the morning greeting for the most recent active study day before
    ``today``.

    Returns ``{"met", "headline", "detail"}`` or ``None`` when there is no prior
    active day to reflect on (e.g. first ever run, or a fresh week's first day).
    """
    today = today or date.today()
    start_by = config.get_start_by()
    end_by   = config.get_end_by()

    bounds = db.get_daily_schedule_bounds()
    prior  = [r for r in bounds if r["day"] < today.isoformat()]
    if not prior:
        return None

    last     = prior[-1]
    met_last = _day_met(last, start_by, end_by)
    prev_day = date.fromisoformat(last["day"])
    when     = _describe_day(prev_day, today)

    # Streak: consecutive active days (ignoring calendar gaps like weekends)
    # ending at the most recent active day that all met the goal.
    streak = 0
    for row in reversed(prior):
        if _day_met(row, start_by, end_by):
            streak += 1
        else:
            break

    if met_last:
        headline = f"You hit your {start_by}–{end_by} window {when}!"
        if streak >= 2:
            detail = (
                f"That's {streak} focused days in a row. "
                "Keep the momentum going today."
            )
        else:
            detail = "Kick today off the same way — start strong, finish on time."
    else:
        fs = datetime.fromisoformat(last["first_start"]).strftime("%H:%M")
        le = datetime.fromisoformat(last["last_end"]).strftime("%H:%M")
        headline = "Let's tighten up the schedule today."
        detail = (
            f"{when.capitalize()} you started at {fs} and wrapped at {le}. "
            f"Aim to be underway before {start_by} and done by {end_by} today."
        )

    return {"met": met_last, "headline": headline, "detail": detail}

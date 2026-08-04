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


def is_late_start(now: datetime) -> str | None:
    """Return the start goal ("HH:MM") if ``now`` is past today's start goal and
    no late-start reason has been logged yet for today; otherwise ``None``.
    """
    start_by = config.get_start_by()
    sh, sm = _parse_hhmm(start_by)
    if now.time() <= time(sh, sm):
        return None
    if db.has_late_start_reason(now.date().isoformat()):
        return None
    return start_by


def _day_flags(row, start_by: str, end_by: str) -> tuple[bool, bool]:
    """Return (started_early, finished_ontime) for a day-bounds row."""
    first_start = datetime.fromisoformat(row["first_start"])
    last_end    = datetime.fromisoformat(row["last_end"])
    sh, sm = _parse_hhmm(start_by)
    eh, em = _parse_hhmm(end_by)
    day = date.fromisoformat(row["day"])

    started_early   = first_start.time() < time(sh, sm)
    finished_ontime = last_end <= datetime.combine(day, time(eh, em))
    return started_early, finished_ontime


def _day_met(row, start_by: str, end_by: str) -> bool:
    """True if the given day's first start was before ``start_by`` and its last
    session ended by ``end_by``."""
    started_early, finished_ontime = _day_flags(row, start_by, end_by)
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
        fs = datetime.fromisoformat(last["first_start"]).strftime("%H:%M")
        le = datetime.fromisoformat(last["last_end"]).strftime("%H:%M")
        headline = f"You hit your {start_by}–{end_by} window {when}!"
        parts = [
            f"You were underway by {fs} (goal {start_by}) and wrapped up by "
            f"{le} (goal {end_by}). Nicely done."
        ]
        if streak >= 2:
            parts.append(
                f"That's {streak} focused days in a row — keep the momentum going today."
            )
        else:
            parts.append("Kick today off the same way.")
        detail = " ".join(parts)
    else:
        started_early, finished_ontime = _day_flags(last, start_by, end_by)
        fs = datetime.fromisoformat(last["first_start"]).strftime("%H:%M")
        le = datetime.fromisoformat(last["last_end"]).strftime("%H:%M")
        log = db.get_day_log(last["day"]) or {}

        headline = "Let's tighten up the schedule today."
        parts: list[str] = []
        if not started_early:
            s = f"{when.capitalize()} you started at {fs} (goal {start_by})."
            reason = log.get("late_start_reason")
            if reason:
                s += f" You noted: “{reason}”"
            parts.append(s)
        if not finished_ontime:
            lead = "You worked until" if parts else f"{when.capitalize()} you worked until"
            s = f"{lead} {le} (goal {end_by})."
            reason = log.get("over_cutoff_reason")
            if reason:
                s += f" You noted: “{reason}”"
            parts.append(s)
        parts.append(
            f"Aim to be underway before {start_by} and done by {end_by} today."
        )
        detail = " ".join(parts)

    return {"met": met_last, "headline": headline, "detail": detail}

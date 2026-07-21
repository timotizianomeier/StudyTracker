"""Persistent JSON config for user preferences not stored in the DB."""

import json
import os

CONFIG_PATH = os.path.expanduser("~/.pomodoro_tracker_config.json")

# Daily schedule goals: start work before START_BY, wrap up by END_BY.
DEFAULT_START_BY = "09:00"
DEFAULT_END_BY   = "18:00"

DEFAULT_BLOCKED_APPS = [
    "WhatsApp",
    "Mail",
    "Messages",
    "Slack",
    "Discord",
    "Telegram",
    "Microsoft Teams",
    "Microsoft Outlook",
    "Mimestream",
    "Spark",
]


def _load() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_blocked_apps() -> list[str]:
    return _load().get("blocked_apps", list(DEFAULT_BLOCKED_APPS))


def is_app_blocking_enabled() -> bool:
    return _load().get("app_blocking_enabled", True)


def save_app_blocking_settings(enabled: bool, apps: list[str]) -> None:
    data = _load()
    data["app_blocking_enabled"] = enabled
    data["blocked_apps"] = apps
    _save(data)


def _valid_hhmm(value: object, fallback: str) -> str:
    """Return value if it is a well-formed 'HH:MM' string, else fallback."""
    if isinstance(value, str):
        parts = value.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}"
    return fallback


def get_start_by() -> str:
    """Target time to have started work by, as 'HH:MM'."""
    return _valid_hhmm(_load().get("start_by"), DEFAULT_START_BY)


def get_end_by() -> str:
    """Target time to have finished work by, as 'HH:MM'."""
    return _valid_hhmm(_load().get("end_by"), DEFAULT_END_BY)


def save_schedule_goals(start_by: str, end_by: str) -> None:
    data = _load()
    data["start_by"] = _valid_hhmm(start_by, DEFAULT_START_BY)
    data["end_by"]   = _valid_hhmm(end_by, DEFAULT_END_BY)
    _save(data)

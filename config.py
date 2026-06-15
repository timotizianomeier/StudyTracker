"""Persistent JSON config for user preferences not stored in the DB."""

import json
import os

CONFIG_PATH = os.path.expanduser("~/.pomodoro_tracker_config.json")

DEFAULT_BLOCKED_APPS = [
    "WhatsApp",
    "Mail",
    "Messages",
    "Slack",
    "Discord",
    "Telegram",
    "Microsoft Teams",
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

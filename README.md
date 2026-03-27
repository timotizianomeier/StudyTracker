# 🍅 Pomodoro Tracker

A macOS menu bar app for tracking focused work sessions. Built with Python, it lives quietly in your menu bar, runs timed Pomodoro sessions, fires a native macOS notification when time is up, and prompts you to log how the session went. All data is stored locally in SQLite — no network, no accounts.

---

## What it does

- **Pomodoro timer** in the menu bar with a live countdown (`🍅 24:59`)
- **Configurable session length** (default 25 min, supports 1–180 min)
- **Native macOS notification** with sound when the session ends
- **Post-session form** asking:
  - Focus rating (1–10 slider)
  - Topic / project label (optional free text)
  - Whether you got distracted, and if so why
- **Session history** with a full log table and summary statistics:
  - Average focus by time of day (morning / afternoon / evening / night)
  - Average focus by topic
  - Total sessions, total focus time, overall average focus rating

---

## Requirements

- macOS (tested on macOS 13+)
- Python 3.10+
- `rumps` (the only third-party dependency — everything else is in the standard library)

---

## Installation

```bash
# 1. Clone or download the project
cd /path/to/StudyTracker

# 2. Install the one dependency
pip install -r requirements.txt

# 3. Run
python3 main.py
```

The `🍅` icon will appear in your menu bar. The SQLite database is created automatically at `~/.pomodoro_tracker.db` on first launch.

> **Notification permissions:** macOS may ask for notification permission the first time a session ends. Grant it once and you won't be asked again.

---

## Usage

| Menu item | What it does |
|---|---|
| `▶ Start Session` | Starts the countdown timer |
| `⏹ Stop Session` | Cancels the current session (no log entry) |
| `⚙ Configure…` | Set the session length in minutes |
| `📋 View History` | Open the history & stats window |
| `Quit` | Exit the app |

### Typical workflow

1. Click `▶ Start Session` and get to work.
2. The menu bar shows the remaining time (`🍅 22:14`).
3. When the timer hits zero, a macOS notification plays a sound.
4. A form pops up — rate your focus, add a topic, note any distractions.
5. Hit **Save Session** (or **Skip** to discard the log entry).
6. Review trends any time via **View History**.

---

## Project structure

```
StudyTracker/
├── main.py          # rumps menu bar app and timer logic
├── db.py            # SQLite setup, writes, and aggregation queries
├── forms.py         # All tkinter UI (configure dialog, session form, history window)
├── requirements.txt
└── README.md
```

---

## Data

Sessions are stored in `~/.pomodoro_tracker.db` with this schema:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-incremented primary key |
| `timestamp` | TEXT | ISO-8601 datetime when the session ended |
| `duration` | INTEGER | Session length in minutes |
| `focus` | INTEGER | Focus rating 1–10 (NULL if skipped) |
| `topic` | TEXT | Optional topic or project label |
| `distracted` | INTEGER | 1 if distracted, 0 otherwise |
| `reason` | TEXT | Optional distraction reason |

You can query or export the database directly with any SQLite tool (e.g. `sqlite3 ~/.pomodoro_tracker.db`).

---

## Stopping the app

Click `Quit` in the menu, or kill the process:

```bash
pkill -f "python3 main.py"
```

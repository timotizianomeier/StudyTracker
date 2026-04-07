# 🍅 Pomodoro Tracker

A macOS menu bar app for tracking focused work sessions. Built with Python, it lives quietly in your menu bar, runs timed Pomodoro sessions, fires a native macOS notification with sound when time is up, and prompts you to log how the session went. All data is stored locally in SQLite — no network, no accounts.

---

## What it does

- **Pomodoro timer** in the menu bar with a live countdown (`🍅 24:59`)
- **Configurable session length** via a slider (5–55 min, default 25 min)
- **Pause & resume** a session at any time without losing progress
- **Toggle the countdown display** — show only the 🍅 icon if you find the clock distracting
- **Native macOS notification with sound** when the session ends
- **Post-session popup form** asking:
  - Focus rating (1–10 slider)
  - Topic / project label (optional free text)
  - Whether you got distracted, and if so why
- **Session history** with a full log table and summary statistics:
  - Average focus by time of day (morning / afternoon / evening / night)
  - Average focus by topic
  - Total sessions, total focus time, overall average focus rating
  - Daily study-time histogram by topic
- **Insights (Beta)** — distraction analytics window:
  - Top distraction words (frequency table with visual bar)
  - Distraction rate by hour of day and day of week
  - Weekly distraction rate trend line chart
- **Guided meditations** accessible any time from the menu:
  - 💨 **Breathing Exercise (1 min)** — animated box breathing (4 s inhale · 4 s hold · 4 s exhale · 4 s hold), backed by research on HRV and parasympathetic activation
  - 🌿 **5-4-3-2-1 Grounding** — step-by-step sensory grounding with emoji cues (👁️ see · 🖐️ touch · 👂 hear · 👃 smell · 👅 taste) and optional text fields to write down what you notice

---

## Requirements

- macOS (tested on macOS 13+)
- Python 3.10+
- `rumps`, `alembic`, `SQLAlchemy` (see `requirements.txt`)

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
| `⏸ Pause Session` | Pauses the timer (timer thread keeps running but time doesn't tick down); label changes to `▶ Resume Session` |
| `▶ Resume Session` | Resumes a paused session |
| `⏹ Stop Session` | Cancels the current session (no log entry created) |
| `✓ Show countdown` | Toggles the clock display next to the icon; when off, only `🍅` (or `⏸` if paused) is shown |
| `⚙ Configure…` | Slider to set session length from 5 to 55 minutes |
| `📋 View History` | Open the history & stats window (session log, statistics, daily chart) |
| `🔍 Insights (Beta)` | Open the distraction insights window |
| `🧘 Meditate ▶` | Submenu with two guided meditations (available any time) |
| `  💨 Breathing Exercise (1 min)` | Animated box-breathing timer with dark-mode UI |
| `  🌿 5-4-3-2-1 Grounding` | Step-by-step sensory grounding with emoji cues and text fields |
| `Quit` | Exit the app |

### Menu bar icon guide

| Display | Meaning |
|---|---|
| `🍅` | Idle — no session running |
| `🍅 22:14` | Session running, 22 min 14 s remaining |
| `⏸ 22:14` | Session paused at 22 min 14 s |
| `⏸` | Session paused (countdown display turned off) |

### Typical workflow

1. Click `▶ Start Session` and get to work.
2. The menu bar shows the remaining time (`🍅 22:14`).
3. Need a moment? Click `⏸ Pause Session` — the timer freezes. Click `▶ Resume Session` to continue.
4. When the timer hits zero, a macOS notification plays a sound and a popup form appears.
5. Rate your focus, add a topic, note any distractions, then hit **Save Session** (or **Skip** to discard).
6. Review trends any time via **View History** or dig into distractions via **Insights (Beta)**.

---

## Project structure

```
StudyTracker/
├── main.py          # rumps menu bar app and timer logic
├── db.py            # SQLite setup, writes, and aggregation queries
├── forms.py         # All tkinter UI (configure dialog, session form, history window, insights window)
├── alembic/         # Database migrations (Alembic)
│   └── versions/    # Migration scripts
├── alembic.ini      # Alembic configuration
├── requirements.txt
└── README.md
```

---

## Data

Sessions are stored in `~/.pomodoro_tracker.db` with this schema:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-incremented primary key |
| `start_time` | TEXT | ISO-8601 datetime when the session started |
| `timestamp` | TEXT | ISO-8601 datetime when the session ended |
| `duration` | INTEGER | Session length in minutes |
| `focus` | INTEGER | Focus rating 1–10 (NULL if skipped) |
| `topic` | TEXT | Optional topic or project label |
| `distracted` | INTEGER | 1 if distracted, 0 otherwise |
| `reason` | TEXT | Optional distraction reason |

Schema migrations are managed with [Alembic](https://alembic.sqlalchemy.org/). To apply any pending migrations after pulling:

```bash
alembic upgrade head
```

You can query or export the database directly with any SQLite tool (e.g. `sqlite3 ~/.pomodoro_tracker.db`).

---

## Stopping the app

Click `Quit` in the menu, or kill the process:

```bash
pkill -f "python3 main.py"
```

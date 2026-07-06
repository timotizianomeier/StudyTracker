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
  - Term (academic term / semester label, remembered across sessions)
  - Topic / project label (optional free text)
  - Whether you got distracted, and if so why
- **Mid-session distraction logging** — record what distracted you in the moment; entries are shown in the post-session form so you can reflect on them
- **Screen-lock awareness** — if your screen locks mid-session, you're asked on unlock whether you took a break or kept working; the timer adjusts accordingly
- **App Blocker** — automatically quits distracting apps when a session starts, and closes any that are opened mid-session (see [App Blocker](#app-blocker))
- **Interrupts toggle** — switch app-blocker interruptions off globally from the menu, or just for one session via a checkbox in the start dialog
- **Shutdown guard** — macOS shutdown, restart, or logout is blocked while a session is running; stop the session (or quit the app) first
- **Session history** with a full log table and summary statistics:
  - Average focus by time of day (morning / afternoon / evening / night)
  - Average focus by topic and by term
  - Total sessions, total focus time, overall average focus rating
  - Daily study-time histogram by topic
- **Insights (Beta)** — distraction analytics window:
  - Top distraction words (frequency table with visual bar)
  - Distraction rate by hour of day and day of week
  - Weekly distraction rate trend line chart
- **Guided meditations** accessible any time from the menu:
  - 💨 **Breathing Exercise (1 min)** — animated box breathing (4 s inhale · 4 s hold · 4 s exhale · 4 s hold)
  - 🌿 **5-4-3-2-1 Grounding** — step-by-step sensory grounding with emoji cues and optional text fields

---

## Requirements

- macOS 13 or later
- Python 3.10 or later (`python3 --version` to check)
- Dependencies listed in `requirements.txt` (installed via pip)

---

## Installation

Using a virtual environment is strongly recommended — it avoids permission errors and keeps dependencies isolated.

```bash
# 1. Clone or download the project
cd /path/to/StudyTracker

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python3 main.py
```

The `🍅` icon will appear in your **menu bar** (top-right of the screen) — the app has no Dock icon by design.

The SQLite database is created automatically at `~/.pomodoro_tracker.db` on first launch. App blocker preferences are stored at `~/.pomodoro_tracker_config.json`.

> **Each time you open a new terminal**, re-activate the virtual environment before running:
> ```bash
> source .venv/bin/activate
> python3 main.py
> ```

---

## Usage

### Menu items

| Menu item | What it does |
|---|---|
| `▶ Start Session` | Opens a duration picker (with a "Disable interrupts for this session" checkbox), then starts the countdown |
| `⏸ Pause Session` | Freezes the timer; label changes to `▶ Resume Session` |
| `▶ Resume Session` | Resumes a paused session |
| `⏹ Stop Session` | Cancels the session (asks to log it if ≥ 5 minutes elapsed) |
| `💭 Record Distraction` | Log what just distracted you mid-session; replayed in the post-session form |
| `✓ Show countdown` | Toggles the clock display; when off, only the icon is shown |
| `🔇 / 🔊 Play sound` | Toggles the completion sound |
| `✓ Interrupts` | Globally toggles app-blocker interruptions on/off |
| `⚙ Configuration ▶` | Submenu: `⏱ Session Duration…` (5–55 min slider) and `🚫 App Blocker…` |
| `📋 View History` | Full session log, statistics, and daily chart |
| `🔍 Insights (Beta)` | Distraction analytics window |
| `🧘 Meditate ▶` | Submenu with two guided meditations (available any time) |
| `Quit` | Exit the app |

### Menu bar icon guide

| Display | Meaning |
|---|---|
| `🍅` | Idle — no session running |
| `🍅 22:14` | Session running, 22 min 14 s remaining |
| `⏸ 22:14` | Session paused at 22 min 14 s |
| `⏸` | Session paused, countdown display off |

### Typical workflow

1. Click `▶ Start Session`, set your duration, and get to work.
2. The menu bar shows the remaining time (`🍅 22:14`). Any blocked apps are automatically closed.
3. If something distracts you, click `💭 Record Distraction` to note it without breaking flow.
4. When the timer hits zero, a macOS notification plays a sound and a popup form appears.
5. Rate your focus, add a topic, review any logged distractions, then hit **Save Session**.
6. Review trends via **View History** or dig into distractions via **Insights (Beta)**.

---

## App Blocker

The app blocker helps keep distracting apps off your screen during focus sessions.

**Default blocked apps:** WhatsApp, Mail, Messages, Slack, Discord, Telegram, Microsoft Teams, Microsoft Outlook, Mimestream, Spark.

**How it works:**

- **On session start** — any blocked apps that are already running are quit automatically (gracefully, as if you quit them yourself).
- **Mid-session** — if a blocked app is opened or brought to the front, it is immediately quit and a brief popup confirms this.

**To configure:** Click `⚙ Configuration → 🚫 App Blocker…` in the menu. You can enable/disable the feature and add or remove apps from the list. App names must match exactly what macOS shows (the name as it appears in the Dock or Activity Monitor).

**Turning interruptions off temporarily:** Untick `✓ Interrupts` in the menu to disable app blocking globally without touching your app list, or tick **Disable interrupts for this session** in the start dialog to skip blocking for a single session.

> **Automation permission:** The first time the app blocker quits an app, macOS will show a prompt: *"python3 wants to control [App]."* Click **OK** to grant it. If you accidentally denied it, go to **System Settings → Privacy & Security → Automation** and enable it for Python.

---

## Troubleshooting

### The app doesn't appear in the menu bar

- Make sure you ran `python3 main.py` and it's still running (it has no Dock icon).
- Check that you're looking in the menu bar at the **top-right** of your screen — it may be hidden if the bar is full. Try hiding other menu bar items to make room.
- If you see an error in the terminal, check the common errors below.

### `ModuleNotFoundError: No module named 'rumps'` (or any other module)

You either haven't installed dependencies or your virtual environment isn't active:

```bash
source .venv/bin/activate   # activate the venv
pip install -r requirements.txt
python3 main.py
```

If you skipped the virtual environment and used `pip install` directly, make sure `pip` and `python3` refer to the same Python:

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

### `pip install` fails or says "externally managed environment"

macOS Ventura and later protect the system Python. Use a virtual environment (see [Installation](#installation)), or if you installed Python via Homebrew:

```bash
pip install --break-system-packages -r requirements.txt
```

### App blocker doesn't close apps / nothing happens

1. Check that app blocking is enabled: `⚙ Configuration → 🚫 App Blocker…` → **Enable app blocking warnings** should be ticked.
2. Check that `✓ Interrupts` is ticked in the menu, and that you didn't tick **Disable interrupts for this session** when starting the session.
3. Verify the app name matches exactly — open Activity Monitor, find the app, and use the name shown there.
4. Grant Automation permission: **System Settings → Privacy & Security → Automation** → enable entries under Python.

### My Mac won't shut down / restart

A running session blocks shutdown, restart, and logout by design (you'll get a "Shutdown blocked" notification). Stop the session or quit the app via its `Quit` menu item, then shut down.

### Notifications don't appear

Go to **System Settings → Notifications** and make sure Python (or Script Editor) is allowed to send notifications. The first notification prompt may have appeared behind other windows.

### Multiple 🍅 icons in the menu bar

You have more than one instance running. Quit all of them and restart:

```bash
pkill -f "python3 main.py"
python3 main.py
```

### Database errors on launch

If you pulled new code, a schema migration may be needed:

```bash
alembic upgrade head
```

---

## Project structure

```
StudyTracker/
├── main.py          # rumps menu bar app, timer logic, app blocker
├── forms.py         # All tkinter UI (all windows and dialogs)
├── db.py            # SQLite setup, writes, and aggregation queries
├── config.py        # Persistent JSON config (app blocker settings)
├── window_runner.py # Subprocess host for tkinter windows
├── alembic/         # Database migrations
│   └── versions/
├── alembic.ini
├── requirements.txt
└── README.md
```

---

## Data

Sessions are stored in `~/.pomodoro_tracker.db`:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-incremented primary key |
| `start_time` | TEXT | ISO-8601 datetime when the session started |
| `timestamp` | TEXT | ISO-8601 datetime when the session ended |
| `duration` | INTEGER | Session length in minutes |
| `focus` | INTEGER | Focus rating 1–10 (NULL if skipped) |
| `topic` | TEXT | Optional topic or project label |
| `term` | TEXT | Academic term / semester label |
| `distracted` | INTEGER | 1 if distracted, 0 otherwise |
| `reason` | TEXT | Optional distraction reason |

App blocker preferences are stored separately in `~/.pomodoro_tracker_config.json`.

To apply schema migrations after pulling updates:

```bash
alembic upgrade head
```

You can query the database directly with any SQLite tool:

```bash
sqlite3 ~/.pomodoro_tracker.db "SELECT * FROM sessions ORDER BY timestamp DESC LIMIT 10;"
```

---

## Stopping the app

Click `Quit` in the menu, or from the terminal:

```bash
pkill -f "python3 main.py"
```

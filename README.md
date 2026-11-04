# 🍅 Pomodoro Tracker

A lightweight macOS menu bar app for tracking focused study and work sessions. Built with Python, it lives quietly in your menu bar, runs timed Pomodoro sessions, blocks distracting apps while you work, tracks your daily schedule goals, and prompts you to log how each session went. All data is stored locally in SQLite — no network, no accounts.

---

## ⚡ Quick Start (macOS)

Open **Terminal** and copy-paste the following commands:

```bash
# 1. Clone the repository
git clone https://github.com/timotizianomeier/StudyTracker.git
cd StudyTracker

# 2. Verify your Python has tkinter (used for popup windows)
python3 -c "import tkinter"
```

> **If step 2 prints `No module named '_tkinter'`:**
> - **Using Homebrew Python?** Run: `brew install python-tk`
> - **Otherwise:** Install Python from [python.org/downloads/macos](https://www.python.org/downloads/macos/) (includes `tkinter` out of the box).

Then create the virtual environment, install dependencies, and launch the app:

```bash
# 3. Create & activate a virtual environment, install dependencies, and run
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Look at the **top-right menu bar** of your screen — you'll see a **`🍅`** icon! (The app has no Dock icon by design.)

### Starting it next time

Whenever you want to launch the app again from a new terminal:

```bash
cd /path/to/StudyTracker
source .venv/bin/activate
python3 main.py
```

Or run it **in the background** so you can close the terminal window:

```bash
cd /path/to/StudyTracker && ./.venv/bin/python3 main.py >/dev/null 2>&1 &
```

---

## ✨ What It Does

- **Menu bar Pomodoro timer** with a live countdown (`🍅 24:59`)
- **Configurable session length** via a slider (5–55 min, default 25 min)
- **Pause & resume** a session at any time without losing progress
- **Toggle the countdown display** — show only the `🍅` icon if you find the clock distracting
- **Native macOS notification with sound** when a session finishes
- **Post-session popup form**:
  - **Term** chip selector (remembers your most recent term, or lets you add a new one)
  - **Focus rating** (1–10 slider, pre-set to today's average focus — or your last active day's average on your first session of the day)
  - **Topic / Project** chip selector (automatically filtered to show only topics from the selected term, plus an input to add a new topic)
  - **Distraction log** — review mid-session distractions and optionally note what distracted you
  - **Accidental-discard guard** — asks for confirmation if you press `Esc` or close the window before saving
- **Mid-session distraction capture (`💭 Record Distraction`)** — jot down a distracting thought in 2 seconds and get right back to focus; replayed when the session ends
- **Daily Schedule Goals (`🎯 Schedule Goals…`)**:
  - Set your target daily working window (default: start by `09:00`, finish by `18:00`)
  - **First-session daily check-in**: When you start your first session of the day, see a recap of your previous active study day — celebrating multi-day streaks when you hit your window, or showing clear cards for missed morning-start / evening-cutoff goals along with the notes you left yourself
  - **Late-start & past-cutoff reflection**: Prompts for a short note if your first session starts after your morning goal or if a session finishes past your evening cutoff
- **Screen-lock awareness** — if you lock your screen mid-session, asks on unlock whether you took a break (rewinds timer) or kept studying (keeps elapsed time)
- **App Blocker** — automatically quits distracting apps when a session starts and blocks them if opened mid-session (see [App Blocker](#-app-blocker))
- **Per-session Interrupts toggle** — interrupts default to **on** for every new session; disable them for the current session via the Start Session checkbox or the `✓ Interrupts` menu item, and they automatically reset to **on** when the session ends
- **Shutdown guard** — blocks macOS shutdown/restart/logout while a session is actively running so a session isn't lost accidentally
- **Session History (`📋 View History`)** — full log table, filterable by term, with summary stats and an interactive daily study chart (clickable topic legend & gap-aware timeline)
- **Insights (`🔍 Insights (Beta)`)** — distraction analytics & focus-vs-start-time charts
- **Guided meditations (`🧘 Meditate`)** — **Breathing Exercise (1 min)** and **5-4-3-2-1 Grounding** available any time from the menu bar

---

## 🧭 Usage

### Menu items

| Menu item | What it does |
|---|---|
| `▶ Start Session` | Opens the duration picker (with a *"Disable interrupts for this session"* checkbox), runs the daily schedule check-in on your first session of the day, and starts the countdown |
| `⏸ Pause Session` | Freezes the timer; label changes to `▶ Resume Session` |
| `▶ Resume Session` | Resumes a paused session |
| `⏹ Stop Session` | Ends the session early (prompts to log it if ≥ 5 minutes elapsed) |
| `💭 Record Distraction` | Quick popup to note what distracted you mid-session |
| `✓ Show countdown` | Toggles the `MM:SS` countdown next to the `🍅` icon |
| `✓ Play sound` | Toggles the completion sound |
| `✓ Interrupts` | Toggles app-blocker interruptions on/off for the current session (resets to **on** after each session) |
| `📋 View History` | Opens session history, statistics, and daily topic chart |
| `🔍 Insights (Beta)` | Opens distraction & focus analytics |
| `🧘 Meditate ▶` | `💨 Breathing Exercise (1 min)` and `🌿 5-4-3-2-1 Grounding` |
| `⚙ Configuration ▶` | `⏱ Session Duration…`, `🚫 App Blocker…`, and `🎯 Schedule Goals…` |
| `Quit` | Exits the menu bar app |

---

## 🚫 App Blocker

The app blocker keeps distracting apps off your screen during focus sessions.

**Default blocked apps:** WhatsApp, Mail, Messages, Slack, Discord, Telegram, Microsoft Teams, Microsoft Outlook, Mimestream, Spark.

- **On session start** (or when re-enabling interrupts mid-session): any running blocked apps are quit gracefully.
- **Mid-session**: if a blocked app is launched or brought to the front, a warning dialog appears and closes it.
- **Customize**: Click `⚙ Configuration → 🚫 App Blocker…` to enable/disable blocking or edit the app list. Use the exact app name shown in the Dock / Activity Monitor.

> **macOS Automation Permission:** The first time the app blocker quits an app, macOS will ask: *"Python wants to control [App]."* Click **Allow**. You can manage this anytime in **System Settings → Privacy & Security → Automation**.

---

## 🛠 Troubleshooting

### 1. `ModuleNotFoundError: No module named '_tkinter'`
Your Python installation doesn't have the Tk GUI library installed.
- If you use **Homebrew**:
  ```bash
  brew install python-tk
  ```
  Then recreate the virtual environment (`rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`).
- Or install the official macOS Python from [python.org/downloads/macos](https://www.python.org/downloads/macos/), which bundles `tkinter`.

### 2. `ModuleNotFoundError: No module named 'rumps'`
Your virtual environment isn't activated, or dependencies aren't installed yet:
```bash
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

### 3. The `🍅` icon doesn't appear
- Look at the **top-right menu bar** (not the Dock).
- On MacBooks with a camera notch, if you have many menu bar icons, macOS may hide new icons behind the notch — try quitting or hiding a few menu bar extras.

### 4. Multiple `🍅` icons in the menu bar
More than one instance is running. Stop all instances and start a single one:
```bash
pkill -f "main.py"
python3 main.py
```

### 5. Notifications don't appear
Open **System Settings → Notifications** and allow notifications for **Python** (the completion chime still plays via `afplay` even if banner notifications are disabled).

---

## 📁 Project Structure & Local Data

```text
StudyTracker/
├── main.py            # rumps menu bar app, timer loop, screen-lock & app-blocker observers
├── forms.py           # All tkinter windows, dialogs, and charts
├── schedule_goals.py  # Daily start/cutoff schedule-goal evaluation logic
├── db.py              # SQLite persistence & analytics queries
├── config.py          # JSON config persistence (app blocker & schedule goals)
├── window_runner.py   # Subprocess launcher for tkinter windows
├── alembic/           # Optional database migrations
├── requirements.txt   # Python dependencies
└── README.md
```

All data stays on your Mac:
- **Database**: `~/.pomodoro_tracker.db` (created automatically on first launch)
- **Settings**: `~/.pomodoro_tracker_config.json` (blocked apps & schedule goals)

To stop the app at any time, click **`Quit`** in the `🍅` menu or run `pkill -f "main.py"`.

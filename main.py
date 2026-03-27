#!/usr/bin/env python3
"""
Pomodoro Tracker – macOS menu bar app
Run with:  python main.py
"""

import queue
import subprocess
import threading
import time

import rumps

import db
from forms import show_configure_window, show_history_window, show_session_form

# ─── App ──────────────────────────────────────────────────────────────────────

class PomodoroApp(rumps.App):
    """Menu-bar Pomodoro timer with session logging."""

    _ICON_IDLE = "🍅"

    def __init__(self) -> None:
        super().__init__(self._ICON_IDLE, quit_button=None)

        # State
        self.session_minutes: int = 25
        self.time_remaining:  int = 0
        self.is_running:     bool = False
        self._timer_thread: threading.Thread | None = None
        self._done_queue: queue.Queue[int] = queue.Queue()

        # Menu items
        self._start_item  = rumps.MenuItem("▶  Start Session",  callback=self._start_session)
        self._stop_item   = rumps.MenuItem("⏹  Stop Session")
        self._config_item = rumps.MenuItem("⚙  Configure…",     callback=self._configure)
        self._hist_item   = rumps.MenuItem("📋  View History",   callback=self._view_history)
        self._quit_item   = rumps.MenuItem("Quit",              callback=rumps.quit_application)

        self.menu = [
            self._start_item,
            self._stop_item,
            None,
            self._config_item,
            self._hist_item,
            None,
            self._quit_item,
        ]

        # Tick every 0.5 s: update title and detect session completion
        self._tick = rumps.Timer(self._on_tick, 0.5)
        self._tick.start()

        db.init_db()

    # ── Internal timer ────────────────────────────────────────────────────────

    def _countdown(self, minutes: int) -> None:
        """Background thread: counts down and signals completion."""
        remaining = minutes * 60
        self.time_remaining = remaining
        while remaining > 0 and self.is_running:
            time.sleep(1)
            if self.is_running:
                remaining -= 1
                self.time_remaining = remaining

        if self.is_running:          # ended naturally, not stopped
            self.is_running = False
            self._done_queue.put(minutes)

    def _on_tick(self, _: rumps.Timer) -> None:
        """Main-thread poll: update countdown display and handle completion."""
        if self.is_running:
            m, s = divmod(self.time_remaining, 60)
            self.title = f"🍅 {m:02d}:{s:02d}"

        if not self._done_queue.empty():
            duration = self._done_queue.get_nowait()
            self.title = self._ICON_IDLE
            self._set_running(False)
            self._notify(duration)
            result = show_session_form(duration)
            if result:
                db.save_session(
                    duration,
                    result["focus"],
                    result["topic"],
                    result["distracted"],
                    result["reason"],
                )

    # ── Notification ──────────────────────────────────────────────────────────

    def _notify(self, duration: int) -> None:
        try:
            subprocess.run(
                [
                    "osascript", "-e",
                    f'display notification "Your {duration}-minute session is complete — '
                    f'take a break!" with title "🍅 Pomodoro Tracker" '
                    f'sound name "Glass"',
                ],
                check=False,
                timeout=5,
            )
        except Exception:
            pass

    # ── Menu state helpers ────────────────────────────────────────────────────

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        if running:
            self._start_item.set_callback(None)
            self._stop_item.set_callback(self._stop_session)
        else:
            self._start_item.set_callback(self._start_session)
            self._stop_item.set_callback(None)

    # ── Menu callbacks ────────────────────────────────────────────────────────

    def _start_session(self, _: rumps.MenuItem) -> None:
        if self.is_running:
            return
        self._set_running(True)
        self._timer_thread = threading.Thread(
            target=self._countdown,
            args=(self.session_minutes,),
            daemon=True,
        )
        self._timer_thread.start()

    def _stop_session(self, _: rumps.MenuItem) -> None:
        self.is_running = False
        self.title = self._ICON_IDLE
        self._set_running(False)

    def _configure(self, _: rumps.MenuItem) -> None:
        new_val = show_configure_window(self.session_minutes)
        if new_val is not None:
            self.session_minutes = new_val

    def _view_history(self, _: rumps.MenuItem) -> None:
        if self.is_running:
            rumps.alert(
                title="Session in progress",
                message="Stop or finish your current session before viewing history.",
                ok="OK",
            )
            return
        show_history_window()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PomodoroApp().run()

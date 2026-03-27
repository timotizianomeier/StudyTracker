#!/usr/bin/env python3
"""
Pomodoro Tracker – macOS menu bar app
Run with:  python3 main.py
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time

import rumps

import db

# ─── Subprocess window helpers ────────────────────────────────────────────────
# tkinter cannot run inside the rumps process: the Cocoa NSRunLoop (rumps) and
# the Tk event loop both require exclusive use of the main thread, so calling
# mainloop() from a rumps callback deadlocks.  Every window is therefore
# opened in a fresh subprocess via window_runner.py, which has no NSRunLoop
# and is free to run tkinter normally.

_RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "window_runner.py")


def _run_window(window_type: str, *args) -> dict | int | None:
    """
    Open a window in a subprocess and block until it closes.
    Returns the parsed JSON result printed by the subprocess, or None.
    Safe to call from a background thread.
    """
    cmd = [sys.executable, _RUNNER, window_type] + [str(a) for a in args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        out = proc.stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def _launch_window(window_type: str, *args) -> None:
    """Open a window in a subprocess without waiting (fire-and-forget)."""
    cmd = [sys.executable, _RUNNER, window_type] + [str(a) for a in args]
    try:
        subprocess.Popen(cmd)
    except Exception:
        pass


# ─── App ──────────────────────────────────────────────────────────────────────

class PomodoroApp(rumps.App):
    """Menu-bar Pomodoro timer with session logging."""

    _ICON_IDLE   = "🍅"
    _ICON_PAUSED = "⏸"

    def __init__(self) -> None:
        super().__init__(self._ICON_IDLE, quit_button=None)

        # State
        self.session_minutes: int  = 25
        self.time_remaining:  int  = 0
        self.is_running:      bool = False
        self.is_paused:       bool = False
        self.show_clock:      bool = True
        self._timer_thread: threading.Thread | None = None
        self._done_queue: queue.Queue[int] = queue.Queue()

        # Menu items
        self._status_item = rumps.MenuItem("No session running")
        self._start_item  = rumps.MenuItem("▶  Start Session",  callback=self._start_session)
        self._pause_item  = rumps.MenuItem("⏸  Pause Session")
        self._stop_item   = rumps.MenuItem("⏹  Stop Session")
        self._clock_item  = rumps.MenuItem("✓  Show countdown", callback=self._toggle_clock)
        self._config_item = rumps.MenuItem("⚙  Configure…",     callback=self._configure)
        self._hist_item   = rumps.MenuItem("📋  View History",   callback=self._view_history)
        self._quit_item   = rumps.MenuItem("Quit",              callback=rumps.quit_application)

        self._meditate_item = rumps.MenuItem("🧘  Meditate")
        self._meditate_item["breathing"] = rumps.MenuItem(
            "💨  Breathing Exercise (1 min)", callback=self._breathing_exercise
        )
        self._meditate_item["grounding"] = rumps.MenuItem(
            "🌿  5-4-3-2-1 Grounding", callback=self._grounding_exercise
        )

        self.menu = [
            self._status_item,
            None,
            self._start_item,
            self._pause_item,
            self._stop_item,
            None,
            self._clock_item,
            self._config_item,
            self._hist_item,
            self._meditate_item,
            None,
            self._quit_item,
        ]

        self._tick = rumps.Timer(self._on_tick, 0.5)
        self._tick.start()

        db.init_db()

    # ── Internal timer ────────────────────────────────────────────────────────

    def _countdown(self, minutes: int) -> None:
        """Background thread: counts down (skipping ticks while paused)."""
        remaining = minutes * 60
        self.time_remaining = remaining
        while remaining > 0 and self.is_running:
            time.sleep(1)
            if self.is_running and not self.is_paused:
                remaining -= 1
                self.time_remaining = remaining
        if self.is_running:
            self.is_running = False
            self._done_queue.put(minutes)

    def _on_tick(self, _: rumps.Timer) -> None:
        """Main-thread poll: refresh title and handle session completion."""
        if self.is_running:
            m, s = divmod(self.time_remaining, 60)
            time_str = f"{m:02d}:{s:02d}"
            icon = self._ICON_PAUSED if self.is_paused else self._ICON_IDLE
            self._status_item.title = (
                f"⏸  {time_str} — paused" if self.is_paused
                else f"⏱  {time_str} remaining"
            )
            self.title = f"{icon} {time_str}" if self.show_clock else icon

        if not self._done_queue.empty():
            duration = self._done_queue.get_nowait()
            self.is_paused = False
            self.title = self._ICON_IDLE
            self._set_running(False)
            self._notify(duration)
            # Run the session form in a background thread so the main thread
            # stays free (session is over so there's nothing else to tick).
            def _show_form() -> None:
                result = _run_window("session_form", duration)
                if result:
                    db.save_session(
                        duration,
                        result["focus"],
                        result.get("topic"),
                        result["distracted"],
                        result.get("reason"),
                    )
            threading.Thread(target=_show_form, daemon=True).start()

    # ── Notification ──────────────────────────────────────────────────────────

    def _notify(self, duration: int) -> None:
        try:
            rumps.notification(
                title="🍅 Pomodoro Tracker",
                subtitle="Session complete!",
                message=f"Your {duration}-minute session is done — take a break!",
                sound=True,
            )
        except Exception:
            try:
                subprocess.run(
                    ["osascript", "-e",
                     f'display notification "Your {duration}-minute session is done — '
                     f'take a break!" with title "🍅 Pomodoro Tracker" '
                     f'sound name "Glass"'],
                    check=False, timeout=5,
                )
            except Exception:
                pass

    # ── Menu state helpers ────────────────────────────────────────────────────

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        if running:
            self._start_item.set_callback(None)
            self._pause_item.set_callback(self._pause_session)
            self._stop_item.set_callback(self._stop_session)
        else:
            self._start_item.set_callback(self._start_session)
            self._pause_item.set_callback(None)
            self._stop_item.set_callback(None)
            self._pause_item.title = "⏸  Pause Session"
            self._status_item.title = "No session running"

    # ── Menu callbacks ────────────────────────────────────────────────────────

    def _start_session(self, _: rumps.MenuItem) -> None:
        if self.is_running:
            return
        self.is_paused = False
        self._set_running(True)
        self._timer_thread = threading.Thread(
            target=self._countdown, args=(self.session_minutes,), daemon=True
        )
        self._timer_thread.start()

    def _pause_session(self, _: rumps.MenuItem) -> None:
        if not self.is_running:
            return
        self.is_paused = not self.is_paused
        self._pause_item.title = (
            "▶  Resume Session" if self.is_paused else "⏸  Pause Session"
        )

    def _stop_session(self, _: rumps.MenuItem) -> None:
        elapsed_seconds = self.session_minutes * 60 - self.time_remaining
        self.is_running = False
        self.is_paused = False
        self.title = self._ICON_IDLE
        self._set_running(False)

        if elapsed_seconds >= 300:   # only log if at least 5 minutes elapsed
            elapsed_minutes = max(1, round(elapsed_seconds / 60))
            def _show_form() -> None:
                result = _run_window("session_form", elapsed_minutes)
                if result:
                    db.save_session(
                        elapsed_minutes,
                        result["focus"],
                        result.get("topic"),
                        result["distracted"],
                        result.get("reason"),
                    )
            threading.Thread(target=_show_form, daemon=True).start()

    def _toggle_clock(self, _: rumps.MenuItem) -> None:
        self.show_clock = not self.show_clock
        self._clock_item.title = (
            "✓  Show countdown" if self.show_clock else "    Show countdown"
        )
        if not self.show_clock and self.is_running:
            self.title = self._ICON_PAUSED if self.is_paused else self._ICON_IDLE

    def _configure(self, _: rumps.MenuItem) -> None:
        # Run in a background thread so the menu bar stays responsive.
        def _run() -> None:
            result = _run_window("configure", self.session_minutes)
            if result is not None:
                self.session_minutes = result
        threading.Thread(target=_run, daemon=True).start()

    def _view_history(self, _: rumps.MenuItem) -> None:
        if self.is_running:
            rumps.alert(
                title="Session in progress",
                message="Stop or finish your current session before viewing history.",
                ok="OK",
            )
            return
        _launch_window("history")

    def _breathing_exercise(self, _: rumps.MenuItem) -> None:
        _launch_window("breathing")

    def _grounding_exercise(self, _: rumps.MenuItem) -> None:
        _launch_window("grounding")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PomodoroApp().run()

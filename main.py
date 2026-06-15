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
from datetime import datetime

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
        self._done_queue:  queue.Queue[int] = queue.Queue()
        self._start_queue: queue.Queue[int] = queue.Queue()
        self._session_start_time: datetime | None = None
        self.sound_on:    bool = True
        self._distractions: list[str] = []
        self._app_warning_showing: bool = False

        # Screen-lock state
        self._lock_time: datetime | None = None
        self._time_remaining_at_lock: int = 0
        self._was_running_at_lock: bool = False
        self._was_paused_at_lock: bool = False
        self._time_adjustment: int = 0          # applied by countdown thread
        self._unlock_result_queue: queue.Queue = queue.Queue()
        self._screen_observers: list = []       # keep refs alive (prevent GC)
        # True while waiting for the user to answer the unlock popup; gates
        # normal session-complete handling so it doesn't race the popup.
        self._defer_until_unlock: bool = False
        self._session_finished_while_locked: bool = False
        self._finished_duration: int = 0

        # Menu items
        self._status_item = rumps.MenuItem("No session running")
        self._start_item  = rumps.MenuItem("▶  Start Session",  callback=self._start_session)
        self._pause_item  = rumps.MenuItem("⏸  Pause Session")
        self._stop_item   = rumps.MenuItem("⏹  Stop Session")
        self._clock_item  = rumps.MenuItem("✓  Show countdown", callback=self._toggle_clock)
        self._sound_item  = rumps.MenuItem("✓  Play sound",     callback=self._toggle_sound)
        self._config_item        = rumps.MenuItem("⚙  Configure…",     callback=self._configure)
        self._app_blocker_item   = rumps.MenuItem("🚫  App Blocker…",  callback=self._configure_app_blocker)
        self._distract_item      = rumps.MenuItem("💭  Record Distraction")
        self._hist_item     = rumps.MenuItem("📋  View History",       callback=self._view_history)
        self._insights_item = rumps.MenuItem("🔍  Insights (Beta)",   callback=self._view_insights)
        self._quit_item     = rumps.MenuItem("Quit",                   callback=rumps.quit_application)

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
            self._distract_item,
            None,
            self._clock_item,
            self._sound_item,
            self._hist_item,
            self._insights_item,
            self._meditate_item,
            None,
            self._config_item,
            self._app_blocker_item,
            None,
            self._quit_item,
        ]

        self._tick = rumps.Timer(self._on_tick, 0.5)
        self._tick.start()

        db.init_db()
        self._setup_screen_lock_detection()

    # ── Internal timer ────────────────────────────────────────────────────────

    def _countdown(self, seconds: int) -> None:
        """Background thread: counts down (skipping ticks while paused)."""
        remaining = seconds
        self.time_remaining = remaining
        while remaining > 0 and self.is_running:
            time.sleep(1)
            # Apply any pending time adjustment (e.g. from screen-lock handling).
            # Checked before decrement so it takes effect before the next tick.
            adj = self._time_adjustment
            if adj:
                remaining = max(0, remaining + adj)
                self._time_adjustment = 0
                self.time_remaining = remaining
            if remaining > 0 and self.is_running and not self.is_paused:
                remaining -= 1
                self.time_remaining = remaining
        if self.is_running:
            self.is_running = False
            self._done_queue.put(self.session_minutes)

    def _on_tick(self, _: rumps.Timer) -> None:
        """Main-thread poll: refresh title and handle session start/completion."""
        # Handle unlock-dialog result (answered after screen-lock)
        if not self._unlock_result_queue.empty():
            item = self._unlock_result_queue.get_nowait()
            result, elapsed = item
            took_break = not result or result.get("break", True)
            self._defer_until_unlock = False

            if not took_break:
                # User kept working through the lock period
                if self._session_finished_while_locked:
                    # Session already completed while locked — finalise it now
                    self._session_finished_while_locked = False
                    finished_dur = self._finished_duration
                    self._finished_duration = 0
                    self.is_paused = False
                    self.title = self._ICON_IDLE
                    self._set_running(False)
                    session_start = self._session_start_time
                    distractions_copy = list(self._distractions)
                    def _show_form_kept(d=finished_dur, ss=session_start, dc=distractions_copy) -> None:
                        form_result = _run_window("session_form", d, json.dumps(dc))
                        if form_result:
                            db.save_session(
                                d,
                                form_result["focus"],
                                form_result.get("topic"),
                                form_result["distracted"],
                                form_result.get("reason"),
                                start_time=ss,
                                term=form_result.get("term"),
                            )
                    threading.Thread(target=_show_form_kept, daemon=True).start()
                # else: timer still running — it kept counting, just continue
            else:
                # User was on a break — restore timer to the moment they left
                if self._session_finished_while_locked:
                    # Session completed while they were away — restart from lock time
                    self._session_finished_while_locked = False
                    self._finished_duration = 0
                    self.is_running = True
                    self._set_running(True)
                    self.is_paused = False
                    self._timer_thread = threading.Thread(
                        target=self._countdown,
                        args=(self._time_remaining_at_lock,),
                        daemon=True,
                    )
                    self._timer_thread.start()
                else:
                    # Timer still running — wind time back to when screen locked
                    self._time_adjustment = (
                        self._time_remaining_at_lock - self.time_remaining
                    )

        # Handle a pending start request (duration chosen in the picker window)
        if not self.is_running and not self._start_queue.empty():
            duration = self._start_queue.get_nowait()
            self.session_minutes = duration
            self.is_paused = False
            self._distractions.clear()
            self._session_start_time = datetime.now()
            self._set_running(True)
            self._timer_thread = threading.Thread(
                target=self._countdown, args=(self.session_minutes * 60,), daemon=True
            )
            self._timer_thread.start()
            threading.Thread(target=self._app_blocker_poll, daemon=True).start()

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
            if self._defer_until_unlock:
                # Timer finished while screen was locked — fire notification but
                # hold the session form until the user answers the unlock popup.
                self._session_finished_while_locked = True
                self._finished_duration = duration
                self._notify(duration)
            else:
                self.is_paused = False
                self._lock_time = None
                self.title = self._ICON_IDLE
                self._set_running(False)
                self._notify(duration)
                # Run the session form in a background thread so the main thread
                # stays free (session is over so there's nothing else to tick).
                session_start = self._session_start_time
                distractions_copy = list(self._distractions)
                def _show_form(d=duration, ss=session_start, dc=distractions_copy) -> None:
                    result = _run_window("session_form", d, json.dumps(dc))
                    if result:
                        db.save_session(
                            d,
                            result["focus"],
                            result.get("topic"),
                            result["distracted"],
                            result.get("reason"),
                            start_time=ss,
                            term=result.get("term"),
                        )
                threading.Thread(target=_show_form, daemon=True).start()

    # ── Notification ──────────────────────────────────────────────────────────

    def _notify(self, duration: int) -> None:
        if self.sound_on:
            # Play sound immediately via afplay — works regardless of notification
            # permissions.  Glass.aiff is a standard macOS system sound.
            try:
                subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
            except Exception:
                pass
        try:
            rumps.notification(
                title="🍅 Pomodoro Tracker",
                subtitle="Session complete!",
                message=f"Your {duration}-minute session is done — take a break!",
                sound=self.sound_on,
            )
        except Exception:
            try:
                sound_clause = 'sound name "Glass"' if self.sound_on else ""
                subprocess.run(
                    ["osascript", "-e",
                     f'display notification "Your {duration}-minute session is done — '
                     f'take a break!" with title "🍅 Pomodoro Tracker" '
                     f'{sound_clause}'],
                    check=False, timeout=5,
                )
            except Exception:
                pass

    # ── Screen-lock detection ─────────────────────────────────────────────────

    def _setup_screen_lock_detection(self) -> None:
        try:
            from Foundation import NSDistributedNotificationCenter, NSOperationQueue
            center = NSDistributedNotificationCenter.defaultCenter()
            token_lock = center.addObserverForName_object_queue_usingBlock_(
                "com.apple.screenIsLocked", None, NSOperationQueue.mainQueue(),
                lambda _n: self._on_screen_locked(),
            )
            token_unlock = center.addObserverForName_object_queue_usingBlock_(
                "com.apple.screenIsUnlocked", None, NSOperationQueue.mainQueue(),
                lambda _n: self._on_screen_unlocked(),
            )
            self._screen_observers = [token_lock, token_unlock]
        except Exception:
            pass  # PyObjC unavailable; screen-lock feature disabled

    def _on_screen_locked(self) -> None:
        if not self.is_running:
            return
        self._lock_time = datetime.now()
        self._time_remaining_at_lock = self.time_remaining
        self._was_paused_at_lock = self.is_paused
        if self.is_paused:
            # Already paused — no popup needed on unlock, timer stays paused
            self._was_running_at_lock = False
        else:
            # Actively running — let timer keep counting, show popup on unlock
            self._was_running_at_lock = True
            self._defer_until_unlock = True

    def _on_screen_unlocked(self) -> None:
        if not self._was_running_at_lock or self._lock_time is None:
            # Was already paused at lock (or not running) — nothing to do
            return
        lock_time = self._lock_time
        self._lock_time = None
        self._was_running_at_lock = False

        elapsed = int((datetime.now() - lock_time).total_seconds())

        def _ask() -> None:
            result = _run_window("screen_lock_dialog", elapsed)
            self._unlock_result_queue.put((result, elapsed))

        threading.Thread(target=_ask, daemon=True).start()

    # ── Menu state helpers ────────────────────────────────────────────────────

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        if running:
            self._start_item.set_callback(None)
            self._pause_item.set_callback(self._pause_session)
            self._stop_item.set_callback(self._stop_session)
            self._distract_item.set_callback(self._record_distraction)
        else:
            self._start_item.set_callback(self._start_session)
            self._pause_item.set_callback(None)
            self._stop_item.set_callback(None)
            self._distract_item.set_callback(None)
            self._pause_item.title = "⏸  Pause Session"
            self._status_item.title = "No session running"

    # ── Menu callbacks ────────────────────────────────────────────────────────

    def _start_session(self, _: rumps.MenuItem) -> None:
        if self.is_running:
            return
        # Open the duration-picker window in a background thread; the result
        # is picked up by _on_tick on the main thread to safely start the session.
        def _run() -> None:
            result = _run_window("start_session", self.session_minutes)
            if result is not None:
                self._start_queue.put(result)
        threading.Thread(target=_run, daemon=True).start()

    def _record_distraction(self, _: rumps.MenuItem) -> None:
        if not self.is_running:
            return
        def _run() -> None:
            result = _run_window("distraction_input")
            if result:
                self._distractions.append(result)
        threading.Thread(target=_run, daemon=True).start()

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
        self._was_running_at_lock = False
        self._defer_until_unlock = False
        self._session_finished_while_locked = False
        self._finished_duration = 0
        self._lock_time = None
        self.title = self._ICON_IDLE
        self._set_running(False)

        if elapsed_seconds >= 300:   # only log if at least 5 minutes elapsed
            elapsed_minutes = max(1, round(elapsed_seconds / 60))
            session_start = self._session_start_time
            distractions_copy = list(self._distractions)
            def _show_form(em=elapsed_minutes, ss=session_start, dc=distractions_copy) -> None:
                result = _run_window("session_form", em, json.dumps(dc))
                if result:
                    db.save_session(
                        em,
                        result["focus"],
                        result.get("topic"),
                        result["distracted"],
                        result.get("reason"),
                        start_time=ss,
                        term=result.get("term"),
                    )
            threading.Thread(target=_show_form, daemon=True).start()

    # ── App blocker ───────────────────────────────────────────────────────────

    def _check_blocked_apps(self) -> str | None:
        """Return the name of the first blocked app found running, or None."""
        import config as _cfg
        if not _cfg.is_app_blocking_enabled():
            return None
        blocked = set(_cfg.get_blocked_apps())
        if not blocked:
            return None
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 "tell application \"System Events\" to get name of "
                 "(processes where background only is false)"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
            running = {name.strip() for name in result.stdout.split(",")}
            for app in blocked:
                if app in running:
                    return app
        except Exception:
            pass
        return None

    def _app_blocker_poll(self) -> None:
        """Background thread: check every 30 s for blocked apps during a session."""
        last_warned = 0.0
        time.sleep(10)  # short grace period at session start
        while self.is_running:
            now = time.monotonic()
            # 3-minute cooldown between warnings; skip while paused or warning showing
            if (not self.is_paused
                    and not self._app_warning_showing
                    and now - last_warned > 180):
                detected = self._check_blocked_apps()
                if detected:
                    self._app_warning_showing = True
                    last_warned = now
                    def _warn(app: str = detected) -> None:
                        _run_window("app_warning", app)
                        self._app_warning_showing = False
                    threading.Thread(target=_warn, daemon=True).start()
            time.sleep(30)

    def _configure_app_blocker(self, _: rumps.MenuItem) -> None:
        def _run() -> None:
            import config as _cfg
            result = _run_window("app_blocker_settings")
            if result is not None:
                _cfg.save_app_blocking_settings(result["enabled"], result["apps"])
        threading.Thread(target=_run, daemon=True).start()

    def _toggle_clock(self, _: rumps.MenuItem) -> None:
        self.show_clock = not self.show_clock
        self._clock_item.title = (
            "✓  Show countdown" if self.show_clock else "    Show countdown"
        )
        if not self.show_clock and self.is_running:
            self.title = self._ICON_PAUSED if self.is_paused else self._ICON_IDLE

    def _toggle_sound(self, _: rumps.MenuItem) -> None:
        self.sound_on = not self.sound_on
        self._sound_item.title = (
            "✓  Play sound" if self.sound_on else "    Play sound"
        )

    def _configure(self, _: rumps.MenuItem) -> None:
        # Run in a background thread so the menu bar stays responsive.
        def _run() -> None:
            result = _run_window("configure", self.session_minutes)
            if result is not None:
                self.session_minutes = result
        threading.Thread(target=_run, daemon=True).start()

    def _view_insights(self, _: rumps.MenuItem) -> None:
        _launch_window("insights")

    def _view_history(self, _: rumps.MenuItem) -> None:
        _launch_window("history")

    def _breathing_exercise(self, _: rumps.MenuItem) -> None:
        _launch_window("breathing")

    def _grounding_exercise(self, _: rumps.MenuItem) -> None:
        _launch_window("grounding")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PomodoroApp().run()

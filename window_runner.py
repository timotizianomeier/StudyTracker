#!/usr/bin/env python3
"""
Standalone window host – launched as a subprocess by main.py.

Running tkinter inside the rumps process creates a deadlock: rumps' Cocoa
NSRunLoop and tkinter's Tk event loop both need the main thread and block
each other.  The fix is to run each window in a separate Python process that
has no NSRunLoop conflict and is not a background (LSUIElement) app.

Usage (called by main.py, not directly):
    python3 window_runner.py <window_type> [arg …]

Return value: JSON printed to stdout (for windows that return data).
"""

import json
import os
import sys

# Ensure the project directory is on the path regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _activate() -> None:
    """Make this fresh process the active foreground app."""
    try:
        from AppKit import NSApp
        NSApp.setActivationPolicy_(0)           # Regular (not LSUIElement)
        NSApp.activateIgnoringOtherApps_(True)
    except Exception:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(1)

    _activate()
    window = sys.argv[1]

    if window == "configure":
        current = int(sys.argv[2]) if len(sys.argv) > 2 else 25
        from forms import show_configure_window
        result = show_configure_window(current)
        if result is not None:
            print(json.dumps(result), flush=True)

    elif window == "session_form":
        duration = int(sys.argv[2])
        from forms import show_session_form
        result = show_session_form(duration)
        if result is not None:
            print(json.dumps(result), flush=True)

    elif window == "history":
        from forms import show_history_window
        show_history_window()

    elif window == "breathing":
        from forms import show_breathing_exercise
        show_breathing_exercise()

    elif window == "grounding":
        from forms import show_grounding_exercise
        show_grounding_exercise()


if __name__ == "__main__":
    main()

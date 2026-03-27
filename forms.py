"""All tkinter UI: configure dialog, session feedback form, history window."""

import os
import subprocess
import tkinter as tk
from tkinter import ttk

import db


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _bring_to_front(root: tk.Tk) -> None:
    """Reliably raise a tkinter window to the front from a macOS menu bar app.

    rumps runs as a background (LSUIElement) process, so the NSApp is never
    automatically the active application.  We must explicitly activate it
    before entering the Tk event loop, otherwise the window is created but
    remains invisible / non-interactive.
    """
    try:
        from AppKit import NSApp          # always available – rumps depends on pyobjc
        NSApp.activateIgnoringOtherApps_(True)
    except Exception:
        pass
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    root.after(300, lambda: root.attributes("-topmost", False))
    root.focus_force()


def _theme(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("aqua")        # macOS native look
    except tk.TclError:
        style.theme_use("clam")
    return style


# ─── Configure window ────────────────────────────────────────────────────────

def show_configure_window(current_minutes: int) -> int | None:
    """
    Slider dialog to change session duration (5–55 min).
    Returns the new duration (int) or None if cancelled.
    """
    _MIN, _MAX = 5, 55
    result: list[int | None] = [None]

    root = tk.Tk()
    root.title("Configure Session")
    root.geometry("360x210")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Session length", font=("", 13)).pack()

    # Clamp to the valid range in case a legacy value is outside it.
    # Use DoubleVar – ttk.Scale updates it as a float internally.
    clamped = max(_MIN, min(_MAX, current_minutes))
    dur_var = tk.DoubleVar(value=float(clamped))

    val_label = ttk.Label(frame, text=f"{clamped} min", font=("", 26, "bold"))
    val_label.pack(pady=(4, 10))

    def _on_slider(val: str) -> None:
        v = int(float(val))
        val_label.config(text=f"{v} min")

    slider_row = ttk.Frame(frame)
    slider_row.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(slider_row, text=str(_MIN), foreground="gray").pack(side=tk.LEFT)
    ttk.Scale(
        slider_row, from_=_MIN, to=_MAX, orient=tk.HORIZONTAL,
        variable=dur_var, command=_on_slider, length=240,
    ).pack(side=tk.LEFT, padx=8, expand=True, fill=tk.X)
    ttk.Label(slider_row, text=str(_MAX), foreground="gray").pack(side=tk.LEFT)

    def _ok() -> None:
        result[0] = int(round(dur_var.get()))
        root.quit()

    def _cancel() -> None:
        root.quit()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=(10, 0))
    ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="   OK   ", command=_ok).pack(side=tk.LEFT, padx=6)

    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.bind("<Return>", lambda _: _ok())
    root.bind("<Escape>", lambda _: _cancel())

    root.mainloop()
    root.destroy()
    return result[0]


# ─── Post-session feedback form ───────────────────────────────────────────────

def show_session_form(duration_minutes: int) -> dict | None:
    """
    Modal form shown after each session ends.
    Returns dict {focus, topic, distracted, reason} or None if skipped.
    """
    result: list[dict | None] = [None]

    root = tk.Tk()
    root.title("Session Complete!")
    root.geometry("460x540")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    # ── Scrollable container ──────────────────────────────────────────────────
    outer = ttk.Frame(root)
    outer.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(outer, highlightthickness=0)
    vscroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    frame = ttk.Frame(canvas, padding=24)
    canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw")

    def _on_frame_configure(_: tk.Event) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event: tk.Event) -> None:
        canvas.itemconfig(canvas_window, width=event.width)

    frame.bind("<Configure>", _on_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    # ── Header ────────────────────────────────────────────────────────────────
    ttk.Label(frame, text="🍅  Session Complete!", font=("", 17, "bold")).pack(pady=(0, 4))
    ttk.Label(
        frame,
        text=f"Duration: {duration_minutes} min",
        foreground="gray",
        font=("", 12),
    ).pack(pady=(0, 18))

    # ── Focus rating ──────────────────────────────────────────────────────────
    focus_lf = ttk.LabelFrame(frame, text="  Focus Rating  ", padding=12)
    focus_lf.pack(fill=tk.X, pady=(0, 12))

    focus_var = tk.DoubleVar(value=7.0)

    rating_lbl = ttk.Label(
        focus_lf, text="7", font=("", 32, "bold"), width=3, anchor="center"
    )
    rating_lbl.pack()

    def _on_scale(val: str) -> None:
        rating_lbl.config(text=str(int(float(val))))

    ttk.Scale(
        focus_lf, from_=1, to=10, orient=tk.HORIZONTAL,
        variable=focus_var, command=_on_scale, length=340,
    ).pack(pady=(6, 2))

    tips = ttk.Frame(focus_lf)
    tips.pack(fill=tk.X)
    ttk.Label(tips, text="1 – terrible", foreground="gray", font=("", 10)).pack(side=tk.LEFT)
    ttk.Label(tips, text="10 – perfect", foreground="gray", font=("", 10)).pack(side=tk.RIGHT)

    # ── Topic ─────────────────────────────────────────────────────────────────
    topic_lf = ttk.LabelFrame(frame, text="  Topic / Project (optional)  ", padding=12)
    topic_lf.pack(fill=tk.X, pady=(0, 12))

    topic_var = tk.StringVar()
    ttk.Entry(topic_lf, textvariable=topic_var, font=("", 13)).pack(fill=tk.X)
    ttk.Label(
        topic_lf,
        text="e.g.  Math homework · Work report · Reading",
        foreground="gray",
        font=("", 10),
    ).pack(anchor=tk.W, pady=(4, 0))

    # ── Distraction ───────────────────────────────────────────────────────────
    distract_lf = ttk.LabelFrame(frame, text="  Distractions  ", padding=12)
    distract_lf.pack(fill=tk.X, pady=(0, 12))

    distracted_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        distract_lf,
        text="I got distracted during this session",
        variable=distracted_var,
    ).pack(anchor=tk.W)

    reason_container = ttk.Frame(distract_lf)
    ttk.Label(reason_container, text="What distracted you?").pack(anchor=tk.W)
    reason_text = tk.Text(
        reason_container, height=3, font=("", 12), wrap=tk.WORD,
        relief="solid", borderwidth=1,
    )
    reason_text.pack(fill=tk.X, pady=(2, 0))

    def _toggle_reason(*_: object) -> None:
        if distracted_var.get():
            reason_container.pack(fill=tk.X, pady=(10, 0))
        else:
            reason_container.pack_forget()

    distracted_var.trace_add("write", _toggle_reason)

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(16, 0))

    def _submit() -> None:
        result[0] = {
            "focus": max(1, min(10, int(float(focus_var.get())))),
            "topic": topic_var.get().strip() or None,
            "distracted": distracted_var.get(),
            "reason": (
                reason_text.get("1.0", tk.END).strip() or None
                if distracted_var.get()
                else None
            ),
        }
        root.quit()

    def _skip() -> None:
        root.quit()

    ttk.Button(btn_frame, text="Skip (don't log)", command=_skip).pack(side=tk.LEFT)
    ttk.Button(btn_frame, text="💾  Save Session", command=_submit).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", _skip)
    root.bind("<Escape>", lambda _: _skip())

    root.mainloop()
    root.destroy()
    return result[0]


# ─── History window ───────────────────────────────────────────────────────────

def show_history_window() -> None:
    """Read-only history & stats viewer."""
    root = tk.Tk()
    root.title("🍅 Pomodoro History")
    root.geometry("900x600")
    root.minsize(700, 450)
    _theme(root)
    _bring_to_front(root)

    nb = ttk.Notebook(root)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # ── Tab 1: Session log ────────────────────────────────────────────────────
    log_tab = ttk.Frame(nb)
    nb.add(log_tab, text="  Session Log  ")

    cols = ("date", "time", "dur", "focus", "topic", "dist", "reason")
    col_labels = {
        "date":  "Date",
        "time":  "Time",
        "dur":   "Min",
        "focus": "Focus",
        "topic": "Topic",
        "dist":  "Distracted",
        "reason":"Notes",
    }
    col_widths = {
        "date": 100, "time": 70, "dur": 50,
        "focus": 55, "topic": 160, "dist": 75, "reason": 220,
    }

    tree_frame = ttk.Frame(log_tab)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
    for col in cols:
        tree.heading(col, text=col_labels[col])
        tree.column(col, width=col_widths[col], anchor="center" if col in ("dur", "focus", "dist") else "w")

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    hsb.pack(side=tk.BOTTOM, fill=tk.X)
    tree.pack(fill=tk.BOTH, expand=True)

    sessions = db.get_all_sessions()
    for i, row in enumerate(sessions):
        ts = row["timestamp"]
        try:
            date_part, time_part = ts[:10], ts[11:16]
        except (IndexError, TypeError):
            date_part, time_part = ts, ""
        tag = "even" if i % 2 == 0 else "odd"
        tree.insert(
            "", tk.END, tags=(tag,),
            values=(
                date_part,
                time_part,
                row["duration"],
                row["focus"] if row["focus"] is not None else "–",
                row["topic"] or "",
                "Yes" if row["distracted"] else "No",
                row["reason"] or "",
            ),
        )

    tree.tag_configure("even", background="#f7f7f7")
    tree.tag_configure("odd",  background="#ffffff")

    # Status bar for log tab
    summary = db.get_summary()
    status_text = (
        f"  {summary.get('total_sessions', 0)} sessions  •  "
        f"{summary.get('total_minutes', 0) or 0} total minutes  •  "
        f"Avg focus: {summary.get('avg_focus') or '–'}"
    )
    ttk.Label(log_tab, text=status_text, foreground="gray", anchor="w").pack(
        fill=tk.X, padx=8, pady=(0, 6)
    )

    # ── Tab 2: Statistics ─────────────────────────────────────────────────────
    stats_tab = ttk.Frame(nb, padding=16)
    nb.add(stats_tab, text="  Statistics  ")

    # Summary banner
    banner = ttk.LabelFrame(stats_tab, text="  Overall  ", padding=12)
    banner.pack(fill=tk.X, pady=(0, 16))

    total_s   = summary.get("total_sessions") or 0
    total_min = summary.get("total_minutes")  or 0
    avg_focus = summary.get("avg_focus")       or "–"
    total_h   = f"{total_min // 60}h {total_min % 60}m" if total_min else "0m"

    for text in (
        f"Sessions completed: {total_s}",
        f"Total focus time:   {total_h}",
        f"Average focus:      {avg_focus} / 10",
    ):
        ttk.Label(banner, text=text, font=("", 13)).pack(anchor=tk.W, pady=1)

    # Two-column layout for the breakdown tables
    cols_frame = ttk.Frame(stats_tab)
    cols_frame.pack(fill=tk.BOTH, expand=True)
    cols_frame.columnconfigure(0, weight=1)
    cols_frame.columnconfigure(1, weight=1)

    # By time of day
    tod_lf = ttk.LabelFrame(cols_frame, text="  Avg Focus by Time of Day  ", padding=10)
    tod_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

    tod_tree = ttk.Treeview(
        tod_lf, columns=("period", "avg", "count"), show="headings", height=6
    )
    tod_tree.heading("period", text="Period")
    tod_tree.heading("avg",    text="Avg Focus")
    tod_tree.heading("count",  text="Sessions")
    tod_tree.column("period", width=190, anchor="w")
    tod_tree.column("avg",    width=80,  anchor="center")
    tod_tree.column("count",  width=70,  anchor="center")
    tod_tree.pack(fill=tk.BOTH, expand=True)

    for row in db.get_stats_by_time_of_day():
        tod_tree.insert("", tk.END, values=(row["period"], row["avg_focus"], row["sessions"]))

    # By topic
    top_lf = ttk.LabelFrame(cols_frame, text="  Avg Focus by Topic  ", padding=10)
    top_lf.grid(row=0, column=1, sticky="nsew")

    top_tree = ttk.Treeview(
        top_lf, columns=("topic", "avg", "count", "total"), show="headings", height=6
    )
    top_tree.heading("topic", text="Topic")
    top_tree.heading("avg",   text="Avg Focus")
    top_tree.heading("count", text="Sessions")
    top_tree.heading("total", text="Total min")
    top_tree.column("topic", width=140, anchor="w")
    top_tree.column("avg",   width=75,  anchor="center")
    top_tree.column("count", width=65,  anchor="center")
    top_tree.column("total", width=70,  anchor="center")

    tsb = ttk.Scrollbar(top_lf, orient="vertical", command=top_tree.yview)
    top_tree.configure(yscrollcommand=tsb.set)
    tsb.pack(side=tk.RIGHT, fill=tk.Y)
    top_tree.pack(fill=tk.BOTH, expand=True)

    for row in db.get_stats_by_topic():
        top_tree.insert(
            "", tk.END,
            values=(row["topic"], row["avg_focus"], row["sessions"], row["total_min"])
        )

    # Refresh / Close buttons
    btn_bar = ttk.Frame(stats_tab)
    btn_bar.pack(fill=tk.X, pady=(12, 0))

    def _refresh() -> None:
        root.destroy()
        show_history_window()

    ttk.Button(btn_bar, text="↺  Refresh", command=_refresh).pack(side=tk.LEFT)
    ttk.Button(btn_bar, text="Close", command=root.destroy).pack(side=tk.RIGHT)

    root.mainloop()
    # No root.destroy() – destroy is called by Close button or window close

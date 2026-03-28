"""All tkinter UI: configure dialog, session feedback form, history window,
breathing exercise, and 5-4-3-2-1 grounding."""

import math
import tkinter as tk
from tkinter import ttk

import db


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _bring_to_front(root: tk.Tk) -> None:
    """Raise and focus the window once it is rendered.

    NSApp activation policy is handled by _open_window() in main.py before
    any tkinter function is called.  This helper only needs to lift the window
    and steal keyboard focus — done twice (immediately + after 100 ms) so it
    works regardless of how long the initial widget build takes.
    """
    def _raise() -> None:
        try:
            root.lift()
            root.attributes("-topmost", True)
            root.focus_force()
            root.after(800, lambda: root.attributes("-topmost", False))
        except Exception:
            pass

    _raise()
    root.after(100, _raise)


def _theme(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("aqua")        # macOS native look
    except tk.TclError:
        style.theme_use("clam")
    return style


# ─── Shared: duration-picker widget builder ───────────────────────────────────

def _build_duration_picker(
    frame: ttk.Frame,
    current_minutes: int,
    _min: int = 5,
    _max: int = 55,
) -> tk.DoubleVar:
    """
    Add a session-length label, value display, and slider to *frame*.
    Returns the DoubleVar that holds the chosen value.
    """
    ttk.Label(frame, text="Session length", font=("", 13)).pack()

    clamped  = max(_min, min(_max, current_minutes))
    dur_var  = tk.DoubleVar(value=float(clamped))
    val_label = ttk.Label(frame, text=f"{clamped} min", font=("", 26, "bold"))
    val_label.pack(pady=(4, 10))

    def _on_slider(val: str) -> None:
        val_label.config(text=f"{int(float(val))} min")

    slider_row = ttk.Frame(frame)
    slider_row.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(slider_row, text=str(_min), foreground="gray").pack(side=tk.LEFT)
    ttk.Scale(
        slider_row, from_=_min, to=_max, orient=tk.HORIZONTAL,
        variable=dur_var, command=_on_slider, length=240,
    ).pack(side=tk.LEFT, padx=8, expand=True, fill=tk.X)
    ttk.Label(slider_row, text=str(_max), foreground="gray").pack(side=tk.LEFT)
    return dur_var


# ─── Start-session window (slider + Play button) ──────────────────────────────

def show_start_window(current_minutes: int) -> int | None:
    """
    Duration picker shown when the user clicks Start Session.
    Returns the chosen duration (int) or None if cancelled.
    """
    result: list[int | None] = [None]

    root = tk.Tk()
    root.title("Start Session")
    root.geometry("360x230")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    dur_var = _build_duration_picker(frame, current_minutes)

    def _start() -> None:
        result[0] = int(round(dur_var.get()))
        root.quit()

    def _cancel() -> None:
        root.quit()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=(10, 0))
    ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="▶  Start", command=_start).pack(side=tk.LEFT, padx=6)

    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.bind("<Return>", lambda _: _start())
    root.bind("<Escape>", lambda _: _cancel())

    root.mainloop()
    root.destroy()
    return result[0]


# ─── Configure window ────────────────────────────────────────────────────────

def show_configure_window(current_minutes: int) -> int | None:
    """
    Slider dialog to change the default session duration without starting.
    Returns the new duration (int) or None if cancelled.
    """
    result: list[int | None] = [None]

    root = tk.Tk()
    root.title("Configure Session")
    root.geometry("360x230")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    dur_var = _build_duration_picker(frame, current_minutes)

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

    # Enable trackpad / mouse-wheel scrolling anywhere in the window.
    # bind_all catches the event even when the pointer is over a child widget.
    def _on_mousewheel(event: tk.Event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 30)), "units")

    root.bind_all("<MouseWheel>", _on_mousewheel)

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

    # Enable trackpad/mousewheel scrolling on the session log treeview
    tree.bind("<MouseWheel>",
              lambda e: tree.yview_scroll(int(-1 * (e.delta / 30)), "units"))

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

    style = ttk.Style(root)
    style.configure("Treeview", foreground="#000000", background="#ffffff",
                    fieldbackground="#ffffff", rowheight=22)
    style.configure("Treeview.Heading", foreground="#000000")
    style.map("Treeview", foreground=[("selected", "#ffffff")])

    tree.tag_configure("even", background="#f0f0f0", foreground="#000000")
    tree.tag_configure("odd",  background="#ffffff", foreground="#000000")

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

    # ── Tab 3: Daily Histogram ────────────────────────────────────────────────
    hist_tab = ttk.Frame(nb)
    nb.add(hist_tab, text="  Daily Chart  ")

    hist_data = db.get_daily_by_topic()
    if not hist_data:
        ttk.Label(hist_tab, text="No sessions recorded yet.",
                  font=("", 13), foreground="gray").pack(expand=True)
    else:
        # ── Organise data ────────────────────────────────────────────────
        # day_topic[day][topic] = (total_min, avg_focus, sessions)
        day_topic: dict[str, dict[str, tuple[int, float | None, int]]] = {}
        all_topics: set[str] = set()
        for _row in hist_data:
            _d, _t = _row["day"], _row["topic"]
            if _d not in day_topic:
                day_topic[_d] = {}
            day_topic[_d][_t] = (_row["total_min"], _row["avg_focus"], _row["sessions"])
            all_topics.add(_t)

        hist_days   = sorted(day_topic.keys())
        hist_topics = sorted(all_topics)

        def _day_avg_focus(day: str) -> float | None:
            """Weighted average focus for the day (weighted by session count)."""
            total_s, weighted = 0, 0.0
            for _total_m, _af, _s in day_topic[day].values():
                if _af is not None:
                    weighted += _af * _s
                    total_s  += _s
            return round(weighted / total_s, 1) if total_s else None

        _PALETTE = [
            "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
            "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
        ]
        topic_color = {t: _PALETTE[i % len(_PALETTE)] for i, t in enumerate(hist_topics)}

        # ── Layout constants ─────────────────────────────────────────────
        ML, MR, MT, MB = 58, 24, 48, 56   # margins: left, right, top, bottom
        BW, BG = 52, 18                    # bar width, gap between bars
        CH     = 260                       # chart drawable height
        SEG_LABEL_MIN_H = 22               # min pixel height to show a focus label inside segment

        _max_min = max(sum(v[0] for v in day_topic[d].values()) for d in hist_days)
        _max_h   = _max_min / 60.0
        _y_max   = max(0.5, math.ceil(_max_h * 2) / 2)   # round up to nearest 0.5 h

        _canvas_w = ML + MR + len(hist_days) * (BW + BG)
        _canvas_h = MT + CH + MB

        def _min_to_y(minutes: float) -> int:
            return MT + CH - int(CH * minutes / (_y_max * 60))

        # ── Legend (fixed, below chart) ──────────────────────────────────
        leg_frame = ttk.Frame(hist_tab)
        leg_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=ML + 8, pady=(0, 6))
        for _t in hist_topics:
            _swatch = tk.Canvas(leg_frame, width=14, height=14,
                                highlightthickness=0, bg=topic_color[_t])
            _swatch.pack(side=tk.LEFT, padx=(0, 4))
            ttk.Label(leg_frame, text=_t, font=("", 11)).pack(
                side=tk.LEFT, padx=(0, 16))

        # ── Scrollable canvas ────────────────────────────────────────────
        _scroll_frame = ttk.Frame(hist_tab)
        _scroll_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        _hsb = ttk.Scrollbar(_scroll_frame, orient="horizontal")
        _hsb.pack(side=tk.BOTTOM, fill=tk.X)

        cv = tk.Canvas(_scroll_frame, bg="white", highlightthickness=0,
                       xscrollcommand=_hsb.set)
        cv.pack(fill=tk.BOTH, expand=True)
        _hsb.config(command=cv.xview)
        cv.configure(scrollregion=(0, 0, _canvas_w, _canvas_h))

        # Scroll to most-recent (right end) on open
        cv.after(150, lambda: cv.xview_moveto(1.0))

        # Mousewheel scrolls the chart horizontally
        cv.bind("<MouseWheel>",
                lambda e: cv.xview_scroll(int(-1 * (e.delta / 30)), "units"))

        # ── Grid lines + Y-axis labels ───────────────────────────────────
        _n_ticks = int(_y_max / 0.5) + 1
        for _i in range(_n_ticks):
            _vh = _i * 0.5
            _gy = _min_to_y(_vh * 60)
            cv.create_line(ML, _gy, _canvas_w - MR, _gy,
                           fill="#e4e4e4", dash=(3, 4))
            _lbl = f"{int(_vh)}h" if _vh == int(_vh) else f"{_vh:.1f}h"
            cv.create_text(ML - 6, _gy, text=_lbl, anchor="e",
                           font=("", 11), fill="#555")

        # ── Axes ─────────────────────────────────────────────────────────
        cv.create_line(ML, MT, ML, MT + CH, fill="#bbb")
        cv.create_line(ML, MT + CH, _canvas_w - MR, MT + CH, fill="#bbb")

        # ── Title ────────────────────────────────────────────────────────
        cv.create_text(ML + (_canvas_w - ML - MR) / 2, 8,
                       text="Daily Study Time by Module",
                       anchor="n", font=("", 13, "bold"), fill="#333")

        # ── Bars ─────────────────────────────────────────────────────────
        for _di, _day in enumerate(hist_days):
            _x0 = ML + _di * (BW + BG)
            _x1 = _x0 + BW
            _cx = (_x0 + _x1) / 2
            _day_data = day_topic[_day]
            _total_m  = sum(v[0] for v in _day_data.values())
            _yc       = MT + CH   # y-cursor, stacks from bottom up

            for _tp in hist_topics:
                if _tp not in _day_data:
                    continue
                _seg_m, _seg_af, _ = _day_data[_tp]
                _bh  = max(1, int(CH * _seg_m / (_y_max * 60)))
                _yt  = _yc - _bh
                cv.create_rectangle(_x0, _yt, _x1, _yc,
                                    fill=topic_color[_tp], outline="white", width=1)
                # Focus label inside segment (only if segment is tall enough)
                if _seg_af is not None and _bh >= SEG_LABEL_MIN_H:
                    _mid_y = (_yt + _yc) / 2
                    cv.create_text(_cx, _mid_y, text=f"{_seg_af:.1f}",
                                   font=("", 10, "bold"), fill="white",
                                   anchor="center")
                _yc = _yt

            # Day average-focus label (top line above bar)
            _daf = _day_avg_focus(_day)
            if _daf is not None:
                cv.create_text(_cx, _yc - 4, text=f"★ {_daf:.1f}",
                               anchor="s", font=("", 10), fill="#555")
                _yc -= 16   # shift so hours label doesn't overlap

            # Total-hours label (second line above bar)
            _th = _total_m / 60
            _total_lbl = f"{_th:.1f}h" if _th >= 0.1 else f"{_total_m}m"
            cv.create_text(_cx, _yc - 2, text=_total_lbl, anchor="s",
                           font=("", 11, "bold"), fill="#222")

            # Date label below x-axis (rotated 45°)
            _short = _day[5:]   # "MM-DD"
            cv.create_text(_x0 + BW // 2, MT + CH + 5,
                           text=_short, anchor="nw",
                           font=("", 10), fill="#555", angle=45)

    root.mainloop()
    # No root.destroy() – destroy is called by Close button or window close


# ─── Breathing exercise ───────────────────────────────────────────────────────

def show_breathing_exercise() -> None:
    """
    1-minute box-breathing exercise: 4 s inhale · 4 s hold · 4 s exhale · 4 s hold.

    Box breathing (also called 4-4-4-4 or square breathing) is well-studied
    for activating the parasympathetic nervous system, reducing cortisol, and
    improving HRV.  See: Zaccaro et al. (2018) Front. Hum. Neurosci.
    """
    TOTAL  = 60
    PHASES = [                  # (label, duration_s, kind)
        ("BREATHE IN",  4, 0),  # 0 → expand circle
        ("HOLD",        4, 1),  # 1 → hold at MAX
        ("BREATHE OUT", 4, 2),  # 2 → shrink circle
        ("HOLD",        4, 3),  # 3 → hold at MIN
    ]
    CYCLE              = sum(p[1] for p in PHASES)   # 16 s  → 3.75 cycles
    MIN_R, MAX_R       = 42, 100
    BG, CLR, CLR_GLOW  = "#0d1b2a", "#4fa3d9", "#1d4a72"
    CW = CH            = 260

    root = tk.Tk()
    root.title("Breathing Exercise")
    root.geometry("310x440")
    root.resizable(False, False)
    root.configure(bg=BG)
    _bring_to_front(root)

    # ── Header ────────────────────────────────────────────────────────────
    tk.Label(root, text="Box Breathing", font=("", 17, "bold"),
             bg=BG, fg="white").pack(pady=(18, 3))
    tk.Label(root, text="Inhale 4 s  ·  Hold 4 s  ·  Exhale 4 s  ·  Hold 4 s",
             font=("", 10), bg=BG, fg="#6a9ec0").pack()

    # ── Animated canvas ───────────────────────────────────────────────────
    canvas = tk.Canvas(root, width=CW, height=CH, bg=BG, highlightthickness=0)
    canvas.pack(pady=(8, 0))
    cx = cy = CW // 2

    pt_phase = canvas.create_text(cx, cy - 16, text="", font=("", 15, "bold"), fill="white")
    pt_count = canvas.create_text(cx, cy + 26, text="", font=("", 40, "bold"), fill="white")

    # ── Progress bar (hand-drawn for dark-theme consistency) ──────────────
    pb_cv = tk.Canvas(root, width=260, height=6, bg=BG, highlightthickness=0)
    pb_cv.pack(pady=(4, 0))
    pb_cv.create_rectangle(0, 0, 260, 6, fill="#1d3a52", outline="")
    pb_bar = pb_cv.create_rectangle(0, 0, 0, 6, fill=CLR, outline="")

    time_lbl = tk.Label(root, text="1:00 remaining", font=("", 11), bg=BG, fg="#6a9ec0")
    time_lbl.pack(pady=(5, 8))

    running = [True]
    elapsed = [0.0]

    def _draw(r: int) -> None:
        canvas.delete("circle")
        gr = r + 16
        canvas.create_oval(cx-gr, cy-gr, cx+gr, cy+gr,
                           fill=CLR_GLOW, outline="", tags="circle")
        canvas.create_oval(cx-r,  cy-r,  cx+r,  cy+r,
                           fill=CLR,      outline="", tags="circle")
        canvas.tag_raise(pt_phase)
        canvas.tag_raise(pt_count)

    def _stop() -> None:
        running[0] = False
        root.quit()

    stop_btn = tk.Button(root, text="Stop", command=_stop,
                          bg="#1d3a52", fg="white", relief="flat",
                          activebackground="#2a5272", activeforeground="white",
                          font=("", 12), padx=18, pady=6, cursor="hand2", bd=0)
    stop_btn.pack(pady=(0, 14))

    def _tick() -> None:
        if not running[0]:
            return
        elapsed[0] = min(elapsed[0] + 0.05, float(TOTAL))
        t = elapsed[0]

        if t >= TOTAL:
            # ── Completion screen ─────────────────────────────────────────
            running[0] = False
            canvas.destroy()
            pb_cv.destroy()
            time_lbl.destroy()
            stop_btn.destroy()
            done = tk.Frame(root, bg=BG)
            done.pack(expand=True, fill=tk.BOTH)
            tk.Label(done, text="🎉", font=("", 52), bg=BG).pack(pady=(16, 6))
            tk.Label(done, text="Well done!", font=("", 18, "bold"),
                     bg=BG, fg="white").pack()
            tk.Label(done, text="One minute of box breathing complete.",
                     font=("", 11), bg=BG, fg="#6a9ec0").pack(pady=(4, 20))
            ttk.Button(done, text="Close", command=root.quit).pack()
            return

        # ── Current phase ─────────────────────────────────────────────────
        t_cycle = t % CYCLE
        accum   = 0.0
        idx, t_phase = 0, 0.0
        for i, (_, dur, _) in enumerate(PHASES):
            if t_cycle < accum + dur:
                idx     = i
                t_phase = t_cycle - accum
                break
            accum += dur

        label, dur, kind = PHASES[idx]
        prog = t_phase / dur

        r = int(
            MIN_R + (MAX_R - MIN_R) * prog   if kind == 0 else
            MAX_R                             if kind == 1 else
            MAX_R - (MAX_R - MIN_R) * prog   if kind == 2 else
            MIN_R
        )

        _draw(r)
        canvas.itemconfig(pt_phase, text=label)
        canvas.itemconfig(pt_count, text=str(max(1, math.ceil(dur - t_phase))))

        pb_cv.coords(pb_bar, 0, 0, int(260 * t / TOTAL), 6)
        rem = int(TOTAL - t)
        time_lbl.config(text=f"0:{rem:02d} remaining")
        root.after(50, _tick)

    _draw(MIN_R)
    canvas.itemconfig(pt_phase, text=PHASES[0][0])
    canvas.itemconfig(pt_count, text=str(PHASES[0][1]))
    root.protocol("WM_DELETE_WINDOW", _stop)
    root.after(100, _tick)
    root.mainloop()
    root.destroy()


# ─── 5-4-3-2-1 grounding ─────────────────────────────────────────────────────

def show_grounding_exercise() -> None:
    """
    Guide through the 5-4-3-2-1 sensory grounding technique.

    Grounding brings attention back to the present moment via the five senses.
    The technique is widely used in CBT and trauma-informed care to interrupt
    anxiety or dissociation.  Each step shows an emoji cue and numbered entry
    fields to write down what you notice.
    """
    STEPS = [
        (5, "👁️",  "5 things you can SEE",
         "Look around and name 5 things you can see right now."),
        (4, "🖐️",  "4 things you can TOUCH",
         "Notice 4 things you can physically feel — textures, temperature, weight."),
        (3, "👂",  "3 things you can HEAR",
         "Listen carefully and identify 3 distinct sounds around you."),
        (2, "👃",  "2 things you can SMELL",
         "Take a slow breath and notice 2 things you can smell."),
        (1, "👅",  "1 thing you can TASTE",
         "Focus inward — what is one thing you can taste right now?"),
    ]

    root = tk.Tk()
    root.title("5-4-3-2-1 Grounding")
    root.geometry("430x530")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    step = [0]

    # ── Header ────────────────────────────────────────────────────────────
    header = ttk.Frame(root, padding=(24, 16, 24, 0))
    header.pack(fill=tk.X)

    step_lbl = ttk.Label(header, text="Step 1 of 5",
                          font=("", 11), foreground="gray")
    step_lbl.pack()

    # tk.Label for emoji so we can control bg colour precisely
    emoji_lbl = tk.Label(header, text=STEPS[0][1], font=("", 60))
    emoji_lbl.pack(pady=(2, 0))

    title_lbl = ttk.Label(header, text=STEPS[0][2], font=("", 14, "bold"))
    title_lbl.pack(pady=(4, 2))

    instr_lbl = ttk.Label(header, text=STEPS[0][3], font=("", 12),
                           foreground="gray", wraplength=370, justify="center")
    instr_lbl.pack(pady=(0, 10))

    sep = ttk.Separator(root, orient="horizontal")
    sep.pack(fill=tk.X, padx=24)

    # ── Entry fields (rebuilt for each step) ─────────────────────────────
    entries_pane = ttk.Frame(root, padding=(32, 10, 32, 4))
    entries_pane.pack(fill=tk.X)

    def _build_entries(n: int) -> None:
        for w in entries_pane.winfo_children():
            w.destroy()
        for i in range(n):
            row = ttk.Frame(entries_pane)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=f"{i + 1}.", width=3, font=("", 13)).pack(side=tk.LEFT)
            e = ttk.Entry(row, font=("", 13))
            e.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Focus the first entry automatically
        rows = entries_pane.winfo_children()
        if rows:
            for w in rows[0].winfo_children():
                if isinstance(w, ttk.Entry):
                    w.focus_set()
                    break

    _build_entries(STEPS[0][0])

    # ── Footer ────────────────────────────────────────────────────────────
    footer = ttk.Frame(root, padding=(24, 8, 24, 18))
    footer.pack(fill=tk.X, side=tk.BOTTOM)

    next_var = tk.StringVar(value="Next →")
    next_btn = ttk.Button(footer, textvariable=next_var, command=lambda: _advance())
    next_btn.pack(side=tk.RIGHT)

    def _advance() -> None:
        step[0] += 1
        if step[0] >= len(STEPS):
            # ── Completion screen ─────────────────────────────────────────
            header.pack_forget()
            entries_pane.pack_forget()
            sep.pack_forget()
            done = ttk.Frame(root, padding=36)
            done.pack(expand=True)
            ttk.Label(done, text="🎉", font=("", 64)).pack()
            ttk.Label(done, text="Well done!", font=("", 18, "bold")).pack(pady=(8, 4))
            ttk.Label(done,
                       text="You've completed the 5-4-3-2-1 grounding exercise.\n"
                            "Take a moment to notice how you feel.",
                       font=("", 12), foreground="gray",
                       justify="center", wraplength=340).pack(pady=(0, 4))
            next_var.set("Close")
            next_btn.config(command=root.destroy)
            return

        n, emoji, title, instr = STEPS[step[0]]
        step_lbl.config(text=f"Step {step[0] + 1} of {len(STEPS)}")
        emoji_lbl.config(text=emoji)
        title_lbl.config(text=title)
        instr_lbl.config(text=instr)
        _build_entries(n)

        if step[0] == len(STEPS) - 1:
            next_var.set("Finish ✓")

    root.bind("<Return>", lambda _: _advance())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()

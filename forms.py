"""All tkinter UI: configure dialog, session feedback form, history window,
breathing exercise, and 5-4-3-2-1 grounding."""

import datetime
import math
import tkinter as tk
from tkinter import ttk

import db


# ─── Design tokens ────────────────────────────────────────────────────────────

C_PRIMARY       = "#c0392b"   # tomato red — selected state, primary actions
C_CHIP_SEL_BG   = "#c0392b"
C_CHIP_SEL_FG   = "#ffffff"
C_CHIP_UNSEL_BG = "#eeeeee"
C_CHIP_UNSEL_FG = "#555555"
C_MUTED         = "#888888"
C_DIVIDER       = "#e0e0e0"
C_ROW_EVEN      = "#f8f8f8"
C_ROW_ODD       = "#ffffff"

FS_XS = 10   # captions / hints
FS_SM = 12   # body
FS_MD = 15   # section headers / window titles
FS_LG = 24   # large numbers (focus rating, duration picker)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _center_window(root: tk.Tk) -> None:
    """Position the window in the center of the screen."""
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")
    root.deiconify()


def _bring_to_front(root: tk.Tk) -> None:
    """Raise and focus the window once it is rendered.

    NSApp activation policy is handled by _open_window() in main.py before
    any tkinter function is called.  This helper only needs to lift the window
    and steal keyboard focus — done twice (immediately + after 100 ms) so it
    works regardless of how long the initial widget build takes.
    """
    _center_window(root)

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


def _section_header(parent: ttk.Frame, text: str) -> ttk.Frame:
    """Render a small-caps section label with a hairline separator to its right."""
    hdr = ttk.Frame(parent)
    hdr.pack(fill=tk.X, pady=(14, 3))
    ttk.Label(hdr, text=text.upper(), font=("", FS_XS, "bold"), foreground=C_MUTED).pack(side=tk.LEFT)
    ttk.Separator(hdr, orient="horizontal").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
    return hdr


def _focus_descriptor(val: int) -> str:
    if val <= 2: return "Terrible"
    if val <= 4: return "Poor"
    if val == 5: return "Fair"
    if val <= 7: return "Good"
    if val == 8: return "Great"
    return "Excellent"


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
    ttk.Label(frame, text="Session length", font=("", FS_SM)).pack()

    clamped  = max(_min, min(_max, current_minutes))
    dur_var  = tk.DoubleVar(value=float(clamped))
    val_label = ttk.Label(frame, text=f"{clamped} min", font=("", FS_LG, "bold"))
    val_label.pack(pady=(4, 10))

    def _on_slider(val: str) -> None:
        val_label.config(text=f"{round(float(val))} min")

    slider_row = ttk.Frame(frame)
    slider_row.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(slider_row, text=str(_min), foreground=C_MUTED).pack(side=tk.LEFT)
    ttk.Scale(
        slider_row, from_=_min, to=_max, orient=tk.HORIZONTAL,
        variable=dur_var, command=_on_slider, length=240,
    ).pack(side=tk.LEFT, padx=8, expand=True, fill=tk.X)
    ttk.Label(slider_row, text=str(_max), foreground=C_MUTED).pack(side=tk.LEFT)
    return dur_var


# ─── Start-session window (slider + Play button) ──────────────────────────────

def show_start_window(current_minutes: int) -> int | None:
    """
    Duration picker shown when the user clicks Start Session.
    Returns the chosen duration (int) or None if cancelled.
    """
    result: list[int | None] = [None]

    root = tk.Tk()
    root.withdraw()
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
    root.withdraw()
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


# ─── Screen-lock return dialog ────────────────────────────────────────────────

def show_screen_lock_dialog(elapsed_seconds: int) -> dict | None:
    """
    Shown after the screen unlocks during an active session.
    Returns {"break": True} if the user was resting, {"break": False} if studying.
    Defaults to "break" when the window is closed without answering.
    """
    mins, secs = divmod(elapsed_seconds, 60)
    if mins and secs:
        duration_str = f"{mins} min {secs} sec"
    elif mins:
        duration_str = f"{mins} min"
    else:
        duration_str = f"{secs} sec"

    result: list[dict | None] = [{"break": True}]  # safe default

    root = tk.Tk()
    root.withdraw()
    root.title("Welcome back!")
    root.geometry("400x180")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Welcome back!", font=("", FS_MD, "bold")).pack(pady=(0, 8))
    ttk.Label(
        frame,
        text=f"Screen was locked for {duration_str}.\nWere you on a break?",
        font=("", FS_SM),
        justify=tk.CENTER,
    ).pack(pady=(0, 18))

    def _was_break() -> None:
        result[0] = {"break": True}
        root.quit()

    def _kept_studying() -> None:
        result[0] = {"break": False}
        root.quit()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack()
    ttk.Button(btn_frame, text="Yes, I was on a break", command=_was_break).pack(
        side=tk.LEFT, padx=6
    )
    ttk.Button(btn_frame, text="No, I kept studying", command=_kept_studying).pack(
        side=tk.LEFT, padx=6
    )

    root.protocol("WM_DELETE_WINDOW", _was_break)
    root.bind("<Return>", lambda _: _was_break())
    root.bind("<Escape>", lambda _: _was_break())

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
    root.withdraw()
    root.title("Session Complete!")
    root.resizable(False, False)
    _theme(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    # ── Header ────────────────────────────────────────────────────────────────
    ttk.Label(frame, text="🍅  Session Complete!", font=("", FS_MD, "bold")).pack(pady=(0, 4))
    ttk.Label(
        frame,
        text=f"Duration: {duration_minutes} min",
        foreground=C_MUTED,
        font=("", FS_SM),
    ).pack(pady=(0, 4))

    # ── Term ──────────────────────────────────────────────────────────────────
    term_sec_hdr = _section_header(frame, "Term")

    term_error_lbl = ttk.Label(
        frame, text="⚠  Please enter a term before saving.", foreground="red", font=("", FS_SM)
    )

    existing_terms = db.get_all_terms()
    last_term      = db.get_last_term()
    term_var       = tk.StringVar(value=last_term or "")
    term_chip_btns: dict[str, tk.Button] = {}

    term_frame = ttk.Frame(frame)
    term_frame.pack(fill=tk.X, pady=(0, 4))

    def _on_term_changed(*_: object) -> None:
        cur = term_var.get()
        for t, b in term_chip_btns.items():
            b.config(
                bg=C_CHIP_SEL_BG   if cur == t else C_CHIP_UNSEL_BG,
                fg=C_CHIP_SEL_FG   if cur == t else C_CHIP_UNSEL_FG,
            )
        if cur.strip():
            term_error_lbl.pack_forget()

    if existing_terms:
        tc_outer = ttk.Frame(term_frame)
        tc_outer.pack(fill=tk.X, pady=(0, 8))
        TERM_AVAIL_W = 360
        rows_of_terms: list[list[str]] = [[]]
        row_w = 0
        for _t in existing_terms:
            _bw = len(_t) * 7 + 36
            if row_w > 0 and row_w + _bw > TERM_AVAIL_W:
                rows_of_terms.append([])
                row_w = 0
            rows_of_terms[-1].append(_t)
            row_w += _bw
        for _ri, _row_terms in enumerate(rows_of_terms):
            _rf = ttk.Frame(tc_outer)
            _rf.pack(fill=tk.X, anchor=tk.W, pady=(0 if _ri == 0 else 2, 0))
            for _term_name in _row_terms:
                _btn = tk.Button(
                    _rf, text=_term_name, relief="flat",
                    bg=C_CHIP_UNSEL_BG, fg=C_CHIP_UNSEL_FG,
                    font=("", FS_SM), padx=14, pady=6, cursor="hand2", bd=0,
                    command=lambda t=_term_name: term_var.set(t),
                )
                _btn.pack(side=tk.LEFT, padx=(0, 6), pady=(0, 2))
                term_chip_btns[_term_name] = _btn
        ttk.Label(term_frame, text="Or add a new term:", foreground=C_MUTED, font=("", FS_XS)).pack(anchor=tk.W)
    else:
        ttk.Label(
            term_frame,
            text="e.g.  Spring 2025 · Autumn 2025 · Summer",
            foreground=C_MUTED, font=("", FS_XS),
        ).pack(anchor=tk.W, pady=(0, 4))
    ttk.Entry(term_frame, textvariable=term_var, font=("", FS_SM)).pack(fill=tk.X)
    term_var.trace_add("write", _on_term_changed)
    if last_term and last_term in term_chip_btns:
        term_chip_btns[last_term].config(bg=C_CHIP_SEL_BG, fg=C_CHIP_SEL_FG)

    # ── Focus rating ──────────────────────────────────────────────────────────
    focus_sec_hdr = _section_header(frame, "Focus Rating")
    focus_frame = ttk.Frame(frame)
    focus_frame.pack(fill=tk.X, pady=(0, 4))

    _summary = db.get_summary()
    _avg = _summary.get("avg_focus")
    default_focus = float(max(1, min(10, round(_avg))) if _avg else 7)

    focus_var = tk.DoubleVar(value=default_focus)

    rating_lbl = ttk.Label(
        focus_frame, text=str(int(default_focus)), font=("", FS_LG, "bold"), width=3, anchor="center"
    )
    rating_lbl.pack()

    desc_lbl = ttk.Label(
        focus_frame, text=_focus_descriptor(int(default_focus)), font=("", FS_XS), foreground=C_MUTED
    )
    desc_lbl.pack(pady=(0, 4))

    def _on_scale(val: str) -> None:
        v = int(float(val))
        rating_lbl.config(text=str(v))
        desc_lbl.config(text=_focus_descriptor(v))

    ttk.Scale(
        focus_frame, from_=1, to=10, orient=tk.HORIZONTAL,
        variable=focus_var, command=_on_scale, length=340,
    ).pack(pady=(4, 2))

    tips = ttk.Frame(focus_frame)
    tips.pack(fill=tk.X)
    ttk.Label(tips, text="1 – terrible", foreground=C_MUTED, font=("", FS_XS)).pack(side=tk.LEFT)
    ttk.Label(tips, text="10 – perfect", foreground=C_MUTED, font=("", FS_XS)).pack(side=tk.RIGHT)

    # ── Topic ─────────────────────────────────────────────────────────────────
    topic_sec_hdr = _section_header(frame, "Topic / Project")
    topic_frame = ttk.Frame(frame)
    topic_frame.pack(fill=tk.X, pady=(0, 4))

    error_lbl = ttk.Label(frame, text="⚠  Please enter a topic before saving.", foreground="red", font=("", FS_SM))

    topic_var = tk.StringVar()
    existing_topics = db.get_all_topics()
    chip_btns: dict[str, tk.Button] = {}

    def _on_topic_var_changed(*_: object) -> None:
        current = topic_var.get()
        for t, b in chip_btns.items():
            b.config(
                bg=C_CHIP_SEL_BG   if current == t else C_CHIP_UNSEL_BG,
                fg=C_CHIP_SEL_FG   if current == t else C_CHIP_UNSEL_FG,
            )
        if current.strip():
            error_lbl.pack_forget()

    if existing_topics:
        chips_outer = ttk.Frame(topic_frame)
        chips_outer.pack(fill=tk.X, pady=(0, 8))

        AVAIL_W = 360
        rows_of_topics: list[list[str]] = [[]]
        row_w = 0
        for _t in existing_topics:
            _bw = len(_t) * 7 + 36
            if row_w > 0 and row_w + _bw > AVAIL_W:
                rows_of_topics.append([])
                row_w = 0
            rows_of_topics[-1].append(_t)
            row_w += _bw

        for _ri, _row_topics in enumerate(rows_of_topics):
            _row_frame = ttk.Frame(chips_outer)
            _row_frame.pack(fill=tk.X, anchor=tk.W, pady=(0 if _ri == 0 else 2, 0))
            for _topic in _row_topics:
                _btn = tk.Button(
                    _row_frame, text=_topic, relief="flat",
                    bg=C_CHIP_UNSEL_BG, fg=C_CHIP_UNSEL_FG,
                    font=("", FS_SM), padx=14, pady=6, cursor="hand2", bd=0,
                    command=lambda t=_topic: topic_var.set(t),
                )
                _btn.pack(side=tk.LEFT, padx=(0, 6), pady=(0, 2))
                chip_btns[_topic] = _btn

        ttk.Label(topic_frame, text="Or add a new one:", foreground=C_MUTED, font=("", FS_XS)).pack(anchor=tk.W)
    else:
        ttk.Label(
            topic_frame,
            text="e.g.  Math homework · Work report · Reading",
            foreground=C_MUTED, font=("", FS_XS),
        ).pack(anchor=tk.W, pady=(0, 4))
    ttk.Entry(topic_frame, textvariable=topic_var, font=("", FS_SM)).pack(fill=tk.X)
    topic_var.trace_add("write", _on_topic_var_changed)

    # ── Distraction ───────────────────────────────────────────────────────────
    _section_header(frame, "Distractions")
    distract_frame = ttk.Frame(frame)
    distract_frame.pack(fill=tk.X, pady=(0, 4))

    distracted_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        distract_frame,
        text="I got distracted during this session",
        variable=distracted_var,
    ).pack(anchor=tk.W)

    reason_container = ttk.Frame(distract_frame)
    ttk.Label(reason_container, text="What distracted you?", font=("", FS_SM)).pack(anchor=tk.W)
    reason_text = tk.Text(
        reason_container, height=3, font=("", FS_SM), wrap=tk.WORD,
        relief="solid", borderwidth=1,
    )
    reason_text.pack(fill=tk.X, pady=(2, 0))

    def _resize_to_fit() -> None:
        root.update_idletasks()
        root.geometry(f"460x{root.winfo_reqheight()}")
        _center_window(root)

    def _toggle_reason(*_: object) -> None:
        if distracted_var.get():
            reason_container.pack(fill=tk.X, pady=(10, 0))
        else:
            reason_container.pack_forget()
        _resize_to_fit()

    distracted_var.trace_add("write", _toggle_reason)

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(16, 0))

    def _submit() -> None:
        term = term_var.get().strip()
        if not term:
            term_error_lbl.pack(before=focus_sec_hdr, pady=(0, 6))
            root.update_idletasks()
            root.geometry(f"460x{root.winfo_reqheight()}")
            _center_window(root)
            return
        topic = topic_var.get().strip()
        if not topic:
            error_lbl.pack(before=btn_frame, pady=(0, 6))
            root.update_idletasks()
            root.geometry(f"460x{root.winfo_reqheight()}")
            _center_window(root)
            return
        result[0] = {
            "focus": max(1, min(10, int(float(focus_var.get())))),
            "topic": topic,
            "term":  term,
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

    _resize_to_fit()
    _bring_to_front(root)

    root.mainloop()
    root.destroy()
    return result[0]


# ─── History window ───────────────────────────────────────────────────────────

def show_history_window() -> None:
    """Read-only history & stats viewer."""
    root = tk.Tk()
    root.withdraw()
    root.title("🍅 Pomodoro History")
    root.geometry("900x620")
    root.minsize(700, 450)
    _theme(root)

    # ── Term filter header ────────────────────────────────────────────────────
    all_terms    = db.get_all_terms()
    has_untagged = db.has_untagged_sessions()
    term_options = ["All Terms"] + all_terms + (["Untagged"] if has_untagged else [])

    last_term    = db.get_last_term()
    default_term = last_term if last_term in term_options else "All Terms"

    hdr = ttk.Frame(root, padding=(10, 8, 10, 4))
    hdr.pack(fill=tk.X)
    ttk.Label(hdr, text="Term:", font=("", FS_SM, "bold")).pack(side=tk.LEFT, padx=(0, 8))
    term_var = tk.StringVar(value=default_term)
    ttk.Combobox(
        hdr, textvariable=term_var, values=term_options,
        state="readonly", width=24, font=("", FS_SM),
    ).pack(side=tk.LEFT)

    nb_holder: list[ttk.Notebook | None] = [None]

    def _get_tf() -> str | None:
        sel = term_var.get()
        return None if sel == "All Terms" else (db.UNTAGGED if sel == "Untagged" else sel)

    def _rebuild(*_: object) -> None:
        if nb_holder[0] is not None:
            nb_holder[0].destroy()
        tf = _get_tf()
        nb = ttk.Notebook(root)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))
        nb_holder[0] = nb

        style = ttk.Style(root)
        style.configure("Treeview", foreground="#000000", background="#ffffff",
                        fieldbackground="#ffffff", rowheight=24)
        style.configure("Treeview.Heading", foreground="#000000")
        style.map("Treeview", foreground=[("selected", "#ffffff")])

        # ── Tab 1: Session log ────────────────────────────────────────────────
        log_tab = ttk.Frame(nb)
        nb.add(log_tab, text="  Session Log  ")

        log_cols = ("date", "time", "dur", "focus", "topic", "dist", "reason")
        log_col_labels = {
            "date": "Date", "time": "Time", "dur": "Min",
            "focus": "Focus", "topic": "Topic", "dist": "Distracted", "reason": "Notes",
        }
        log_col_widths = {
            "date": 100, "time": 70, "dur": 50,
            "focus": 55, "topic": 160, "dist": 75, "reason": 220,
        }

        tree_frame = ttk.Frame(log_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tree = ttk.Treeview(tree_frame, columns=log_cols, show="headings", selectmode="browse")
        for col in log_cols:
            tree.heading(col, text=log_col_labels[col])
            tree.column(col, width=log_col_widths[col],
                        anchor="center" if col in ("dur", "focus", "dist") else "w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(fill=tk.BOTH, expand=True)
        tree.bind("<MouseWheel>",
                  lambda e: tree.yview_scroll(int(-1 * (e.delta / 30)), "units"))

        tree.tag_configure("even", background=C_ROW_EVEN, foreground="#000000")
        tree.tag_configure("odd",  background=C_ROW_ODD,  foreground="#000000")

        sessions = db.get_all_sessions(tf)
        for i, row in enumerate(sessions):
            ts = row["start_time"] or row["timestamp"]
            try:
                date_part, time_part = ts[:10], ts[11:16]
            except (IndexError, TypeError):
                date_part, time_part = ts, ""
            tree.insert(
                "", tk.END, tags=("even" if i % 2 == 0 else "odd",),
                values=(
                    date_part, time_part, row["duration"],
                    row["focus"] if row["focus"] is not None else "–",
                    row["topic"] or "",
                    "Yes" if row["distracted"] else "No",
                    row["reason"] or "",
                ),
            )

        summary = db.get_summary(tf)
        status_text = (
            f"  {summary.get('total_sessions', 0)} sessions  •  "
            f"{summary.get('total_minutes', 0) or 0} total minutes  •  "
            f"Avg focus: {summary.get('avg_focus') or '–'}"
        )
        log_bottom = ttk.Frame(log_tab)
        log_bottom.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Label(log_bottom, text=status_text, foreground="gray", anchor="w").pack(side=tk.LEFT)
        ttk.Button(log_bottom, text="Close", command=root.destroy).pack(side=tk.RIGHT)

        # ── Tab 2: Statistics ─────────────────────────────────────────────────
        stats_tab = ttk.Frame(nb, padding=16)
        nb.add(stats_tab, text="  Statistics  ")

        total_s   = summary.get("total_sessions") or 0
        total_min = summary.get("total_minutes")  or 0
        avg_focus = summary.get("avg_focus")       or "–"
        total_h   = f"{total_min // 60}h {total_min % 60}m" if total_min else "0m"

        banner = ttk.LabelFrame(stats_tab, text="  Overall  ", padding=12)
        banner.pack(fill=tk.X, pady=(0, 16))
        for text in (
            f"Sessions completed: {total_s}",
            f"Total focus time:   {total_h}",
            f"Average focus:      {avg_focus} / 10",
        ):
            ttk.Label(banner, text=text, font=("", FS_SM)).pack(anchor=tk.W, pady=1)

        cols_frame = ttk.Frame(stats_tab)
        cols_frame.pack(fill=tk.BOTH, expand=True)
        cols_frame.columnconfigure(0, weight=1)
        cols_frame.columnconfigure(1, weight=1)

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
        for row in db.get_stats_by_time_of_day(tf):
            tod_tree.insert("", tk.END, values=(row["period"], row["avg_focus"], row["sessions"]))

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
        for row in db.get_stats_by_topic(tf):
            top_tree.insert(
                "", tk.END,
                values=(row["topic"], row["avg_focus"], row["sessions"], row["total_min"])
            )

        btn_bar = ttk.Frame(stats_tab)
        btn_bar.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(btn_bar, text="↺  Refresh", command=_rebuild).pack(side=tk.LEFT)
        ttk.Button(btn_bar, text="Close", command=root.destroy).pack(side=tk.RIGHT)

        # ── Tab 3: Daily Histogram ────────────────────────────────────────────
        hist_tab = ttk.Frame(nb)
        nb.add(hist_tab, text="  Daily Chart  ")

        hist_data = db.get_daily_by_topic(tf)
        if not hist_data:
            ttk.Label(hist_tab, text="No sessions recorded yet.",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
        else:
            day_topic: dict[str, dict[str, tuple[int, float | None, int]]] = {}
            all_topics_set: set[str] = set()
            for _row in hist_data:
                _d, _t = _row["day"], _row["topic"]
                if _d not in day_topic:
                    day_topic[_d] = {}
                day_topic[_d][_t] = (_row["total_min"], _row["avg_focus"], _row["sessions"])
                all_topics_set.add(_t)

            hist_days   = sorted(day_topic.keys())
            hist_topics = sorted(all_topics_set)

            def _day_avg_focus(day: str) -> float | None:
                total_m, weighted = 0.0, 0.0
                for _total_m, _af, _s in day_topic[day].values():
                    if _af is not None:
                        weighted += _af * _total_m
                        total_m  += _total_m
                return round(weighted / total_m, 1) if total_m else None

            _PALETTE = [
                "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
                "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
            ]
            topic_color = {t: _PALETTE[i % len(_PALETTE)] for i, t in enumerate(hist_topics)}

            ML, MR, MT, MB = 58, 24, 48, 56
            BW, BG = 52, 18
            CH     = 260
            SEG_LABEL_MIN_H = 22

            _max_min = max(sum(v[0] for v in day_topic[d].values()) for d in hist_days)
            _max_h   = _max_min / 60.0
            _y_max   = max(0.5, math.ceil(_max_h * 2) / 2)
            _canvas_w = ML + MR + len(hist_days) * (BW + BG)
            _canvas_h = MT + CH + MB

            def _min_to_y(minutes: float) -> int:
                return MT + CH - int(CH * minutes / (_y_max * 60))

            hist_btn_bar = ttk.Frame(hist_tab)
            hist_btn_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 6))
            ttk.Button(hist_btn_bar, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            leg_frame = ttk.Frame(hist_tab)
            leg_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=ML + 8, pady=(0, 4))
            for _t in hist_topics:
                _swatch = tk.Canvas(leg_frame, width=14, height=14,
                                    highlightthickness=0, bg=topic_color[_t])
                _swatch.pack(side=tk.LEFT, padx=(0, 4))
                ttk.Label(leg_frame, text=_t, font=("", 11)).pack(side=tk.LEFT, padx=(0, 16))

            _scroll_frame = ttk.Frame(hist_tab)
            _scroll_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
            _hsb = ttk.Scrollbar(_scroll_frame, orient="horizontal")
            _hsb.pack(side=tk.BOTTOM, fill=tk.X)
            cv = tk.Canvas(_scroll_frame, bg="white", highlightthickness=0,
                           xscrollcommand=_hsb.set)
            cv.pack(fill=tk.BOTH, expand=True)
            _hsb.config(command=cv.xview)
            cv.configure(scrollregion=(0, 0, _canvas_w, _canvas_h))
            cv.after(150, lambda: cv.xview_moveto(1.0))
            cv.bind("<MouseWheel>",
                    lambda e: cv.xview_scroll(int(-1 * (e.delta / 30)), "units"))

            _n_ticks = int(_y_max / 0.5) + 1
            for _i in range(_n_ticks):
                _vh = _i * 0.5
                _gy = _min_to_y(_vh * 60)
                cv.create_line(ML, _gy, _canvas_w - MR, _gy, fill="#e4e4e4", dash=(3, 4))
                _lbl = f"{int(_vh)}h" if _vh == int(_vh) else f"{_vh:.1f}h"
                cv.create_text(ML - 6, _gy, text=_lbl, anchor="e", font=("", 11), fill="#555")

            cv.create_line(ML, MT, ML, MT + CH, fill="#bbb")
            cv.create_line(ML, MT + CH, _canvas_w - MR, MT + CH, fill="#bbb")
            cv.create_text(ML + (_canvas_w - ML - MR) / 2, 8,
                           text="Daily Study Time by Module",
                           anchor="n", font=("", 13, "bold"), fill="#333")

            for _di, _day in enumerate(hist_days):
                _x0 = ML + _di * (BW + BG)
                _x1 = _x0 + BW
                _cx = (_x0 + _x1) / 2
                _day_data = day_topic[_day]
                _total_m  = sum(v[0] for v in _day_data.values())
                _yc       = MT + CH

                for _tp in hist_topics:
                    if _tp not in _day_data:
                        continue
                    _seg_m, _seg_af, _ = _day_data[_tp]
                    _bh = max(1, int(CH * _seg_m / (_y_max * 60)))
                    _yt = _yc - _bh
                    cv.create_rectangle(_x0, _yt, _x1, _yc,
                                        fill=topic_color[_tp], outline="white", width=1)
                    if _seg_af is not None and _bh >= SEG_LABEL_MIN_H:
                        cv.create_text((_x0 + _x1) / 2, (_yt + _yc) / 2,
                                       text=f"{_seg_af:.1f}",
                                       font=("", 10, "bold"), fill="white", anchor="center")
                    _yc = _yt

                _daf = _day_avg_focus(_day)
                if _daf is not None:
                    cv.create_text(_cx, _yc - 4, text=f"★ {_daf:.1f}",
                                   anchor="s", font=("", 10), fill="#555")
                    _yc -= 16

                _th = _total_m / 60
                cv.create_text(_cx, _yc - 2,
                               text=f"{_th:.1f}h" if _th >= 0.1 else f"{_total_m}m",
                               anchor="s", font=("", 11, "bold"), fill="#222")
                cv.create_text(_x0 + BW // 2, MT + CH + 5, text=_day[5:],
                               anchor="nw", font=("", 10), fill="#555", angle=45)

    term_var.trace_add("write", _rebuild)
    _rebuild()
    _bring_to_front(root)
    root.mainloop()


# ─── Insights (Beta) window ──────────────────────────────────────────────────

def show_insights_window() -> None:
    """Distraction Insights window with seven analytical views."""
    root = tk.Tk()
    root.withdraw()
    root.title("🔍 Insights (Beta)")
    root.geometry("960x700")
    root.minsize(780, 520)
    _theme(root)

    # ── Term filter header ────────────────────────────────────────────────────
    all_terms    = db.get_all_terms()
    has_untagged = db.has_untagged_sessions()
    term_options = ["All Terms"] + all_terms + (["Untagged"] if has_untagged else [])

    last_term    = db.get_last_term()
    default_term = last_term if last_term in term_options else "All Terms"

    hdr = ttk.Frame(root, padding=(10, 8, 10, 4))
    hdr.pack(fill=tk.X)
    ttk.Label(hdr, text="Term:", font=("", FS_SM, "bold")).pack(side=tk.LEFT, padx=(0, 8))
    term_var = tk.StringVar(value=default_term)
    ttk.Combobox(
        hdr, textvariable=term_var, values=term_options,
        state="readonly", width=24, font=("", FS_SM),
    ).pack(side=tk.LEFT)

    nb_holder: list[ttk.Notebook | None] = [None]

    def _get_tf() -> str | None:
        sel = term_var.get()
        return None if sel == "All Terms" else (db.UNTAGGED if sel == "Untagged" else sel)

    def _rebuild(*_: object) -> None:  # noqa: C901
        if nb_holder[0] is not None:
            nb_holder[0].destroy()
        tf = _get_tf()
        nb = ttk.Notebook(root)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))
        nb_holder[0] = nb

        # ── Tab 1: Distraction Words ──────────────────────────────────────────
        words_tab = ttk.Frame(nb, padding=12)
        nb.add(words_tab, text="  Top Words  ")

        dist_sum  = db.get_distraction_summary(tf)
        total_s   = dist_sum["total_sessions"]
        dist_s    = dist_sum["distracted_sessions"]
        dist_pct  = dist_sum["distraction_rate"]

        banner = ttk.LabelFrame(words_tab, text="  Overview  ", padding=10)
        banner.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            banner,
            text=f"Sessions with distractions:  {dist_s} of {total_s}  ({dist_pct}%)",
            font=("", FS_SM),
        ).pack(anchor=tk.W)

        word_data = db.get_distraction_word_freq(term=tf)

        if not word_data:
            ttk.Label(words_tab, text="No distraction notes recorded yet.",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
            w_btn = ttk.Frame(words_tab)
            w_btn.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(w_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)
        else:
            import tkinter.font as _tkfont
            import math as _math
            import random as _random_mod

            max_count = word_data[0][1]
            min_count = word_data[-1][1]

            WC_W, WC_H = 900, 190
            WC_MIN_SZ  = 11
            WC_MAX_SZ  = 36
            WC_COLORS  = [
                "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
                "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
            ]

            wc_lf = ttk.LabelFrame(words_tab, text="  Word Cloud  ", padding=6)
            wc_lf.pack(fill=tk.X, pady=(0, 8))
            cv_wc = tk.Canvas(wc_lf, bg="white", height=WC_H, width=WC_W, highlightthickness=0)
            cv_wc.pack()

            _placed: list[tuple[float, float, float, float]] = []
            _wc_cx, _wc_cy = WC_W / 2.0, WC_H / 2.0
            _rng = _random_mod.Random(42)

            for _idx, (_word, _count) in enumerate(word_data):
                _t    = (_count - min_count) / (max_count - min_count) if max_count > min_count else 1.0
                _fsz  = round(WC_MIN_SZ + _t * (WC_MAX_SZ - WC_MIN_SZ))
                _wgt  = "bold" if _t >= 0.5 else "normal"
                _fobj = _tkfont.Font(family="Helvetica", size=_fsz, weight=_wgt)
                _tw   = _fobj.measure(_word) + 6
                _th   = _fobj.metrics("linespace") + 4
                _color = WC_COLORS[_idx % len(WC_COLORS)]
                _angle = _rng.uniform(0, 2 * _math.pi)
                _step  = 0
                while _step < 700:
                    _r  = _step * 0.55
                    _tx = _wc_cx + _r * _math.cos(_angle)
                    _ty = _wc_cy + _r * _math.sin(_angle)
                    _tx = max(_tw / 2 + 2, min(WC_W - _tw / 2 - 2, _tx))
                    _ty = max(_th / 2 + 2, min(WC_H - _th / 2 - 2, _ty))
                    _bx0, _by0 = _tx - _tw / 2, _ty - _th / 2
                    _bx1, _by1 = _tx + _tw / 2, _ty + _th / 2
                    if not any(
                        _bx1 > _px0 and _bx0 < _px1 and _by1 > _py0 and _by0 < _py1
                        for _px0, _py0, _px1, _py1 in _placed
                    ):
                        _placed.append((_bx0, _by0, _bx1, _by1))
                        cv_wc.create_text(_tx, _ty, text=_word, font=_fobj, fill=_color)
                        break
                    _angle += 0.28
                    _step  += 1

            BAR_LEN = 28
            w_btn = ttk.Frame(words_tab)
            w_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))
            ttk.Button(w_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            w_cols = ("rank", "word", "count", "bar")
            wf = ttk.Frame(words_tab)
            wf.pack(fill=tk.BOTH, expand=True)
            w_tree = ttk.Treeview(wf, columns=w_cols, show="headings", selectmode="browse")
            w_tree.heading("rank",  text="#")
            w_tree.heading("word",  text="Word")
            w_tree.heading("count", text="Count")
            w_tree.heading("bar",   text="Frequency")
            w_tree.column("rank",  width=44,  anchor="center")
            w_tree.column("word",  width=160, anchor="w")
            w_tree.column("count", width=70,  anchor="center")
            w_tree.column("bar",   width=380, anchor="w")
            w_vsb = ttk.Scrollbar(wf, orient="vertical", command=w_tree.yview)
            w_tree.configure(yscrollcommand=w_vsb.set)
            w_vsb.pack(side=tk.RIGHT, fill=tk.Y)
            w_tree.pack(fill=tk.BOTH, expand=True)
            w_tree.bind("<MouseWheel>",
                        lambda e: w_tree.yview_scroll(int(-1 * (e.delta / 30)), "units"))

            w_style = ttk.Style(root)
            w_style.configure("Treeview", foreground="#000000", background="#ffffff",
                              fieldbackground="#ffffff", rowheight=24)
            w_style.configure("Treeview.Heading", foreground="#000000")
            w_style.map("Treeview", foreground=[("selected", "#ffffff")])

            for i, (word, count) in enumerate(word_data):
                filled = round(count / max_count * BAR_LEN)
                bar    = "█" * filled + "░" * (BAR_LEN - filled)
                w_tree.insert("", tk.END, tags=("even" if i % 2 == 0 else "odd",),
                              values=(i + 1, word, count, bar))
            w_tree.tag_configure("even", background=C_ROW_EVEN, foreground="#000000")
            w_tree.tag_configure("odd",  background=C_ROW_ODD,  foreground="#000000")

        # ── Tab 2: When Distracted ────────────────────────────────────────────
        when_tab = ttk.Frame(nb, padding=8)
        nb.add(when_tab, text="  When Distracted  ")

        hour_rows = db.get_distraction_by_hour(tf)
        hour_dict: dict[int, tuple[int, int]] = {
            row["hour"]: (row["total_sessions"], row["distracted_sessions"] or 0)
            for row in hour_rows
        }
        hour_rates: list[tuple[int, float, int, int]] = []
        for h in range(24):
            total, dist = hour_dict.get(h, (0, 0))
            rate = round(dist / total * 100, 1) if total else 0.0
            hour_rates.append((h, rate, total, dist))

        WD_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        wd_rows = db.get_distraction_by_weekday(tf)
        wd_dict: dict[int, tuple[int, int]] = {
            row["weekday"]: (row["total_sessions"], row["distracted_sessions"] or 0)
            for row in wd_rows
        }
        wd_rates: list[tuple[str, float, int, int]] = []
        for i in range(7):
            total, dist = wd_dict.get(i, (0, 0))
            rate = round(dist / total * 100, 1) if total else 0.0
            wd_rates.append((WD_LABELS[i], rate, total, dist))

        no_when_data = (
            not any(x[2] > 0 for x in hour_rates)
            and not any(x[2] > 0 for x in wd_rates)
        )
        if no_when_data:
            ttk.Label(when_tab, text="No session data yet.",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
        else:
            charts_frame = ttk.Frame(when_tab)
            charts_frame.pack(fill=tk.BOTH, expand=True)
            charts_frame.columnconfigure(0, weight=3)
            charts_frame.columnconfigure(1, weight=2)

            DIST_CLR  = "#e15759"
            EMPTY_CLR = "#e8e8e8"

            hour_lf = ttk.LabelFrame(
                charts_frame, text="  Distraction Rate by Hour of Day  ", padding=8
            )
            hour_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

            BW, BG_H   = 18, 4
            H_ML, H_MR = 48, 12
            H_MT, H_MB = 36, 44
            H_CH       = 200
            active_hours = [x for x in hour_rates if x[2] > 0]
            h_max_rate   = max((x[1] for x in active_hours), default=0)
            h_y_max      = max(10.0, math.ceil(h_max_rate / 10) * 10)
            h_canvas_w   = H_ML + H_MR + 24 * (BW + BG_H)
            h_canvas_h   = H_MT + H_CH + H_MB
            h_rate_to_y  = lambda r: H_MT + H_CH - int(H_CH * r / h_y_max)  # noqa: E731

            cv_h_frame = ttk.Frame(hour_lf)
            cv_h_frame.pack(fill=tk.BOTH, expand=True)
            h_hsb = ttk.Scrollbar(cv_h_frame, orient="horizontal")
            h_hsb.pack(side=tk.BOTTOM, fill=tk.X)
            cv_hour = tk.Canvas(cv_h_frame, bg="white", highlightthickness=0,
                                xscrollcommand=h_hsb.set)
            cv_hour.pack(fill=tk.BOTH, expand=True)
            h_hsb.config(command=cv_hour.xview)
            cv_hour.configure(scrollregion=(0, 0, h_canvas_w, h_canvas_h))
            cv_hour.bind("<MouseWheel>",
                         lambda e: cv_hour.xview_scroll(int(-1 * (e.delta / 30)), "units"))

            for i in range(int(h_y_max / 10) + 1):
                pct = i * 10
                gy  = h_rate_to_y(pct)
                cv_hour.create_line(H_ML, gy, h_canvas_w - H_MR, gy, fill="#e8e8e8", dash=(3, 4))
                cv_hour.create_text(H_ML - 4, gy, text=f"{pct}%", anchor="e", font=("", 9), fill="#888")
            cv_hour.create_line(H_ML, H_MT, H_ML, H_MT + H_CH, fill="#ccc")
            cv_hour.create_line(H_ML, H_MT + H_CH, h_canvas_w - H_MR, H_MT + H_CH, fill="#ccc")

            for h, rate, total, dist in hour_rates:
                x0 = H_ML + h * (BW + BG_H)
                x1 = x0 + BW
                cx = (x0 + x1) / 2
                bar_top = h_rate_to_y(rate) if rate > 0 else H_MT + H_CH
                color   = DIST_CLR if (total > 0 and rate > 0) else (EMPTY_CLR if total > 0 else "#f4f4f4")
                cv_hour.create_rectangle(x0, bar_top, x1, H_MT + H_CH, fill=color, outline="")
                if rate > 0:
                    cv_hour.create_text(cx, bar_top - 3, text=f"{rate:.0f}%",
                                        anchor="s", font=("", 8), fill="#555")
                cv_hour.create_text(cx, H_MT + H_CH + 4, text=f"{h:02d}",
                                    anchor="n", font=("", 9), fill="#555")
            if active_hours:
                first_h  = active_hours[0][0]
                scroll_x = max(0.0, (first_h * (BW + BG_H) - 20) / h_canvas_w)
                cv_hour.after(150, lambda: cv_hour.xview_moveto(scroll_x))

            wd_lf = ttk.LabelFrame(
                charts_frame, text="  Distraction Rate by Day of Week  ", padding=8
            )
            wd_lf.grid(row=0, column=1, sticky="nsew")

            WD_BW, WD_BG = 38, 10
            WD_ML, WD_MR = 48, 12
            WD_MT, WD_MB = 36, 36
            WD_CH        = 200
            wd_max_rate  = max((x[1] for x in wd_rates if x[2] > 0), default=0)
            wd_y_max     = max(10.0, math.ceil(wd_max_rate / 10) * 10)
            wd_canvas_w  = WD_ML + WD_MR + 7 * (WD_BW + WD_BG)
            wd_canvas_h  = WD_MT + WD_CH + WD_MB
            wd_rate_to_y = lambda r: WD_MT + WD_CH - int(WD_CH * r / wd_y_max)  # noqa: E731

            cv_wd = tk.Canvas(wd_lf, bg="white", highlightthickness=0,
                              width=wd_canvas_w, height=wd_canvas_h)
            cv_wd.pack(fill=tk.BOTH, expand=True)

            for i in range(int(wd_y_max / 10) + 1):
                pct = i * 10
                gy  = wd_rate_to_y(pct)
                cv_wd.create_line(WD_ML, gy, wd_canvas_w - WD_MR, gy, fill="#e8e8e8", dash=(3, 4))
                cv_wd.create_text(WD_ML - 4, gy, text=f"{pct}%", anchor="e", font=("", 9), fill="#888")
            cv_wd.create_line(WD_ML, WD_MT, WD_ML, WD_MT + WD_CH, fill="#ccc")
            cv_wd.create_line(WD_ML, WD_MT + WD_CH, wd_canvas_w - WD_MR, WD_MT + WD_CH, fill="#ccc")

            for i, (label, rate, total, dist) in enumerate(wd_rates):
                x0 = WD_ML + i * (WD_BW + WD_BG)
                x1 = x0 + WD_BW
                cx = (x0 + x1) / 2
                bar_top = wd_rate_to_y(rate) if rate > 0 else WD_MT + WD_CH
                color   = DIST_CLR if (total > 0 and rate > 0) else (EMPTY_CLR if total > 0 else "#f4f4f4")
                cv_wd.create_rectangle(x0, bar_top, x1, WD_MT + WD_CH, fill=color, outline="")
                if rate > 0:
                    cv_wd.create_text(cx, bar_top - 3, text=f"{rate:.0f}%",
                                      anchor="s", font=("", 9), fill="#555")
                cv_wd.create_text(cx, WD_MT + WD_CH + 4, text=label,
                                  anchor="n", font=("", 10), fill="#555")

        wh_btn = ttk.Frame(when_tab)
        wh_btn.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(wh_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)

        # ── Tab 3: Daily Trend ────────────────────────────────────────────────
        daily_tab = ttk.Frame(nb, padding=8)
        nb.add(daily_tab, text="  Daily Trend  ")

        daily_rows = db.get_daily_distraction_rate(tf)

        if not daily_rows:
            ttk.Label(daily_tab, text="No session data yet.",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
        else:
            daily_pts: list[tuple[str, float, int, int]] = []
            for row in daily_rows:
                total = row["total_sessions"]
                dist  = row["distracted_sessions"] or 0
                rate  = round(dist / total * 100, 1) if total else 0.0
                daily_pts.append((row["day"], rate, total, dist))

            D_PT_GAP  = 48
            D_ML, D_MR = 58, 24
            D_MT, D_MB = 44, 64
            D_CH       = 220
            d_n        = len(daily_pts)
            d_canvas_w = D_ML + D_MR + max(1, d_n - 1) * D_PT_GAP + (D_PT_GAP if d_n == 1 else 10)
            d_canvas_h = D_MT + D_CH + D_MB
            D_Y_MAX    = 100.0
            DIST_CLR_D = "#e15759"
            d_rate_to_y = lambda r: D_MT + D_CH - int(D_CH * r / D_Y_MAX)  # noqa: E731
            d_pt_x      = lambda i: D_ML + (D_PT_GAP // 2 if d_n == 1 else i * D_PT_GAP)  # noqa: E731

            daily_btn = ttk.Frame(daily_tab)
            daily_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 6))
            ttk.Button(daily_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            d_scroll = ttk.Frame(daily_tab)
            d_scroll.pack(fill=tk.BOTH, expand=True)
            d_hsb = ttk.Scrollbar(d_scroll, orient="horizontal")
            d_hsb.pack(side=tk.BOTTOM, fill=tk.X)
            cv_daily = tk.Canvas(d_scroll, bg="white", highlightthickness=0, xscrollcommand=d_hsb.set)
            cv_daily.pack(fill=tk.BOTH, expand=True)
            d_hsb.config(command=cv_daily.xview)
            cv_daily.configure(scrollregion=(0, 0, d_canvas_w, d_canvas_h))
            cv_daily.bind("<MouseWheel>",
                          lambda e: cv_daily.xview_scroll(int(-1 * (e.delta / 30)), "units"))

            for i in range(6):
                pct = i * 20
                gy  = d_rate_to_y(pct)
                cv_daily.create_line(D_ML, gy, d_canvas_w - D_MR, gy, fill="#e8e8e8", dash=(3, 4))
                cv_daily.create_text(D_ML - 4, gy, text=f"{pct}%", anchor="e", font=("", 10), fill="#888")
            cv_daily.create_line(D_ML, D_MT, D_ML, D_MT + D_CH, fill="#ccc")
            cv_daily.create_line(D_ML, D_MT + D_CH, d_canvas_w - D_MR, D_MT + D_CH, fill="#ccc")
            cv_daily.create_text(
                (D_ML + d_canvas_w - D_MR) / 2, 10, text="Daily Distraction Rate",
                anchor="n", font=("", 13, "bold"), fill="#333",
            )

            d_coords = [(d_pt_x(i), d_rate_to_y(pt[1])) for i, pt in enumerate(daily_pts)]
            for i in range(len(d_coords) - 1):
                cv_daily.create_line(
                    d_coords[i][0], d_coords[i][1], d_coords[i + 1][0], d_coords[i + 1][1],
                    fill=DIST_CLR_D, width=2,
                )

            DOT_R = 5
            for pt, (cx, cy) in zip(daily_pts, d_coords):
                day, rate, total, dist = pt
                cv_daily.create_oval(cx - DOT_R, cy - DOT_R, cx + DOT_R, cy + DOT_R,
                                     fill=DIST_CLR_D, outline="white", width=2)
                cv_daily.create_text(cx, cy - DOT_R - 4, text=f"{rate:.0f}%",
                                     anchor="s", font=("", 10, "bold"), fill=DIST_CLR_D)
                d_obj = datetime.date.fromisoformat(day)
                lbl = d_obj.strftime("%a\n%-d")
                cv_daily.create_text(cx, D_MT + D_CH + 5, text=lbl,
                                     anchor="nw", font=("", 9), fill="#555", angle=45)
            cv_daily.after(150, lambda: cv_daily.xview_moveto(1.0))

        # ── Tab 4: Weekly Trend ───────────────────────────────────────────────
        trend_tab = ttk.Frame(nb, padding=8)
        nb.add(trend_tab, text="  Weekly Trend  ")

        weekly_rows = db.get_weekly_distraction_rate(tf)

        if not weekly_rows:
            ttk.Label(trend_tab, text="No session data yet.",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
        else:
            trend_pts: list[tuple[str, float, int, int]] = []
            for row in weekly_rows:
                total = row["total_sessions"]
                dist  = row["distracted_sessions"] or 0
                rate  = round(dist / total * 100, 1) if total else 0.0
                trend_pts.append((row["week"], rate, total, dist))

            PT_GAP     = 60
            T_ML, T_MR = 58, 24
            T_MT, T_MB = 44, 64
            T_CH       = 220
            n_pts      = len(trend_pts)
            t_canvas_w = T_ML + T_MR + max(1, n_pts - 1) * PT_GAP + (PT_GAP if n_pts == 1 else 10)
            t_canvas_h = T_MT + T_CH + T_MB
            T_Y_MAX    = 100.0
            DIST_CLR_T = "#e15759"
            t_rate_to_y = lambda r: T_MT + T_CH - int(T_CH * r / T_Y_MAX)  # noqa: E731
            t_pt_x      = lambda i: T_ML + (PT_GAP // 2 if n_pts == 1 else i * PT_GAP)  # noqa: E731

            trend_btn = ttk.Frame(trend_tab)
            trend_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 6))
            ttk.Button(trend_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            t_scroll = ttk.Frame(trend_tab)
            t_scroll.pack(fill=tk.BOTH, expand=True)
            t_hsb = ttk.Scrollbar(t_scroll, orient="horizontal")
            t_hsb.pack(side=tk.BOTTOM, fill=tk.X)
            cv_trend = tk.Canvas(t_scroll, bg="white", highlightthickness=0, xscrollcommand=t_hsb.set)
            cv_trend.pack(fill=tk.BOTH, expand=True)
            t_hsb.config(command=cv_trend.xview)
            cv_trend.configure(scrollregion=(0, 0, t_canvas_w, t_canvas_h))
            cv_trend.bind("<MouseWheel>",
                          lambda e: cv_trend.xview_scroll(int(-1 * (e.delta / 30)), "units"))

            for i in range(6):
                pct = i * 20
                gy  = t_rate_to_y(pct)
                cv_trend.create_line(T_ML, gy, t_canvas_w - T_MR, gy, fill="#e8e8e8", dash=(3, 4))
                cv_trend.create_text(T_ML - 4, gy, text=f"{pct}%", anchor="e", font=("", 10), fill="#888")
            cv_trend.create_line(T_ML, T_MT, T_ML, T_MT + T_CH, fill="#ccc")
            cv_trend.create_line(T_ML, T_MT + T_CH, t_canvas_w - T_MR, T_MT + T_CH, fill="#ccc")
            cv_trend.create_text(
                (T_ML + t_canvas_w - T_MR) / 2, 10, text="Weekly Distraction Rate",
                anchor="n", font=("", 13, "bold"), fill="#333",
            )

            t_coords = [(t_pt_x(i), t_rate_to_y(pt[1])) for i, pt in enumerate(trend_pts)]
            for i in range(len(t_coords) - 1):
                cv_trend.create_line(
                    t_coords[i][0], t_coords[i][1], t_coords[i + 1][0], t_coords[i + 1][1],
                    fill=DIST_CLR_T, width=2,
                )

            DOT_R = 5
            for pt, (cx, cy) in zip(trend_pts, t_coords):
                week, rate, total, dist = pt
                cv_trend.create_oval(cx - DOT_R, cy - DOT_R, cx + DOT_R, cy + DOT_R,
                                     fill=DIST_CLR_T, outline="white", width=2)
                cv_trend.create_text(cx, cy - DOT_R - 4, text=f"{rate:.0f}%",
                                     anchor="s", font=("", 10, "bold"), fill=DIST_CLR_T)
                cv_trend.create_text(cx, T_MT + T_CH + 5, text=week[5:],
                                     anchor="nw", font=("", 9), fill="#555", angle=45)
            cv_trend.after(150, lambda: cv_trend.xview_moveto(1.0))

        # ── Tab 5: Focus vs Study Time (scatter + regression) ────────────────
        scatter_tab = ttk.Frame(nb, padding=8)
        nb.add(scatter_tab, text="  Focus vs Time  ")

        scatter_rows = db.get_daily_focus_vs_time(tf)
        scatter_pts: list[tuple[float, float]] = [
            (float(r["total_min"]), float(r["avg_focus"])) for r in scatter_rows
        ]

        if len(scatter_pts) < 2:
            ttk.Label(scatter_tab, text="Not enough data yet (need ≥ 2 days with focus scores).",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
            ttk.Button(scatter_tab, text="Close", command=root.destroy).pack(side=tk.BOTTOM, anchor=tk.E, pady=4)
        else:
            xs = [p[0] for p in scatter_pts]
            ys = [p[1] for p in scatter_pts]
            n  = len(xs)
            x_mean = sum(xs) / n
            y_mean = sum(ys) / n
            sxx    = sum((x - x_mean) ** 2 for x in xs)
            sxy    = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
            slope     = sxy / sxx if sxx > 0 else 0.0
            intercept = y_mean - slope * x_mean
            y_pred    = [slope * x + intercept for x in xs]
            ss_tot    = sum((y - y_mean) ** 2 for y in ys)
            ss_res    = sum((y - yp) ** 2 for y, yp in zip(ys, y_pred))
            r_sq      = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
            r_sign    = "+" if slope >= 0 else ""

            SC_ML, SC_MR = 68, 24
            SC_MT, SC_MB = 44, 56
            SC_CH        = 260
            SC_CW        = 560
            x_min_v = 0.0
            x_max_v = max(max(xs) * 1.1, 60.0)
            y_min_v = 0.0
            y_max_v = 10.0

            def sc_x(v: float) -> float:
                return SC_ML + (v - x_min_v) / (x_max_v - x_min_v) * SC_CW

            def sc_y(v: float) -> float:
                return SC_MT + SC_CH - (v - y_min_v) / (y_max_v - y_min_v) * SC_CH

            sc_canvas_w = SC_ML + SC_CW + SC_MR
            sc_canvas_h = SC_MT + SC_CH + SC_MB

            sc_outer = ttk.Frame(scatter_tab)
            sc_outer.pack(fill=tk.BOTH, expand=True)
            sc_btn = ttk.Frame(scatter_tab)
            sc_btn.pack(fill=tk.X, pady=(4, 0))
            ttk.Button(sc_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            stats_frame = ttk.LabelFrame(sc_outer, text="  Regression Stats  ", padding=12)
            stats_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
            slope_per_hr = slope * 60
            stat_lines = [
                ("n (days)",  f"{n}"),
                ("R²",        f"{r_sq:.3f}"),
                ("Slope",     f"{r_sign}{slope:.4f} focus/min"),
                ("",          f"({r_sign}{slope_per_hr:.2f} focus/hr)"),
                ("Intercept", f"{intercept:.2f}"),
            ]
            for label, val in stat_lines:
                row_f = ttk.Frame(stats_frame)
                row_f.pack(fill=tk.X, pady=2)
                if label:
                    ttk.Label(row_f, text=f"{label}:", font=("", FS_SM, "bold"), width=10,
                              anchor="w").pack(side=tk.LEFT)
                ttk.Label(row_f, text=val, font=("", FS_SM), foreground=C_MUTED).pack(side=tk.LEFT)
            interp_txt = (
                "Positive slope: more study → higher focus" if slope > 0
                else "Negative slope: more study → lower focus" if slope < 0
                else "No trend detected"
            )
            ttk.Label(stats_frame, text=interp_txt, font=("", FS_XS, "italic"),
                      foreground="#777", wraplength=160).pack(pady=(12, 0))

            cv_sc = tk.Canvas(sc_outer, bg="white", highlightthickness=0,
                              width=sc_canvas_w, height=sc_canvas_h)
            cv_sc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            for yv in range(0, 11, 2):
                gy = sc_y(yv)
                cv_sc.create_line(SC_ML, gy, SC_ML + SC_CW, gy, fill="#e8e8e8", dash=(3, 4))
                cv_sc.create_text(SC_ML - 5, gy, text=str(yv), anchor="e", font=("", 9), fill="#888")

            x_tick = 30
            xv = x_tick
            while xv <= x_max_v:
                gx = sc_x(xv)
                cv_sc.create_line(gx, SC_MT, gx, SC_MT + SC_CH, fill="#e8e8e8", dash=(3, 4))
                cv_sc.create_text(gx, SC_MT + SC_CH + 4, text=str(int(xv)), anchor="n", font=("", 9), fill="#888")
                xv += x_tick

            cv_sc.create_line(SC_ML, SC_MT, SC_ML, SC_MT + SC_CH, fill="#bbb", width=1)
            cv_sc.create_line(SC_ML, SC_MT + SC_CH, SC_ML + SC_CW, SC_MT + SC_CH, fill="#bbb", width=1)
            cv_sc.create_text((SC_ML + SC_ML + SC_CW) / 2, sc_canvas_h - 6,
                              text="Total study time that day (minutes)", anchor="s", font=("", 11), fill="#444")
            cv_sc.create_text(14, (SC_MT + SC_MT + SC_CH) / 2,
                              text="Avg focus", anchor="center", font=("", 11), fill="#444", angle=90)
            cv_sc.create_text((SC_ML + SC_ML + SC_CW) / 2, 10,
                              text="Focus vs Study Time per Day", anchor="n", font=("", 13, "bold"), fill="#333")

            if sxx > 0:
                reg_x0 = x_min_v
                reg_x1 = x_max_v
                reg_y0 = max(y_min_v, min(y_max_v, slope * reg_x0 + intercept))
                reg_y1 = max(y_min_v, min(y_max_v, slope * reg_x1 + intercept))
                cv_sc.create_line(sc_x(reg_x0), sc_y(reg_y0), sc_x(reg_x1), sc_y(reg_y1),
                                  fill="#4e79a7", width=2, dash=(6, 3))

            DOT_R = 5
            for xv, yv in scatter_pts:
                cx = sc_x(xv)
                cy = sc_y(yv)
                cv_sc.create_oval(cx - DOT_R, cy - DOT_R, cx + DOT_R, cy + DOT_R,
                                  fill="#f28e2b", outline="white", width=1)

        # ── Tab 6: Start Time Effect ──────────────────────────────────────────
        start_tab = ttk.Frame(nb, padding=8)
        nb.add(start_tab, text="  Start Time Effect  ")

        start_rows = db.get_focus_by_start_hour(tf)

        if not start_rows:
            ttk.Label(start_tab, text="Not enough data yet.",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
            ttk.Button(start_tab, text="Close", command=root.destroy).pack(side=tk.BOTTOM, anchor=tk.E, pady=4)
        else:
            start_data = [(r["start_group"], float(r["avg_focus"]), int(r["days"])) for r in start_rows]

            ST_ML, ST_MR = 68, 24
            ST_MT, ST_MB = 60, 80
            ST_CH        = 240
            BAR_W        = 100
            BAR_GAP      = 60
            n_bars       = len(start_data)
            st_canvas_w  = ST_ML + ST_MR + n_bars * BAR_W + (n_bars - 1) * BAR_GAP + 20
            st_canvas_h  = ST_MT + ST_CH + ST_MB
            ST_Y_MAX     = 10.0
            BAR_COLORS   = ["#59a14f", "#f28e2b", "#e15759"]

            def st_y(v: float) -> float:
                return ST_MT + ST_CH - (v / ST_Y_MAX) * ST_CH

            st_outer = ttk.Frame(start_tab)
            st_outer.pack(fill=tk.BOTH, expand=True)
            st_btn = ttk.Frame(start_tab)
            st_btn.pack(fill=tk.X, pady=(4, 0))
            ttk.Button(st_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            cv_st = tk.Canvas(st_outer, bg="white", highlightthickness=0,
                              width=st_canvas_w, height=st_canvas_h)
            cv_st.pack(fill=tk.BOTH, expand=True)

            for yv in range(0, 11, 2):
                gy = st_y(yv)
                cv_st.create_line(ST_ML, gy, st_canvas_w - ST_MR, gy, fill="#e8e8e8", dash=(3, 4))
                cv_st.create_text(ST_ML - 5, gy, text=str(yv), anchor="e", font=("", 9), fill="#888")
            cv_st.create_line(ST_ML, ST_MT, ST_ML, ST_MT + ST_CH, fill="#bbb", width=1)
            cv_st.create_line(ST_ML, ST_MT + ST_CH, st_canvas_w - ST_MR, ST_MT + ST_CH, fill="#bbb", width=1)
            cv_st.create_text((ST_ML + st_canvas_w - ST_MR) / 2, 10,
                              text="Avg Focus by First Session Start Time",
                              anchor="n", font=("", 13, "bold"), fill="#333")
            cv_st.create_text(14, (ST_MT + ST_MT + ST_CH) / 2,
                              text="Avg focus (0–10)", anchor="center", font=("", 11), fill="#444", angle=90)

            for i, (group, avg_focus, days) in enumerate(start_data):
                x0 = ST_ML + 10 + i * (BAR_W + BAR_GAP)
                x1 = x0 + BAR_W
                cx = (x0 + x1) / 2
                bar_top = st_y(avg_focus)
                color   = BAR_COLORS[i % len(BAR_COLORS)]
                cv_st.create_rectangle(x0, bar_top, x1, ST_MT + ST_CH, fill=color, outline="", stipple="")
                cv_st.create_text(cx, bar_top - 6, text=f"{avg_focus:.1f}",
                                  anchor="s", font=("", 12, "bold"), fill=color)
                cv_st.create_text(cx, ST_MT + ST_CH + 6, text=group,
                                  anchor="n", font=("", 11, "bold"), fill="#444")
                cv_st.create_text(cx, ST_MT + ST_CH + 26,
                                  text=f"({days} day{'s' if days != 1 else ''})",
                                  anchor="n", font=("", 9), fill="#888")

        # ── Tab 7: Focus vs Session Start Time (individual scatter) ──────────
        fsct_tab = ttk.Frame(nb, padding=8)
        nb.add(fsct_tab, text="  Focus vs Start Time  ")

        fsct_rows = db.get_focus_vs_start_time(tf)
        fsct_pts: list[tuple[float, int]] = []
        for r in fsct_rows:
            st = r["start_time"]
            if not st:
                continue
            try:
                h = int(st[11:13])
                m = int(st[14:16])
                fsct_pts.append((h + m / 60.0, int(r["focus"])))
            except (IndexError, ValueError):
                continue

        if len(fsct_pts) < 2:
            ttk.Label(fsct_tab, text="Not enough data yet (need ≥ 2 sessions with focus scores).",
                      font=("", FS_SM), foreground=C_MUTED).pack(expand=True)
            ttk.Button(fsct_tab, text="Close", command=root.destroy).pack(side=tk.BOTTOM, anchor=tk.E, pady=4)
        else:
            FSCT_ML, FSCT_MR = 60, 30
            FSCT_MT, FSCT_MB = 50, 60
            FSCT_CW, FSCT_CH = 820, 340
            FSCT_W = FSCT_ML + FSCT_CW + FSCT_MR
            FSCT_H = FSCT_MT + FSCT_CH + FSCT_MB

            all_hours = [p[0] for p in fsct_pts]
            x_min = max(0.0, min(all_hours) - 0.5)
            x_max = min(24.0, max(all_hours) + 0.5)

            def fsct_x(h: float) -> float:
                return FSCT_ML + (h - x_min) / (x_max - x_min) * FSCT_CW

            def fsct_y(v: float) -> float:
                return FSCT_MT + FSCT_CH - ((v - 1) / 9.0) * FSCT_CH

            fsct_outer = ttk.Frame(fsct_tab)
            fsct_outer.pack(fill=tk.BOTH, expand=True)
            fsct_btn = ttk.Frame(fsct_tab)
            fsct_btn.pack(fill=tk.X, pady=(4, 0))
            ttk.Button(fsct_btn, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            cv_fsct = tk.Canvas(fsct_outer, bg="white", highlightthickness=0, width=FSCT_W, height=FSCT_H)
            cv_fsct.pack(fill=tk.BOTH, expand=True)

            cv_fsct.create_text((FSCT_ML + FSCT_ML + FSCT_CW) / 2, 12,
                                text="Focus Score vs Session Start Time",
                                anchor="n", font=("", 13, "bold"), fill="#333")

            for yv in range(1, 11):
                gy = fsct_y(float(yv))
                cv_fsct.create_line(FSCT_ML, gy, FSCT_ML + FSCT_CW, gy, fill="#e8e8e8", dash=(3, 4))
                cv_fsct.create_text(FSCT_ML - 6, gy, text=str(yv), anchor="e", font=("", 9), fill="#888")

            cv_fsct.create_line(FSCT_ML, FSCT_MT, FSCT_ML, FSCT_MT + FSCT_CH, fill="#bbb", width=1)
            cv_fsct.create_line(FSCT_ML, FSCT_MT + FSCT_CH, FSCT_ML + FSCT_CW, FSCT_MT + FSCT_CH,
                                fill="#bbb", width=1)
            cv_fsct.create_text(14, FSCT_MT + FSCT_CH / 2,
                                text="Focus (1–10)", anchor="center", font=("", 11), fill="#444", angle=90)

            x_tick_start = int(x_min) + (1 if x_min != int(x_min) else 0)
            for h in range(x_tick_start, int(x_max) + 1):
                gx = fsct_x(float(h))
                cv_fsct.create_line(gx, FSCT_MT + FSCT_CH, gx, FSCT_MT + FSCT_CH + 4, fill="#bbb")
                cv_fsct.create_text(gx, FSCT_MT + FSCT_CH + 8, text=f"{h:02d}:00",
                                    anchor="n", font=("", 9), fill="#666")

            cv_fsct.create_text(FSCT_ML + FSCT_CW / 2, FSCT_MT + FSCT_CH + FSCT_MB - 8,
                                text="Session start time", anchor="s", font=("", 11), fill="#444")

            from collections import defaultdict
            buckets: dict[int, list[int]] = defaultdict(list)
            BIN = 0.5
            for hv, fv in fsct_pts:
                buckets[int(hv / BIN)].append(fv)
            avg_pts = sorted(
                ((k * BIN + BIN / 2, sum(v) / len(v)) for k, v in buckets.items()),
                key=lambda p: p[0]
            )
            if len(avg_pts) >= 2:
                avg_coords = []
                for hv, av in avg_pts:
                    avg_coords += [fsct_x(hv), fsct_y(av)]
                cv_fsct.create_line(*avg_coords, fill="#e15759", width=2, smooth=True)
                for hv, av in avg_pts:
                    mx, my = fsct_x(hv), fsct_y(av)
                    cv_fsct.create_oval(mx - 4, my - 4, mx + 4, my + 4,
                                        fill="#e15759", outline="white", width=1)

            DOT_R = 5
            for hv, fv in fsct_pts:
                cx = fsct_x(hv)
                cy = fsct_y(float(fv))
                cv_fsct.create_oval(cx - DOT_R, cy - DOT_R, cx + DOT_R, cy + DOT_R,
                                    fill="#4e79a7", outline="white", width=1)

            lx, ly = FSCT_ML + FSCT_CW - 160, FSCT_MT + 10
            cv_fsct.create_oval(lx, ly + 3, lx + 10, ly + 13, fill="#4e79a7", outline="")
            cv_fsct.create_text(lx + 14, ly + 8, text="Session", anchor="w", font=("", 9), fill="#555")
            cv_fsct.create_line(lx + 50, ly + 8, lx + 60, ly + 8, fill="#e15759", width=2)
            cv_fsct.create_oval(lx + 52, ly + 4, lx + 58, ly + 10, fill="#e15759", outline="")
            cv_fsct.create_text(lx + 64, ly + 8, text="30-min avg", anchor="w", font=("", 9), fill="#555")

    term_var.trace_add("write", _rebuild)
    _rebuild()
    _bring_to_front(root)
    root.mainloop()


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
    root.withdraw()
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

    stop_btn = ttk.Button(root, text="Stop", command=_stop)
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
    anxiety or dissociation.  Each step shows an emoji cue and instruction text.
    """
    STEPS = [
        ("👁️",  "5 things you can SEE",
         "Look around and name 5 things you can see right now."),
        ("🖐️",  "4 things you can TOUCH",
         "Notice 4 things you can physically feel — textures, temperature, weight."),
        ("👂",  "3 things you can HEAR",
         "Listen carefully and identify 3 distinct sounds around you."),
        ("👃",  "2 things you can SMELL",
         "Take a slow breath and notice 2 things you can smell."),
        ("👅",  "1 thing you can TASTE",
         "Focus inward — what is one thing you can taste right now?"),
    ]

    root = tk.Tk()
    root.withdraw()
    root.title("5-4-3-2-1 Grounding")
    root.geometry("380x340")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    step = [0]

    # ── Content ───────────────────────────────────────────────────────────
    content = ttk.Frame(root, padding=(24, 24, 24, 8))
    content.pack(fill=tk.BOTH, expand=True)

    step_lbl = ttk.Label(content, text="Step 1 of 5",
                          font=("", FS_XS), foreground=C_MUTED)
    step_lbl.pack()

    emoji_lbl = tk.Label(content, text=STEPS[0][0], font=("", 72))
    emoji_lbl.pack(pady=(8, 4))

    title_lbl = ttk.Label(content, text=STEPS[0][1], font=("", FS_MD, "bold"))
    title_lbl.pack(pady=(0, 8))

    instr_lbl = ttk.Label(content, text=STEPS[0][2], font=("", FS_SM),
                           foreground=C_MUTED, wraplength=320, justify="center")
    instr_lbl.pack()

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
            content.pack_forget()
            done = ttk.Frame(root, padding=36)
            done.pack(expand=True)
            ttk.Label(done, text="🎉", font=("", 64)).pack()
            ttk.Label(done, text="Well done!", font=("", 18, "bold")).pack(pady=(8, 4))
            ttk.Label(done,
                       text="You've completed the 5-4-3-2-1 grounding exercise.\n"
                            "Take a moment to notice how you feel.",
                       font=("", FS_SM), foreground=C_MUTED,
                       justify="center", wraplength=300).pack(pady=(0, 4))
            next_var.set("Close")
            next_btn.config(command=root.destroy)
            return

        emoji, title, instr = STEPS[step[0]]
        step_lbl.config(text=f"Step {step[0] + 1} of {len(STEPS)}")
        emoji_lbl.config(text=emoji)
        title_lbl.config(text=title)
        instr_lbl.config(text=instr)

        if step[0] == len(STEPS) - 1:
            next_var.set("Finish ✓")

    root.bind("<Return>", lambda _: _advance())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()

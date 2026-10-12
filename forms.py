"""All tkinter UI: configure dialog, session feedback form, history window,
breathing exercise, and 5-4-3-2-1 grounding."""

import colorsys
import datetime
import math
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

import db


# ─── Design tokens ────────────────────────────────────────────────────────────

C_PRIMARY       = "#c0392b"   # tomato red — selected state, primary actions
C_PRIMARY_SOFT  = "#fbe9e6"   # tomato tint — selected presets, late-work box
C_PRIMARY_INK   = "#8f2a1f"   # tomato text that stays readable on the tint
C_CHIP_SEL_BG   = "#c0392b"
C_CHIP_SEL_FG   = "#ffffff"  # white on tomato — near-black here was unreadable
C_CHIP_UNSEL_BG = "#ffffff"
C_CHIP_UNSEL_FG = "#3d3a34"
C_MUTED         = "#888888"   # hints on the system window background (light or dark)
C_DIVIDER       = "#e0e0e0"
C_ROW_EVEN      = "#f8f8f8"
C_ROW_ODD       = "#ffffff"

# Card-style windows (start, configure, session form, statistics) paint their
# own light surfaces instead of the system background.
C_BG             = "#f6f5f2"  # warm window ground
C_CARD           = "#ffffff"
C_BORDER         = "#e4e1db"  # card hairlines
C_CONTROL_BORDER = "#d6d2ca"  # text fields, secondary buttons
C_TEXT           = "#1f1d1a"
C_TEXT_2         = "#3d3a34"
C_INK_MUTED      = "#6b675f"  # 5.6:1 on white; #888888 is only 3.5:1
C_TRACK          = "#efede8"  # empty part of a bar
C_NOTICE_BG      = "#fff4d6"
C_NOTICE_BORDER  = "#f0dfa8"
C_NOTICE_FG      = "#4a3d12"

FS_XS = 11   # captions / hints / section labels
FS_SM = 13   # body
FS_MD = 15   # card titles
FS_LG = 20   # window titles
FS_XL = 32   # large numbers (duration picker, stat tiles)

# Curated set for the common case; past its end a fixed list would have to
# repeat a colour, so wider charts switch to hues spread over the actual count.
TOPIC_PALETTE = [
    "#4e79a7", "#f28e2b", "#59a14f", "#b6992d", "#499894",
    "#e15759", "#79706e", "#d37295", "#b07aa1", "#9d7660",
]
_HUE_OFFSET = 0.5417   # rotates the generated ramp off pure cyan


def _topic_palette(n: int) -> list[str]:
    """`n` visually distinct fills — no two series ever share a colour."""
    if n <= len(TOPIC_PALETTE):
        return TOPIC_PALETTE[:n]
    colors = []
    for i in range(n):
        hue      = (i / n + _HUE_OFFSET) % 1.0
        sat, val = (0.60, 0.70) if i % 2 == 0 else (0.40, 0.92)
        r, g, b  = colorsys.hsv_to_rgb(hue, sat, val)
        colors.append(f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}")
    return colors


def _readable_fg(widget: tk.Misc, bg: str) -> str:
    """Dark or light label text, whichever reads on `bg`.

    Goes through winfo_rgb so it also resolves the macOS system colours the
    ttk theme hands out (which flip with the OS light/dark setting).
    """
    r, g, b = (c / 257 for c in widget.winfo_rgb(bg))
    return "#333333" if (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6 else "#f0f0f0"


def _dimmed(color: str, amount: float = 0.8, toward: int = 235) -> str:
    """`color` faded toward the grey level `toward` (0-255).

    De-emphasised marks should sink into whatever they sit on, so callers pass
    the surface they are drawn against: the white plot area, or the legend's
    theme background.
    """
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(c + (toward - c) * amount) for c in (r, g, b))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _wheel_steps(event: "tk.Event") -> int:
    """Convert a <MouseWheel> delta into scroll units.

    macOS trackpads report small per-event deltas (±1…±10, velocity-scaled);
    classic mice report multiples of ±120.  Dividing by a fixed 30 truncates
    the trackpad case to 0, so normalise both explicitly.
    """
    d = event.delta
    if abs(d) >= 120:
        d = int(d / 120)
    return -int(d)


def _bind_wheel_yscroll(widget) -> None:
    """Make trackpad / mouse-wheel scrolling work on a vertically scrolling widget."""
    _bind_wheel_yscroll_to(widget, widget)


def _bind_wheel_yscroll_to(widget, target) -> None:
    """Scroll `target` vertically when the wheel / trackpad moves over `widget`."""
    def _on_wheel(e: "tk.Event") -> str:
        steps = _wheel_steps(e)
        if steps:
            target.yview_scroll(steps, "units")
        return "break"
    widget.bind("<MouseWheel>", _on_wheel)


def _bind_canvas_hscroll(canvas: tk.Canvas) -> None:
    """Make trackpad / mouse-wheel scrolling work on a horizontally scrolling canvas.

    Both vertical and horizontal swipes pan the chart; on macOS a horizontal
    swipe arrives as <Shift-MouseWheel>.  xscrollincrement keeps each step
    small so trackpad event streams feel smooth.
    """
    canvas.configure(xscrollincrement=12)
    def _on_wheel(e: "tk.Event") -> str:
        steps = _wheel_steps(e)
        if steps:
            canvas.xview_scroll(steps, "units")
        return "break"
    canvas.bind("<MouseWheel>", _on_wheel)
    canvas.bind("<Shift-MouseWheel>", _on_wheel)


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


# ─── Card-style widgets ───────────────────────────────────────────────────────
# Plain tk widgets with explicit colours: the aqua theme ignores background
# colours on most ttk widgets, and tk.Button can't be recoloured on macOS at
# all, so chips and buttons on card windows are Labels that act like buttons.

def _card_theme(root: tk.Tk) -> ttk.Style:
    """_theme() plus the warm ground and the ttk styles used on top of it."""
    style = _theme(root)
    root.configure(bg=C_BG)
    for name, bg in (("Card", C_CARD), ("Ground", C_BG)):
        style.configure(f"{name}.TCheckbutton", background=bg, foreground=C_TEXT_2, font=("", FS_SM))
        style.configure(f"{name}.Horizontal.TScale", background=bg)
    return style


def _bg_of(widget: tk.Misc) -> str:
    try:
        return widget.cget("bg")
    except tk.TclError:   # ttk widgets have no -bg
        return C_BG


def _label(parent: tk.Misc, text: str = "", *, size: int = FS_SM, bold: bool = False,
           fg: str = C_TEXT, **kw) -> tk.Label:
    kw.setdefault("bg", _bg_of(parent))
    return tk.Label(parent, text=text, font=("", size, "bold" if bold else "normal"),
                    fg=fg, bd=0, **kw)


def _caption(parent: tk.Misc, text: str) -> tk.Label:
    """Small upper-case section label."""
    return _label(parent, text.upper(), size=FS_XS, bold=True, fg=C_INK_MUTED)


def _card(parent: tk.Misc, bg: str = C_CARD, border: str = C_BORDER) -> tk.Frame:
    """White panel with a hairline border."""
    return tk.Frame(parent, bg=bg, bd=0, highlightthickness=1,
                    highlightbackground=border, highlightcolor=border)


def _text_field_opts() -> dict:
    """Shared look for tk.Entry / tk.Text on card windows."""
    return dict(
        font=("", FS_SM), bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground=C_CONTROL_BORDER, highlightcolor=C_PRIMARY,
    )


class _Pill(tk.Label):
    """A Label that behaves like a button: click, Space/Return, Tab focus."""

    STYLES = {
        # name:       (bg,             fg,            border,           bold)
        "chip":      (C_CARD,         C_TEXT_2,      C_BORDER,         False),
        "chip_on":   (C_PRIMARY,      "#ffffff",     C_PRIMARY,        False),
        "soft_on":   (C_PRIMARY_SOFT, C_PRIMARY_INK, C_PRIMARY,        True),
        "add":       (C_BG,           C_INK_MUTED,   C_CONTROL_BORDER, False),
        "primary":   (C_PRIMARY,      "#ffffff",     C_PRIMARY,        True),
        "secondary": (C_CARD,         C_TEXT_2,      C_CONTROL_BORDER, False),
        "quiet":     (None,           C_INK_MUTED,   None,             False),  # parent's bg
    }

    def __init__(self, parent: tk.Misc, text: str, command, *, style: str = "chip",
                 padx: int = 12, pady: int = 5, size: int = FS_SM, **kw) -> None:
        super().__init__(parent, text=text, bd=0, highlightthickness=1,
                         highlightcolor=C_TEXT,          # drawn while focused
                         padx=padx, pady=pady, cursor="hand2", takefocus=1, **kw)
        self._command = command
        self._size = size
        self.set_style(style)
        for seq in ("<Button-1>", "<space>", "<Return>"):
            self.bind(seq, self._invoke)

    def _invoke(self, _: object = None) -> str:
        self._command()
        return "break"

    def set_style(self, style: str) -> None:
        bg, fg, border, bold = self.STYLES[style]
        bg = bg or _bg_of(self.master)
        self.configure(
            bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
            highlightbackground=border or bg,
            font=("", self._size, "bold" if bold else "normal"),
        )


def _flow_rows(parent: tk.Misc, texts: list[str], avail_w: int) -> list[tuple[tk.Frame, str]]:
    """Wrap pills onto as many rows as `avail_w` px needs.

    Returns a (row frame, text) pair per item; callers create each pill in
    its row frame and pack it to the left.
    """
    f = tkfont.Font(family="", size=FS_SM)
    out: list[tuple[tk.Frame, str]] = []
    row, row_w = None, 0
    for t in texts:
        w = f.measure(t) + 2 * 12 + 2 + 6   # text + padx + border + gap
        if row is None or (row_w and row_w + w > avail_w):
            row = tk.Frame(parent, bg=_bg_of(parent))
            row.pack(fill=tk.X, anchor=tk.W, pady=(6 if out else 0, 0))
            row_w = 0
        out.append((row, t))
        row_w += w
    return out


# ─── Shared: duration-picker widget builder ───────────────────────────────────

DURATION_PRESETS = (15, 25, 45, 50)


def _build_duration_picker(
    frame: tk.Misc,
    current_minutes: int,
    _min: int = 5,
    _max: int = 55,
) -> tk.DoubleVar:
    """
    Add a card to *frame* with a big minutes readout, one-click presets, and
    a slider for anything in between.
    Returns the DoubleVar that holds the chosen value.
    """
    card = _card(frame)
    card.pack(fill=tk.X)
    inner = tk.Frame(card, bg=C_CARD)
    inner.pack(fill=tk.X, padx=20, pady=18)

    clamped = max(_min, min(_max, current_minutes))
    dur_var = tk.DoubleVar(value=float(clamped))

    readout = tk.Frame(inner, bg=C_CARD)
    readout.pack()
    num_lbl = _label(readout, str(clamped), size=FS_XL, bold=True)
    num_lbl.pack(side=tk.LEFT)
    _label(readout, "min", size=FS_MD, fg=C_INK_MUTED).pack(side=tk.LEFT, anchor="s", padx=(6, 0), pady=(0, 8))

    presets = tk.Frame(inner, bg=C_CARD)
    presets.pack(fill=tk.X, pady=(12, 10))
    preset_pills: dict[int, _Pill] = {}
    for i, m in enumerate(DURATION_PRESETS):
        presets.columnconfigure(i, weight=1, uniform="preset")
        pill = _Pill(presets, str(m), lambda m=m: dur_var.set(float(m)), pady=7)
        pill.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
        preset_pills[m] = pill

    slider_row = tk.Frame(inner, bg=C_CARD)
    slider_row.pack(fill=tk.X)
    _label(slider_row, str(_min), size=FS_XS, fg=C_INK_MUTED).pack(side=tk.LEFT)
    ttk.Scale(
        slider_row, from_=_min, to=_max, orient=tk.HORIZONTAL,
        variable=dur_var, style="Card.Horizontal.TScale",
    ).pack(side=tk.LEFT, padx=8, expand=True, fill=tk.X)
    _label(slider_row, str(_max), size=FS_XS, fg=C_INK_MUTED).pack(side=tk.LEFT)

    def _sync(*_: object) -> None:
        v = round(dur_var.get())
        num_lbl.config(text=str(v))
        for m, pill in preset_pills.items():
            pill.set_style("soft_on" if m == v else "chip")

    dur_var.trace_add("write", _sync)
    _sync()
    return dur_var


def _dialog_frame(root: tk.Tk, title: str, width: int = 400) -> tk.Frame:
    """Padded ground-coloured content frame with a window-title heading."""
    frame = tk.Frame(root, bg=C_BG, padx=28, pady=24)
    frame.pack(fill=tk.BOTH, expand=True)
    tk.Frame(frame, bg=C_BG, width=width - 56, height=0).pack()   # fixes the width
    _label(frame, title, size=FS_LG, bold=True).pack(anchor=tk.W, pady=(0, 16))
    return frame


# ─── Start-session window (slider + Play button) ──────────────────────────────

def show_start_window(current_minutes: int, interrupts_on: bool = True) -> dict | None:
    """
    Duration picker shown when the user clicks Start Session.
    `interrupts_on` reflects the menu-bar dropdown's global "Interrupts" toggle,
    so this window's checkbox stays in sync with it instead of always
    defaulting to unchecked.
    Returns {"minutes": int, "disable_interrupts": bool}, or None if cancelled.
    """
    result: list[dict | None] = [None]

    root = tk.Tk()
    root.withdraw()
    root.title("Start Session")
    root.resizable(False, False)
    _card_theme(root)

    frame = _dialog_frame(root, "Start a session")

    dur_var = _build_duration_picker(frame, current_minutes)

    disable_interrupts_var = tk.BooleanVar(value=not interrupts_on)
    interrupts_check = ttk.Checkbutton(
        frame, text="Disable interrupts for this session",
        variable=disable_interrupts_var, style="Ground.TCheckbutton",
    )
    interrupts_check.pack(anchor=tk.W, pady=(14, 0))
    if not interrupts_on:
        # Already disabled globally via the menu-bar toggle - reflect that
        # here instead of letting the user uncheck a box that has no effect.
        interrupts_check.state(["disabled"])

    def _start() -> None:
        result[0] = {
            "minutes": int(round(dur_var.get())),
            "disable_interrupts": disable_interrupts_var.get(),
        }
        root.quit()

    def _cancel() -> None:
        root.quit()

    btn_frame = tk.Frame(frame, bg=C_BG)
    btn_frame.pack(fill=tk.X, pady=(18, 0))
    _Pill(btn_frame, "Cancel", _cancel, style="secondary", padx=18, pady=9).pack(side=tk.LEFT)
    _Pill(btn_frame, "▶  Start focusing", _start, style="primary", size=FS_MD, pady=8).pack(
        side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0)
    )

    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.bind("<Return>", lambda _: _start())
    root.bind("<Escape>", lambda _: _cancel())

    _bring_to_front(root)
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
    root.resizable(False, False)
    _card_theme(root)

    frame = _dialog_frame(root, "Default session length")

    dur_var = _build_duration_picker(frame, current_minutes)

    def _ok() -> None:
        result[0] = int(round(dur_var.get()))
        root.quit()

    def _cancel() -> None:
        root.quit()

    btn_frame = tk.Frame(frame, bg=C_BG)
    btn_frame.pack(fill=tk.X, pady=(18, 0))
    _Pill(btn_frame, "Save", _ok, style="primary", padx=22, pady=9).pack(side=tk.RIGHT)
    _Pill(btn_frame, "Cancel", _cancel, style="secondary", padx=18, pady=9).pack(side=tk.RIGHT, padx=(0, 10))

    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.bind("<Return>", lambda _: _ok())
    root.bind("<Escape>", lambda _: _cancel())

    _bring_to_front(root)
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


# ─── Distraction capture popup ────────────────────────────────────────────────

def show_distraction_input() -> str | None:
    """
    Tiny quick-capture popup shown mid-session when the user records a distraction.
    Returns the distraction text or None if cancelled.
    """
    result: list[str | None] = [None]

    root = tk.Tk()
    root.withdraw()
    root.title("Record Distraction")
    root.geometry("360x160")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="💭  What's distracting you?", font=("", FS_SM, "bold")).pack(anchor=tk.W)
    ttk.Label(
        frame, text="Note it down, then get back to focus.",
        font=("", FS_XS), foreground=C_MUTED,
    ).pack(anchor=tk.W, pady=(2, 10))

    text_var = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=text_var, font=("", FS_SM))
    entry.pack(fill=tk.X)
    entry.focus_set()

    def _submit() -> None:
        txt = text_var.get().strip()
        if txt:
            result[0] = txt
        root.quit()

    def _cancel() -> None:
        root.quit()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(12, 0))
    ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT)
    ttk.Button(btn_frame, text="Record ✓", command=_submit).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.bind("<Return>", lambda _: _submit())
    root.bind("<Escape>", lambda _: _cancel())

    root.mainloop()
    root.destroy()
    return result[0]


# ─── Post-session feedback form ───────────────────────────────────────────────

def show_session_form(
    duration_minutes: int,
    distractions: list[str] | None = None,
    late_cutoff: str | None = None,
) -> dict | None:
    """
    Modal form shown after each session ends.
    Returns dict {focus, topic, distracted, reason, late_reason} or None if skipped.

    If ``late_cutoff`` (an "HH:MM" string) is given, the session ended past the
    daily cutoff and an extra "why still working late?" box is shown; its text
    is returned under ``late_reason``.
    """
    result: list[dict | None] = [None]

    FORM_W = 460
    PAD    = 28
    AVAIL  = FORM_W - 2 * PAD

    root = tk.Tk()
    root.withdraw()
    root.title("Session Complete!")
    root.resizable(False, False)
    _card_theme(root)

    # ── Header (pinned) ───────────────────────────────────────────────────────
    header = tk.Frame(root, bg=C_CARD)
    header.pack(side=tk.TOP, fill=tk.X)
    tk.Frame(root, bg=C_BORDER, height=1).pack(side=tk.TOP, fill=tk.X)
    hdr_inner = tk.Frame(header, bg=C_CARD)
    hdr_inner.pack(fill=tk.X, padx=PAD, pady=(22, 18))
    badge = tk.Canvas(hdr_inner, width=44, height=44, bg=C_CARD, highlightthickness=0, bd=0)
    badge.create_oval(1, 1, 43, 43, fill=C_PRIMARY_SOFT, outline="")
    badge.create_line(13, 23, 19, 29, 31, 16, fill=C_PRIMARY, width=3,
                      capstyle=tk.ROUND, joinstyle=tk.ROUND)
    badge.pack(side=tk.LEFT)
    titles = tk.Frame(hdr_inner, bg=C_CARD)
    titles.pack(side=tk.LEFT, padx=(14, 0))
    _label(titles, "Session complete", size=FS_LG, bold=True).pack(anchor=tk.W)
    _label(
        titles, f"{duration_minutes} min · ended {datetime.datetime.now():%H:%M}",
        fg=C_INK_MUTED,
    ).pack(anchor=tk.W)

    # ── Footer (pinned) — packed before the scroll area so it keeps its space ─
    footer = tk.Frame(root, bg=C_CARD)
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    tk.Frame(root, bg=C_BORDER, height=1).pack(side=tk.BOTTOM, fill=tk.X)

    # The form can grow taller than the screen once both the distraction and
    # late-work notes are showing.  Host the fields in a scrollable canvas with
    # a capped height; the header and the Save button stay pinned outside it.
    outer = tk.Frame(root, bg=C_BG)
    outer.pack(fill=tk.BOTH, expand=True)
    _vsb = ttk.Scrollbar(outer, orient="vertical")
    _canvas = tk.Canvas(outer, bg=C_BG, highlightthickness=0, bd=0, yscrollcommand=_vsb.set)
    _vsb.config(command=_canvas.yview)
    _vsb.pack(side=tk.RIGHT, fill=tk.Y)
    _canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    frame = tk.Frame(_canvas, bg=C_BG, padx=PAD, pady=20)
    _frame_id = _canvas.create_window((0, 0), window=frame, anchor="nw")
    _canvas.bind("<Configure>", lambda e: _canvas.itemconfigure(_frame_id, width=e.width))
    frame.bind("<Configure>", lambda e: _canvas.configure(scrollregion=_canvas.bbox("all")))

    def _on_wheel(e: "tk.Event") -> None:
        # bind_all reaches every widget in the window, so ignore the event when
        # the cursor is over a text box (it scrolls itself — scrolling both at
        # once jiggles the form) and when the whole form already fits.
        w = root.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if isinstance(w, tk.Text):
                return
            w = w.master
        if frame.winfo_reqheight() > _canvas.winfo_height():
            steps = _wheel_steps(e)
            if steps:
                _canvas.yview_scroll(steps, "units")
    _canvas.bind_all("<MouseWheel>", _on_wheel)

    def _section(title: str) -> tuple[tk.Frame, tk.Frame]:
        """A labelled block in the form; returns (block, its heading row)."""
        sec = tk.Frame(frame, bg=C_BG)
        sec.pack(fill=tk.X, pady=(0, 18))
        head = tk.Frame(sec, bg=C_BG)
        head.pack(fill=tk.X, pady=(0, 8))
        _caption(head, title).pack(side=tk.LEFT)
        return sec, head

    # ── Distraction reminder ──────────────────────────────────────────────────
    if distractions:
        notice = _card(frame, bg=C_NOTICE_BG, border=C_NOTICE_BORDER)
        notice.pack(fill=tk.X, pady=(0, 18))
        n_in = tk.Frame(notice, bg=C_NOTICE_BG)
        n_in.pack(fill=tk.X, padx=14, pady=12)
        _label(n_in, "DISTRACTIONS TO FOLLOW UP ON", size=FS_XS, bold=True, fg=C_NOTICE_FG).pack(anchor=tk.W)
        _label(
            n_in, "\n".join(f"•  {d}" for d in distractions), fg=C_NOTICE_FG,
            justify=tk.LEFT, anchor="w", wraplength=AVAIL - 30,
        ).pack(anchor=tk.W, pady=(4, 0))

    def _chip_group(title: str, var: tk.StringVar, options: list[str],
                    noun: str, example: str) -> tk.Label:
        """Chips for the known values plus "+ New", which reveals a text box.

        Returns the section's (hidden) validation-error label.
        """
        sec, _ = _section(title)
        pills: dict[str, _Pill] = {}

        entry_box = tk.Frame(sec, bg=C_BG)
        entry = tk.Entry(entry_box, textvariable=var, **_text_field_opts())
        entry.pack(fill=tk.X, ipady=5)
        error_lbl = _label(sec, f"⚠  Please choose or enter a {noun} before saving.", fg=C_PRIMARY_INK)

        def _new() -> None:
            if var.get() in pills:
                var.set("")
            if not entry_box.winfo_ismapped():
                entry_box.pack(fill=tk.X, pady=(8, 0), before=error_lbl if error_lbl.winfo_ismapped() else None)
                _resize_to_fit()
            entry.focus_set()

        if options:
            chips = tk.Frame(sec, bg=C_BG)
            chips.pack(fill=tk.X)
            rows = _flow_rows(chips, [*options, f"+ New {noun}"], AVAIL)
            for i, (row, text) in enumerate(rows):
                if i == len(options):
                    _Pill(row, text, _new, style="add").pack(side=tk.LEFT)
                else:
                    pill = _Pill(row, text, lambda t=text: var.set(t))
                    pill.pack(side=tk.LEFT, padx=(0, 6))
                    pills[text] = pill
            if var.get() and var.get() not in pills:
                entry_box.pack(fill=tk.X, pady=(8, 0))
        else:
            entry_box.pack(fill=tk.X)
            _label(entry_box, example, size=FS_XS, fg=C_INK_MUTED).pack(anchor=tk.W, pady=(4, 0))

        def _sync(*_: object) -> None:
            cur = var.get()
            for t, pill in pills.items():
                pill.set_style("chip_on" if cur == t else "chip")
            if cur.strip():
                error_lbl.pack_forget()

        var.trace_add("write", _sync)
        _sync()
        return error_lbl

    # ── Term ──────────────────────────────────────────────────────────────────
    term_var = tk.StringVar(value=db.get_last_term() or "")
    term_error_lbl = _chip_group(
        "Term", term_var, db.get_all_terms(), "term",
        "e.g.  Spring 2025 · Autumn 2025 · Summer",
    )

    # ── Topic ─────────────────────────────────────────────────────────────────
    topic_var = tk.StringVar()
    error_lbl = _chip_group(
        "Topic / Project", topic_var, db.get_all_topics(), "topic",
        "e.g.  Math homework · Work report · Reading",
    )

    # ── Focus rating ──────────────────────────────────────────────────────────
    focus_sec, focus_head = _section("How focused were you?")

    _summary = db.get_summary()
    _avg = _summary.get("avg_focus")
    default_focus = int(max(1, min(10, round(_avg))) if _avg else 7)
    focus_var = tk.IntVar(value=default_focus)

    desc_lbl = _label(focus_head, "", bold=True, fg=C_PRIMARY_INK)
    desc_lbl.pack(side=tk.RIGHT)

    focus_grid = tk.Frame(focus_sec, bg=C_BG)
    focus_grid.pack(fill=tk.X)
    focus_cells: list[_Pill] = []

    def _nudge(step: int) -> str:
        focus_var.set(max(1, min(10, focus_var.get() + step)))
        focus_cells[focus_var.get() - 1].focus_set()
        return "break"

    for i in range(10):
        focus_grid.columnconfigure(i, weight=1, uniform="focus")
        cell = _Pill(focus_grid, str(i + 1), lambda v=i + 1: focus_var.set(v), padx=0, pady=8)
        cell.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0))
        cell.bind("<Left>",  lambda _: _nudge(-1))
        cell.bind("<Right>", lambda _: _nudge(+1))
        focus_cells.append(cell)

    ends = tk.Frame(focus_sec, bg=C_BG)
    ends.pack(fill=tk.X, pady=(6, 0))
    _label(ends, "Terrible", size=FS_XS, fg=C_INK_MUTED).pack(side=tk.LEFT)
    _label(ends, "Perfect", size=FS_XS, fg=C_INK_MUTED).pack(side=tk.RIGHT)

    def _on_focus(*_: object) -> None:
        v = focus_var.get()
        desc_lbl.config(text=f"{v} · {_focus_descriptor(v)}")
        for i, cell in enumerate(focus_cells):
            cell.set_style("chip_on" if i + 1 == v else "chip")

    focus_var.trace_add("write", _on_focus)
    _on_focus()

    # ── Distraction ───────────────────────────────────────────────────────────
    distract_sec, _ = _section("Distractions")
    distract_card = _card(distract_sec)
    distract_card.pack(fill=tk.X)
    distract_frame = tk.Frame(distract_card, bg=C_CARD)
    distract_frame.pack(fill=tk.X, padx=14, pady=12)

    distracted_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        distract_frame,
        text="I got distracted during this session",
        variable=distracted_var,
        style="Card.TCheckbutton",
    ).pack(anchor=tk.W)

    reason_container = tk.Frame(distract_frame, bg=C_CARD)
    _label(reason_container, "What distracted you?", fg=C_INK_MUTED).pack(anchor=tk.W)
    reason_text = tk.Text(
        reason_container, height=3, width=1, wrap=tk.WORD, padx=8, pady=6,
        **_text_field_opts(),
    )
    reason_text.pack(fill=tk.X, pady=(4, 0))

    _centered = [False]

    def _resize_to_fit() -> None:
        root.update_idletasks()
        chrome = header.winfo_reqheight() + footer.winfo_reqheight() + 2   # + hairlines
        req_h = frame.winfo_reqheight() + chrome
        max_h = int(root.winfo_screenheight() * 0.85)
        win_h = min(req_h, max_h)          # cap so the window never exceeds the screen
        if req_h > max_h:
            _vsb.pack(side=tk.RIGHT, fill=tk.Y, before=_canvas)
            win_w = FORM_W + (_vsb.winfo_reqwidth() or 16)
        else:
            _vsb.pack_forget()             # no overflow — don't reserve a scrollbar
            win_w = FORM_W
        if _centered[0]:
            # Keep the window where the user put it; just resize, clamping the
            # bottom edge back onto the screen if growth would push it off.
            x, y = root.winfo_x(), root.winfo_y()
            y = max(0, min(y, root.winfo_screenheight() - win_h))
            root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        else:
            root.geometry(f"{win_w}x{win_h}")
            _center_window(root)
            _centered[0] = True
        root.update_idletasks()
        _canvas.configure(scrollregion=_canvas.bbox("all"))

    def _toggle_reason(*_: object) -> None:
        if distracted_var.get():
            reason_container.pack(fill=tk.X, pady=(10, 0))
        else:
            reason_container.pack_forget()
        _resize_to_fit()

    distracted_var.trace_add("write", _toggle_reason)

    # ── Working late (past the daily cutoff) ──────────────────────────────────
    late_text = None
    late_error_lbl = None
    if late_cutoff:
        late_card = _card(frame, bg=C_PRIMARY_SOFT, border="#f2c9c2")
        late_card.pack(fill=tk.X, pady=(0, 18))
        late_inner = tk.Frame(late_card, bg=C_PRIMARY_SOFT)
        late_inner.pack(fill=tk.X, padx=14, pady=12)
        _label(
            late_inner, f"It's past {late_cutoff} — what kept you working late?",
            bold=True, fg=C_PRIMARY_INK, wraplength=AVAIL - 30, justify=tk.LEFT,
        ).pack(anchor=tk.W)
        _label(
            late_inner, "You'll see this note when your next study day begins. (Required)",
            size=FS_XS, fg=C_PRIMARY_INK, wraplength=AVAIL - 30, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(2, 8))
        late_text = tk.Text(
            late_inner, height=3, width=1, wrap=tk.WORD, padx=8, pady=6,
            **_text_field_opts(),
        )
        late_text.pack(fill=tk.X)
        late_error_lbl = _label(late_inner, "⚠  Please add a note before saving.",
                                size=FS_XS, fg=C_PRIMARY_INK)

    # ── Buttons ───────────────────────────────────────────────────────────────
    def _submit() -> None:
        term = term_var.get().strip()
        if not term:
            term_error_lbl.pack(anchor=tk.W, pady=(6, 0))
            _resize_to_fit()
            return
        topic = topic_var.get().strip()
        if not topic:
            error_lbl.pack(anchor=tk.W, pady=(6, 0))
            _resize_to_fit()
            return
        late_reason = late_text.get("1.0", tk.END).strip() if late_text is not None else None
        if late_text is not None and not late_reason:
            late_error_lbl.pack(anchor=tk.W, pady=(4, 0))
            _resize_to_fit()
            return
        result[0] = {
            "focus": max(1, min(10, focus_var.get())),
            "topic": topic,
            "term":  term,
            "distracted": distracted_var.get(),
            "reason": (
                reason_text.get("1.0", tk.END).strip() or None
                if distracted_var.get()
                else None
            ),
            "late_reason": late_reason,
        }
        root.quit()

    def _skip() -> None:
        root.quit()

    def _confirm_discard() -> None:
        # Guard the accidental-discard paths (Escape / window close): a finished
        # session is real study time, so require an explicit confirmation before
        # throwing it away.  Default is "No" so a second stray keypress keeps it.
        if messagebox.askyesno(
            "Discard session?",
            "This finished session hasn't been logged yet.\n\n"
            "Discard it without saving?",
            parent=root,
            default=messagebox.NO,
            icon=messagebox.WARNING,
        ):
            root.quit()
        # otherwise stay in the form so the session can still be saved

    btn_frame = tk.Frame(footer, bg=C_CARD)
    btn_frame.pack(fill=tk.X, padx=PAD, pady=(14, 18))
    _Pill(btn_frame, "Skip, don't log", _skip, style="quiet", padx=4, pady=9).pack(side=tk.LEFT)
    _Pill(btn_frame, "Save session", _submit, style="primary", size=FS_MD, padx=22, pady=8).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", _confirm_discard)
    root.bind("<Escape>", lambda _: _confirm_discard())

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
        _bind_wheel_yscroll(tree)

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
        stats_tab = ttk.Frame(nb)
        nb.add(stats_tab, text="  Statistics  ")
        stats_body = tk.Frame(stats_tab, bg=C_BG, padx=20, pady=18)
        stats_body.pack(fill=tk.BOTH, expand=True)

        total_s   = summary.get("total_sessions") or 0
        total_min = summary.get("total_minutes")  or 0
        avg_focus = summary.get("avg_focus")
        total_h   = f"{total_min // 60}h {total_min % 60}m" if total_min else "0m"

        tiles = tk.Frame(stats_body, bg=C_BG)
        tiles.pack(fill=tk.X)
        for i, (cap, value, unit) in enumerate((
            ("Sessions",      str(total_s),                                  ""),
            ("Focus time",    total_h,                                       ""),
            ("Average focus", str(avg_focus) if avg_focus is not None else "–", "/ 10"),
        )):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            tile = _card(tiles)
            tile.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 12, 0))
            t_in = tk.Frame(tile, bg=C_CARD)
            t_in.pack(fill=tk.X, padx=18, pady=14)
            _caption(t_in, cap).pack(anchor=tk.W)
            t_val = tk.Frame(t_in, bg=C_CARD)
            t_val.pack(anchor=tk.W)
            _label(t_val, value, size=FS_XL, bold=True).pack(side=tk.LEFT)
            if unit:
                _label(t_val, unit, size=FS_MD, fg=C_INK_MUTED).pack(
                    side=tk.LEFT, anchor="s", padx=(4, 0), pady=(0, 8))

        bar_cols = tk.Frame(stats_body, bg=C_BG)
        bar_cols.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        bar_cols.rowconfigure(0, weight=1)

        def _bar_card(col: int, title: str, legend: str) -> tk.Frame:
            """A titled card whose row list scrolls once it outgrows the card."""
            bar_cols.columnconfigure(col, weight=1, uniform="barcol")
            card = _card(bar_cols)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 12, 0))
            head = tk.Frame(card, bg=C_CARD)
            head.pack(fill=tk.X, padx=18, pady=(16, 12))
            _label(head, title, size=FS_MD, bold=True).pack(side=tk.LEFT)
            _label(head, legend, size=FS_XS, fg=C_INK_MUTED).pack(side=tk.RIGHT)

            holder = tk.Frame(card, bg=C_CARD)
            holder.pack(fill=tk.BOTH, expand=True, padx=(18, 8), pady=(0, 12))
            cv = tk.Canvas(holder, bg=C_CARD, highlightthickness=0, bd=0, width=1, height=1)
            sb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
            cv.configure(yscrollcommand=sb.set)
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            body = tk.Frame(cv, bg=C_CARD)
            body_id = cv.create_window((0, 0), window=body, anchor="nw")

            def _fit(_: object = None) -> None:
                cv.itemconfigure(body_id, width=cv.winfo_width())
                cv.configure(scrollregion=(0, 0, cv.winfo_width(), body.winfo_reqheight()))
                if body.winfo_reqheight() > cv.winfo_height() > 1:
                    if not sb.winfo_ismapped():
                        sb.pack(side=tk.RIGHT, fill=tk.Y)
                elif sb.winfo_ismapped():
                    sb.pack_forget()

            cv.bind("<Configure>", _fit)
            body.bind("<Configure>", _fit)
            body._scroll_canvas = cv   # read by _bar_row for wheel scrolling
            _bind_wheel_yscroll_to(cv, cv)
            _bind_wheel_yscroll_to(body, cv)
            return body

        def _bar_row(body: tk.Frame, label: str, value: float, value_text: str,
                     color: str, dot: bool = False) -> None:
            """Label and value on one line, a full-width 0–10 bar beneath."""
            row = tk.Frame(body, bg=C_CARD)
            row.pack(fill=tk.X, pady=(0, 14))
            line = tk.Frame(row, bg=C_CARD)
            line.pack(fill=tk.X)
            if dot:
                d = tk.Canvas(line, width=10, height=10, bg=C_CARD, highlightthickness=0, bd=0)
                d.create_oval(0, 0, 9, 9, fill=color, outline="")
                d.pack(side=tk.LEFT, padx=(0, 8))
            short = label if len(label) <= 28 else label[:27] + "…"
            _label(line, value_text, fg=C_TEXT_2).pack(side=tk.RIGHT)
            _label(line, short, fg=C_TEXT_2, anchor="w").pack(side=tk.LEFT)
            track = tk.Frame(row, bg=C_TRACK, height=8)
            track.pack(fill=tk.X, pady=(6, 0))
            tk.Frame(track, bg=color).place(relx=0, rely=0, relheight=1,
                                           relwidth=max(0.0, min(1.0, value / 10)))
            cv = body._scroll_canvas
            for w in (row, line, track, *line.winfo_children()):
                _bind_wheel_yscroll_to(w, cv)

        def _empty(body: tk.Frame) -> None:
            _label(body, "No rated sessions yet.", fg=C_INK_MUTED).pack(anchor=tk.W)

        tod_body = _bar_card(0, "Focus by time of day", "avg · sessions")
        tod_rows = db.get_stats_by_time_of_day(tf)
        for row in tod_rows:
            period = row["period"].split(" ", 1)[-1]   # drop the emoji prefix
            _bar_row(tod_body, period, row["avg_focus"],
                     f"{row['avg_focus']} · {row['sessions']}", C_PRIMARY)
        if not tod_rows:
            _empty(tod_body)

        # Same colour per topic as the Daily Chart tab, which colours the
        # sorted set of topics in that chart's data.
        hist_data   = db.get_daily_by_topic(tf)
        _chart_tops = sorted({r["topic"] for r in hist_data})
        _top_color  = dict(zip(_chart_tops, _topic_palette(len(_chart_tops))))

        top_body = _bar_card(1, "Focus by topic", "avg · total time")
        top_rows = db.get_stats_by_topic(tf)
        for row in top_rows:
            mins = row["total_min"] or 0
            _bar_row(top_body, row["topic"], row["avg_focus"],
                     f"{row['avg_focus']} · {mins // 60}h {mins % 60:02d}m",
                     _top_color.get(row["topic"], C_INK_MUTED), dot=True)
        if not top_rows:
            _empty(top_body)

        btn_bar = tk.Frame(stats_body, bg=C_BG)
        btn_bar.pack(fill=tk.X, pady=(14, 0))
        _Pill(btn_bar, "↺  Refresh", _rebuild, style="secondary", padx=16, pady=7).pack(side=tk.LEFT)
        _Pill(btn_bar, "Close", root.destroy, style="secondary", padx=16, pady=7).pack(side=tk.RIGHT)

        # ── Tab 3: Daily Histogram ────────────────────────────────────────────
        hist_tab = ttk.Frame(nb)
        nb.add(hist_tab, text="  Daily Chart  ")

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

            # Every calendar day between the first and last session, so days
            # off show up as gaps rather than being silently closed up.
            _worked     = sorted(day_topic.keys())
            _first      = datetime.date.fromisoformat(_worked[0])
            _last       = datetime.date.fromisoformat(_worked[-1])
            hist_days   = [(_first + datetime.timedelta(days=_i)).isoformat()
                           for _i in range((_last - _first).days + 1)]
            hist_topics = sorted(all_topics_set)

            def _day_avg_focus(day: str) -> float | None:
                total_m, weighted = 0.0, 0.0
                for _total_m, _af, _s in day_topic.get(day, {}).values():
                    if _af is not None:
                        weighted += _af * _total_m
                        total_m  += _total_m
                return round(weighted / total_m, 1) if total_m else None

            topic_color = dict(zip(hist_topics, _topic_palette(len(hist_topics))))
            _topic_idx  = {t: i for i, t in enumerate(hist_topics)}

            ML, MR, MT, MB = 58, 24, 48, 56
            BW, BG = 52, 18
            CH     = 260
            SEG_LABEL_MIN_H = 22
            SEG_MUTED, SEG_MUTED_FG = "#e2e2e2", "#cfcfcf"

            _max_min = max(sum(v[0] for v in day_topic[d].values()) for d in _worked)
            _max_h   = _max_min / 60.0
            _y_max   = max(0.5, math.ceil(_max_h * 2) / 2)
            _canvas_w = ML + MR + len(hist_days) * (BW + BG)
            _canvas_h = MT + CH + MB

            def _min_to_y(minutes: float) -> int:
                return MT + CH - int(CH * minutes / (_y_max * 60))

            hist_btn_bar = ttk.Frame(hist_tab)
            hist_btn_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 6))
            ttk.Button(hist_btn_bar, text="Close", command=root.destroy).pack(side=tk.RIGHT)

            # Legend flows onto as many rows as the window width needs, so no
            # module label is ever clipped off the right edge.  Clicking an
            # entry isolates that module in the chart above.
            _leg_bg   = ttk.Style().lookup("TFrame", "background") or "#ffffff"
            _leg_font = tkfont.Font(family="", size=11)
            _LEG_ROW_H, _LEG_GAP = 20, 18
            leg_cv = tk.Canvas(hist_tab, bg=_leg_bg, highlightthickness=0,
                               height=_LEG_ROW_H + 4, cursor="hand2")
            leg_cv.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 4))
            _leg_grey   = int(sum(c / 257 for c in leg_cv.winfo_rgb(_leg_bg)) / 3)
            _leg_fg     = _readable_fg(leg_cv, _leg_bg)
            _leg_fg_off = _dimmed(_leg_fg, 0.5, _leg_grey)
            _leg_last_w = [0]
            _selected: set[str] = set()   # empty == show every module

            def _draw_legend(_evt=None, force: bool = False) -> None:
                _w = leg_cv.winfo_width()
                if _w <= 1 or (_w == _leg_last_w[0] and not force):
                    return
                _leg_last_w[0] = _w
                leg_cv.delete("all")
                _x, _y, _rows = 0, _LEG_ROW_H // 2, 1
                for _i, _t in enumerate(hist_topics):
                    _iw = 12 + 5 + _leg_font.measure(_t) + _LEG_GAP
                    if _x and _x + _iw > _w:
                        _x, _y, _rows = 0, _y + _LEG_ROW_H, _rows + 1
                    _on = (not _selected) or _t in _selected
                    # Invisible hit target so the gap between swatch and label
                    # is clickable too.
                    leg_cv.create_rectangle(_x, _y - 9, _x + _iw - _LEG_GAP + 4, _y + 9,
                                            fill=_leg_bg, outline="", tags=(f"leg{_i}",))
                    leg_cv.create_rectangle(
                        _x, _y - 6, _x + 12, _y + 6, outline="",
                        fill=(topic_color[_t] if _on
                              else _dimmed(topic_color[_t], 0.6, _leg_grey)),
                        tags=(f"leg{_i}",))
                    leg_cv.create_text(_x + 17, _y, text=_t, anchor="w",
                                       font=_leg_font,
                                       fill=_leg_fg if _on else _leg_fg_off,
                                       tags=(f"leg{_i}",))
                    _x += _iw
                leg_cv.configure(height=_rows * _LEG_ROW_H + 4)

            leg_cv.bind("<Configure>", _draw_legend)

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
            _bind_canvas_hscroll(cv)

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
                _day_data = day_topic.get(_day, {})
                _total_m  = sum(v[0] for v in _day_data.values())
                _yc       = MT + CH

                for _tp in hist_topics:
                    if _tp not in _day_data:
                        continue
                    _seg_m, _seg_af, _ = _day_data[_tp]
                    _bh = max(1, int(CH * _seg_m / (_y_max * 60)))
                    _yt = _yc - _bh
                    cv.create_rectangle(_x0, _yt, _x1, _yc, fill=topic_color[_tp],
                                        outline="white", width=1,
                                        tags=(f"seg{_topic_idx[_tp]}",))
                    if _seg_af is not None and _bh >= SEG_LABEL_MIN_H:
                        cv.create_text((_x0 + _x1) / 2, (_yt + _yc) / 2,
                                       text=f"{_seg_af:.1f}", font=("", 10, "bold"),
                                       fill=_readable_fg(cv, topic_color[_tp]),
                                       anchor="center",
                                       tags=(f"segtxt{_topic_idx[_tp]}",))
                    _yc = _yt

                _daf = _day_avg_focus(_day)
                if _daf is not None:
                    cv.create_text(_cx, _yc - 4, text=f"★ {_daf:.1f}",
                                   anchor="s", font=("", 10), fill="#555")
                    _yc -= 16

                if _total_m:
                    _th = _total_m / 60
                    cv.create_text(_cx, _yc - 2,
                                   text=f"{_th:.1f}h" if _th >= 0.1 else f"{_total_m}m",
                                   anchor="s", font=("", 11, "bold"), fill="#222")
                # angle rotates counterclockwise; NE anchor makes the label
                # slant down-left below the axis instead of up into the bars
                cv.create_text(_x0 + BW // 2, MT + CH + 6, text=_day[5:],
                               anchor="ne", font=("", 10), angle=45,
                               fill="#555" if _total_m else "#b4b4b4")

            def _apply_highlight() -> None:
                """Repaint segments: selected modules keep their colour, every
                other one drops to a single flat grey so the selection is the
                only thing with colour.  Empty selection == show everything."""
                for _i, _t in enumerate(hist_topics):
                    _on = (not _selected) or _t in _selected
                    cv.itemconfigure(f"seg{_i}",
                                     fill=topic_color[_t] if _on else SEG_MUTED)
                    cv.itemconfigure(f"segtxt{_i}",
                                     fill=_readable_fg(cv, topic_color[_t]) if _on
                                     else SEG_MUTED_FG)
                _draw_legend(force=True)

            def _on_legend_click(evt: tk.Event) -> None:
                for _item in leg_cv.find_overlapping(evt.x, evt.y, evt.x, evt.y):
                    for _tag in leg_cv.gettags(_item):
                        if _tag.startswith("leg"):
                            _t = hist_topics[int(_tag[3:])]
                            _selected.symmetric_difference_update({_t})
                            if len(_selected) == len(hist_topics):
                                _selected.clear()   # all on == none filtered
                            _apply_highlight()
                            return
                if _selected:            # click on blank legend space resets
                    _selected.clear()
                    _apply_highlight()

            leg_cv.bind("<Button-1>", _on_legend_click)

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
            _bind_wheel_yscroll(w_tree)

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
            _bind_canvas_hscroll(cv_hour)

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
            _bind_canvas_hscroll(cv_daily)

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
                cv_daily.create_text(cx, D_MT + D_CH + 6, text=lbl,
                                     anchor="ne", font=("", 9), fill="#555", angle=45)
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
            _bind_canvas_hscroll(cv_trend)

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
                cv_trend.create_text(cx, T_MT + T_CH + 6, text=week[5:],
                                     anchor="ne", font=("", 9), fill="#555", angle=45)
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


# ─── App blocker: warning dialog ──────────────────────────────────────────────

def show_app_warning_dialog(app_name: str) -> None:
    """Topmost warning shown when a distracting app is detected — quits it and auto-dismisses."""
    import subprocess
    import threading

    def _quit_app() -> None:
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "{app_name}" to quit'],
                timeout=5, check=False,
            )
        except Exception:
            pass

    root = tk.Tk()
    root.withdraw()
    root.title("Stay Focused!")
    root.geometry("380x190")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    frame = ttk.Frame(root, padding=28)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="🚫  Distracting App Closed", font=("", FS_MD, "bold")).pack(pady=(0, 10))
    ttk.Label(
        frame,
        text=f"{app_name} has been closed.\nStay focused on your session!",
        font=("", FS_SM),
        justify=tk.CENTER,
    ).pack(pady=(0, 20))

    def _dismiss() -> None:
        root.quit()

    ttk.Button(frame, text="OK", command=_dismiss).pack()

    root.protocol("WM_DELETE_WINDOW", _dismiss)
    root.bind("<Return>", lambda _: _dismiss())
    root.bind("<Escape>", lambda _: _dismiss())

    def _quit_then_close() -> None:
        _quit_app()
        root.after(0, _dismiss)

    root.after(100, lambda: threading.Thread(target=_quit_then_close, daemon=True).start())

    root.mainloop()
    root.destroy()


# ─── App blocker: settings window ────────────────────────────────────────────

def show_app_blocker_settings() -> dict | None:
    """
    Settings window for the app blocking feature.
    Returns {"enabled": bool, "apps": [str, ...]} or None if cancelled.
    """
    import config as _cfg

    current_enabled = _cfg.is_app_blocking_enabled()
    current_apps    = _cfg.get_blocked_apps()

    result: list[dict | None] = [None]

    root = tk.Tk()
    root.withdraw()
    root.title("App Blocker")
    root.geometry("400x440")
    root.resizable(False, False)
    _theme(root)
    _bring_to_front(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="🚫  App Blocker", font=("", FS_MD, "bold")).pack(pady=(0, 4))
    ttk.Label(
        frame,
        text="Show a warning when these apps are open\nduring a focus session.",
        font=("", FS_SM),
        foreground=C_MUTED,
        justify=tk.CENTER,
    ).pack(pady=(0, 12))

    enabled_var = tk.BooleanVar(value=current_enabled)
    ttk.Checkbutton(frame, text="Enable app blocking warnings", variable=enabled_var).pack(anchor=tk.W)

    _section_header(frame, "Blocked Apps")

    list_frame = ttk.Frame(frame)
    list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    vsb = ttk.Scrollbar(list_frame)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    apps_listbox = tk.Listbox(
        list_frame, yscrollcommand=vsb.set,
        font=("", FS_SM), selectmode=tk.SINGLE, height=8,
    )
    apps_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.config(command=apps_listbox.yview)

    for app in current_apps:
        apps_listbox.insert(tk.END, app)

    add_frame = ttk.Frame(frame)
    add_frame.pack(fill=tk.X, pady=(8, 0))

    new_app_var = tk.StringVar()
    new_entry = ttk.Entry(add_frame, textvariable=new_app_var, font=("", FS_SM))
    new_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

    def _add() -> None:
        name = new_app_var.get().strip()
        if name and name not in apps_listbox.get(0, tk.END):
            apps_listbox.insert(tk.END, name)
            new_app_var.set("")
        new_entry.focus_set()

    def _remove() -> None:
        sel = apps_listbox.curselection()
        if sel:
            apps_listbox.delete(sel[0])

    ttk.Button(add_frame, text="Add", command=_add).pack(side=tk.LEFT)
    ttk.Button(frame, text="Remove Selected", command=_remove).pack(anchor=tk.W, pady=(4, 0))

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(16, 0))

    def _save() -> None:
        result[0] = {
            "enabled": enabled_var.get(),
            "apps": list(apps_listbox.get(0, tk.END)),
        }
        root.quit()

    def _cancel() -> None:
        root.quit()

    ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="Save", command=_save).pack(side=tk.RIGHT, padx=6)

    new_entry.bind("<Return>", lambda _: _add())
    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.bind("<Escape>", lambda _: _cancel())

    root.mainloop()
    root.destroy()
    return result[0]


# ─── Schedule goals: morning greeting ─────────────────────────────────────────

def show_schedule_greeting(met: bool, headline: str, detail: str) -> None:
    """Output-only modal shown on the first session start of a new day.

    ``met`` picks the celebratory vs. encouraging styling; ``headline`` and
    ``detail`` are pre-composed by the caller (which owns the schedule config).
    """
    root = tk.Tk()
    root.withdraw()
    # The "morning" greeting fires on the day's FIRST session, whenever that is.
    hour = datetime.datetime.now().hour
    root.title(
        "Good morning!" if hour < 12
        else "Good afternoon!" if hour < 18
        else "Good evening!"
    )
    root.resizable(False, False)
    _theme(root)

    frame = ttk.Frame(root, padding=28)
    frame.pack(fill=tk.BOTH, expand=True)

    accent = "#2e7d32" if met else C_PRIMARY
    emoji  = "🎉" if met else "💪"

    ttk.Label(frame, text=emoji, font=("", 40)).pack(pady=(0, 6))
    tk.Label(
        frame, text=headline, font=("", FS_MD, "bold"),
        fg=accent, wraplength=360, justify=tk.CENTER,
    ).pack(pady=(0, 8))
    ttk.Label(
        frame, text=detail, font=("", FS_SM), foreground=C_MUTED,
        wraplength=360, justify=tk.CENTER,
    ).pack(pady=(0, 20))

    def _dismiss() -> None:
        root.quit()

    ttk.Button(frame, text="Let's go →", command=_dismiss).pack()

    root.protocol("WM_DELETE_WINDOW", _dismiss)
    root.bind("<Return>", lambda _: _dismiss())
    root.bind("<Escape>", lambda _: _dismiss())

    _bring_to_front(root)
    root.mainloop()
    root.destroy()


# ─── Schedule goals: late-start reason ────────────────────────────────────────

def show_late_start_form(start_by: str, started_at: str) -> str | None:
    """Required-reason prompt shown when the first session of the day starts
    after the start goal.  Returns the reason text, or None if dismissed.
    """
    result: list[str | None] = [None]

    root = tk.Tk()
    root.withdraw()
    root.title("Starting late")
    root.resizable(False, False)
    _theme(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        frame, text="⏰  Starting after your goal",
        fg=C_PRIMARY, font=("", FS_MD, "bold"),
    ).pack(anchor=tk.W)
    ttk.Label(
        frame,
        text=f"It's {started_at} — past your {start_by} start goal.\n"
             f"What held you up?",
        font=("", FS_SM), foreground=C_MUTED, justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(4, 2))
    ttk.Label(
        frame, text="You'll see this note when your next study day begins. (Required)",
        font=("", FS_XS), foreground=C_MUTED,
    ).pack(anchor=tk.W, pady=(0, 8))

    reason_text = tk.Text(
        frame, height=3, width=44, font=("", FS_SM), wrap=tk.WORD,
        relief="solid", borderwidth=1,
    )
    reason_text.pack(fill=tk.X)
    reason_text.focus_set()

    error_lbl = ttk.Label(
        frame, text="⚠  Please add a note before continuing.",
        foreground="red", font=("", FS_XS),
    )

    btn_frame = ttk.Frame(frame)

    def _submit() -> None:
        txt = reason_text.get("1.0", tk.END).strip()
        if not txt:
            error_lbl.pack(before=btn_frame, anchor=tk.W, pady=(6, 0))
            return
        result[0] = txt
        root.quit()

    def _confirm_discard() -> None:
        if messagebox.askyesno(
            "Skip note?",
            "Without a note this late start won't be recorded.\n\nSkip anyway?",
            parent=root, default=messagebox.NO, icon=messagebox.WARNING,
        ):
            root.quit()

    btn_frame.pack(fill=tk.X, pady=(14, 0))
    ttk.Button(btn_frame, text="Save note →", command=_submit).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", _confirm_discard)
    root.bind("<Escape>", lambda _: _confirm_discard())

    _bring_to_front(root)
    root.mainloop()
    root.destroy()
    return result[0]


# ─── Schedule goals: settings window ──────────────────────────────────────────

def show_schedule_settings() -> dict | None:
    """
    Settings window for the daily start/cutoff goals.
    Returns {"start_by": "HH:MM", "end_by": "HH:MM"} or None if cancelled.
    """
    import config as _cfg

    result: list[dict | None] = [None]

    root = tk.Tk()
    root.withdraw()
    root.title("Schedule Goals")
    root.resizable(False, False)
    _theme(root)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="🎯  Schedule Goals", font=("", FS_MD, "bold")).pack(pady=(0, 4))
    ttk.Label(
        frame,
        text="Set your daily working window. You'll be\nasked for a short note when you miss it.",
        font=("", FS_SM), foreground=C_MUTED, justify=tk.CENTER,
    ).pack(pady=(0, 14))

    def _split(hhmm: str) -> tuple[str, str]:
        h, m = hhmm.split(":")
        return h, m

    sh, sm = _split(_cfg.get_start_by())
    eh, em = _split(_cfg.get_end_by())

    start_h = tk.StringVar(value=sh)
    start_m = tk.StringVar(value=sm)
    end_h   = tk.StringVar(value=eh)
    end_m   = tk.StringVar(value=em)

    def _time_row(label: str, hvar: tk.StringVar, mvar: tk.StringVar) -> None:
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row, text=label, font=("", FS_SM), width=14).pack(side=tk.LEFT)
        tk.Spinbox(
            row, from_=0, to=23, wrap=True, width=3, format="%02.0f",
            textvariable=hvar, font=("", FS_SM), justify=tk.CENTER,
        ).pack(side=tk.LEFT)
        ttk.Label(row, text=":", font=("", FS_SM)).pack(side=tk.LEFT, padx=2)
        tk.Spinbox(
            row, from_=0, to=59, wrap=True, width=3, format="%02.0f", increment=5,
            textvariable=mvar, font=("", FS_SM), justify=tk.CENTER,
        ).pack(side=tk.LEFT)

    _time_row("Start work by", start_h, start_m)
    _time_row("Finish work by", end_h, end_m)

    error_lbl = ttk.Label(frame, text="", foreground="red", font=("", FS_XS))

    def _norm(hvar: tk.StringVar, mvar: tk.StringVar) -> str | None:
        try:
            h, m = int(hvar.get()), int(mvar.get())
        except ValueError:
            return None
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
        return None

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(14, 0))

    def _save() -> None:
        start_by = _norm(start_h, start_m)
        end_by   = _norm(end_h, end_m)
        if start_by is None or end_by is None:
            error_lbl.config(text="⚠  Please enter valid times.")
            error_lbl.pack(before=btn_frame, pady=(0, 6))
            return
        if end_by <= start_by:
            error_lbl.config(text="⚠  Finish time must be after start time.")
            error_lbl.pack(before=btn_frame, pady=(0, 6))
            return
        _cfg.save_schedule_goals(start_by, end_by)
        result[0] = {"start_by": start_by, "end_by": end_by}
        root.quit()

    def _cancel() -> None:
        root.quit()

    ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="Save", command=_save).pack(side=tk.RIGHT, padx=6)

    root.protocol("WM_DELETE_WINDOW", _cancel)
    root.bind("<Escape>", lambda _: _cancel())

    _bring_to_front(root)
    root.mainloop()
    root.destroy()
    return result[0]

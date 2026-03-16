"""
Full-screen tkinter touchpad / trackpad test — run as a subprocess by the
manual test runner.

Tests:
  - Drawing coverage across the pad surface (20×12 grid, ≥25% required)
  - Left click detection
  - Right click detection
  - Scroll detection

Exit codes:
  0  — Pass clicked (all criteria met)
  1  — Fail / Skip clicked, or window closed without completing
  2  — tkinter not available or no display server
"""

import platform
import sys

# ── Visual constants ────────────────────────────────────────────────────────

_BG = "#1a1a1a"
_FG = "#cccccc"
_ACCENT = "#2a5ab8"
_GREEN = "#1a6b1a"
_GREEN_H = "#228822"
_RED = "#8b1a1a"
_RED_H = "#a02020"
_GREY = "#3a3a3a"
_GREY_H = "#4a4a4a"
_PASS_DISABLED_BG = "#2a2a2a"
_PASS_ENABLED_BG = "#1a6b1a"
_PASS_HOVER_BG = "#228822"

_GRID_COLS = 20
_GRID_ROWS = 12
_COVERAGE_THRESHOLD = 25  # percent


# ── Main UI ──────────────────────────────────────────────────────────────────


def run_touchpad_test() -> bool:
    try:
        import tkinter as tk
    except ImportError:
        sys.exit(2)

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title("Touchpad / Trackpad Test")
    root.configure(bg=_BG)
    if platform.system() == "Darwin":
        root.attributes("-fullscreen", True)
        root.createcommand("::tk::mac::Fullscreen", lambda: None)
    else:
        root.attributes("-fullscreen", True)

    # ── State ────────────────────────────────────────────────────────────────
    left_clicks = [0]
    right_clicks = [0]
    scroll_total = [0]
    coverage_pct = [0]

    visited_cells: set[tuple[int, int]] = set()
    last_draw_pos: list[tuple[int, int] | None] = [None]

    # ── Helper: Label-based button ────────────────────────────────────────────
    def _make_btn(parent, text, bg, fg, command, hover_bg):
        lbl = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=("Courier", 13, "bold"),
            padx=28,
            pady=8,
            cursor="hand2",
        )
        lbl.bind("<Enter>", lambda e, w=lbl, c=hover_bg: w.configure(bg=c))
        lbl.bind("<Leave>", lambda e, w=lbl, c=bg: w.configure(bg=c))
        lbl.bind("<ButtonPress-1>", lambda e: command())
        return lbl

    # ── Top bar ───────────────────────────────────────────────────────────────
    topbar = tk.Frame(root, bg=_BG)
    topbar.pack(fill="x", padx=16, pady=(12, 0))

    tk.Label(
        topbar,
        text="Touchpad / Trackpad Test",
        bg=_BG,
        fg="#4a9eff",
        font=("Courier", 16, "bold"),
    ).pack(side="left")

    coverage_lbl = tk.Label(
        topbar, text="Coverage: 0%", bg=_BG, fg="#555", font=("Courier", 13, "bold")
    )
    coverage_lbl.pack(side="right")

    # Instruction line
    tk.Label(
        root,
        text="Draw across the pad surface. Left-click, right-click, and scroll in the zones.",
        bg=_BG,
        fg="#888",
        font=("Courier", 11),
    ).pack(fill="x", padx=16, pady=(4, 0))

    # ── Content area (packed after bottom bar so expand=True doesn't hide it) ─
    content = tk.Frame(root, bg=_BG)

    # Left: drawing canvas
    canvas = tk.Canvas(
        content,
        bg="#0d0d0d",
        cursor="crosshair",
        highlightthickness=1,
        highlightbackground="#333",
    )
    canvas.pack(side="left", fill="both", expand=True, padx=(0, 10))

    # Right: zone panels
    right_col = tk.Frame(content, bg=_BG, width=220)
    right_col.pack(side="right", fill="y")
    right_col.pack_propagate(False)

    # ── Zone panel factory ────────────────────────────────────────────────────
    def _make_zone(parent, title_text):
        """Return (frame, count_label, status_label)."""
        frame = tk.Frame(parent, bg="#111111", highlightthickness=1, highlightbackground="#2a2a2a")
        frame.pack(fill="x", pady=(0, 8))

        tk.Label(
            frame,
            text=title_text,
            bg="#111111",
            fg="#888",
            font=("Courier", 10, "bold"),
            justify="center",
        ).pack(pady=(10, 0))

        count_lbl = tk.Label(frame, text="0", bg="#111111", fg="#555", font=("Courier", 28, "bold"))
        count_lbl.pack()

        status_lbl = tk.Label(
            frame, text="waiting...", bg="#111111", fg="#555", font=("Courier", 10)
        )
        status_lbl.pack(pady=(0, 10))

        return frame, count_lbl, status_lbl

    lc_frame, lc_count, lc_status = _make_zone(right_col, "LEFT CLICK\nclick here")
    rc_frame, rc_count, rc_status = _make_zone(right_col, "RIGHT CLICK\nright-click here")
    sc_frame, sc_count, sc_status = _make_zone(right_col, "SCROLL\nscroll here")

    # ── Pass / completion logic ───────────────────────────────────────────────
    result = ["fail"]  # "pass" | "fail" | "skip"

    def _do_done():
        result[0] = "pass"
        root.destroy()

    def _do_fail_btn():
        result[0] = "fail"
        root.destroy()

    def _do_skip_btn():
        result[0] = "skip"
        root.destroy()

    pass_unlocked = [False]

    def _check_pass_unlock():
        ok = (
            left_clicks[0] >= 1
            and right_clicks[0] >= 1
            and scroll_total[0] >= 1
            and coverage_pct[0] >= _COVERAGE_THRESHOLD
        )
        pass_unlocked[0] = ok
        if ok:
            pass_lbl.configure(bg=_PASS_ENABLED_BG, fg="white", cursor="hand2")
            pass_lbl.bind("<Enter>", lambda e: pass_lbl.configure(bg=_PASS_HOVER_BG))
            pass_lbl.bind("<Leave>", lambda e: pass_lbl.configure(bg=_PASS_ENABLED_BG))
            pass_lbl.bind("<ButtonPress-1>", lambda e: _do_done())
        else:
            pass_lbl.configure(bg=_PASS_DISABLED_BG, fg="#555", cursor="arrow")
            pass_lbl.unbind("<Enter>")
            pass_lbl.unbind("<Leave>")
            pass_lbl.unbind("<ButtonPress-1>")

    def _activate_zone(frame, count_lbl, status_lbl, count: int, ready_text: str):
        frame.configure(bg="#0d1f0d")
        for child in frame.winfo_children():
            try:
                child.configure(bg="#0d1f0d")
            except Exception:
                pass
        count_lbl.configure(text=str(count), fg="#2a8a2a")
        status_lbl.configure(text=ready_text, fg="#2a8a2a")

    # ── Coverage tracking ─────────────────────────────────────────────────────
    def _cell_for(x: int, y: int) -> tuple[int, int] | None:
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 0 or ch <= 0:
            return None
        col = int(x / cw * _GRID_COLS)
        row = int(y / ch * _GRID_ROWS)
        col = max(0, min(_GRID_COLS - 1, col))
        row = max(0, min(_GRID_ROWS - 1, row))
        return col, row

    def _update_coverage(x: int, y: int):
        cell = _cell_for(x, y)
        if cell is None:
            return
        if cell not in visited_cells:
            visited_cells.add(cell)
            total_cells = _GRID_COLS * _GRID_ROWS
            pct = int(len(visited_cells) / total_cells * 100)
            coverage_pct[0] = pct
            if pct >= _COVERAGE_THRESHOLD:
                coverage_lbl.configure(text=f"Coverage: {pct}%", fg=_GREEN)
            else:
                coverage_lbl.configure(text=f"Coverage: {pct}%", fg="#555")
            _check_pass_unlock()

    # ── Canvas event handlers ────────────────────────────────────────────────
    def _on_motion(event):
        x, y = event.x, event.y
        prev = last_draw_pos[0]
        if prev is not None:
            canvas.create_line(
                prev[0],
                prev[1],
                x,
                y,
                fill="#2a5ab8",
                width=2,
                capstyle="round",
            )
        last_draw_pos[0] = (x, y)
        _update_coverage(x, y)

    def _on_leave(event):
        last_draw_pos[0] = None

    canvas.bind("<B1-Motion>", _on_motion)
    canvas.bind("<Leave>", _on_leave)

    # ── Zone click / scroll handlers ──────────────────────────────────────────
    def _on_left_click(event):
        left_clicks[0] += 1
        _activate_zone(lc_frame, lc_count, lc_status, left_clicks[0], "detected")
        _check_pass_unlock()

    def _on_right_click(event):
        right_clicks[0] += 1
        _activate_zone(rc_frame, rc_count, rc_status, right_clicks[0], "detected")
        _check_pass_unlock()

    def _on_scroll(event):
        scroll_total[0] += 1
        _activate_zone(sc_frame, sc_count, sc_status, scroll_total[0], "detected")
        _check_pass_unlock()

    # Bind left-click zone (left click on canvas counts too, but zone panels
    # are the labelled areas).  We bind on all zone frame children for reliability.
    def _bind_zone_clicks(frame, left_handler=None, right_handler=None, scroll_handler=None):
        targets = [frame, *list(frame.winfo_children())]
        for w in targets:
            if left_handler:
                w.bind("<Button-1>", left_handler)
            if right_handler:
                w.bind("<Button-2>", right_handler)
                w.bind("<Button-3>", right_handler)
            if scroll_handler:
                w.bind("<MouseWheel>", scroll_handler)
                w.bind("<Button-4>", scroll_handler)
                w.bind("<Button-5>", scroll_handler)

    _bind_zone_clicks(lc_frame, left_handler=_on_left_click)
    _bind_zone_clicks(rc_frame, right_handler=_on_right_click)
    _bind_zone_clicks(sc_frame, scroll_handler=_on_scroll)

    # Also bind scroll on the scroll zone label directly for cursor feedback
    for child in sc_frame.winfo_children():
        child.configure(cursor="sb_v_double_arrow")
    sc_frame.configure(cursor="sb_v_double_arrow")

    # Set appropriate cursors on click zones
    for child in lc_frame.winfo_children():
        try:
            child.configure(cursor="hand2")
        except Exception:
            pass
    lc_frame.configure(cursor="hand2")
    for child in rc_frame.winfo_children():
        try:
            child.configure(cursor="hand2")
        except Exception:
            pass
    rc_frame.configure(cursor="hand2")

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bottom = tk.Frame(root, bg=_BG)
    bottom.pack(fill="x", pady=(4, 18))

    tk.Label(
        bottom,
        text="Complete all zones and reach 25% coverage to enable Pass.",
        bg=_BG,
        fg="#555",
        font=("Courier", 10),
    ).pack()

    btn_row = tk.Frame(bottom, bg=_BG)
    btn_row.pack(pady=(10, 0))

    def _do_clear():
        canvas.delete("all")
        visited_cells.clear()
        last_draw_pos[0] = None
        coverage_pct[0] = 0
        coverage_lbl.configure(text="Coverage: 0%", fg="#555")
        _check_pass_unlock()

    _make_btn(btn_row, "Clear", "#2a2a2a", "#888", _do_clear, "#3a3a3a").pack(side="left", padx=10)

    _make_btn(btn_row, "Fail", _RED, "white", _do_fail_btn, _RED_H).pack(side="left", padx=10)

    pass_lbl = tk.Label(
        btn_row,
        text="Pass",
        bg=_PASS_DISABLED_BG,
        fg="#555",
        font=("Courier", 13, "bold"),
        padx=28,
        pady=8,
        cursor="arrow",
    )
    pass_lbl.pack(side="left", padx=10)

    _make_btn(btn_row, "Skip", _GREY, "#aaa", _do_skip_btn, _GREY_H).pack(side="left", padx=10)

    # Pack content after bottom so the expanding canvas doesn't hide the buttons
    content.pack(fill="both", expand=True, padx=16, pady=8)

    # ── Initialise ────────────────────────────────────────────────────────────

    def _on_root_key(event):
        k = event.keysym.lower()
        if k == "p" and pass_unlocked[0]:
            _do_done()
        elif k == "f":
            _do_fail_btn()
        elif k == "s":
            _do_skip_btn()

    root.bind("<Key>", _on_root_key)
    root.focus_force()
    _check_pass_unlock()

    root.mainloop()
    return result[0]


if __name__ == "__main__":
    try:
        r = run_touchpad_test()
        sys.exit(0 if r == "pass" else (3 if r == "skip" else 1))
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)

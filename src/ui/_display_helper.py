"""
Full-screen tkinter colour-cycle — run as a subprocess by DisplayTestScreen.

Exit codes:
  0  — cycle completed (all colours shown)
  1  — user pressed ESC / closed the window early
  2  — tkinter not available or no display server
"""

import sys

_COLORS: list[tuple[str, str]] = [
    ("Black", "#000000"),
    ("White", "#FFFFFF"),
    ("Red", "#FF0000"),
    ("Green", "#00FF00"),
    ("Blue", "#0000FF"),
    ("Cyan", "#00FFFF"),
    ("Magenta", "#FF00FF"),
    ("Gray", "#7F7F7F"),
]
_N = len(_COLORS)

_INSTRUCTIONS = (
    "DISPLAY COLOUR TEST\n\n"
    f"The screen will cycle through {_N} solid colors.\n\n"
    "On each colour, look carefully for:\n\n"
    "  Dead pixels      — dots stuck at the wrong colour\n"
    "  Backlight bleed  — bright patches at screen edges\n"
    "                     (most visible on the black screen)\n"
    "  Colour uniformity— no dark or bright patches across the panel\n"
    "  Screen damage    — cracks or pressure marks\n\n"
    "Press any key or click anywhere to advance.\n"
    "Press ESC to end the cycle early."
)


_BG_DARK = "#0d0d0d"
_BG_BTN_F = "#8b1a1a"
_BG_BTN_P = "#1a6b1a"
_BG_BTN_S = "#3a3a3a"


def run_display_test() -> str:
    """Show full-screen colour cycle then Pass/Fail/Skip. Returns 'pass'/'fail'/'skip'."""
    try:
        import tkinter as tk
    except ImportError:
        sys.exit(2)

    result = ["skip"]
    phase = [-1]

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title("Display Test")
    root.attributes("-fullscreen", True)
    root.configure(bg=_BG_DARK, cursor="none")

    instr = tk.Label(
        root,
        text=_INSTRUCTIONS,
        bg=_BG_DARK,
        fg="#e0e0e0",
        font=("Courier", 14),
        justify="left",
    )
    instr.place(relx=0.5, rely=0.45, anchor="center")

    hint_var = tk.StringVar(value="  Press any key or click to begin   |   ESC to end cycle  ")
    hint = tk.Label(root, textvariable=hint_var, bg="#1a1a1a", fg="#cccccc", font=("Courier", 11))
    hint.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0)

    def _make_btn(parent, text, bg, command, hover_bg):
        lbl = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg="white",
            font=("Courier", 13, "bold"),
            padx=28,
            pady=10,
            cursor="hand2",
        )
        lbl.bind("<Enter>", lambda e, w=lbl, c=hover_bg: w.configure(bg=c))
        lbl.bind("<Leave>", lambda e, w=lbl, c=bg: w.configure(bg=c))
        lbl.bind("<ButtonPress-1>", lambda e: command())
        return lbl

    def _show_judgment(cycle_complete: bool):
        """Replace full-screen colour with dark background and Pass/Fail/Skip buttons."""
        root.unbind("<Key>")
        root.unbind("<Button-1>")
        root.configure(bg=_BG_DARK, cursor="")

        def _judgment_key(event):
            k = event.keysym.lower()
            if k == "p":
                _do("pass")
            elif k == "f":
                _do("fail")
            elif k == "s":
                _do("skip")

        root.bind("<Key>", _judgment_key)

        if instr.winfo_ismapped():
            instr.place_forget()

        msg = (
            "Colour cycle complete.\nDid the display pass all checks?"
            if cycle_complete
            else "Cycle ended early.\nReview what you observed and mark below."
        )
        tk.Label(
            root,
            text=msg,
            bg=_BG_DARK,
            fg="#cccccc",
            font=("Courier", 14),
            justify="center",
        ).place(relx=0.5, rely=0.4, anchor="center")

        btn_frame = tk.Frame(root, bg=_BG_DARK)
        btn_frame.place(relx=0.5, rely=0.6, anchor="center")

        def _do(r):
            result[0] = r
            root.destroy()

        _make_btn(btn_frame, "Fail", _BG_BTN_F, lambda: _do("fail"), "#a02020").pack(
            side="left", padx=14
        )
        _make_btn(btn_frame, "Pass", _BG_BTN_P, lambda: _do("pass"), "#228822").pack(
            side="left", padx=14
        )
        _make_btn(btn_frame, "Skip", _BG_BTN_S, lambda: _do("skip"), "#4a4a4a").pack(
            side="left", padx=14
        )

        hint_var.set("  Mark the result above  ")
        hint.configure(bg="#1a1a1a")

    def advance(_event=None):
        phase[0] += 1
        if phase[0] >= _N:
            _show_judgment(cycle_complete=True)
            return
        name, bg = _COLORS[phase[0]]
        root.configure(bg=bg)
        if instr.winfo_ismapped():
            instr.place_forget()
        hint.configure(bg="#1a1a1a")
        hint_var.set(
            f"  {name}   {phase[0] + 1} / {_N}   |   any key / click to advance   |   ESC to end  "
        )

    def on_key(event):
        if event.keysym == "Escape":
            _show_judgment(cycle_complete=False)
        else:
            advance()

    root.bind("<Key>", on_key)
    root.bind("<Button-1>", advance)
    root.focus_force()
    root.mainloop()
    return result[0]


if __name__ == "__main__":
    try:
        r = run_display_test()
        sys.exit(0 if r == "pass" else (3 if r == "skip" else 1))
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)

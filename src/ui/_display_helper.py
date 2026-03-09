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


def run_display_test() -> bool:
    """Show full-screen colour cycle. Returns True if completed, False if skipped."""
    try:
        import tkinter as tk
    except ImportError:
        sys.exit(2)

    completed = [False]
    phase = [-1]

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title("Display Test")
    root.attributes("-fullscreen", True)
    root.configure(bg="#0d0d0d", cursor="none")

    instr = tk.Label(
        root,
        text=_INSTRUCTIONS,
        bg="#0d0d0d",
        fg="#e0e0e0",
        font=("Courier", 14),
        justify="left",
    )
    instr.place(relx=0.5, rely=0.45, anchor="center")

    hint_var = tk.StringVar(value="  Press any key or click to begin   |   ESC to skip  ")
    hint = tk.Label(
        root,
        textvariable=hint_var,
        bg="#1a1a1a",
        fg="#cccccc",
        font=("Courier", 11),
    )
    hint.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0)

    def advance(_event=None):
        phase[0] += 1
        if phase[0] >= _N:
            completed[0] = True
            root.destroy()
            return
        name, bg = _COLORS[phase[0]]
        root.configure(bg=bg)
        if instr.winfo_ismapped():
            instr.place_forget()
        hint.configure(bg="#1a1a1a")
        hint_var.set(f"  {name}   {phase[0] + 1} / {_N}   |   any key / click to advance   |   ESC to end  ")

    def on_key(event):
        if event.keysym == "Escape":
            root.destroy()
        else:
            advance()

    root.bind("<Key>", on_key)
    root.bind("<Button-1>", advance)
    root.focus_force()
    root.mainloop()
    return completed[0]


if __name__ == "__main__":
    try:
        result = run_display_test()
        sys.exit(0 if result else 1)
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)

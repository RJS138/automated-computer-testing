"""
Full-screen tkinter HDMI / video-out test — run as a subprocess by the manual test runner.

Exit codes:
  0  — Pass clicked
  1  — Fail or Skip clicked / window closed
  2  — tkinter not available or no display server
"""

import json
import platform
import subprocess
import sys

# ── Visual constants ─────────────────────────────────────────────────────────

_BG = "#1a1a1a"
_FG = "#cccccc"
_ACCENT = "#2a5ab8"
_GREEN = "#1a6b1a"
_GREEN_H = "#228822"
_RED = "#8b1a1a"
_RED_H = "#a02020"
_GREY = "#3a3a3a"
_GREY_H = "#4a4a4a"
_NEW_BG = "#0d1f0d"

_COLOUR_TEST_BG = "#444466"
_COLOUR_TEST_BG_H = "#555577"

_CYCLE_COLOURS = [
    ("Black", "#000000"),
    ("White", "#ffffff"),
    ("Red", "#ff0000"),
    ("Green", "#00ff00"),
    ("Blue", "#0000ff"),
    ("Cyan", "#00ffff"),
    ("Magenta", "#ff00ff"),
    ("Grey", "#7f7f7f"),
]


# ── Display enumeration ──────────────────────────────────────────────────────


def _enumerate_displays() -> list[dict]:
    """Return list of dicts with keys: name, resolution, connection, status, key."""
    os_name = platform.system()
    displays: list[dict] = []

    if os_name == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                timeout=10,
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)
            for gpu in data.get("SPDisplaysDataType", []):
                for ndrvs in gpu.get("spdisplays_ndrvs", []):
                    name = ndrvs.get("_name", "Unknown Display").strip()
                    resolution = ndrvs.get("spdisplays_resolution", "").strip()
                    connection = ndrvs.get("spdisplays_connection_type", "").strip()
                    online_raw = ndrvs.get("spdisplays_online", "").strip().lower()
                    status = (
                        "connected" if online_raw in ("yes", "spdisplays_yes") else "disconnected"
                    )
                    key = f"{name}|{resolution}"
                    displays.append(
                        {
                            "name": name,
                            "resolution": resolution,
                            "connection": connection,
                            "status": status,
                            "key": key,
                        }
                    )
        except Exception:
            pass

    elif os_name == "Linux":
        try:
            out = subprocess.check_output(
                ["xrandr", "--query"], timeout=10, stderr=subprocess.DEVNULL
            )
            for line in out.decode("utf-8", errors="replace").splitlines():
                if " connected" in line or " disconnected" in line:
                    parts = line.split()
                    display_name = parts[0] if parts else "Unknown"
                    connected = " connected" in line
                    status = "connected" if connected else "disconnected"
                    resolution = ""
                    # Look for WxH+x+y pattern in the line
                    for part in parts:
                        if "x" in part and "+" in part:
                            resolution = part.split("+")[0]
                            break
                    displays.append(
                        {
                            "name": display_name,
                            "resolution": resolution,
                            "connection": "",
                            "status": status,
                            "key": display_name,
                        }
                    )
        except Exception:
            pass

    elif os_name == "Windows":
        try:
            ps_cmd = (
                "Get-WmiObject -Class Win32_DesktopMonitor | "
                "Select-Object Name,ScreenWidth,ScreenHeight | "
                "ConvertTo-Json"
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                timeout=15,
                stderr=subprocess.DEVNULL,
            )
            raw = json.loads(out.decode("utf-8", errors="replace"))
            if isinstance(raw, dict):
                raw = [raw]
            for entry in raw:
                name = (entry.get("Name") or "Unknown Monitor").strip()
                w = entry.get("ScreenWidth")
                h = entry.get("ScreenHeight")
                resolution = f"{w}×{h}" if w and h else ""
                displays.append(
                    {
                        "name": name,
                        "resolution": resolution,
                        "connection": "",
                        "status": "connected",
                        "key": name,
                    }
                )
        except Exception:
            pass

    return displays


# ── Main UI ──────────────────────────────────────────────────────────────────


def run_hdmi_test() -> bool:
    """Show full-screen HDMI/video-out test. Returns True if Pass clicked."""
    try:
        import tkinter as tk
    except ImportError:
        sys.exit(2)

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title("HDMI / Video Out Test")
    root.attributes("-fullscreen", True)
    root.configure(bg=_BG)

    result = [None]  # "pass" | "fail" | "skip"

    # State
    baseline_keys: set[str] = set()
    current_displays: list[dict] = []

    # ── Helper: label-based button ───────────────────────────────────────────

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

    # ── Actions ──────────────────────────────────────────────────────────────

    def _do_pass():
        result[0] = "pass"
        root.destroy()

    def _do_fail():
        result[0] = "fail"
        root.destroy()

    def _do_skip():
        result[0] = "skip"
        root.destroy()

    # ── Top bar ──────────────────────────────────────────────────────────────

    topbar = tk.Frame(root, bg=_BG)
    topbar.pack(fill="x", padx=16, pady=(12, 0))

    tk.Label(
        topbar,
        text="HDMI / Video Out Test",
        bg=_BG,
        fg="#4a9eff",
        font=("Courier", 16, "bold"),
    ).pack(side="left")

    count_var = tk.StringVar(value="")
    tk.Label(topbar, textvariable=count_var, bg=_BG, fg=_FG, font=("Courier", 11)).pack(
        side="right", padx=(0, 4)
    )

    # ── Instruction text ─────────────────────────────────────────────────────

    tk.Label(
        root,
        text=(
            "Connect an external monitor via HDMI / DisplayPort / USB-C, "
            "then click Refresh. Newly detected displays are highlighted in green."
        ),
        bg=_BG,
        fg="#888888",
        font=("Courier", 11),
        wraplength=900,
        justify="left",
    ).pack(anchor="w", padx=16, pady=(8, 0))

    # ── Display list area ────────────────────────────────────────────────────

    list_outer = tk.Frame(root, bg="#111111")

    # Header row
    header = tk.Frame(list_outer, bg=_BG)
    header.pack(fill="x", padx=0, pady=(0, 2))

    tk.Label(
        header,
        text="Display",
        bg=_BG,
        fg="#666666",
        font=("Courier", 10, "bold"),
        width=28,
        anchor="w",
    ).pack(side="left", padx=(8, 0))
    tk.Label(
        header,
        text="Resolution",
        bg=_BG,
        fg="#666666",
        font=("Courier", 10, "bold"),
        width=18,
        anchor="w",
    ).pack(side="left")
    tk.Label(
        header,
        text="Connection",
        bg=_BG,
        fg="#666666",
        font=("Courier", 10, "bold"),
        width=20,
        anchor="w",
    ).pack(side="left")
    tk.Label(
        header,
        text="Status",
        bg=_BG,
        fg="#666666",
        font=("Courier", 10, "bold"),
        width=14,
        anchor="w",
    ).pack(side="left")

    rows_frame = tk.Frame(list_outer, bg="#111111")
    rows_frame.pack(fill="both", expand=True, padx=4, pady=4)

    def _rebuild_rows():
        for w in rows_frame.winfo_children():
            w.destroy()

        if not current_displays:
            tk.Label(
                rows_frame,
                text="No displays detected.",
                bg="#111111",
                fg="#555555",
                font=("Courier", 11),
            ).pack(anchor="w", padx=8, pady=8)
            return

        for disp in current_displays:
            is_new = disp["key"] not in baseline_keys
            row_bg = _NEW_BG if is_new else "#111111"
            name_fg = "#1a9b1a" if is_new else _FG
            name_text = f"★ NEW  {disp['name']}" if is_new else f"       {disp['name']}"
            status_fg = "#1a9b1a" if disp["status"] == "connected" else "#555555"

            row = tk.Frame(rows_frame, bg=row_bg)
            row.pack(fill="x", padx=0, pady=1)

            tk.Label(
                row,
                text=name_text,
                bg=row_bg,
                fg=name_fg,
                font=("Courier", 11),
                width=28,
                anchor="w",
            ).pack(side="left", padx=(8, 0), pady=3)
            tk.Label(
                row,
                text=disp["resolution"] or "—",
                bg=row_bg,
                fg="#888888",
                font=("Courier", 11),
                width=18,
                anchor="w",
            ).pack(side="left", pady=3)
            tk.Label(
                row,
                text=disp["connection"] or "—",
                bg=row_bg,
                fg="#888888",
                font=("Courier", 11),
                width=20,
                anchor="w",
            ).pack(side="left", pady=3)
            tk.Label(
                row,
                text=disp["status"],
                bg=row_bg,
                fg=status_fg,
                font=("Courier", 11),
                width=14,
                anchor="w",
            ).pack(side="left", pady=3)

    def _update_count():
        total = len(current_displays)
        new_count = sum(1 for d in current_displays if d["key"] not in baseline_keys)
        if new_count > 0:
            count_var.set(f"{total} display(s) detected  •  {new_count} new")
        else:
            count_var.set(f"{total} display(s) detected")

    # ── Colour test window ───────────────────────────────────────────────────

    colour_win = [None]  # holds Toplevel reference

    def _open_colour_test():
        if colour_win[0] is not None:
            try:
                colour_win[0].lift()
                colour_win[0].focus_force()
                return
            except Exception:
                colour_win[0] = None

        win = tk.Toplevel(root)
        win.title("Colour Test — External Monitor")
        win.geometry("800x600")
        win.configure(bg="#000000")
        colour_win[0] = win

        phase = [-1]
        _N = len(_CYCLE_COLOURS)

        instr_lbl = tk.Label(
            win,
            text="Drag this window to the external monitor, then click to cycle colours.",
            bg="#000000",
            fg="#cccccc",
            font=("Courier", 12),
            wraplength=700,
        )
        instr_lbl.place(relx=0.5, rely=0.5, anchor="center")

        colour_lbl = tk.Label(
            win, text="", bg="#000000", fg="#cccccc", font=("Courier", 14, "bold")
        )
        colour_lbl.place(relx=0.5, rely=0.08, anchor="center")

        hint_lbl = tk.Label(
            win,
            text="Click or press any key to advance",
            bg="#1a1a1a",
            fg="#888888",
            font=("Courier", 10),
        )
        hint_lbl.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0)

        def _advance(_event=None):
            phase[0] += 1
            if phase[0] >= _N:
                phase[0] = 0
            name, bg = _CYCLE_COLOURS[phase[0]]
            win.configure(bg=bg)
            instr_lbl.place_forget()
            colour_lbl.configure(
                bg=bg,
                fg="#000000" if bg in ("#ffffff", "#00ff00", "#00ffff") else "#ffffff",
                text=f"{name}  ({phase[0] + 1}/{_N})",
            )
            hint_lbl.configure(bg=bg)
            colour_lbl.place(relx=0.5, rely=0.08, anchor="center")

        win.bind("<ButtonPress-1>", _advance)
        win.bind("<Key>", _advance)
        win.focus_force()

        def _on_close():
            colour_win[0] = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    # ── Scan logic ───────────────────────────────────────────────────────────

    colour_btn_holder = [None]  # Label widget, shown/hidden based on display count

    def _scan():
        current_displays.clear()
        current_displays.extend(_enumerate_displays())
        _rebuild_rows()
        _update_count()
        _refresh_colour_btn()

    def _refresh_colour_btn():
        # Show colour test button only when more than one display is detected
        if len(current_displays) > 1:
            if colour_btn_holder[0] is None:
                btn = _make_btn(
                    btn_row,
                    "Colour Test →",
                    _COLOUR_TEST_BG,
                    "white",
                    _open_colour_test,
                    _COLOUR_TEST_BG_H,
                )
                btn.pack(side="left", padx=10, before=fail_btn)
                colour_btn_holder[0] = btn
        else:
            if colour_btn_holder[0] is not None:
                colour_btn_holder[0].destroy()
                colour_btn_holder[0] = None

    def _set_baseline():
        devs = _enumerate_displays()
        for d in devs:
            baseline_keys.add(d["key"])
        _scan()

    # ── Bottom bar ───────────────────────────────────────────────────────────

    bottom = tk.Frame(root, bg=_BG)
    bottom.pack(fill="x", pady=(0, 18))

    tk.Label(
        bottom,
        text="Connect each output one at a time and click Refresh to detect new displays.",
        bg=_BG,
        fg="#555555",
        font=("Courier", 10),
    ).pack()

    btn_row = tk.Frame(bottom, bg=_BG)
    btn_row.pack(pady=(10, 0))

    _make_btn(btn_row, "Refresh", _ACCENT, "white", _scan, "#3a6acc").pack(side="left", padx=10)

    # Colour Test button inserted dynamically (before Fail)
    fail_btn = _make_btn(btn_row, "Fail", _RED, "white", _do_fail, _RED_H)
    fail_btn.pack(side="left", padx=10)

    _make_btn(btn_row, "Pass", _GREEN, "white", _do_pass, _GREEN_H).pack(side="left", padx=10)
    _make_btn(btn_row, "Skip", _GREY, _FG, _do_skip, _GREY_H).pack(side="left", padx=10)

    # Pack list_outer after bottom bar so expand=True doesn't hide the buttons
    list_outer.pack(fill="both", expand=True, padx=16, pady=10)

    def _on_root_key(event):
        k = event.keysym.lower()
        if k == "p":
            _do_pass()
        elif k == "f":
            _do_fail()
        elif k == "s":
            _do_skip()

    root.bind("<Key>", _on_root_key)
    root.protocol("WM_DELETE_WINDOW", _do_fail)
    root.focus_force()

    root.after(200, _set_baseline)

    root.mainloop()
    return result[0] or "fail"


if __name__ == "__main__":
    try:
        r = run_hdmi_test()
        sys.exit(0 if r == "pass" else (3 if r == "skip" else 1))
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)

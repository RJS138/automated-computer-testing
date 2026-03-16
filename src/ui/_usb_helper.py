"""
Full-screen tkinter USB port test — run as a subprocess by the manual test runner.

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


# ── USB enumeration ──────────────────────────────────────────────────────────


def _enumerate_usb() -> list[dict]:
    """Return list of dicts with keys: name, speed, key."""
    os_name = platform.system()
    devices: list[dict] = []

    if os_name == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPUSBDataType", "-json"],
                timeout=10,
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)

            def _walk(items):
                for item in items:
                    name = item.get("_name", "").strip()
                    manufacturer = item.get("manufacturer", "").strip()
                    speed = item.get("device_speed", "").strip()
                    if name:
                        key = f"{name}|{manufacturer}"
                        devices.append({"name": name, "speed": speed, "key": key})
                    # Recurse into sub-items
                    for sub_key in ("_items", "hubs", "devices"):
                        sub = item.get(sub_key)
                        if isinstance(sub, list):
                            _walk(sub)

            for top_key in ("SPUSBDataType",):
                top = data.get(top_key, [])
                for controller in top:
                    items = controller.get("_items", [])
                    _walk(items)
                    # Also walk the controller itself if it has a name
                    name = controller.get("_name", "").strip()
                    manufacturer = controller.get("manufacturer", "").strip()
                    speed = controller.get("device_speed", "").strip()
                    if name and name not in (
                        "USB 3.0 Bus",
                        "USB 2.0 Bus",
                        "USB31Bus",
                        "USB30Bus",
                        "USB Bus",
                        "AppleUSBHub",
                    ):
                        key = f"{name}|{manufacturer}"
                        devices.append({"name": name, "speed": speed, "key": key})

        except Exception:
            pass

    elif os_name == "Linux":
        try:
            out = subprocess.check_output(["lsusb"], timeout=10, stderr=subprocess.DEVNULL)
            for line in out.decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                # Format: Bus NNN Device NNN: ID xxxx:xxxx Description
                parts = line.split(":", 2)
                name = parts[2].strip() if len(parts) >= 3 else line
                # Skip root hubs
                if "root hub" in name.lower():
                    continue
                devices.append({"name": name, "speed": "", "key": line})
        except Exception:
            pass

    elif os_name == "Windows":
        try:
            ps_cmd = "Get-PnpDevice -Class USB | Select-Object FriendlyName,Status | ConvertTo-Json"
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                timeout=15,
                stderr=subprocess.DEVNULL,
            )
            raw = json.loads(out.decode("utf-8", errors="replace"))
            if isinstance(raw, dict):
                raw = [raw]
            for entry in raw:
                friendly = (entry.get("FriendlyName") or "").strip()
                if not friendly:
                    continue
                status = (entry.get("Status") or "").strip()
                devices.append({"name": friendly, "speed": status, "key": friendly})
        except Exception:
            pass

    return devices


# ── Main UI ──────────────────────────────────────────────────────────────────


def run_usb_test(port_type: str = "USB-A") -> bool:
    """Show full-screen USB port test. Returns True if Pass clicked, False otherwise."""
    try:
        import tkinter as tk
    except ImportError:
        sys.exit(2)

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title(f"{port_type} Port Test")
    root.attributes("-fullscreen", True)
    root.configure(bg=_BG)

    result = [None]  # "pass" | "fail" | "skip"

    # State
    baseline_keys: set[str] = set()
    current_devices: list[dict] = []

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
        text=f"{port_type} Port Test",
        bg=_BG,
        fg="#4a9eff",
        font=("Courier", 16, "bold"),
    ).pack(side="left")

    count_var = tk.StringVar(value="")
    tk.Label(topbar, textvariable=count_var, bg=_BG, fg=_FG, font=("Courier", 11)).pack(
        side="right", padx=(0, 4)
    )

    # ── Instruction text ─────────────────────────────────────────────────────

    instr_text = (
        f"Plug a known-good device into each {port_type} port, click Scan, "
        f"verify it appears highlighted below. Test each port individually."
    )
    tk.Label(
        root,
        text=instr_text,
        bg=_BG,
        fg="#888888",
        font=("Courier", 11),
        wraplength=900,
        justify="left",
    ).pack(anchor="w", padx=16, pady=(8, 0))

    # ── Device list area ─────────────────────────────────────────────────────

    list_outer = tk.Frame(root, bg="#111111")

    # Header row
    header = tk.Frame(list_outer, bg=_BG)
    header.pack(fill="x", padx=0, pady=(0, 2))

    tk.Label(
        header,
        text="Device",
        bg=_BG,
        fg="#666666",
        font=("Courier", 10, "bold"),
        width=50,
        anchor="w",
    ).pack(side="left", padx=(8, 0))
    tk.Label(
        header,
        text="Speed / Status",
        bg=_BG,
        fg="#666666",
        font=("Courier", 10, "bold"),
        width=30,
        anchor="w",
    ).pack(side="left")

    # Scrollable rows area
    rows_frame = tk.Frame(list_outer, bg="#111111")
    rows_frame.pack(fill="both", expand=True, padx=4, pady=4)

    def _rebuild_rows():
        for w in rows_frame.winfo_children():
            w.destroy()

        if not current_devices:
            no_dev_lbl = tk.Label(
                rows_frame,
                text="No USB devices detected.",
                bg="#111111",
                fg="#555555",
                font=("Courier", 11),
            )
            no_dev_lbl.pack(anchor="w", padx=8, pady=8)
            return

        for dev in current_devices:
            is_new = dev["key"] not in baseline_keys
            row_bg = _NEW_BG if is_new else "#111111"
            name_fg = "#1a9b1a" if is_new else _FG
            name_text = f"★ NEW  {dev['name']}" if is_new else f"       {dev['name']}"

            row = tk.Frame(rows_frame, bg=row_bg)
            row.pack(fill="x", padx=0, pady=1)

            tk.Label(
                row,
                text=name_text,
                bg=row_bg,
                fg=name_fg,
                font=("Courier", 11),
                width=50,
                anchor="w",
            ).pack(side="left", padx=(8, 0), pady=3)
            tk.Label(
                row,
                text=dev["speed"] or "—",
                bg=row_bg,
                fg="#888888",
                font=("Courier", 11),
                width=30,
                anchor="w",
            ).pack(side="left", pady=3)

    def _update_count():
        total = len(current_devices)
        new_count = sum(1 for d in current_devices if d["key"] not in baseline_keys)
        if new_count > 0:
            count_var.set(f"{total} device(s) detected  •  {new_count} new")
        else:
            count_var.set(f"{total} device(s) detected")

    # ── Scan logic ───────────────────────────────────────────────────────────

    def _scan():
        current_devices.clear()
        current_devices.extend(_enumerate_usb())
        _rebuild_rows()
        _update_count()

    def _set_baseline():
        devs = _enumerate_usb()
        for d in devs:
            baseline_keys.add(d["key"])
        _scan()

    # ── Bottom bar ───────────────────────────────────────────────────────────

    bottom = tk.Frame(root, bg=_BG)
    bottom.pack(fill="x", pady=(0, 18))

    tk.Label(
        bottom,
        text="Plug in a device to each port one at a time, scan after each.",
        bg=_BG,
        fg="#555555",
        font=("Courier", 10),
    ).pack()

    btn_row = tk.Frame(bottom, bg=_BG)
    btn_row.pack(pady=(10, 0))

    _make_btn(btn_row, "Scan Again", _ACCENT, "white", _scan, "#3a6acc").pack(side="left", padx=10)
    _make_btn(btn_row, "Fail", _RED, "white", _do_fail, _RED_H).pack(side="left", padx=10)
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

    # Capture baseline after window is visible
    root.after(200, _set_baseline)

    root.mainloop()
    return result[0] or "fail"


if __name__ == "__main__":
    try:
        port = sys.argv[1] if len(sys.argv) > 1 else "USB-A"
        r = run_usb_test(port)
        sys.exit(0 if r == "pass" else (3 if r == "skip" else 1))
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)

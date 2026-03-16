"""
Full-screen tkinter webcam test — run as a subprocess by the manual test runner.

Exit codes:
  0  — Pass clicked
  1  — Fail or Skip clicked / window closed
  2  — cv2/Pillow not available, no display server, or no cameras found
"""

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

_DD_BG = "#252525"
_DD_HOVER = "#303030"


# ── Main UI ──────────────────────────────────────────────────────────────────


def run_webcam_test() -> bool:
    """Show full-screen webcam preview. Returns True if Pass clicked."""
    try:
        import tkinter as tk

        import cv2
        from PIL import Image, ImageTk
    except ImportError:
        sys.exit(2)

    # ── Camera enumeration ───────────────────────────────────────────────────

    import platform as _platform

    # Suppress cv2's own stderr noise during probing
    available_indices: list[int] = []
    for i in range(5):
        try:
            cap_probe = cv2.VideoCapture(i)
            if cap_probe.isOpened():
                available_indices.append(i)
            cap_probe.release()
        except Exception:
            pass

    no_cameras = not available_indices

    # ── tkinter root ─────────────────────────────────────────────────────────

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title("Webcam Test")
    root.attributes("-fullscreen", True)
    root.configure(bg=_BG)

    # ── No-camera error screen ───────────────────────────────────────────────

    if no_cameras:
        result_nc = [None]

        def _nc_fail():
            result_nc[0] = "fail"
            root.destroy()

        def _nc_skip():
            result_nc[0] = "skip"
            root.destroy()

        tk.Label(root, text="Webcam Test", bg=_BG, fg="#4a9eff", font=("Courier", 16, "bold")).pack(
            pady=(48, 0)
        )

        if _platform.system() == "Darwin":
            msg = (
                "No cameras detected.\n\n"
                "On macOS, camera access must be granted to the application\n"
                "running this test (e.g. Terminal or iTerm2).\n\n"
                "To grant access:\n"
                "  System Settings → Privacy & Security → Camera\n"
                "  Enable the toggle for your terminal application.\n\n"
                "Re-launch the app after granting permission."
            )
        else:
            msg = (
                "No cameras detected.\n\n"
                "Ensure a webcam is connected and that this application\n"
                "has permission to access it, then re-launch."
            )

        tk.Label(root, text=msg, bg=_BG, fg="#aaaaaa", font=("Courier", 12), justify="left").pack(
            pady=24, padx=60
        )

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

        btn_row = tk.Frame(root, bg=_BG)
        btn_row.pack(pady=16)
        _make_btn(btn_row, "Fail", _RED, "white", _nc_fail, _RED_H).pack(side="left", padx=10)
        _make_btn(btn_row, "Skip", _GREY, "#aaa", _nc_skip, _GREY_H).pack(side="left", padx=10)

        root.focus_force()
        root.mainloop()
        return result_nc[0] or "fail"

    result = [None]  # "pass" | "fail" | "skip"
    cap = [None]  # current cv2.VideoCapture
    running = [False]
    photo_ref = [None]  # prevent GC of ImageTk.PhotoImage

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

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def _cleanup():
        running[0] = False
        if cap[0] is not None:
            try:
                cap[0].release()
            except Exception:
                pass
            cap[0] = None

    # ── Actions ──────────────────────────────────────────────────────────────

    def _do_pass():
        result[0] = "pass"
        _cleanup()
        root.destroy()

    def _do_fail():
        result[0] = "fail"
        _cleanup()
        root.destroy()

    def _do_skip():
        result[0] = "skip"
        _cleanup()
        root.destroy()

    # ── Top bar ──────────────────────────────────────────────────────────────

    topbar = tk.Frame(root, bg=_BG)
    topbar.pack(fill="x", padx=16, pady=(12, 0))

    tk.Label(topbar, text="Webcam Test", bg=_BG, fg="#4a9eff", font=("Courier", 16, "bold")).pack(
        side="left"
    )

    # Camera dropdown — Label + tk.Menu (NOT tk.OptionMenu)
    cam_names = [f"Camera {i}" for i in available_indices]
    cam_var = tk.StringVar(value=cam_names[0])

    cam_menu = tk.Menu(
        root,
        tearoff=0,
        bg=_DD_BG,
        fg="#cccccc",
        activebackground=_ACCENT,
        activeforeground="white",
        font=("Courier", 11),
        relief="flat",
    )

    dropdown_frame = tk.Frame(topbar, bg=_BG)
    dropdown_frame.pack(side="right")

    tk.Label(dropdown_frame, text="Camera:", bg=_BG, fg="#888888", font=("Courier", 11)).pack(
        side="left", padx=(0, 6)
    )

    dropdown_lbl = tk.Label(
        dropdown_frame,
        textvariable=cam_var,
        bg=_DD_BG,
        fg="#cccccc",
        font=("Courier", 11),
        padx=14,
        pady=4,
        cursor="hand2",
    )
    dropdown_lbl.pack(side="left")
    tk.Label(dropdown_frame, text=" ▾", bg=_BG, fg="#666666", font=("Courier", 11)).pack(
        side="left"
    )

    def _show_cam_dropdown(event=None):
        x = dropdown_lbl.winfo_rootx()
        y = dropdown_lbl.winfo_rooty() + dropdown_lbl.winfo_height()
        cam_menu.tk_popup(x, y)

    dropdown_lbl.bind("<ButtonPress-1>", _show_cam_dropdown)
    dropdown_lbl.bind("<Enter>", lambda e: dropdown_lbl.configure(bg=_DD_HOVER))
    dropdown_lbl.bind("<Leave>", lambda e: dropdown_lbl.configure(bg=_DD_BG))

    # ── Info bar ─────────────────────────────────────────────────────────────

    info_var = tk.StringVar(value="Opening camera…")
    tk.Label(root, textvariable=info_var, bg=_BG, fg="#888888", font=("Courier", 11)).pack(
        anchor="w", padx=16, pady=(4, 0)
    )

    # ── Bottom bar (packed before canvas so expand=True doesn't push it off) ──

    bottom = tk.Frame(root, bg=_BG)
    bottom.pack(fill="x", pady=(0, 18))

    tk.Label(
        bottom,
        text="Verify the live preview is clear, then mark Pass or Fail.",
        bg=_BG,
        fg="#555555",
        font=("Courier", 10),
    ).pack()

    btn_row = tk.Frame(bottom, bg=_BG)
    btn_row.pack(pady=(10, 0))

    _make_btn(btn_row, "Fail", _RED, "white", _do_fail, _RED_H).pack(side="left", padx=10)
    _make_btn(btn_row, "Pass", _GREEN, "white", _do_pass, _GREEN_H).pack(side="left", padx=10)
    _make_btn(btn_row, "Skip", _GREY, _FG, _do_skip, _GREY_H).pack(side="left", padx=10)

    # ── Preview canvas ───────────────────────────────────────────────────────

    canvas = tk.Canvas(root, bg="#0d0d0d", highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=16, pady=8)

    # ── Camera open / switch ─────────────────────────────────────────────────

    def _open_camera(idx: int):
        # Stop existing capture
        running[0] = False
        if cap[0] is not None:
            try:
                cap[0].release()
            except Exception:
                pass
            cap[0] = None

        try:
            new_cap = cv2.VideoCapture(idx)
            if not new_cap.isOpened():
                info_var.set(f"Camera {idx}: failed to open")
                return
            cap[0] = new_cap
        except Exception as exc:
            info_var.set(f"Camera {idx}: error — {exc}")
            return

        # Read resolution and FPS
        fw = int(cap[0].get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cap[0].get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap[0].get(cv2.CAP_PROP_FPS)
        fps_str = f"{fps:.0f}" if fps and fps > 0 else "?"
        info_var.set(f"{fw} × {fh} @ {fps_str} fps")

        running[0] = True
        _schedule_frame()

    def _switch_camera(idx: int, name: str):
        cam_var.set(name)
        _open_camera(idx)

    # Populate the dropdown menu
    for cam_idx, cam_name in zip(available_indices, cam_names, strict=False):
        cam_menu.add_command(
            label=cam_name,
            command=lambda i=cam_idx, n=cam_name: _switch_camera(i, n),
        )

    # ── Live preview loop ────────────────────────────────────────────────────

    def _update_frame():
        if not running[0] or cap[0] is None:
            return

        ret, frame = cap[0].read()
        if not ret or frame is None:
            if running[0]:
                root.after(33, _update_frame)
            return

        # Fit frame into canvas maintaining aspect ratio
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 2 or ch < 2:
            if running[0]:
                root.after(33, _update_frame)
            return

        fh_px, fw_px = frame.shape[:2]
        scale = min(cw / fw_px, ch / fh_px)
        new_w = max(1, int(fw_px * scale))
        new_h = max(1, int(fh_px * scale))

        frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        photo = ImageTk.PhotoImage(image=img)
        photo_ref[0] = photo  # keep reference — prevents GC

        x0 = (cw - new_w) // 2
        y0 = (ch - new_h) // 2

        canvas.delete("all")
        canvas.create_image(x0, y0, anchor="nw", image=photo)

        if running[0]:
            root.after(33, _update_frame)

    def _schedule_frame():
        if running[0]:
            root.after(33, _update_frame)

    # ── Wire up and start ────────────────────────────────────────────────────

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

    # Open first camera after window is visible
    root.after(200, lambda: _open_camera(available_indices[0]))

    root.mainloop()
    return result[0] or "fail"


if __name__ == "__main__":
    try:
        r = run_webcam_test()
        sys.exit(0 if r == "pass" else (3 if r == "skip" else 1))
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)

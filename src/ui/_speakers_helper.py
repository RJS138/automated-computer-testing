"""
Full-screen tkinter speaker / audio test — run as a subprocess by the manual
test runner.

Generates audio using stdlib only (array + math + wave), plays via platform
subprocess, and challenges the technician with a spoken 4-digit code to
confirm the audio path is fully working.

Exit codes:
  0  — Pass clicked (all steps completed, code confirmed or TTS unavailable)
  1  — Fail / Skip clicked, or window closed without completing
  2  — tkinter not available, no display server, or audio system unavailable
"""

import sys
import platform
import math
import array
import wave
import tempfile
import shutil
import subprocess
import threading
import random
import os
from pathlib import Path

# ── Visual constants ────────────────────────────────────────────────────────

_BG            = "#1a1a1a"
_FG            = "#cccccc"
_ACCENT        = "#2a5ab8"
_GREEN         = "#1a6b1a"
_GREEN_H       = "#228822"
_RED           = "#8b1a1a"
_RED_H         = "#a02020"
_GREY          = "#3a3a3a"
_GREY_H        = "#4a4a4a"
_PASS_DISABLED_BG = "#2a2a2a"
_PASS_ENABLED_BG  = "#1a6b1a"
_PASS_HOVER_BG    = "#228822"

_SAMPLE_RATE = 44100
_AMPLITUDE   = 28000   # 16-bit max ~32767; leave headroom


# ── Audio generation ────────────────────────────────────────────────────────

def _generate_tone(freq: float, duration: float, channel: str) -> bytes:
    """Return raw 16-bit stereo PCM bytes for a sine tone.

    channel: 'both' | 'left' | 'right'
    """
    n_samples = int(_SAMPLE_RATE * duration)
    buf = array.array("h")
    for i in range(n_samples):
        v = int(_AMPLITUDE * math.sin(2 * math.pi * freq * i / _SAMPLE_RATE))
        if channel == "left":
            buf.append(v)
            buf.append(0)
        elif channel == "right":
            buf.append(0)
            buf.append(v)
        else:  # both
            buf.append(v)
            buf.append(v)
    return buf.tobytes()


def _generate_sweep(f_start: float, f_end: float, duration: float) -> bytes:
    """Return raw 16-bit stereo PCM for a logarithmic frequency sweep (both ch)."""
    n_samples = int(_SAMPLE_RATE * duration)
    buf = array.array("h")
    log_start = math.log(f_start)
    log_end   = math.log(f_end)
    phase = 0.0
    for i in range(n_samples):
        t    = i / _SAMPLE_RATE
        frac = i / n_samples
        freq = math.exp(log_start + frac * (log_end - log_start))
        phase += 2 * math.pi * freq / _SAMPLE_RATE
        v = int(_AMPLITUDE * math.sin(phase))
        buf.append(v)
        buf.append(v)
    return buf.tobytes()


def _write_wav(path: str, pcm: bytes) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(pcm)


# ── Playback ────────────────────────────────────────────────────────────────

def _play_wav(path: str):
    """Return a Popen (or thread-like object) for non-blocking WAV playback."""
    system = platform.system()
    if system == "Darwin":
        return subprocess.Popen(["afplay", path],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    elif system == "Windows":
        # winsound blocks; run in thread and expose .is_alive() / poll()
        class _WinThread:
            def __init__(self, p):
                self._t = threading.Thread(target=self._run, args=(p,), daemon=True)
                self._done = False
                self._t.start()
            def _run(self, p):
                try:
                    import winsound
                    winsound.PlaySound(p, winsound.SND_FILENAME)
                except Exception:
                    pass
                self._done = True
            def poll(self):
                return 0 if self._done else None
            def terminate(self):
                pass  # no clean kill for winsound
        return _WinThread(path)
    else:  # Linux
        for cmd in (
            ["aplay",  path],
            ["paplay", path],
            ["ffplay", "-nodisp", "-autoexit", path],
            ["mpv",    "--no-video", path],
        ):
            if shutil.which(cmd[0]):
                return subprocess.Popen(cmd,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
        return None


def _tts_speak(text: str):
    """Speak text via platform TTS. Returns (Popen_or_None, tts_available: bool)."""
    system = platform.system()
    if system == "Darwin":
        p = subprocess.Popen(["say", text],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        return p, True
    elif system == "Windows":
        script = (
            "Add-Type -AssemblyName System.Speech; "
            f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')"
        )
        p = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return p, True
    else:  # Linux
        if shutil.which("espeak"):
            p = subprocess.Popen(["espeak", text],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return p, True
        if shutil.which("festival"):
            p = subprocess.Popen(["festival", "--tts"],
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            try:
                p.stdin.write(text.encode())
                p.stdin.close()
            except Exception:
                pass
            return p, True
        return None, False


# ── Step definitions ─────────────────────────────────────────────────────────

_STEPS = [
    {
        "title":  "Both Speakers",
        "desc":   "Plays a 1 kHz tone through both channels for 3 seconds.\nListen for audio from both left and right speakers.",
        "audio":  ("tone", 1000, 3.0, "both"),
    },
    {
        "title":  "Left Speaker",
        "desc":   "Plays a 1 kHz tone through the LEFT channel only for 3 seconds.\nYou should hear audio from the left speaker only.",
        "audio":  ("tone", 1000, 3.0, "left"),
    },
    {
        "title":  "Right Speaker",
        "desc":   "Plays a 1 kHz tone through the RIGHT channel only for 3 seconds.\nYou should hear audio from the right speaker only.",
        "audio":  ("tone", 1000, 3.0, "right"),
    },
    {
        "title":  "Frequency Sweep",
        "desc":   "Plays a logarithmic sweep from 200 Hz to 8 kHz over 5 seconds\nthrough both channels. Listen for a smooth, rising tone.",
        "audio":  ("sweep", 200, 8000, 5.0),
    },
    {
        "title":  "Spoken Code",
        "desc":   "A 4-digit code will be spoken aloud.\nType the code you hear to confirm audio is working.",
        "audio":  None,   # handled specially
    },
]


# ── Main UI ──────────────────────────────────────────────────────────────────

def run_speakers_test() -> bool:
    try:
        import tkinter as tk
    except ImportError:
        sys.exit(2)

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title("Speaker / Audio Test")
    root.configure(bg=_BG)
    if platform.system() == "Darwin":
        root.attributes("-fullscreen", True)
        root.createcommand("::tk::mac::Fullscreen", lambda: None)
    else:
        root.attributes("-fullscreen", True)

    # ── Pre-generate all WAV files ───────────────────────────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="touchstone_audio_")
    wav_paths = []
    try:
        for i, step in enumerate(_STEPS):
            if step["audio"] is None:
                wav_paths.append(None)
                continue
            a = step["audio"]
            path = os.path.join(tmp_dir, f"step_{i}.wav")
            if a[0] == "tone":
                _write_wav(path, _generate_tone(a[1], a[2], a[3]))
            else:  # sweep
                _write_wav(path, _generate_sweep(a[1], a[2], a[3]))
            wav_paths.append(path)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        sys.exit(2)

    # ── Spoken code ──────────────────────────────────────────────────────────
    code_digits  = [str(random.randint(0, 9)) for _ in range(4)]
    code_str     = "".join(code_digits)
    # Prefixing with "The code is" gives context and prevents digits being
    # run together or misread as a multi-digit number by the TTS engine.
    spoken_text  = "The code is " + ", ".join(code_digits)   # e.g. "The code is 2, 7, 4, 1"

    # Check TTS availability early (Linux only needs a probe)
    _tts_available = [True]
    if platform.system() == "Linux":
        if not shutil.which("espeak") and not shutil.which("festival"):
            _tts_available[0] = False

    # ── State ────────────────────────────────────────────────────────────────
    current_step  = [0]
    step_played   = [False] * len(_STEPS)
    code_confirmed  = [False]
    pass_unlocked   = [False]
    playback_proc  = [None]   # current Popen / WinThread
    tts_proc       = [None]

    # ── Layout ───────────────────────────────────────────────────────────────
    topbar = tk.Frame(root, bg=_BG)
    topbar.pack(fill="x", padx=16, pady=(12, 0))
    tk.Label(topbar, text="Speaker / Audio Test", bg=_BG, fg="#4a9eff",
             font=("Courier", 16, "bold")).pack(side="left")

    content = tk.Frame(root, bg=_BG)

    # Left panel — step list
    left_panel = tk.Frame(content, bg="#111111", width=240)
    left_panel.pack(side="left", fill="y", padx=(0, 10))
    left_panel.pack_propagate(False)

    tk.Label(left_panel, text="Steps", bg="#111111", fg="#666",
             font=("Courier", 10, "bold"), anchor="w").pack(
        fill="x", padx=12, pady=(12, 4))

    step_labels: list[tk.Label] = []
    for i, step in enumerate(_STEPS):
        lbl = tk.Label(
            left_panel,
            text=f"  ○  {step['title']}",
            bg="#111111", fg="#555",
            font=("Courier", 11), anchor="w",
            justify="left",
        )
        lbl.pack(fill="x", padx=8, pady=2)
        step_labels.append(lbl)

    # Right panel — step detail
    right_panel = tk.Frame(content, bg=_BG)
    right_panel.pack(side="left", fill="both", expand=True)

    detail_title = tk.Label(right_panel, text="", bg=_BG, fg="#4a9eff",
                            font=("Courier", 15, "bold"), anchor="w", justify="left")
    detail_title.pack(fill="x", pady=(8, 4))

    detail_desc = tk.Label(right_panel, text="", bg=_BG, fg=_FG,
                           font=("Courier", 11), anchor="w", justify="left",
                           wraplength=600)
    detail_desc.pack(fill="x", pady=(0, 12))

    # Play button row
    play_row = tk.Frame(right_panel, bg=_BG)
    play_row.pack(anchor="w", pady=(0, 8))

    def _make_btn(parent, text, bg, fg, command, hover_bg):
        lbl = tk.Label(parent, text=text, bg=bg, fg=fg,
                       font=("Courier", 13, "bold"), padx=28, pady=8, cursor="hand2")
        lbl.bind("<Enter>",         lambda e, w=lbl, c=hover_bg: w.configure(bg=c))
        lbl.bind("<Leave>",         lambda e, w=lbl, c=bg:       w.configure(bg=c))
        lbl.bind("<ButtonPress-1>", lambda e: command())
        return lbl

    play_btn = _make_btn(play_row, "▶  Play", _ACCENT, "white", lambda: _play_step(), "#3a6fd8")
    play_btn.pack(side="left", padx=(0, 14))

    play_status = tk.Label(play_row, text="", bg=_BG, fg="#888",
                            font=("Courier", 11))
    play_status.pack(side="left")

    next_btn_frame = tk.Frame(right_panel, bg=_BG)
    next_btn_frame.pack(anchor="w", pady=(4, 0))

    # Code challenge widgets (step 5) — hidden until step 4
    code_frame = tk.Frame(right_panel, bg=_BG)

    code_hint = tk.Label(code_frame, text="", bg=_BG, fg="#aaa",
                         font=("Courier", 11), anchor="w", justify="left")
    code_hint.pack(anchor="w", pady=(8, 4))

    code_entry_row = tk.Frame(code_frame, bg=_BG)
    code_entry_row.pack(anchor="w")

    code_var = tk.StringVar()
    code_entry = tk.Entry(
        code_entry_row,
        textvariable=code_var,
        bg="#252525", fg="white",
        insertbackground="white",
        font=("Courier", 18, "bold"),
        width=6, relief="flat",
        highlightthickness=1, highlightbackground="#444",
    )
    code_entry.pack(side="left", padx=(0, 10))

    confirm_btn = _make_btn(code_entry_row, "Confirm", _GREY, _FG, lambda: _confirm_code(), _GREY_H)
    confirm_btn.pack(side="left")

    code_result = tk.Label(code_frame, text="", bg=_BG, fg="#888",
                            font=("Courier", 12, "bold"))
    code_result.pack(anchor="w", pady=(8, 0))

    replay_btn_frame = tk.Frame(code_frame, bg=_BG)
    replay_btn_frame.pack(anchor="w", pady=(8, 0))

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bottom = tk.Frame(root, bg=_BG)
    bottom.pack(fill="x", pady=(4, 18))

    tk.Label(bottom,
             text="Play each step, then confirm the spoken code to enable Pass.",
             bg=_BG, fg="#555", font=("Courier", 10)).pack()

    btn_row = tk.Frame(bottom, bg=_BG)
    btn_row.pack(pady=(10, 0))

    def _do_fail():
        result[0] = "fail"
        root.destroy()

    def _do_skip():
        result[0] = "skip"
        root.destroy()

    _make_btn(btn_row, "Fail", _RED, "white", _do_fail, _RED_H).pack(
        side="left", padx=10)

    pass_lbl = tk.Label(
        btn_row, text="Pass", bg=_PASS_DISABLED_BG, fg="#555",
        font=("Courier", 13, "bold"), padx=28, pady=8, cursor="arrow",
    )
    pass_lbl.pack(side="left", padx=10)

    _make_btn(btn_row, "Skip", _GREY, "#aaa", _do_skip, _GREY_H).pack(
        side="left", padx=10)

    # Pack content after bottom bar so expand=True doesn't hide the buttons
    content.pack(fill="both", expand=True, padx=16, pady=10)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _stop_playback():
        p = playback_proc[0]
        if p is not None:
            try:
                p.terminate()
            except Exception:
                pass
            playback_proc[0] = None
        t = tts_proc[0]
        if t is not None:
            try:
                t.terminate()
            except Exception:
                pass
            tts_proc[0] = None

    def _check_pass_unlock():
        all_played = all(step_played)
        if _tts_available[0]:
            ok = all_played and code_confirmed[0]
        else:
            ok = all_played   # TTS unavailable: visual code is the fallback
        pass_unlocked[0] = ok
        if ok:
            pass_lbl.configure(bg=_PASS_ENABLED_BG, fg="white", cursor="hand2")
            pass_lbl.bind("<Enter>",         lambda e: pass_lbl.configure(bg=_PASS_HOVER_BG))
            pass_lbl.bind("<Leave>",         lambda e: pass_lbl.configure(bg=_PASS_ENABLED_BG))
            pass_lbl.bind("<ButtonPress-1>", lambda e: _do_done())
        else:
            pass_lbl.configure(bg=_PASS_DISABLED_BG, fg="#555", cursor="arrow")
            pass_lbl.unbind("<Enter>")
            pass_lbl.unbind("<Leave>")
            pass_lbl.unbind("<ButtonPress-1>")

    result = ["fail"]   # "pass" | "fail" | "skip"

    def _do_done():
        result[0] = "pass"
        root.destroy()

    def _update_step_list():
        for i, lbl in enumerate(step_labels):
            if i < current_step[0]:
                lbl.configure(text=f"  ✓  {_STEPS[i]['title']}", fg="#2a8a2a")
            elif i == current_step[0]:
                lbl.configure(text=f"  ●  {_STEPS[i]['title']}", fg="#4a9eff")
            else:
                lbl.configure(text=f"  ○  {_STEPS[i]['title']}", fg="#555")

    def _show_step(idx: int):
        current_step[0] = idx
        step = _STEPS[idx]

        detail_title.configure(text=f"Step {idx + 1} of {len(_STEPS)}:  {step['title']}")
        detail_desc.configure(text=step["desc"])

        play_status.configure(text="")
        play_btn.configure(state="normal", cursor="hand2",
                           bg=_ACCENT, fg="white")

        # Remove old next button children
        for w in next_btn_frame.winfo_children():
            w.destroy()

        if idx == len(_STEPS) - 1:
            # Step 5: code challenge
            code_frame.pack(anchor="w", pady=(12, 0))
            _setup_code_step()
        else:
            code_frame.pack_forget()

        _update_step_list()

    def _setup_code_step():
        """Configure widgets for the spoken-code step."""
        # Clear previous entry
        code_var.set("")
        code_result.configure(text="", fg="#888")

        if _tts_available[0]:
            code_hint.configure(
                text="Click Play to hear the spoken code,\nthen type the 4 digits you heard and click Confirm.")
        else:
            code_hint.configure(
                text="TTS is unavailable on this system.\n"
                     "Audio cannot be verified automatically — mark Fail or Skip.",
                fg="#e0a040",
            )

        # Replay button for TTS (shown after first play)
        for w in replay_btn_frame.winfo_children():
            w.destroy()

    def _play_step():
        idx = current_step[0]
        _stop_playback()
        play_status.configure(text="Playing...", fg="#4a9eff")
        play_btn.configure(bg="#1a3a7a", cursor="arrow")

        if idx == len(_STEPS) - 1:
            # Spoken code
            if _tts_available[0]:
                try:
                    proc, avail = _tts_speak(spoken_text)
                except Exception as exc:
                    avail = False
                    proc = None
                    play_status.configure(text=f"TTS error: {exc}", fg=_RED)
                tts_proc[0] = proc
                if not avail or proc is None:
                    _tts_available[0] = False
                    play_status.configure(text="TTS unavailable — mark Fail or Skip", fg="#e0a040")
                    play_btn.configure(bg=_ACCENT, cursor="hand2")
                    _mark_played(idx)
                    return
                root.after(150, lambda: _poll_tts(idx))
            else:
                # TTS unavailable — can't verify audio; technician should fail or skip
                play_status.configure(text="TTS unavailable — mark Fail or Skip", fg="#e0a040")
                play_btn.configure(bg=_ACCENT, cursor="hand2")
                _mark_played(idx)
        else:
            path = wav_paths[idx]
            if path is None:
                play_status.configure(text="No audio file", fg=_RED)
                play_btn.configure(bg=_ACCENT, cursor="hand2")
                return
            proc = _play_wav(path)
            playback_proc[0] = proc
            if proc is None:
                play_status.configure(text="No audio player found", fg=_RED)
                play_btn.configure(bg=_ACCENT, cursor="hand2")
                return
            root.after(150, lambda: _poll_playback(idx))

    def _poll_playback(idx: int):
        p = playback_proc[0]
        if p is None:
            return
        try:
            ret = p.poll()
        except Exception:
            ret = 0
        if ret is None:
            root.after(150, lambda: _poll_playback(idx))
        else:
            playback_proc[0] = None
            play_status.configure(text="✓  Played", fg=_GREEN)
            play_btn.configure(bg=_ACCENT, cursor="hand2")
            _mark_played(idx)

    def _poll_tts(idx: int):
        p = tts_proc[0]
        if p is None:
            return
        try:
            ret = p.poll()
        except Exception:
            ret = 0
        if ret is None:
            root.after(150, lambda: _poll_tts(idx))
        else:
            tts_proc[0] = None
            play_status.configure(text="✓  Spoken", fg=_GREEN)
            play_btn.configure(bg=_ACCENT, cursor="hand2")
            _mark_played(idx)
            # Show replay button
            for w in replay_btn_frame.winfo_children():
                w.destroy()
            _make_btn(replay_btn_frame, "▶  Replay Code",
                      _GREY, _FG, _play_step, _GREY_H).pack(side="left")

    def _mark_played(idx: int):
        step_played[idx] = True
        _update_step_list()

        # Show Next button if not last step, or just check unlock
        for w in next_btn_frame.winfo_children():
            w.destroy()

        if idx < len(_STEPS) - 1:
            def _go_next():
                _stop_playback()
                _show_step(idx + 1)
            _make_btn(next_btn_frame, "Next Step →",
                      _ACCENT, "white", _go_next, "#3a6fd8").pack(side="left")

        _check_pass_unlock()

    def _confirm_code():
        entered = code_var.get().strip()
        if entered == code_str:
            code_confirmed[0] = True
            code_result.configure(text="✓  Correct!", fg=_GREEN)
            confirm_btn.configure(bg=_GREEN, cursor="arrow")
            confirm_btn.unbind("<ButtonPress-1>")
        else:
            code_result.configure(text="✗  Wrong — try again or replay the code.", fg=_RED)
        _check_pass_unlock()

    # Bind Enter key in code entry to confirm
    code_entry.bind("<Return>", lambda e: _confirm_code())

    # ── Initialise ────────────────────────────────────────────────────────────

    def _on_root_key(event):
        # Skip key shortcuts when the code entry has focus (typing the code)
        if root.focus_get() is code_entry:
            return
        k = event.keysym.lower()
        if k == "p" and pass_unlocked[0]:
            _do_done()
        elif k == "f":
            _do_fail()
        elif k == "s":
            _do_skip()

    root.bind("<Key>", _on_root_key)
    _show_step(0)
    root.focus_force()

    try:
        root.mainloop()
    finally:
        _stop_playback()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return result[0]


if __name__ == "__main__":
    try:
        r = run_speakers_test()
        sys.exit(0 if r == "pass" else (3 if r == "skip" else 1))
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)

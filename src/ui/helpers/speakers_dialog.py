"""Full-screen QDialog speaker / audio test.

Port of the tkinter _speakers_helper.py to PySide6 QDialog.
Generates audio using stdlib only (math + wave), plays via platform
subprocess, and challenges the technician with a spoken 4-digit code.
"""

import array
import math
import os
import platform
import random
import shutil
import subprocess
import tempfile
import threading
import wave

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._utils import make_dialog_btn, show_fullscreen

# ── Audio generation (copied from _speakers_helper.py) ─────────────────

_SAMPLE_RATE = 44100
_AMPLITUDE = 28000


def _generate_tone(freq: float, duration: float, channel: str) -> bytes:
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
        else:
            buf.append(v)
            buf.append(v)
    return buf.tobytes()


def _generate_sweep(f_start: float, f_end: float, duration: float) -> bytes:
    n_samples = int(_SAMPLE_RATE * duration)
    buf = array.array("h")
    log_start = math.log(f_start)
    log_end = math.log(f_end)
    phase = 0.0
    for i in range(n_samples):
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


def _play_wav(path: str):
    system = platform.system()
    if system == "Darwin":
        return subprocess.Popen(
            ["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    elif system == "Windows":

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
                pass

        return _WinThread(path)
    else:
        for cmd in (
            ["aplay", path],
            ["paplay", path],
            ["ffplay", "-nodisp", "-autoexit", path],
            ["mpv", "--no-video", path],
        ):
            if shutil.which(cmd[0]):
                return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return None


def _tts_speak(text: str):
    system = platform.system()
    if system == "Darwin":
        p = subprocess.Popen(["say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p, True
    elif system == "Windows":
        script = (
            "Add-Type -AssemblyName System.Speech; "
            f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')"
        )
        p = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return p, True
    else:
        if shutil.which("espeak"):
            p = subprocess.Popen(
                ["espeak", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return p, True
        if shutil.which("festival"):
            p = subprocess.Popen(
                ["festival", "--tts"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                p.stdin.write(text.encode())
                p.stdin.close()
            except Exception:
                pass
            return p, True
        return None, False


# ── Step definitions ──────────────────────────────────────────────────

_STEPS = [
    {
        "title": "Both Speakers",
        "desc": "Plays a 1 kHz tone through both channels for 3 seconds.\nListen for audio from both left and right speakers.",
        "audio": ("tone", 1000, 3.0, "both"),
    },
    {
        "title": "Left Speaker",
        "desc": "Plays a 1 kHz tone through the LEFT channel only for 3 seconds.\nYou should hear audio from the left speaker only.",
        "audio": ("tone", 1000, 3.0, "left"),
    },
    {
        "title": "Right Speaker",
        "desc": "Plays a 1 kHz tone through the RIGHT channel only for 3 seconds.\nYou should hear audio from the right speaker only.",
        "audio": ("tone", 1000, 3.0, "right"),
    },
    {
        "title": "Frequency Sweep",
        "desc": "Plays a logarithmic sweep from 200 Hz to 8 kHz over 5 seconds\nthrough both channels. Listen for a smooth, rising tone.",
        "audio": ("sweep", 200, 8000, 5.0),
    },
    {
        "title": "Spoken Code",
        "desc": "A 4-digit code will be spoken aloud.\nType the code you hear to confirm audio is working.",
        "audio": None,
    },
]


# ── Visual constants ──────────────────────────────────────────────────

_BG = "#1a1a1a"
_FG = "#cccccc"
_ACCENT = "#2a5ab8"


class SpeakersDialog(QDialog):
    """Full-screen speaker / audio test dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_str: str = "fail"
        self.setWindowTitle("Speaker / Audio Test")
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        # Pre-generate WAV files
        self._tmp_dir = tempfile.mkdtemp(prefix="touchstone_audio_")
        self._wav_paths: list[str | None] = []
        for i, step in enumerate(_STEPS):
            if step["audio"] is None:
                self._wav_paths.append(None)
                continue
            a = step["audio"]
            path = os.path.join(self._tmp_dir, f"step_{i}.wav")
            if a[0] == "tone":
                _write_wav(path, _generate_tone(a[1], a[2], a[3]))
            else:
                _write_wav(path, _generate_sweep(a[1], a[2], a[3]))
            self._wav_paths.append(path)

        # Spoken code
        self._code_digits = [str(random.randint(0, 9)) for _ in range(4)]
        self._code_str = "".join(self._code_digits)
        self._spoken_text = "The code is " + ", ".join(self._code_digits)

        # TTS availability
        self._tts_available = True
        if platform.system() == "Linux":
            if not shutil.which("espeak") and not shutil.which("festival"):
                self._tts_available = False

        # State
        self._current_step = 0
        self._step_played = [False] * len(_STEPS)
        self._code_confirmed = False
        self._pass_unlocked = False
        self._playback_proc = None
        self._tts_proc = None

        # Poll timer
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(150)
        self._poll_timer.timeout.connect(self._poll_playback)
        self._poll_step_idx = 0
        self._poll_is_tts = False

        self._build_ui()
        self._show_step(0)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 18)

        # Title
        title = QLabel("Speaker / Audio Test")
        title.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; font-size: 16px; font-weight: bold;"
        )
        root.addWidget(title)

        # Content: left panel (step list) + right panel (detail)
        content = QHBoxLayout()

        # Left panel
        left = QVBoxLayout()
        lbl = QLabel("Steps")
        lbl.setStyleSheet("color: #666; font-family: Courier; font-size: 10px; font-weight: bold;")
        left.addWidget(lbl)

        self._step_labels: list[QLabel] = []
        for _i, step in enumerate(_STEPS):
            sl = QLabel(f"  o  {step['title']}")
            sl.setStyleSheet("color: #555; font-family: Courier; font-size: 11px;")
            left.addWidget(sl)
            self._step_labels.append(sl)
        left.addStretch()

        left_widget = QWidget()
        left_widget.setFixedWidth(240)
        left_widget.setStyleSheet("background: #111111;")
        left_widget.setLayout(left)
        content.addWidget(left_widget)

        # Right panel
        right = QVBoxLayout()

        self._detail_title = QLabel()
        self._detail_title.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; font-size: 15px; font-weight: bold;"
        )
        right.addWidget(self._detail_title)

        self._detail_desc = QLabel()
        self._detail_desc.setStyleSheet(
            f"color: {_FG}; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        self._detail_desc.setWordWrap(True)
        right.addWidget(self._detail_desc)

        # Play button row
        play_row = QHBoxLayout()
        self._play_btn = QPushButton("Play")
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT}; color: white; border: none; "
            "padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }"
            f"QPushButton:hover {{ background: #3a6fd8; }}"
        )
        self._play_btn.clicked.connect(self._play_step)
        play_row.addWidget(self._play_btn)

        self._play_status = QLabel()
        self._play_status.setStyleSheet(
            f"color: #888; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        play_row.addWidget(self._play_status)
        play_row.addStretch()
        right.addLayout(play_row)

        # Next step button
        self._next_btn = QPushButton("Next Step -->")
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT}; color: white; border: none; "
            "padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #3a6fd8; }"
        )
        self._next_btn.setVisible(False)
        self._next_btn.clicked.connect(self._go_next)
        right.addWidget(self._next_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Code challenge widgets
        self._code_widget = QWidget()
        code_layout = QVBoxLayout(self._code_widget)
        code_layout.setContentsMargins(0, 12, 0, 0)

        self._code_hint = QLabel()
        self._code_hint.setStyleSheet(
            f"color: #aaa; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        code_layout.addWidget(self._code_hint)

        entry_row = QHBoxLayout()
        self._code_entry = QLineEdit()
        self._code_entry.setMaxLength(4)
        self._code_entry.setFixedWidth(120)
        self._code_entry.setStyleSheet(
            "QLineEdit { background: #2e2e2e; color: white; border: none; "
            "padding: 6px; font-family: Courier; font-size: 18px; font-weight: bold; }"
        )
        self._code_entry.returnPressed.connect(self._confirm_code)
        entry_row.addWidget(self._code_entry)

        self._confirm_btn = QPushButton("Confirm")
        self._confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_btn.setStyleSheet(
            "QPushButton { background: #3a3a3a; color: #cccccc; border: none; "
            "padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #4a4a4a; }"
        )
        self._confirm_btn.clicked.connect(self._confirm_code)
        entry_row.addWidget(self._confirm_btn)
        entry_row.addStretch()
        code_layout.addLayout(entry_row)

        self._code_result = QLabel()
        self._code_result.setStyleSheet(
            f"color: #888; background: {_BG}; font-family: Courier; font-size: 12px; font-weight: bold;"
        )
        code_layout.addWidget(self._code_result)

        self._replay_btn = QPushButton("Replay Code")
        self._replay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._replay_btn.setStyleSheet(
            "QPushButton { background: #3a3a3a; color: #cccccc; border: none; "
            "padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #4a4a4a; }"
        )
        self._replay_btn.setVisible(False)
        self._replay_btn.clicked.connect(self._play_step)
        code_layout.addWidget(self._replay_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._code_widget.setVisible(False)
        right.addWidget(self._code_widget)

        right.addStretch()
        content.addLayout(right, 1)
        root.addLayout(content, 1)

        # Bottom hint
        hint = QLabel("Play each step, then confirm the spoken code to enable Pass.")
        hint.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 10px;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fail_btn = make_dialog_btn("Fail", "#8b1a1a", "#a02020")
        fail_btn.clicked.connect(lambda: self._finish("fail"))
        btn_row.addWidget(fail_btn)

        self._pass_btn = QPushButton("Pass")
        self._pass_btn.setEnabled(False)
        self._pass_btn.setStyleSheet(
            "QPushButton { background: #2a2a2a; color: #555; border: none; "
            "padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }"
            "QPushButton:enabled { background: #1a6b1a; color: white; }"
            "QPushButton:enabled:hover { background: #228822; }"
        )
        self._pass_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._pass_btn.clicked.connect(lambda: self._finish("pass"))
        btn_row.addWidget(self._pass_btn)

        skip_btn = make_dialog_btn("Skip", "#3a3a3a", "#4a4a4a", fg="#aaa")
        skip_btn.clicked.connect(lambda: self._finish("skip"))
        btn_row.addWidget(skip_btn)

        root.addLayout(btn_row)

    # ── helpers ────────────────────────────────────────────────────────

    def _finish(self, result: str) -> None:
        if result == "pass" and not self._pass_unlocked:
            return
        self._stop_playback()
        self.result_str = result
        self.accept()

    def _stop_playback(self) -> None:
        self._poll_timer.stop()
        for proc in (self._playback_proc, self._tts_proc):
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        self._playback_proc = None
        self._tts_proc = None

    def _check_pass_unlock(self) -> None:
        all_played = all(self._step_played)
        if self._tts_available:
            ok = all_played and self._code_confirmed
        else:
            ok = all_played
        self._pass_unlocked = ok
        self._pass_btn.setEnabled(ok)
        self._pass_btn.setCursor(
            Qt.CursorShape.PointingHandCursor if ok else Qt.CursorShape.ArrowCursor
        )

    def _update_step_list(self) -> None:
        for i, lbl in enumerate(self._step_labels):
            if i < self._current_step:
                lbl.setText(f"  [ok]  {_STEPS[i]['title']}")
                lbl.setStyleSheet("color: #2a8a2a; font-family: Courier; font-size: 11px;")
            elif i == self._current_step:
                lbl.setText(f"  >>  {_STEPS[i]['title']}")
                lbl.setStyleSheet("color: #4a9eff; font-family: Courier; font-size: 11px;")
            else:
                lbl.setText(f"  o  {_STEPS[i]['title']}")
                lbl.setStyleSheet("color: #555; font-family: Courier; font-size: 11px;")

    def _show_step(self, idx: int) -> None:
        self._current_step = idx
        step = _STEPS[idx]
        self._detail_title.setText(f"Step {idx + 1} of {len(_STEPS)}:  {step['title']}")
        self._detail_desc.setText(step["desc"])
        self._play_status.setText("")
        self._next_btn.setVisible(False)

        if idx == len(_STEPS) - 1:
            self._code_widget.setVisible(True)
            self._setup_code_step()
        else:
            self._code_widget.setVisible(False)

        self._update_step_list()

    def _setup_code_step(self) -> None:
        self._code_entry.clear()
        self._code_result.setText("")
        self._replay_btn.setVisible(False)

        if self._tts_available:
            self._code_hint.setText(
                "Click Play to hear the spoken code,\nthen type the 4 digits you heard and click Confirm."
            )
            self._code_hint.setStyleSheet(
                f"color: #aaa; background: {_BG}; font-family: Courier; font-size: 11px;"
            )
        else:
            self._code_hint.setText(
                "TTS is unavailable on this system.\nAudio cannot be verified automatically -- mark Fail or Skip."
            )
            self._code_hint.setStyleSheet(
                f"color: #e0a040; background: {_BG}; font-family: Courier; font-size: 11px;"
            )

    def _play_step(self) -> None:
        idx = self._current_step
        self._stop_playback()
        self._play_status.setText("Playing...")
        self._play_status.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; font-size: 11px;"
        )

        if idx == len(_STEPS) - 1:
            # Spoken code
            if self._tts_available:
                try:
                    proc, avail = _tts_speak(self._spoken_text)
                except Exception:
                    avail = False
                    proc = None
                if not avail or proc is None:
                    self._tts_available = False
                    self._play_status.setText("TTS unavailable -- mark Fail or Skip")
                    self._play_status.setStyleSheet(
                        f"color: #e0a040; background: {_BG}; font-family: Courier; font-size: 11px;"
                    )
                    self._mark_played(idx)
                    return
                self._tts_proc = proc
                self._poll_step_idx = idx
                self._poll_is_tts = True
                self._poll_timer.start()
            else:
                self._play_status.setText("TTS unavailable -- mark Fail or Skip")
                self._play_status.setStyleSheet(
                    f"color: #e0a040; background: {_BG}; font-family: Courier; font-size: 11px;"
                )
                self._mark_played(idx)
        else:
            path = self._wav_paths[idx]
            if path is None:
                self._play_status.setText("No audio file")
                return
            proc = _play_wav(path)
            self._playback_proc = proc
            if proc is None:
                self._play_status.setText("No audio player found")
                return
            self._poll_step_idx = idx
            self._poll_is_tts = False
            self._poll_timer.start()

    def _poll_playback(self) -> None:
        proc = self._tts_proc if self._poll_is_tts else self._playback_proc
        if proc is None:
            self._poll_timer.stop()
            return
        try:
            ret = proc.poll()
        except Exception:
            ret = 0
        if ret is None:
            return  # still playing
        self._poll_timer.stop()
        if self._poll_is_tts:
            self._tts_proc = None
            self._play_status.setText("Spoken")
            self._play_status.setStyleSheet(
                f"color: #1a6b1a; background: {_BG}; font-family: Courier; font-size: 11px;"
            )
            self._replay_btn.setVisible(True)
        else:
            self._playback_proc = None
            self._play_status.setText("Played")
            self._play_status.setStyleSheet(
                f"color: #1a6b1a; background: {_BG}; font-family: Courier; font-size: 11px;"
            )
        self._mark_played(self._poll_step_idx)

    def _mark_played(self, idx: int) -> None:
        self._step_played[idx] = True
        self._update_step_list()
        if idx < len(_STEPS) - 1:
            self._next_btn.setVisible(True)
        self._check_pass_unlock()

    def _go_next(self) -> None:
        self._stop_playback()
        if self._current_step < len(_STEPS) - 1:
            self._show_step(self._current_step + 1)

    def _confirm_code(self) -> None:
        entered = self._code_entry.text().strip()
        if entered == self._code_str:
            self._code_confirmed = True
            self._code_result.setText("Correct!")
            self._code_result.setStyleSheet(
                f"color: #1a6b1a; background: {_BG}; font-family: Courier; font-size: 12px; font-weight: bold;"
            )
            self._confirm_btn.setEnabled(False)
        else:
            self._code_result.setText("Wrong -- try again or replay the code.")
            self._code_result.setStyleSheet(
                f"color: #8b1a1a; background: {_BG}; font-family: Courier; font-size: 12px; font-weight: bold;"
            )
        self._check_pass_unlock()

    # ── events ────────────────────────────────────────────────────────

    def run(self) -> int:
        """Show full-screen and run the dialog. Use instead of QDialog.exec()."""
        show_fullscreen(self)
        return super().exec()

    def keyPressEvent(self, event) -> None:
        # Skip shortcuts when code entry has focus
        if self._code_entry.hasFocus():
            super().keyPressEvent(event)
            return
        key = event.text().lower()
        if key == "p" and self._pass_unlocked:
            self._finish("pass")
        elif key == "f":
            self._finish("fail")
        elif key == "s":
            self._finish("skip")
        elif event.key() == Qt.Key.Key_Escape:
            return  # Don't close dialog on Escape

    def closeEvent(self, event) -> None:
        self._stop_playback()
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        if self.result() != QDialog.DialogCode.Accepted:
            self.result_str = "fail"
        event.accept()

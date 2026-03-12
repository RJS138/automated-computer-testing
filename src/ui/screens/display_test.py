"""Full-screen colour cycle for display testing.

Preferred path: launches _display_helper.py as a subprocess which opens a
native full-screen window via tkinter — fills the entire monitor regardless
of terminal size.

Fallback path (no display server / tkinter unavailable): runs the colour
cycle inside the terminal using the Textual screen background.
"""

import asyncio
import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Static


_COLORS: list[tuple[str, str]] = [
    ("Black",   "#000000"),
    ("White",   "#FFFFFF"),
    ("Red",     "#FF0000"),
    ("Green",   "#00FF00"),
    ("Blue",    "#0000FF"),
    ("Cyan",    "#00FFFF"),
    ("Magenta", "#FF00FF"),
    ("Gray",    "#7F7F7F"),
]

_N = len(_COLORS)

_INSTRUCTIONS = (
    "DISPLAY COLOUR TEST\n\n"
    f"The screen will cycle through {_N} solid colours.\n\n"
    "On each colour, look carefully for:\n\n"
    "  Dead pixels      — dots stuck at the wrong colour\n"
    "  Backlight bleed  — bright patches at the screen edges\n"
    "                     (most visible on the black screen)\n"
    "  Colour uniformity— no dark or bright patches across the panel\n"
    "  Screen damage    — cracks or pressure marks\n\n"
    "Press any key or click anywhere to advance.\n"
    "Press ESC to end the cycle early."
)

_HELPER = Path(__file__).parent.parent / "_display_helper.py"


class DisplayTestScreen(Screen):
    """
    Colour-cycle screen for manual display inspection.

    Launches an external full-screen window when a display server is available
    (macOS / Linux with X11/Wayland / Windows).  Falls back to cycling the
    terminal background when running on a headless TTY (e.g. the live ISO).
    """

    DEFAULT_CSS = """
    DisplayTestScreen {
        layout: vertical;
        background: #0d0d0d;
    }
    #instr {
        width: 100%;
        height: 1fr;
        background: #0d0d0d;
        color: #e0e0e0;
        padding: 4 8;
    }
    #hint {
        dock: bottom;
        width: 100%;
        height: 1;
        background: #1a1a1a;
        color: #cccccc;
        text-align: center;
        padding: 0 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._phase = -1
        self._external_running = False  # True while subprocess is live

    def compose(self) -> ComposeResult:
        yield Static(_INSTRUCTIONS, id="instr")
        yield Label(
            "  Press any key or click to begin   |   ESC to skip  ",
            id="hint",
        )

    async def on_mount(self) -> None:
        result = await self._try_external()
        if result is not None:
            self.dismiss(result)
        # else: no display server — terminal fallback via on_key / on_click

    # ------------------------------------------------------------------
    # External full-screen path
    # ------------------------------------------------------------------

    async def _try_external(self) -> bool | None:
        """
        Launch the display helper as a subprocess.

        In a frozen PyInstaller binary the exe re-invokes itself with
        --run-helper display.  In dev mode the helper script is called
        directly via the Python interpreter.

        Returns True/False on success, None if tkinter is unavailable
        (caller should fall back to terminal mode).
        """
        frozen = hasattr(sys, "_MEIPASS")
        if not frozen and not _HELPER.exists():
            return None

        self._external_running = True
        self.query_one("#instr", Static).update(
            "Display test running in the full-screen window.\n\n"
            "Follow the on-screen instructions.\n\n"
            "When the window closes you will be returned here."
        )
        self.query_one("#hint", Label).update(
            "  Full-screen display test in progress…  "
        )

        if frozen:
            cmd = [sys.executable, "--run-helper", "display"]
        else:
            cmd = [sys.executable, str(_HELPER)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        rc = await proc.wait()
        self._external_running = False

        if rc == 2:
            # tkinter / display unavailable — restore instructions for terminal fallback
            self.query_one("#instr", Static).update(_INSTRUCTIONS)
            self.query_one("#hint", Label).update(
                "  Press any key or click to begin   |   ESC to skip  "
            )
            return None

        if rc == 0:
            return "pass"
        if rc == 3:
            return "skip"
        return "fail"

    # ------------------------------------------------------------------
    # Terminal fallback
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        if self._external_running:
            return
        if event.key == "escape":
            self.dismiss("skip")
        else:
            self._advance()

    def on_click(self, event) -> None:
        if self._external_running:
            return
        self._advance()

    def _advance(self) -> None:
        self._phase += 1
        if self._phase >= _N:
            self.dismiss("pass")
            return

        name, bg = _COLORS[self._phase]

        instr = self.query_one("#instr", Static)
        if instr.display:
            instr.display = False

        self.styles.background = bg

        self.query_one("#hint", Label).update(
            f"  {name}   {self._phase + 1} / {_N}"
            "   |   any key / click to advance   |   ESC to end  "
        )

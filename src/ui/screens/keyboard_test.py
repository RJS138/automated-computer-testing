"""Interactive keyboard test screen.

Preferred path: launches _keyboard_helper.py as a subprocess which opens a
native full-screen tkinter window — captures ALL keys including modifiers
(Shift, Ctrl, Alt, Cmd) that the terminal intercepts before Textual can see them.

Fallback path (no display server / tkinter unavailable): runs the key diagram
inside the Textual terminal screen with partial key capture.
"""

from __future__ import annotations

import asyncio
import platform
import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Label, Static

from ..widgets.keyboard_widget import (
    KeyboardWidget,
    get_layout_path,
    list_layouts,
    load_layout,
)

_HELPER = Path(__file__).parent.parent / "_keyboard_helper.py"

# Default layout by platform
_DEFAULT_LAYOUT = {"Darwin": "macbook_us", "Windows": "full_us"}.get(
    platform.system(), "tkl_us"
)


class KeyboardTestScreen(Screen):
    """Full-screen interactive keyboard diagram."""

    # Priority bindings intercept keys that Textual/app would otherwise consume.
    BINDINGS = [
        Binding("escape",    "capture_key_escape",    show=False, priority=True),
        Binding("tab",       "capture_key_tab",       show=False, priority=True),
        Binding("shift+tab", "capture_key_shift_tab", show=False, priority=True),
        Binding("space",     "capture_key_space",     show=False, priority=True),
        Binding("enter",     "capture_key_enter",     show=False, priority=True),
        Binding("ctrl+c",    "capture_key_ctrl_c",    show=False, priority=True),
        Binding("ctrl+q",    "capture_key_ctrl_q",    show=False, priority=True),
    ]

    DEFAULT_CSS = """
    KeyboardTestScreen {
        layout: vertical;
        background: $background;
        padding: 1 2;
    }
    #header {
        text-align: center;
        color: $primary;
        text-style: bold;
        height: 1;
        margin-bottom: 1;
    }
    #layout-row {
        layout: horizontal;
        height: auto;
        margin-bottom: 1;
    }
    #layout-label {
        color: $text-muted;
        margin-right: 1;
        height: 3;
        content-align: left middle;
    }
    #layout-row Button {
        margin-right: 1;
        min-width: 14;
    }
    #keyboard {
        margin-bottom: 1;
    }
    #external-status {
        text-align: center;
        color: $text-muted;
        height: auto;
        margin: 2 4;
    }
    #instructions {
        text-align: center;
        color: $text-muted;
        height: 1;
        margin-bottom: 1;
    }
    #btn-row {
        layout: horizontal;
        height: auto;
        align: right middle;
    }
    #btn-exit {
        margin-right: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._active_layout_id = _DEFAULT_LAYOUT
        self._layouts = list_layouts()
        # Fall back to first available layout if default is missing
        available_ids = {lid for lid, _ in self._layouts}
        if self._active_layout_id not in available_ids and self._layouts:
            self._active_layout_id = self._layouts[0][0]
        self._current_layout = load_layout(get_layout_path(self._active_layout_id))

    def compose(self) -> ComposeResult:
        yield Label("⌨  Keyboard Test", id="header")

        # Shown while the external tkinter window is launching
        yield Label("", id="external-status")

        with Static(id="layout-row"):
            yield Label("Layout:", id="layout-label")
            for lid, lname in self._layouts:
                variant = "primary" if lid == self._active_layout_id else "default"
                yield Button(lname, id=f"layout-btn-{lid}", variant=variant)

        yield KeyboardWidget(self._current_layout, id="keyboard")
        yield Label(
            "Press every key — each disappears when registered.  "
            "Dimmed keys cannot be captured in a terminal.",
            id="instructions",
        )

        with Static(id="btn-row"):
            yield Button("Exit Early", variant="default",  id="btn-exit")
            yield Button("Done ✓",    variant="success",  id="btn-done")

    async def on_mount(self) -> None:
        result = await self._try_external()
        if result is not None:
            self.dismiss(result)
            return
        # External unavailable — terminal fallback
        self._update_state()

    # ------------------------------------------------------------------
    # External full-screen path
    # ------------------------------------------------------------------

    async def _try_external(self) -> bool | None:
        """
        Launch the keyboard helper as a subprocess.

        In a frozen PyInstaller binary the exe re-invokes itself with
        --run-helper keyboard.  In dev mode the helper script is called
        directly via the Python interpreter.

        Returns True/False on success, None if tkinter/display is unavailable
        (caller should fall back to terminal mode).
        """
        frozen = hasattr(sys, "_MEIPASS")
        if not frozen and not _HELPER.exists():
            return None

        # Hide terminal widgets while the external window is running
        self.query_one("#layout-row", Static).display = False
        self.query_one(KeyboardWidget).display = False
        self.query_one("#instructions", Label).display = False
        self.query_one("#btn-row", Static).display = False

        status = self.query_one("#external-status", Label)
        status.display = True
        status.update(
            "Keyboard test running in the full-screen window.\n\n"
            "Follow the on-screen instructions.\n\n"
            "When the window closes you will be returned here."
        )

        if frozen:
            cmd = [sys.executable, "--run-helper", "keyboard"]
        else:
            cmd = [sys.executable, str(_HELPER)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        rc = await proc.wait()

        if rc == 2:
            # No display / tkinter unavailable — restore terminal UI
            self.query_one("#external-status", Label).display = False
            self.query_one("#layout-row", Static).display = True
            self.query_one(KeyboardWidget).display = True
            self.query_one("#instructions", Label).display = True
            self.query_one("#btn-row", Static).display = True
            return None

        return rc == 0

    # ------------------------------------------------------------------
    # Key marking
    # ------------------------------------------------------------------

    def _mark(self, key: str) -> None:
        kbd = self.query_one(KeyboardWidget)
        if kbd.handle_key(key):
            self._update_state()

    def _update_state(self) -> None:
        kbd = self.query_one(KeyboardWidget)
        self.query_one("#header", Label).update(
            f"⌨  Keyboard Test  —  {kbd.pressed_count} / {kbd.total_keys} keys"
        )
        self.query_one("#btn-done", Button).disabled = not kbd.all_pressed

    # ------------------------------------------------------------------
    # Priority binding actions (keys Textual normally intercepts)
    # ------------------------------------------------------------------

    def action_capture_key_escape(self) -> None:
        self._mark("escape")

    def action_capture_key_tab(self) -> None:
        self._mark("tab")

    def action_capture_key_shift_tab(self) -> None:
        self._mark("shift")
        self._mark("tab")

    def action_capture_key_space(self) -> None:
        self._mark("space")

    def action_capture_key_enter(self) -> None:
        self._mark("enter")

    def action_capture_key_ctrl_c(self) -> None:
        self._mark("ctrl")
        self._mark("c")

    def action_capture_key_ctrl_q(self) -> None:
        self._mark("ctrl")
        self._mark("q")

    # ------------------------------------------------------------------
    # General key handler — catches everything else
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        event.stop()
        key = event.key
        # Split combo keys (e.g. "ctrl+a") to mark each part
        if "+" in key:
            for part in key.split("+"):
                self._mark(part)
        else:
            self._mark(key)

    # ------------------------------------------------------------------
    # Button handler
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "btn-exit":
            self.dismiss(False)
            return

        if btn_id == "btn-done":
            self.dismiss(True)
            return

        if btn_id.startswith("layout-btn-"):
            layout_id = btn_id[len("layout-btn-"):]
            self._switch_layout(layout_id)

    # ------------------------------------------------------------------
    # Layout switching
    # ------------------------------------------------------------------

    def _switch_layout(self, layout_id: str) -> None:
        try:
            new_layout = load_layout(get_layout_path(layout_id))
        except Exception:
            return

        self._active_layout_id = layout_id
        self._current_layout   = new_layout

        self.query_one(KeyboardWidget).load_layout(new_layout)

        # Update button variants
        for lid, _ in self._layouts:
            btn = self.query_one(f"#layout-btn-{lid}", Button)
            btn.variant = "primary" if lid == layout_id else "default"

        self._update_state()

"""
System readiness check screen — runs before customer info entry.

## Adding a new check
1. Create a subclass of BaseCheck anywhere below the registry section.
2. Decorate it with @register.
3. Set class attributes: key, label, description, platforms (empty = all), optional.
4. Implement run() → CheckResult.

That's it. The screen picks it up automatically.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Literal

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Label, Static

# ===========================================================================
# Types
# ===========================================================================

Status = Literal["ok", "warn", "fail", "pending"]

STATUS_ICON: dict[str, str] = {"ok": "✓", "warn": "⚠", "fail": "✗", "pending": "…"}
STATUS_COLOR: dict[str, str] = {"ok": "green", "warn": "yellow", "fail": "red", "pending": "white"}


@dataclass
class CheckResult:
    """Immutable outcome of running a single check."""

    status: Status
    detail: str
    # If set, an install button is shown for this check.
    install_cmd: list[str] = field(default_factory=list)
    install_label: str = ""
    # If True, clicking install restarts the app elevated instead of running install_cmd.
    is_elevation_action: bool = False


@dataclass
class CheckState:
    """Live state for one check as used by the screen (definition + result)."""

    key: str
    label: str
    description: str
    optional: bool
    result: CheckResult = field(default_factory=lambda: CheckResult(status="pending", detail=""))


# ===========================================================================
# Registry
# ===========================================================================

_REGISTRY: list[type[BaseCheck]] = []


def register(cls: type[BaseCheck]) -> type[BaseCheck]:
    """Decorator — registers a check so the screen discovers it automatically."""
    _REGISTRY.append(cls)
    return cls


def get_checks() -> list[BaseCheck]:
    """Return instances of all checks that apply to the current platform."""
    sys_name = platform.system()
    return [cls() for cls in _REGISTRY if not cls.platforms or sys_name in cls.platforms]


# ===========================================================================
# Base check class
# ===========================================================================


class BaseCheck:
    """
    Subclass this to add a new readiness check.

    Class attributes (set on the subclass, not in __init__):
        key         Unique string identifier.
        label       Short human-readable name shown in the UI.
        description One-line explanation of why this check matters.
        platforms   Tuple of platform.system() strings this applies to.
                    Empty tuple means the check runs on every platform.
        optional    If True, a failing result is shown as a warning, not an error.
    """

    key: str = ""
    label: str = ""
    description: str = ""
    platforms: tuple[str, ...] = ()
    optional: bool = False

    def run(self) -> CheckResult:
        raise NotImplementedError

    def to_state(self) -> CheckState:
        return CheckState(
            key=self.key,
            label=self.label,
            description=self.description,
            optional=self.optional,
        )


# ===========================================================================
# Check implementations
# — Add new checks here (or in a separate module if the list grows large).
# ===========================================================================


@register
class UnixElevationCheck(BaseCheck):
    """Checks whether the process is running as root on macOS / Linux."""

    key = "elevation"
    label = "Root / sudo Access"
    description = "Required for SMART data and full hardware access."
    platforms = ("Darwin", "Linux")

    def run(self) -> CheckResult:
        is_root = os.geteuid() == 0
        return CheckResult(
            status="ok" if is_root else "warn",
            detail=("Running as root" if is_root else "Running as regular user — some tests may be limited"),
            install_label="Restart with sudo",
            is_elevation_action=True,
        )


@register
class WindowsAdminCheck(BaseCheck):
    """Checks whether the process has Administrator rights on Windows."""

    key = "elevation"
    label = "Administrator Access"
    description = "Required for SMART data, full hardware queries, and accurate results."
    platforms = ("Windows",)

    def run(self) -> CheckResult:
        try:
            import ctypes

            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        return CheckResult(
            status="ok" if is_admin else "fail",
            detail=("Running as Administrator" if is_admin else "Not running as Administrator"),
            install_label="Restart as Admin",
            is_elevation_action=True,
        )


@register
class SmartctlCheck(BaseCheck):
    """Checks whether smartctl (smartmontools) is available on PATH."""

    key = "smartctl"
    label = "smartctl (smartmontools)"
    description = "Required for SMART drive health, serial numbers, and reallocated sector counts."
    platforms = ()  # all platforms

    # Install command varies by platform — resolved at runtime in run().
    _INSTALL: dict[str, tuple[list[str], str]] = {
        "Darwin": (["brew", "install", "smartmontools"], "brew install smartmontools"),
        "Linux": (["apt-get", "install", "-y", "smartmontools"], "apt install smartmontools"),
        "Windows": ([], "Download from smartmontools.org"),
    }

    def run(self) -> CheckResult:
        path = shutil.which("smartctl")
        if path:
            try:
                out = subprocess.run(["smartctl", "--version"], capture_output=True, text=True, timeout=5)
                version = out.stdout.splitlines()[0] if out.stdout else "unknown version"
                return CheckResult(status="ok", detail=f"Found: {path} — {version}")
            except Exception:
                return CheckResult(status="ok", detail=f"Found: {path}")

        cmd, label = self._INSTALL.get(platform.system(), ([], "Install smartmontools"))
        return CheckResult(
            status="fail",
            detail="Not found in PATH — storage SMART tests will be skipped",
            install_cmd=cmd,
            install_label=label,
        )


@register
class MacOSTempCheck(BaseCheck):
    """
    Checks whether CPU temperature data can be read on macOS.

    Preferred: mactop (Apple Silicon + Intel, no root required).
    Fallback:  osx-cpu-temp (Intel only).
    """

    key = "macos_temp"
    label = "CPU Temperature (mactop)"
    description = (
        "mactop reads CPU/GPU temps and power on Apple Silicon and Intel Macs "
        "without requiring sudo. Without it, temperature fields will be blank."
    )
    platforms = ("Darwin",)
    optional = True

    def run(self) -> CheckResult:
        if shutil.which("mactop"):
            return CheckResult(status="ok", detail=f"mactop found: {shutil.which('mactop')}")
        if shutil.which("osx-cpu-temp"):
            return CheckResult(
                status="warn",
                detail="osx-cpu-temp found (Intel only) — install mactop for Apple Silicon support",
                install_cmd=["brew", "install", "mactop"],
                install_label="brew install mactop",
            )
        return CheckResult(
            status="warn",
            detail="No temperature tool found — install mactop for CPU/GPU temp in reports",
            install_cmd=["brew", "install", "mactop"],
            install_label="brew install mactop",
        )


@register
class ReportLabCheck(BaseCheck):
    """Checks whether reportlab is installed and can generate PDFs."""

    key = "pdf"
    label = "PDF Generation (reportlab)"
    description = "Enables PDF reports alongside HTML. Pure-Python, no system libraries required."
    platforms = ()  # all platforms
    optional = True

    def run(self) -> CheckResult:
        try:
            from reportlab.platypus import SimpleDocTemplate  # noqa: F401

            import reportlab

            version = getattr(reportlab, "Version", "unknown")
            return CheckResult(status="ok", detail=f"reportlab {version} — PDF reports enabled")
        except ImportError:
            return CheckResult(
                status="warn",
                detail="reportlab not installed — HTML reports only (PDF skipped)",
                install_cmd=["pip", "install", "reportlab"],
                install_label="pip install reportlab",
            )


# ===========================================================================
# Privilege drop helper (for install commands run as root)
# ===========================================================================


def _drop_to_original_user():
    """
    Return a preexec_fn that drops back to the invoking (non-root) user.

    When launched via `sudo`, SUDO_USER holds the original username. Brew and
    most user-space package managers refuse to run as root, so we restore the
    original uid/gid before exec'ing the install command.

    Returns None (no-op) when not running as root or SUDO_USER is unset.
    """
    import pwd

    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or os.geteuid() != 0:
        return None

    try:
        pw = pwd.getpwnam(sudo_user)
        uid, gid, home = pw.pw_uid, pw.pw_gid, pw.pw_dir
    except KeyError:
        return None

    def _preexec() -> None:
        os.setgid(gid)
        os.setuid(uid)
        os.environ["HOME"] = home
        os.environ["USER"] = sudo_user
        os.environ["LOGNAME"] = sudo_user

    return _preexec


def _relaunch_elevated() -> None:
    """Re-exec the current process with elevated privileges and exit."""
    sys_name = platform.system()
    if sys_name in ("Linux", "Darwin"):
        os.execvpe("sudo", ["sudo", "-E"] + sys.argv, os.environ)
    elif sys_name == "Windows":
        import ctypes

        args = " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
        sys.exit(0)


# ===========================================================================
# Readiness screen
# ===========================================================================


class ReadinessScreen(Screen):
    DEFAULT_CSS = """
    ReadinessScreen {
        align: center middle;
    }
    #ready-panel {
        width: 82;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }
    #ready-title {
        text-align: center;
        text-style: bold;
        margin: 0 0 1 0;
    }
    #overall-status {
        margin: 0 0 1 0;
        text-align: center;
    }
    #checks-container {
        height: auto;
        max-height: 28;
    }
    #footer-row {
        layout: horizontal;
        margin: 1 0 0 0;
        height: auto;
    }
    #btn-recheck {
        width: 1fr;
        margin: 0 1 0 0;
    }
    #btn-continue {
        width: 1fr;
    }
    .install-btn {
        width: 1fr;
        margin: 0 1 0 0;
    }
    """

    # -----------------------------------------------------------------
    # Compose
    # -----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Static(id="ready-panel"):
            yield Label("System Readiness Check", id="ready-title")
            yield Label("Checking...", id="overall-status")
            with ScrollableContainer(id="checks-container"):
                yield Static(id="checks-list")
            with Static(id="footer-row"):
                yield Button("Re-check", variant="default", id="btn-recheck")
                yield Button("Continue →", variant="primary", id="btn-continue")

    def on_mount(self) -> None:
        self.call_after_refresh(self._run_all_checks)

    # -----------------------------------------------------------------
    # Check runner
    # -----------------------------------------------------------------

    async def _run_all_checks(self) -> None:
        self.query_one("#overall-status", Label).update("Running checks...")

        check_instances = get_checks()
        states = [c.to_state() for c in check_instances]

        loop = asyncio.get_event_loop()

        def _execute_all() -> None:
            for check, state in zip(check_instances, states):
                state.result = check.run()

        await loop.run_in_executor(None, _execute_all)

        self._states = states
        self._display_results(states)

    # -----------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------

    def _display_results(self, states: list[CheckState]) -> None:
        overall = self.query_one("#overall-status", Label)
        has_fail = any(s.result.status == "fail" for s in states)
        has_warn = any(s.result.status == "warn" for s in states)

        if has_fail:
            overall.update("[bold red]✗ Issues found — some tests may not work correctly[/bold red]")
        elif has_warn:
            overall.update("[bold yellow]⚠ Warnings — app will work but some features may be limited[/bold yellow]")
        else:
            overall.update("[bold green]✓ All checks passed — ready to test[/bold green]")

        lines: list[str] = []
        for state in states:
            r = state.result
            icon = STATUS_ICON[r.status]
            color = STATUS_COLOR[r.status]
            tag = ""
            if state.optional and r.status != "ok":
                tag = " [dim][optional][/dim]"
            elif not state.optional and r.status == "fail":
                tag = " [dim][required][/dim]"
            lines.append(f"[{color}]{icon}[/{color}] [bold]{state.label}[/bold]{tag}")
            lines.append(f"   [dim]{r.detail}[/dim]")
            if r.status != "ok" and r.install_label:
                action = "→ button below" if r.install_cmd or r.is_elevation_action else f"→ {r.install_label}"
                lines.append(f"   [dim]{action}[/dim]")
            lines.append("")

        self.query_one("#checks-list", Static).update("\n".join(lines))
        self._rebuild_action_buttons(states)

    def _rebuild_action_buttons(self, states: list[CheckState]) -> None:
        for btn in self.query(".install-btn"):
            btn.remove()

        footer = self.query_one("#footer-row", Static)
        recheck_btn = self.query_one("#btn-recheck")

        for state in states:
            r = state.result
            if r.status == "ok":
                continue
            if r.is_elevation_action:
                footer.mount(
                    Button(r.install_label, variant="error", id="btn-elevate", classes="install-btn"),
                    before=recheck_btn,
                )
            elif r.install_cmd:
                footer.mount(
                    Button(
                        r.install_label,
                        variant="warning",
                        id=f"install-{state.key}",
                        classes="install-btn",
                    ),
                    before=recheck_btn,
                )

    # -----------------------------------------------------------------
    # Button handling
    # -----------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "btn-continue":
            from .welcome import WelcomeScreen

            self.app.push_screen(WelcomeScreen())

        elif btn_id == "btn-recheck":
            self.call_after_refresh(self._run_all_checks)

        elif btn_id == "btn-elevate":
            _relaunch_elevated()

        elif btn_id.startswith("install-"):
            key = btn_id[len("install-") :]
            state = next((s for s in self._states if s.key == key), None)
            if state and state.result.install_cmd:
                asyncio.get_event_loop().create_task(self._install(state))

    # -----------------------------------------------------------------
    # Install runner
    # -----------------------------------------------------------------

    async def _install(self, state: CheckState) -> None:
        overall = self.query_one("#overall-status", Label)
        overall.update(f"[yellow]Installing {state.label}...[/yellow]")
        try:
            # Resolve preexec_fn on the main thread before handing off to executor.
            preexec = _drop_to_original_user() if platform.system() != "Windows" else None
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    state.result.install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    preexec_fn=preexec,
                ),
            )
            if result.returncode == 0:
                overall.update(f"[green]{state.label} installed — re-checking...[/green]")
            else:
                overall.update(f"[red]Install failed (exit {result.returncode}): {result.stderr.strip()[:120]}[/red]")
        except Exception as exc:
            overall.update(f"[red]Install error: {exc}[/red]")
        finally:
            await asyncio.sleep(1)
            await self._run_all_checks()

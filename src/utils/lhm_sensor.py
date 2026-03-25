"""
LibreHardwareMonitor sensor utility.

Locates and runs the bundled SensorDump.exe (Windows only) to get comprehensive
hardware sensor readings that are otherwise inaccessible on OEM laptops via
standard WMI/ACPI interfaces.

Priority order for callers:
  1. Bundled SensorDump.exe  (Option B — always works, no user install needed)
  2. LHM/OHM WMI namespace   (Option A — works if user has LHM installed)
  3. ACPI / psutil / etc.    (existing platform fallbacks)
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path


def _sensor_dump_exe() -> Path | None:
    """Return the path to SensorDump.exe, or None if not available / not Windows."""
    if platform.system() != "Windows":
        return None

    if getattr(sys, "frozen", False):
        # Running as a PyInstaller single-file bundle — assets are in _MEIPASS.
        exe = Path(sys._MEIPASS) / "tools" / "windows" / "SensorDump.exe"  # type: ignore[attr-defined]
    else:
        # Dev-tree: look for the publish output produced by build_sensor_dump.bat.
        repo_root = Path(__file__).resolve().parent.parent.parent
        base = repo_root / "tools" / "windows" / "sensor_dump" / "publish"
        for arch in ("x64", "arm64"):
            candidate = base / arch / "SensorDump.exe"
            if candidate.exists():
                return candidate
        return None

    return exe if exe.exists() else None


def get_all_sensors(timeout: int = 15) -> list[dict]:
    """
    Run SensorDump.exe and return all sensor readings as a list of dicts:

        [
          {"hardware": str, "parent": str|None, "type": str, "name": str, "value": float|None},
          ...
        ]

    Returns an empty list if the exe is unavailable or fails.
    Sensor types include: Temperature, Fan, Voltage, Power, Load, Clock, Data, ...
    """
    exe = _sensor_dump_exe()
    if not exe:
        return []
    try:
        r = subprocess.run(
            [str(exe)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = r.stdout.strip()
        if not out:
            return []
        return json.loads(out)
    except Exception:
        return []


def get_sensors_of_type(sensor_type: str, timeout: int = 15) -> list[dict]:
    """Return only sensors with the given SensorType name (e.g. 'Temperature', 'Fan')."""
    return [s for s in get_all_sensors(timeout=timeout) if s.get("type") == sensor_type]


def is_available() -> bool:
    """Return True if SensorDump.exe is present and Windows is the current platform."""
    return _sensor_dump_exe() is not None

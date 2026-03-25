"""Fan test: detect fans and read RPM via multiple platform paths."""

from __future__ import annotations

import asyncio
import platform
import re
import subprocess

from ..models.test_result import TestResult
from .base import BaseTest


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------


def _get_fans_windows() -> tuple[list[dict], str]:
    """
    Read fan RPMs on Windows.

    Priority:
      1. Bundled SensorDump.exe (LibreHardwareMonitor) — most reliable
      2. LibreHardwareMonitor / OpenHardwareMonitor WMI namespace (if running)

    Returns (fans, source) where source is a human-readable label.
    """
    # 1. Bundled SensorDump.exe
    try:
        from ..utils.lhm_sensor import get_sensors_of_type, is_available
        if is_available():
            raw = get_sensors_of_type("Fan")
            fans = [
                {"name": s["name"], "rpm": int(s["value"]), "hardware": s.get("hardware", "")}
                for s in raw if s.get("value") is not None
            ]
            if fans:
                return fans, "lhm_bundled"
    except Exception:
        pass

    # 2. LHM / OHM WMI namespace (opportunistic — works if user has LHM installed)
    try:
        import pythoncom  # type: ignore
        import wmi  # type: ignore

        pythoncom.CoInitialize()
        try:
            for ns in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
                try:
                    hw = wmi.WMI(namespace=ns)
                    fans = []
                    for sensor in hw.Sensor():
                        if getattr(sensor, "SensorType", "") == "Fan":
                            val = getattr(sensor, "Value", None)
                            name = getattr(sensor, "Name", "Fan")
                            hw_name = getattr(sensor, "Parent", "") or ""
                            if val is not None:
                                fans.append({
                                    "name": name,
                                    "rpm": int(float(val)),
                                    "hardware": hw_name,
                                })
                    if fans:
                        return fans, "lhm_wmi"
                except Exception:
                    continue
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        pass

    return [], "none"


# ---------------------------------------------------------------------------
# Linux helpers
# ---------------------------------------------------------------------------


def _get_fans_linux() -> tuple[list[dict], str]:
    """Read fan speeds on Linux via psutil with /sys/class/hwmon fallback."""
    import psutil

    try:
        data = psutil.sensors_fans()
        if data:
            fans = []
            for chip, entries in data.items():
                for e in entries:
                    rpm = getattr(e, "current", None)
                    if rpm is not None:
                        fans.append({
                            "name": e.label or chip,
                            "rpm": int(rpm),
                            "hardware": chip,
                        })
            if fans:
                return fans, "psutil"
    except (AttributeError, NotImplementedError):
        pass

    # /sys/class/hwmon fallback
    from pathlib import Path
    fans = []
    hwmon_root = Path("/sys/class/hwmon")
    if hwmon_root.exists():
        for hwmon in sorted(hwmon_root.iterdir()):
            chip_name = ""
            name_file = hwmon / "name"
            if name_file.exists():
                try:
                    chip_name = name_file.read_text().strip()
                except Exception:
                    pass
            for fan_input in sorted(hwmon.glob("fan*_input")):
                try:
                    rpm = int(fan_input.read_text().strip())
                    idx = re.search(r"fan(\d+)_input", fan_input.name)
                    label_file = hwmon / fan_input.name.replace("_input", "_label")
                    if label_file.exists():
                        label = label_file.read_text().strip()
                    else:
                        label = f"{chip_name} fan{idx.group(1) if idx else ''}"
                    fans.append({"name": label, "rpm": rpm, "hardware": chip_name})
                except Exception:
                    pass
    if fans:
        return fans, "hwmon"

    return [], "none"


# ---------------------------------------------------------------------------
# macOS helpers
# ---------------------------------------------------------------------------


def _get_fans_macos() -> tuple[list[dict], str]:
    """
    Read fan speeds on macOS.

    Uses powermetrics (built-in, requires sudo which Touchstone already has)
    with a 1-second sample.  Falls back to ioreg SMC sensor scan.
    """
    # powermetrics SMC sampler
    try:
        r = subprocess.run(
            ["sudo", "powermetrics", "--samplers", "smc",
             "--sample-count", "1", "--sample-rate", "1000"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        fans = []
        for line in r.stdout.splitlines():
            # "Fan: 1492 RPM" or "Fan0: 1492 RPM"
            m = re.match(r"(Fan\w*)\s*:\s*(\d+)\s*RPM", line.strip(), re.IGNORECASE)
            if m:
                fans.append({"name": m.group(1), "rpm": int(m.group(2)), "hardware": "SMC"})
        if fans:
            return fans, "powermetrics"
    except Exception:
        pass

    # ioreg SMC fan scan
    try:
        r = subprocess.run(
            ["ioreg", "-r", "-c", "IOHWSensor", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        fans = []
        current_name = ""
        current_val: int | None = None
        for line in r.stdout.splitlines():
            line = line.strip()
            if '"name"' in line and "fan" in line.lower():
                m = re.search(r'"name"\s*=\s*"([^"]+)"', line)
                if m:
                    current_name = m.group(1)
            if '"current-value"' in line or '"CurrentValue"' in line:
                m = re.search(r'=\s*(\d+)', line)
                if m and current_name:
                    current_val = int(m.group(1))
            if current_name and current_val is not None:
                fans.append({"name": current_name, "rpm": current_val, "hardware": "IOHWSensor"})
                current_name = ""
                current_val = None
        if fans:
            return fans, "ioreg"
    except Exception:
        pass

    return [], "none"


# ---------------------------------------------------------------------------
# Main test class
# ---------------------------------------------------------------------------


class FanTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()

        sys_name = platform.system()
        loop = asyncio.get_event_loop()

        if sys_name == "Windows":
            fans, source = await loop.run_in_executor(None, _get_fans_windows)
        elif sys_name == "Linux":
            fans, source = await loop.run_in_executor(None, _get_fans_linux)
        elif sys_name == "Darwin":
            fans, source = await loop.run_in_executor(None, _get_fans_macos)
        else:
            fans, source = [], "none"

        data: dict = {
            "fans": fans,
            "fan_count": len(fans),
            "source": source,
        }

        if not fans:
            skip_hint = (
                "Install LibreHardwareMonitor for Windows fan readings"
                if sys_name == "Windows"
                else "Fan sensors not exposed on this hardware"
            )
            data["card_sub_detail"] = ""
            self.result.mark_skip(f"Fan data unavailable — {skip_hint}")
            return self.result

        running = [f for f in fans if f["rpm"] > 0]
        stopped = [f for f in fans if f["rpm"] == 0]

        # Build compact display lines (up to 3 fans shown)
        rpm_parts = [
            f"{f['name']}: {f['rpm']:,} RPM"
            for f in sorted(fans, key=lambda x: -x["rpm"])[:3]
        ]
        data["card_sub_detail"] = "  ·  ".join(rpm_parts)

        fan_word = "fan" if len(fans) == 1 else "fans"

        if stopped and not running:
            self.result.mark_warn(
                summary=f"All {len(fans)} {fan_word} at 0 RPM — check cooling",
                data=data,
            )
        elif stopped:
            self.result.mark_warn(
                summary=f"{len(stopped)} of {len(fans)} {fan_word} not spinning",
                data=data,
            )
        else:
            top = rpm_parts[0] if rpm_parts else f"{len(fans)} {fan_word}"
            self.result.mark_pass(
                summary=f"{len(fans)} {fan_word} · {top}",
                data=data,
            )

        return self.result

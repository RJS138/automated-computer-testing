"""RAM test: capacity, usage, and userspace pattern scan."""

import asyncio
import ctypes
import gc

import psutil

from ..config import RAM_SCAN_MB_FULL, RAM_SCAN_MB_QUICK
from ..models.test_result import TestResult
from .base import BaseTest


def _pattern_scan(size_mb: int) -> tuple[bool, str]:
    """
    Allocate a block of memory, write a byte pattern, read it back.
    Returns (passed, message).

    NOTE: This is a userspace functional check, not a substitute for MemTest86.
    """
    size_bytes = size_mb * 1024 * 1024
    pattern = 0xA5  # 10100101 alternating bits

    try:
        buf = bytearray(size_bytes)
        # Write
        for i in range(0, size_bytes, 4096):
            buf[i] = pattern
        # Verify
        for i in range(0, size_bytes, 4096):
            if buf[i] != pattern:
                return False, f"Pattern mismatch at offset {i}"
        del buf
        gc.collect()
        return True, "Pattern scan passed"
    except MemoryError:
        return False, "MemoryError: insufficient RAM for scan"
    except Exception as exc:
        return False, f"Scan error: {exc}"


class RamTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        data: dict = {
            "total_gb": round(vm.total / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "used_percent": vm.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
        }

        # Attempt to read RAM speed (Windows via wmi, Linux via dmidecode)
        data["speed_mhz"] = await _get_ram_speed()

        # Pattern scan
        scan_mb = RAM_SCAN_MB_QUICK if self.is_quick() else RAM_SCAN_MB_FULL
        # Don't scan more than 50% of available RAM
        max_scan = int(vm.available / (1024**2) * 0.5)
        scan_mb = min(scan_mb, max_scan)
        data["scan_mb"] = scan_mb

        loop = asyncio.get_event_loop()
        scan_ok, scan_msg = await loop.run_in_executor(None, _pattern_scan, scan_mb)

        data["scan_passed"] = scan_ok
        data["scan_message"] = scan_msg

        summary = (
            f"{data['total_gb']} GB total, "
            f"{data['used_percent']}% used — {scan_msg}"
        )

        if not scan_ok:
            self.result.mark_fail(summary=summary, data=data)
        else:
            self.result.mark_pass(summary=summary, data=data)

        return self.result


async def _get_ram_speed() -> str | None:
    """Try to get RAM speed from platform-specific sources."""
    import platform
    loop = asyncio.get_event_loop()

    if platform.system() == "Windows":
        return await loop.run_in_executor(None, _ram_speed_windows)
    elif platform.system() == "Linux":
        return await loop.run_in_executor(None, _ram_speed_linux)
    elif platform.system() == "Darwin":
        return await loop.run_in_executor(None, _ram_speed_darwin)
    return None


def _ram_speed_windows() -> str | None:
    try:
        import wmi  # type: ignore
        c = wmi.WMI()
        speeds = [str(m.Speed) for m in c.Win32_PhysicalMemory() if m.Speed]
        return ", ".join(set(speeds)) + " MHz" if speeds else None
    except Exception:
        return None


def _ram_speed_darwin() -> str | None:
    import subprocess
    try:
        result = subprocess.run(
            ["system_profiler", "SPMemoryDataType"],
            capture_output=True, text=True, timeout=10,
        )
        speeds = []
        mem_type = None
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Speed:"):
                speed = stripped.split(":", 1)[1].strip()
                if speed and speed != "Unknown" and speed not in speeds:
                    speeds.append(speed)
            elif stripped.startswith("Type:") and not mem_type:
                mem_type = stripped.split(":", 1)[1].strip()
        parts = []
        if speeds:
            parts.append(", ".join(speeds))
        if mem_type and mem_type not in ("Unknown", "LPDDR5", ""):
            # Apple Silicon unified memory doesn't expose speed via this path
            pass
        elif mem_type:
            parts.append(f"({mem_type})")
        return " ".join(parts) if parts else None
    except Exception:
        return None


def _ram_speed_linux() -> str | None:
    import subprocess
    try:
        result = subprocess.run(
            ["dmidecode", "-t", "17"],
            capture_output=True, text=True, timeout=5
        )
        speeds = []
        for line in result.stdout.splitlines():
            if "Speed:" in line and "Unknown" not in line:
                parts = line.split(":")
                if len(parts) == 2:
                    speed = parts[1].strip()
                    if speed not in speeds:
                        speeds.append(speed)
        return ", ".join(speeds) if speeds else None
    except Exception:
        return None

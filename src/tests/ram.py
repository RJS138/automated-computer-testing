"""RAM test: capacity, usage, and userspace pattern scan."""

import asyncio
import ctypes
import gc
import time

import psutil

from ..config import RAM_SCAN_MB_FULL, RAM_SCAN_MB_QUICK
from ..models.test_result import TestResult
from .base import BaseTest

# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

# Six classical memory-test patterns: alternating bits (two phases),
# all-ones, all-zeros, and their complements.  Each pattern stresses
# different failure modes (stuck bits, bridging, data retention).
_PATTERNS: list[tuple[int, str]] = [
    (0xA5, "alternating A (10100101)"),
    (0x5A, "alternating B (01011010)"),
    (0xFF, "all ones"),
    (0x00, "all zeros"),
    (0x55, "low alternating (01010101)"),
    (0xAA, "high alternating (10101010)"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fill(buf: bytearray, pattern_byte: int) -> None:
    """Fill *buf* in-place with pattern_byte using C memset — near-RAM-bandwidth speed."""
    ctypes.memset(
        ctypes.addressof(ctypes.c_char.from_buffer(buf)),
        pattern_byte,
        len(buf),
    )


def _first_bad(buf: bytearray, pattern_byte: int) -> int | None:
    """
    Return the index of the first byte that doesn't match pattern_byte, or None.

    Uses bytearray.count() — O(n) C-level scan — to avoid a slow Python loop
    unless a failure is actually detected (uncommon path).
    """
    if buf.count(bytes([pattern_byte])) == len(buf):
        return None
    # Slow path: only reached when corruption is detected
    for i, b in enumerate(buf):
        if b != pattern_byte:
            return i
    return None  # unreachable


# ---------------------------------------------------------------------------
# Quick scan: single pattern, full write+verify, with bandwidth measurement
# ---------------------------------------------------------------------------


def _quick_scan(size_mb: int) -> tuple[bool, str, dict]:
    """
    Single-pattern full scan (quick mode).

    Writes 0xA5 to every byte, reads back and verifies every byte.
    Returns (passed, message, metrics).
    """
    size_bytes = size_mb * 1024 * 1024
    pattern_byte = 0xA5
    metrics: dict = {}

    try:
        buf = bytearray(size_bytes)

        t0 = time.monotonic()
        _fill(buf, pattern_byte)
        write_s = time.monotonic() - t0

        t0 = time.monotonic()
        bad = _first_bad(buf, pattern_byte)
        read_s = time.monotonic() - t0

        metrics["patterns_tested"] = 1
        metrics["ram_write_mb_s"] = round(size_mb / write_s) if write_s > 0 else None
        metrics["ram_read_mb_s"] = round(size_mb / read_s) if read_s > 0 else None

        del buf
        gc.collect()

        if bad is not None:
            return (
                False,
                f"Memory error: pattern 0x{pattern_byte:02X} mismatch at byte {bad}",
                metrics,
            )
        return True, "Pattern scan passed (0xA5 — quick)", metrics

    except MemoryError:
        return False, "MemoryError: insufficient RAM for scan", metrics
    except Exception as exc:
        return False, f"Scan error: {exc}", metrics


# ---------------------------------------------------------------------------
# Full scan: 6 patterns, every byte, bandwidth measurement
# ---------------------------------------------------------------------------


def _full_scan(size_mb: int) -> tuple[bool, str, dict]:
    """
    Multi-pattern full RAM scan (full mode).

    Runs all 6 patterns over the entire allocation.  Uses a single buffer
    allocation reused across patterns to avoid extra GC pressure.
    Reports effective write and read memory bandwidth averaged across all passes.
    """
    size_bytes = size_mb * 1024 * 1024
    metrics: dict = {"patterns_tested": 0, "patterns_failed": []}
    total_write_s = 0.0
    total_read_s = 0.0

    try:
        buf = bytearray(size_bytes)

        for pattern_byte, pattern_name in _PATTERNS:
            t0 = time.monotonic()
            _fill(buf, pattern_byte)
            write_s = time.monotonic() - t0
            total_write_s += write_s

            t0 = time.monotonic()
            bad = _first_bad(buf, pattern_byte)
            read_s = time.monotonic() - t0
            total_read_s += read_s

            metrics["patterns_tested"] += 1

            if bad is not None:
                metrics["patterns_failed"].append(pattern_name)
                del buf
                gc.collect()
                return (
                    False,
                    f"Memory error: {pattern_name} — mismatch at byte {bad} "
                    f"(expected 0x{pattern_byte:02X})",
                    metrics,
                )

        n = len(_PATTERNS)
        total_mb = size_mb * n
        metrics["ram_write_mb_s"] = round(total_mb / total_write_s) if total_write_s > 0 else None
        metrics["ram_read_mb_s"] = round(total_mb / total_read_s) if total_read_s > 0 else None

        del buf
        gc.collect()
        return True, f"All {n} patterns passed", metrics

    except MemoryError:
        return False, "MemoryError: insufficient RAM for full scan", metrics
    except Exception as exc:
        return False, f"Scan error: {exc}", metrics


# ---------------------------------------------------------------------------
# Main test class
# ---------------------------------------------------------------------------


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

        # Cap scan size at 50% of available RAM
        scan_mb = RAM_SCAN_MB_QUICK if self.is_quick() else RAM_SCAN_MB_FULL
        max_scan = int(vm.available / (1024**2) * 0.5)
        scan_mb = min(scan_mb, max_scan)
        data["scan_mb"] = scan_mb

        loop = asyncio.get_event_loop()
        if self.is_quick():
            scan_ok, scan_msg, scan_metrics = await loop.run_in_executor(None, _quick_scan, scan_mb)
        else:
            scan_ok, scan_msg, scan_metrics = await loop.run_in_executor(None, _full_scan, scan_mb)

        data["scan_passed"] = scan_ok
        data["scan_message"] = scan_msg
        data.update(scan_metrics)

        # Build card display lines
        patterns = scan_metrics.get("patterns_tested", 1)
        write_mb_s = scan_metrics.get("ram_write_mb_s")
        read_mb_s = scan_metrics.get("ram_read_mb_s")

        bw_parts = []
        if write_mb_s:
            bw_parts.append(f"W {write_mb_s:,} MB/s")
        if read_mb_s:
            bw_parts.append(f"R {read_mb_s:,} MB/s")
        bw_str = " · ".join(bw_parts)

        data["card_sub_detail"] = bw_str or f"{data['total_gb']} GB · {data['used_percent']}% used"

        if not scan_ok:
            self.result.mark_fail(
                summary=f"Memory error: {scan_msg}",
                data=data,
            )
        else:
            pat_str = f"{patterns} pattern{'s' if patterns > 1 else ''}"
            self.result.mark_pass(
                summary=f"Scan OK · {pat_str} · {scan_mb} MB",
                data=data,
            )

        return self.result


# ---------------------------------------------------------------------------
# RAM speed helpers
# ---------------------------------------------------------------------------


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
            capture_output=True,
            text=True,
            timeout=10,
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
            ["dmidecode", "-t", "17"], capture_output=True, text=True, timeout=5
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

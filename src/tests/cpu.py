"""CPU test: model info, stress test, temperature monitoring."""

import asyncio
import hashlib
import platform
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import psutil

from ..config import CPU_STRESS_FULL, CPU_STRESS_QUICK
from ..thresholds import get_cpu_thresholds
from ..models.test_result import TestResult
from .base import BaseTest


# ---------------------------------------------------------------------------
# CPU stress worker
# ---------------------------------------------------------------------------

def _cpu_worker(duration_seconds: float) -> None:
    """
    Burn CPU for `duration_seconds` per thread.
    hashlib.sha256 releases the GIL so threads genuinely run on separate cores.
    ThreadPoolExecutor avoids the macOS spawn/fd conflict that breaks ProcessPoolExecutor.
    """
    end = time.monotonic() + duration_seconds
    data = b"pc-tester-stress" * 4096  # 64 KB block
    while time.monotonic() < end:
        hashlib.sha256(data).digest()


# ---------------------------------------------------------------------------
# Temperature helpers
# ---------------------------------------------------------------------------

def _get_cpu_temps() -> list[float]:
    """Return a flat list of CPU core temps in °C (empty if unavailable)."""
    if platform.system() == "Darwin":
        return _get_cpu_temps_macos()

    try:
        sensors = psutil.sensors_temperatures()
        if not sensors:
            return []
        for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
            if key in sensors:
                return [e.current for e in sensors[key]]
        first = next(iter(sensors.values()))
        return [e.current for e in first]
    except (AttributeError, NotImplementedError):
        return []


def _read_mactop_sample() -> dict:
    """
    Run `mactop --headless --count 1 --format json` and return the parsed sample dict.
    Returns {} if mactop is not installed or fails.
    No root required.
    """
    import json
    try:
        pm = subprocess.run(
            ["mactop", "--headless", "--count", "1", "--format", "json"],
            capture_output=True, text=True, timeout=10,
        )
        if pm.returncode == 0 and pm.stdout.strip():
            samples = json.loads(pm.stdout)
            return samples[0] if isinstance(samples, list) else samples
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return {}


def _get_cpu_temps_powermetrics() -> list[float]:
    """
    Intel Mac fallback: read CPU die temp via powermetrics (built-in macOS, needs root).
    Tries running directly (works if already root), then sudo -n (passwordless sudo).
    """
    for cmd in (
        ["powermetrics", "-n", "1", "-i", "500", "--samplers", "smc"],
        ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500", "--samplers", "smc"],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                m = re.search(r"CPU die temperature:\s*([\d.]+)", r.stdout, re.IGNORECASE)
                if m:
                    t = float(m.group(1))
                    if t > 0:
                        return [t]
        except Exception:
            pass
    return []


def _get_cpu_temps_macos() -> list[float]:
    """
    Read CPU temperature on macOS.
    1. mactop        — Apple Silicon (no root required; brew install mactop).
    2. powermetrics  — Intel Mac (built-in macOS, needs root/sudo).
    3. osx-cpu-temp  — Intel legacy fallback binary.
    """
    sample = _read_mactop_sample()
    if sample:
        soc = sample.get("soc_metrics", {})
        cpu_temp = soc.get("cpu_temp") or soc.get("soc_temp")
        if cpu_temp and float(cpu_temp) > 0:
            return [float(cpu_temp)]

    # Intel Mac — powermetrics is built-in
    if platform.machine() != "arm64":
        temps = _get_cpu_temps_powermetrics()
        if temps:
            return temps

    # osx-cpu-temp legacy fallback
    try:
        pm = subprocess.run(
            ["osx-cpu-temp"], capture_output=True, text=True, timeout=5,
        )
        if pm.returncode == 0:
            match = re.search(r"([\d.]+)", pm.stdout)
            if match:
                t = float(match.group(1))
                if t > 0:
                    return [t]
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return []


def _temp_unavailable_note() -> str:
    if platform.machine() == "arm64":
        return (
            "CPU temperature unavailable. Install mactop for Apple Silicon support:\n"
            "  brew install mactop"
        )
    return (
        "CPU temperature unavailable. Run as root for powermetrics temp access:\n"
        "  sudo \"./PC Tester (Intel)\""
    )


def _is_mac_fanless() -> bool:
    """True if this Mac has no fan (MacBook Air)."""
    try:
        r = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            capture_output=True, text=True, timeout=3,
        )
        return "air" in r.stdout.strip().lower()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Clock speed helpers
# ---------------------------------------------------------------------------

def _get_clock_speed_macos() -> str | None:
    """
    Get CPU clock speed on macOS.
    • Intel Macs: sysctl hw.cpufrequency_max
    • Apple Silicon: not exposed via sysctl; parse system_profiler for Intel
      fallback, otherwise return None (chip name is the meaningful identifier).
    """
    # Intel path
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.cpufrequency_max"],
            capture_output=True, text=True, timeout=3,
        )
        freq_hz = int(result.stdout.strip())
        if freq_hz > 0:
            return f"{freq_hz / 1e9:.2f} GHz"
    except Exception:
        pass

    # system_profiler fallback (Intel shows "Processor Speed:")
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "Processor Speed:" in line:
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    # Apple Silicon: frequency not exposed via standard interfaces
    return None


# ---------------------------------------------------------------------------
# Main test class
# ---------------------------------------------------------------------------

class CpuTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()

        data: dict = {}

        # --- CPU info ---
        try:
            import cpuinfo  # type: ignore
            info = cpuinfo.get_cpu_info()
            data["brand"] = info.get("brand_raw") or "Unknown"
            data["arch"] = info.get("arch") or "Unknown"
            # hz_advertised_friendly is None on Apple Silicon
            data["hz_advertised"] = info.get("hz_advertised_friendly") or None
        except Exception:
            data["brand"] = "Unknown"
            data["arch"] = "Unknown"
            data["hz_advertised"] = None

        # macOS fallback for clock speed
        if not data["hz_advertised"] and platform.system() == "Darwin":
            data["hz_advertised"] = _get_clock_speed_macos()

        # Apple Silicon note when frequency truly isn't available
        if not data["hz_advertised"] and platform.system() == "Darwin":
            data["hz_advertised"] = "N/A (Apple Silicon — heterogeneous cores, no single clock)"

        data["physical_cores"] = psutil.cpu_count(logical=False) or 0
        data["logical_cores"] = psutil.cpu_count(logical=True) or 0

        # --- Idle/baseline temp ---
        loop = asyncio.get_event_loop()
        temps_before = await loop.run_in_executor(None, _get_cpu_temps)
        data["temp_idle"] = round(max(temps_before), 1) if temps_before else None

        if not temps_before and platform.system() == "Darwin":
            data["temp_note"] = _temp_unavailable_note()

        # --- Stress test ---
        duration = CPU_STRESS_QUICK if self.is_quick() else CPU_STRESS_FULL
        num_workers = data["logical_cores"] or 2

        peak_temp: list[float] = []

        async def monitor_temps(stop_event: asyncio.Event) -> None:
            while not stop_event.is_set():
                temps = await loop.run_in_executor(None, _get_cpu_temps)
                if temps:
                    peak_temp.append(max(temps))
                await asyncio.sleep(2)

        stop_event = asyncio.Event()
        monitor_task = asyncio.create_task(monitor_temps(stop_event))

        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [
                    loop.run_in_executor(executor, _cpu_worker, float(duration))
                    for _ in range(num_workers)
                ]
                await asyncio.gather(*futures)
        finally:
            stop_event.set()
            await monitor_task

        # --- Post-stress metrics ---
        data["stress_duration_s"] = duration
        data["temp_peak"] = round(max(peak_temp), 1) if peak_temp else None

        # Grab extended mactop metrics (GPU temp, power) if available
        mactop_sample = await loop.run_in_executor(None, _read_mactop_sample)
        if mactop_sample:
            soc = mactop_sample.get("soc_metrics", {})
            gpu_temp = soc.get("gpu_temp")
            if gpu_temp and float(gpu_temp) > 0:
                data["gpu_temp"] = round(float(gpu_temp), 1)
            cpu_power = soc.get("cpu_power")
            if cpu_power is not None:
                data["cpu_power_w"] = round(float(cpu_power), 2)
            total_power = soc.get("total_power")
            if total_power is not None:
                data["total_power_w"] = round(float(total_power), 2)

        # --- Determine thresholds for this CPU ---
        has_battery = psutil.sensors_battery() is not None
        is_fanless = _is_mac_fanless() if platform.system() == "Darwin" else False
        thresh = get_cpu_thresholds(
            data.get("brand", "Unknown"),
            platform.system(),
            has_battery,
            is_fanless,
        )
        data["cpu_family"] = thresh["family"]
        data["temp_thresh_idle_warn"] = thresh["idle_warn"]
        data["temp_thresh_load_warn"] = thresh["load_warn"]
        data["temp_thresh_fail"] = thresh["fail"]
        if thresh.get("note"):
            data["temp_thresh_note"] = thresh["note"]

        # --- Determine status ---
        peak = data["temp_peak"]
        idle = data["temp_idle"]

        if peak is not None and peak >= thresh["fail"]:
            self.result.mark_fail(
                summary=f"CPU overheating: peak {peak}°C (limit {thresh['fail']}°C)",
                data=data,
            )
        elif peak is not None and peak >= thresh["load_warn"]:
            note_suffix = " — see report for spec details" if thresh.get("note") else ""
            self.result.mark_warn(
                summary=f"CPU running hot: peak {peak}°C (warn ≥{thresh['load_warn']}°C{note_suffix})",
                data=data,
            )
        elif idle is not None and idle >= thresh["idle_warn"]:
            self.result.mark_warn(
                summary=f"CPU idle temp elevated: {idle}°C (warn ≥{thresh['idle_warn']}°C) — check cooling",
                data=data,
            )
        else:
            freq_str = data.get("hz_advertised") or "N/A"
            temp_str = f"{peak}°C" if peak is not None else "N/A (see report)"
            self.result.mark_pass(
                summary=f"{data['brand']} — {data['logical_cores']} threads — "
                        f"{freq_str} — peak temp {temp_str}",
                data=data,
            )

        return self.result

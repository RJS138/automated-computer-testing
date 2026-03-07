"""GPU test: model, VRAM, temperature — NVIDIA/AMD/Intel."""

import asyncio
import platform
import subprocess

from ..models.test_result import TestResult
from .base import BaseTest


def _query_nvidia() -> list[dict]:
    """Query NVIDIA GPUs via pynvml."""
    gpus = []
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode()
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = None
            try:
                fan = pynvml.nvmlDeviceGetFanSpeed(handle)
            except Exception:
                fan = None
            gpus.append({
                "vendor": "NVIDIA",
                "name": name,
                "vram_total_mb": round(mem_info.total / (1024**2)),
                "vram_used_mb": round(mem_info.used / (1024**2)),
                "temp_c": temp,
                "fan_pct": fan,
            })
        pynvml.nvmlShutdown()
    except Exception:
        pass
    return gpus


def _query_gputil() -> list[dict]:
    """Fallback: query GPUs via GPUtil (wraps nvidia-smi)."""
    gpus = []
    try:
        import GPUtil  # type: ignore
        for g in GPUtil.getGPUs():
            gpus.append({
                "vendor": "NVIDIA",
                "name": g.name,
                "vram_total_mb": round(g.memoryTotal),
                "vram_used_mb": round(g.memoryUsed),
                "temp_c": g.temperature,
                "fan_pct": None,
            })
    except Exception:
        pass
    return gpus


def _query_windows_wmi() -> list[dict]:
    """Query all GPU adapters via WMI (Windows)."""
    gpus = []
    try:
        import wmi  # type: ignore
        c = wmi.WMI()
        for v in c.Win32_VideoController():
            gpus.append({
                "vendor": v.AdapterCompatibility or "Unknown",
                "name": v.Name or "Unknown",
                "vram_total_mb": round(int(v.AdapterRAM or 0) / (1024**2)) if v.AdapterRAM else None,
                "vram_used_mb": None,
                "temp_c": None,
                "fan_pct": None,
                "driver_version": v.DriverVersion,
            })
    except Exception:
        pass
    return gpus


def _query_linux_lspci() -> list[dict]:
    """
    Parse GPU info on Linux: lspci for name/vendor, sysfs for VRAM.
    /sys/class/drm/cardN/device/mem_info_vram_total — AMD
    /proc/driver/nvidia/gpuinfo                     — NVIDIA (fallback)
    """
    from pathlib import Path
    gpus = []
    try:
        result = subprocess.run(
            ["lspci", "-v", "-k"],
            capture_output=True, text=True, timeout=5
        )
        current: dict | None = None
        for line in result.stdout.splitlines():
            if "VGA compatible controller" in line or "3D controller" in line or "Display controller" in line:
                if current:
                    gpus.append(current)
                current = {
                    "vendor": "Unknown",
                    "name": line.split(":", 2)[-1].strip(),
                    "vram_total_mb": None,
                    "vram_used_mb": None,
                    "temp_c": None,
                    "fan_pct": None,
                }
                for vendor in ("NVIDIA", "AMD", "Intel", "ATI"):
                    if vendor.lower() in line.lower():
                        current["vendor"] = vendor
                        break
        if current:
            gpus.append(current)
    except Exception:
        pass

    # Enrich with VRAM from sysfs (works for AMD and some Intel iGPUs)
    try:
        drm = Path("/sys/class/drm")
        for card in sorted(drm.glob("card[0-9]")):
            vram_file = card / "device" / "mem_info_vram_total"
            used_file = card / "device" / "mem_info_vram_used"
            if vram_file.exists():
                vram_mb = round(int(vram_file.read_text().strip()) / (1024 ** 2))
                used_mb = round(int(used_file.read_text().strip()) / (1024 ** 2)) if used_file.exists() else None
                # Match to a GPU that doesn't have VRAM yet
                for g in gpus:
                    if g["vram_total_mb"] is None and g["vendor"] in ("AMD", "ATI", "Intel", "Unknown"):
                        g["vram_total_mb"] = vram_mb
                        if used_mb is not None:
                            g["vram_used_mb"] = used_mb
                        break
    except Exception:
        pass

    return gpus


def _parse_vram_to_mb(vram_str: str) -> int | None:
    """Convert '1536 MB' or '1 GB' or '8 GB' to integer MB."""
    try:
        parts = vram_str.strip().split()
        val = float(parts[0].replace(",", ""))
        unit = parts[1].upper() if len(parts) > 1 else "MB"
        return int(val * 1024) if unit == "GB" else int(val)
    except Exception:
        return None


def _get_macos_total_ram_mb() -> int | None:
    """Return total physical RAM in MB via sysctl hw.memsize."""
    try:
        r = subprocess.run(["sysctl", "-n", "hw.memsize"],
                           capture_output=True, text=True, timeout=3)
        return round(int(r.stdout.strip()) / (1024 ** 2))
    except Exception:
        return None


def _query_macos_system_profiler() -> list[dict]:
    """
    Parse system_profiler SPDisplaysDataType (JSON) on macOS.

    Apple Silicon: no discrete VRAM — GPU uses unified memory.
                   Reports total RAM as 'unified_memory_mb' and sets
                   vram_note so the report can display it correctly.
    Intel Macs:    VRAM reported in 'spdisplays_vram' JSON field.
    """
    import json as _json
    gpus = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True, text=True, timeout=10,
        )
        data = _json.loads(result.stdout)
        entries = data.get("SPDisplaysDataType", [])
        for entry in entries:
            name = entry.get("sppci_model") or entry.get("_name", "Unknown GPU")
            vendor = "Unknown"
            for v in ("Apple", "NVIDIA", "AMD", "ATI", "Intel"):
                if v.lower() in name.lower():
                    vendor = v
                    break

            gpu: dict = {
                "vendor": vendor,
                "name": name,
                "vram_total_mb": None,
                "vram_used_mb": None,
                "temp_c": None,
                "fan_pct": None,
            }

            # GPU core count (Apple Silicon exposes this)
            cores = entry.get("sppci_cores")
            if cores:
                gpu["gpu_cores"] = int(cores)

            # Metal support level
            metal = entry.get("spdisplays_mtlgpufamilysupport") or entry.get("spdisplays_metal")
            if metal:
                gpu["metal_support"] = metal.replace("spdisplays_", "").replace("metal", "Metal ")

            # VRAM — Intel discrete/integrated
            vram_str = entry.get("spdisplays_vram") or entry.get("spdisplays_vram_shared_system_memory")
            if vram_str:
                gpu["vram_total_mb"] = _parse_vram_to_mb(str(vram_str))

            # Apple Silicon: unified memory — no discrete VRAM
            if vendor == "Apple" and gpu["vram_total_mb"] is None:
                total_ram_mb = _get_macos_total_ram_mb()
                gpu["unified_memory_mb"] = total_ram_mb
                gpu["vram_note"] = (
                    f"Unified Memory: {round(total_ram_mb / 1024)} GB "
                    f"(shared between CPU and GPU)"
                ) if total_ram_mb else "Unified Memory (shared)"

            gpus.append(gpu)
    except Exception:
        pass
    return gpus


class GpuTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()
        loop = asyncio.get_event_loop()

        gpus: list[dict] = []

        # 1. Try NVIDIA via pynvml (most detailed)
        nvidia = await loop.run_in_executor(None, _query_nvidia)
        if not nvidia:
            nvidia = await loop.run_in_executor(None, _query_gputil)
        gpus.extend(nvidia)

        # 2. Platform-specific fallback for non-NVIDIA or additional GPUs
        sys = platform.system()
        if sys == "Windows":
            wmi_gpus = await loop.run_in_executor(None, _query_windows_wmi)
            # Merge: add WMI entries not already covered by pynvml
            nvidia_names = {g["name"] for g in gpus}
            for g in wmi_gpus:
                if g["name"] not in nvidia_names:
                    gpus.append(g)
        elif sys == "Linux":
            lspci_gpus = await loop.run_in_executor(None, _query_linux_lspci)
            if not gpus:
                gpus = lspci_gpus
        elif sys == "Darwin":
            mac_gpus = await loop.run_in_executor(None, _query_macos_system_profiler)
            # Merge: pynvml entries take priority, add any Apple/AMD/Intel not already found
            nvidia_names = {g["name"] for g in gpus}
            for g in mac_gpus:
                if g["name"] not in nvidia_names:
                    gpus.append(g)

        data: dict = {"gpus": gpus}

        if not gpus:
            self.result.mark_warn(
                summary="No GPU detected or query failed",
                data=data,
            )
        else:
            names = ", ".join(g.get("name", "Unknown") for g in gpus)
            self.result.mark_pass(
                summary=f"{len(gpus)} GPU(s): {names}",
                data=data,
            )

        return self.result

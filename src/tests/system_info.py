"""System info: BIOS version, board make/model/serial, OS info."""

import asyncio
import platform
import subprocess

from ..models.test_result import TestResult
from .base import BaseTest


def _get_info_windows() -> dict:
    info: dict = {}
    try:
        import wmi  # type: ignore

        c = wmi.WMI()

        for bios in c.Win32_BIOS():
            info["bios_vendor"] = bios.Manufacturer
            info["bios_version"] = bios.SMBIOSBIOSVersion
            info["bios_date"] = bios.ReleaseDate
            info["board_serial"] = bios.SerialNumber

        for board in c.Win32_BaseBoard():
            info["board_manufacturer"] = board.Manufacturer
            info["board_model"] = board.Product
            info["board_serial"] = info.get("board_serial") or board.SerialNumber

        for cs in c.Win32_ComputerSystem():
            info["chassis_manufacturer"] = cs.Manufacturer
            info["chassis_model"] = cs.Model

        for sys in c.Win32_OperatingSystem():
            info["os_name"] = sys.Caption
            info["os_version"] = sys.Version
            info["os_build"] = sys.BuildNumber
            info["install_date"] = sys.InstallDate

        # CPU details
        try:
            procs = c.Win32_Processor()
            if procs:
                cpu = procs[0]
                info["processor_marketing"] = cpu.Name.strip() if cpu.Name else None
                physical = getattr(cpu, "NumberOfCores", None)
                logical = getattr(cpu, "NumberOfLogicalProcessors", None)
                if physical and logical:
                    info["cpu_cores"] = f"{physical} cores / {logical} threads"
                elif physical:
                    info["cpu_cores"] = f"{physical} cores"
        except Exception:
            pass

        # RAM total
        try:
            total_bytes = sum(int(m.Capacity) for m in c.Win32_PhysicalMemory() if m.Capacity)
            if total_bytes:
                info["ram_total"] = f"{total_bytes / (1024**3):.0f} GB"
        except Exception:
            pass

        # GPU(s)
        try:
            gpu_list = []
            for gpu in c.Win32_VideoController():
                name = (gpu.Name or "").strip()
                if not name:
                    continue
                vram_bytes = getattr(gpu, "AdapterRAM", None)
                vram_str = (
                    f"{int(vram_bytes) / (1024**3):.0f} GB VRAM"
                    if vram_bytes and int(vram_bytes) > 0
                    else ""
                )
                entry = name
                if vram_str:
                    entry += f" ({vram_str})"
                gpu_list.append(entry)
            if gpu_list:
                info["gpu_list"] = gpu_list
        except Exception:
            pass

        # Storage
        try:
            storage_list = []
            for disk in c.Win32_DiskDrive():
                name = (disk.Model or disk.Caption or "").strip()
                size_bytes = int(disk.Size) if disk.Size else 0
                size_gb = size_bytes / (1024**3)
                entry = name
                if size_gb:
                    entry += f" · {size_gb:.0f} GB"
                if entry:
                    storage_list.append(entry)
            if storage_list:
                info["storage_list"] = storage_list
        except Exception:
            pass

    except Exception as exc:
        info["error"] = str(exc)
    return info


def _get_info_darwin() -> dict:
    """Query system info on macOS using system_profiler, sw_vers, and sysctl."""
    import json
    import re

    info: dict = {}

    # OS version
    try:
        result = subprocess.run(["sw_vers"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if "ProductName:" in line:
                info["os_name"] = line.split(":", 1)[1].strip()
            elif "ProductVersion:" in line:
                info["os_version"] = line.split(":", 1)[1].strip()
            elif "BuildVersion:" in line:
                info["os_build"] = line.split(":", 1)[1].strip()
    except Exception:
        pass

    # Hardware info via system_profiler
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Model Name:"):
                info["chassis_model"] = line.split(":", 1)[1].strip()
            elif line.startswith("Model Identifier:"):
                info["board_model"] = line.split(":", 1)[1].strip()
            elif "Serial Number" in line:
                info["board_serial"] = line.split(":", 1)[1].strip()
            elif line.startswith("Boot ROM Version:"):
                # Intel Macs
                info["bios_version"] = line.split(":", 1)[1].strip()
            elif line.startswith("System Firmware Version:"):
                # Apple Silicon Macs
                info["bios_version"] = line.split(":", 1)[1].strip()
            elif line.startswith("Chip:") or line.startswith("Processor Name:"):
                info["processor_marketing"] = line.split(":", 1)[1].strip()
            elif line.startswith("Total Number of Cores:"):
                info["cpu_cores"] = line.split(":", 1)[1].strip()
            elif line.startswith("Memory:"):
                info["ram_total"] = line.split(":", 1)[1].strip()
    except Exception:
        pass

    # Firmware build date from kernel version string
    # e.g. "Darwin Kernel Version 25.3.0: Wed Jan 28 20:56:35 PST 2026; ..."
    try:
        result = subprocess.run(
            ["sysctl", "-n", "kern.version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        kern = result.stdout.strip()
        # Format: "... Wed Jan 28 20:56:35 PST 2026; ..."
        match = re.search(r":\s+\w+\s+(\w{3}\s+\d{1,2})\s+[\d:]+\s+\w+\s+(\d{4})", kern)
        if match:
            info["bios_date"] = f"{match.group(1)} {match.group(2)}"  # e.g. "Jan 28 2026"
    except Exception:
        pass

    # Regulatory model number (A-number printed on device, e.g. "A1502")
    # Apple Silicon stores it as hex-encoded bytes: <413135303200>
    # Intel Macs store it as a plain string: "A1502"
    try:
        result = subprocess.run(
            ["ioreg", "-c", "IOPlatformExpertDevice", "-r", "-d", "2"],
            capture_output=True,
            timeout=8,
        )
        stdout = result.stdout.decode("utf-8", errors="ignore")

        # Try plain string format first (Intel Macs)
        m = re.search(r'"regulatory-model-number"\s*=\s*"([^"]+)"', stdout)
        if m:
            raw = m.group(1).strip()
        else:
            # Hex-encoded format (Apple Silicon)
            m = re.search(r'"regulatory-model-number"\s*=\s*<([0-9a-fA-F]+)>', stdout)
            raw = (
                bytes.fromhex(m.group(1)).rstrip(b"\x00").decode("ascii", errors="ignore")
                if m
                else ""
            )

        if re.match(r"^A\d{4}$", raw):
            info["apple_model_number"] = raw
    except Exception:
        pass

    # GPU(s) from SPDisplaysDataType
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        gpu_data = json.loads(result.stdout)
        gpu_list = []
        for gpu in gpu_data.get("SPDisplaysDataType", []):
            name = gpu.get("_name", "").strip()
            if not name:
                continue
            vram = gpu.get("spdisplays_vram", "").strip()
            cores = gpu.get("spdisplays_cores", "").strip()
            parts = [name]
            details = []
            if vram and vram.lower() not in ("shared", "dynamic, max"):
                details.append(vram)
            if cores:
                details.append(f"{cores}-core")
            if details:
                parts.append(f"({', '.join(details)})")
            gpu_list.append(" ".join(parts))
        if gpu_list:
            info["gpu_list"] = gpu_list
    except Exception:
        pass

    # Storage from SPStorageDataType — deduplicated by physical device name
    try:
        result = subprocess.run(
            ["system_profiler", "SPStorageDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        storage_data = json.loads(result.stdout)
        seen_devices: set[str] = set()
        storage_list = []
        for vol in storage_data.get("SPStorageDataType", []):
            phys = vol.get("physical_drive") or {}
            device_name = phys.get("device_name", "").strip()
            # Deduplicate: multiple volumes can share one physical drive
            dedup_key = device_name or vol.get("bsd_name", vol.get("_name", ""))
            if dedup_key in seen_devices:
                continue
            seen_devices.add(dedup_key)
            size_bytes = vol.get("size_in_bytes", 0)
            size_bytes = size_bytes if isinstance(size_bytes, int) else 0
            size_gb = size_bytes / (1024**3)
            medium = phys.get("medium_type", "") or phys.get("protocol", "")
            display = device_name or vol.get("_name", "Unknown")
            entry = display
            if size_gb:
                entry += f" · {size_gb:.0f} GB"
            if medium:
                entry += f" ({medium.upper()})"
            storage_list.append(entry)
        if storage_list:
            info["storage_list"] = storage_list
    except Exception:
        pass

    # Fans from SPPowerDataType
    try:
        result = subprocess.run(
            ["system_profiler", "SPPowerDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        power_data = json.loads(result.stdout)
        fan_list = []
        for entry in power_data.get("SPPowerDataType", []):
            # Key varies by macOS version / hardware
            fans_rpm = entry.get("sppower_cpu_fan_speed_rpm")
            if isinstance(fans_rpm, list):
                for i, rpm in enumerate(fans_rpm, 1):
                    fan_list.append(f"Fan {i}: {rpm} RPM")
            elif isinstance(fans_rpm, (int, float)):
                fan_list.append(f"Fan: {fans_rpm} RPM")
            elif isinstance(fans_rpm, str):
                fan_list.append(f"Fan: {fans_rpm}")
        if fan_list:
            info["fan_list"] = fan_list
    except Exception:
        pass

    info["bios_vendor"] = "Apple"
    info["board_manufacturer"] = "Apple"
    info["chassis_manufacturer"] = "Apple"
    return info


def _get_info_linux() -> dict:
    """Read DMI info from /sys/class/dmi/id/ and dmidecode."""
    from pathlib import Path

    info: dict = {}
    dmi_base = Path("/sys/class/dmi/id")

    def read_dmi(name: str) -> str | None:
        p = dmi_base / name
        try:
            return p.read_text().strip() or None
        except Exception:
            return None

    info["bios_vendor"] = read_dmi("bios_vendor")
    info["bios_version"] = read_dmi("bios_version")
    info["bios_date"] = read_dmi("bios_date")
    info["board_manufacturer"] = read_dmi("board_vendor")
    info["board_model"] = read_dmi("board_name")
    info["board_serial"] = read_dmi("board_serial")
    info["chassis_manufacturer"] = read_dmi("chassis_vendor")
    info["chassis_model"] = read_dmi("chassis_type")

    # OS info
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    info["os_name"] = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass

    info["os_version"] = platform.release()
    info["os_build"] = platform.version()

    # CPU details
    try:
        result = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if line.startswith("Model name:"):
                info["processor_marketing"] = line.split(":", 1)[1].strip()
            elif line.startswith("CPU(s):"):
                logical = line.split(":", 1)[1].strip()
                info["cpu_cores"] = f"{logical} CPUs"
            elif line.startswith("Core(s) per socket:"):
                info["_linux_cores_per_socket"] = line.split(":", 1)[1].strip()
            elif line.startswith("Socket(s):"):
                info["_linux_sockets"] = line.split(":", 1)[1].strip()
        # Build a better core string if available
        cps = info.pop("_linux_cores_per_socket", None)
        sockets = info.pop("_linux_sockets", None)
        if cps and sockets:
            physical = int(cps) * int(sockets)
            info["cpu_cores"] = f"{physical} cores"
    except Exception:
        pass

    # RAM total
    try:
        import psutil

        total_bytes = psutil.virtual_memory().total
        info["ram_total"] = f"{total_bytes / (1024**3):.0f} GB"
    except Exception:
        pass

    # GPU(s) via lspci
    try:
        result = subprocess.run(["lspci", "-mm"], capture_output=True, text=True, timeout=5)
        gpu_list = []
        for line in result.stdout.splitlines():
            lower = line.lower()
            if "vga" in lower or "display" in lower or "3d" in lower:
                # lspci -mm format: slot "class" "vendor" "device" ...
                parts = line.split('"')
                # parts[3] = vendor, parts[5] = device
                vendor = parts[3] if len(parts) > 3 else ""
                device = parts[5] if len(parts) > 5 else ""
                name = f"{vendor} {device}".strip()
                if name:
                    gpu_list.append(name)
        if gpu_list:
            info["gpu_list"] = gpu_list
    except Exception:
        pass

    # Storage via lsblk
    try:
        result = subprocess.run(
            ["lsblk", "-d", "-o", "NAME,SIZE,MODEL,TYPE", "--noheadings"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        storage_list = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name, size = parts[0], parts[1]
            model = " ".join(parts[2:-1]) if len(parts) > 3 else ""
            entry = model.strip() or f"/dev/{name}"
            entry += f" · {size}"
            storage_list.append(entry)
        if storage_list:
            info["storage_list"] = storage_list
    except Exception:
        pass

    return info


class SystemInfoTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()
        loop = asyncio.get_event_loop()

        sys = platform.system()
        if sys == "Windows":
            info = await loop.run_in_executor(None, _get_info_windows)
        elif sys == "Linux":
            info = await loop.run_in_executor(None, _get_info_linux)
        elif sys == "Darwin":
            info = await loop.run_in_executor(None, _get_info_darwin)
        else:
            info = {}

        # Always available via Python
        info["python_platform"] = platform.platform()
        info["hostname"] = platform.node()
        info["machine_arch"] = platform.machine()
        info["processor"] = platform.processor()

        data = info

        if "error" in info:
            self.result.mark_warn(
                summary=f"Partial system info (error: {info['error']})",
                data=data,
            )
        else:
            board = info.get("chassis_model") or info.get("board_model") or "Unknown"
            bios = info.get("bios_version") or "Unknown"
            self.result.mark_pass(
                summary=f"Board: {board} — BIOS: {bios}",
                data=data,
            )

        return self.result

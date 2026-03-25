"""System info: BIOS version, board make/model/serial, OS info."""

import asyncio
import platform
import subprocess

from ..models.test_result import TestResult
from .base import BaseTest


def _run_powershell(script: str, timeout: int = 30) -> str:
    """Run a PowerShell script via -EncodedCommand and return stdout."""
    import base64

    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    # Return stdout regardless of exit code — PowerShell can exit non-zero
    # due to suppressed warnings even when it produced valid JSON output.
    out = r.stdout.strip()
    return out if out else ""


def _get_info_windows_ps() -> dict:
    """Query system info on Windows using PowerShell Get-CimInstance."""
    import json

    info: dict = {}

    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$bios  = Get-CimInstance Win32_BIOS
$board = Get-CimInstance Win32_BaseBoard
$cs    = Get-CimInstance Win32_ComputerSystem
$os    = Get-CimInstance Win32_OperatingSystem
$cpu   = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram   = (Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum
$gpus  = @(Get-CimInstance Win32_VideoController | Where-Object { $_.Name } | ForEach-Object {
    $name = $_.Name.Trim()
    $vram = $_.AdapterRAM
    if ($vram -and [long]$vram -gt 0) { "$name ($([math]::Round([long]$vram/1GB,0)) GB VRAM)" } else { $name }
})
$disks = @(Get-CimInstance Win32_DiskDrive | Where-Object { $_.InterfaceType -ne 'USB' } | ForEach-Object {
    $model = if ($_.Model) { $_.Model.Trim() } else { $_.Caption }
    $sz    = if ($_.Size) { " - $([math]::Round([long]$_.Size/1GB,0)) GB" } else { "" }
    "$model$sz"
})
[PSCustomObject]@{
    bios_vendor          = $bios.Manufacturer
    bios_version         = $bios.SMBIOSBIOSVersion
    bios_date            = if ($bios.ReleaseDate) { $bios.ReleaseDate.ToString("yyyy-MM-dd") } else { $null }
    board_serial         = $bios.SerialNumber
    board_manufacturer   = $board.Manufacturer
    board_model          = $board.Product
    board_serial2        = $board.SerialNumber
    chassis_manufacturer = $cs.Manufacturer
    chassis_model        = $cs.Model
    os_name              = $os.Caption
    os_version           = $os.Version
    os_build             = $os.BuildNumber
    cpu_name             = if ($cpu.Name) { $cpu.Name.Trim() } else { $null }
    cpu_cores            = $cpu.NumberOfCores
    cpu_threads          = $cpu.NumberOfLogicalProcessors
    ram_bytes            = $ram
    gpu_list             = $gpus
    disk_list            = $disks
} | ConvertTo-Json -Depth 3
"""

    try:
        out = _run_powershell(script)
        if not out:
            info["error"] = "PowerShell returned no output"
            return info

        d = json.loads(out)

        for key in (
            "bios_vendor", "bios_version", "bios_date",
            "board_manufacturer", "board_model",
            "chassis_manufacturer", "chassis_model",
            "os_name", "os_version", "os_build",
        ):
            val = d.get(key)
            if val:
                info[key] = str(val)

        # Serial: prefer BIOS serial, fall back to baseboard
        serial = d.get("board_serial") or d.get("board_serial2")
        if serial:
            info["board_serial"] = str(serial)

        cpu_name = d.get("cpu_name")
        if cpu_name:
            info["processor_marketing"] = cpu_name

        cores = d.get("cpu_cores")
        threads = d.get("cpu_threads")
        if cores and threads:
            info["cpu_cores"] = f"{int(cores)} cores / {int(threads)} threads"
        elif cores:
            info["cpu_cores"] = f"{int(cores)} cores"

        ram_bytes = d.get("ram_bytes")
        if ram_bytes:
            info["ram_total"] = f"{int(ram_bytes) / (1024 ** 3):.0f} GB"

        gpu_list = d.get("gpu_list")
        if isinstance(gpu_list, list):
            info["gpu_list"] = [g for g in gpu_list if g]
        elif isinstance(gpu_list, str) and gpu_list:
            info["gpu_list"] = [gpu_list]

        disk_list = d.get("disk_list")
        if isinstance(disk_list, list):
            info["storage_list"] = [item for item in disk_list if item]
        elif isinstance(disk_list, str) and disk_list:
            info["storage_list"] = [disk_list]

    except Exception as exc:
        info["error"] = str(exc)

    return info


def _get_info_windows_wmic() -> dict:
    """Fallback: collect system info via wmic CLI (deprecated but available on Win10/11)."""
    info: dict = {}

    def _wmic(*args: str) -> list[dict[str, str]]:
        """Run wmic and parse /format:list output into a list of dicts (one per instance)."""
        try:
            r = subprocess.run(
                ["wmic"] + list(args) + ["/format:list"],
                capture_output=True, text=True, timeout=15,
            )
            rows: list[dict[str, str]] = []
            current: dict[str, str] = {}
            for line in r.stdout.splitlines():
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    if v.strip():
                        current[k.strip()] = v.strip()
                elif not line and current:
                    rows.append(current)
                    current = {}
            if current:
                rows.append(current)
            return rows
        except Exception:
            return []

    bios = (_wmic("bios", "get", "Manufacturer,SMBIOSBIOSVersion,SerialNumber,ReleaseDate") or [{}])[0]
    if bios.get("Manufacturer"):
        info["bios_vendor"] = bios["Manufacturer"]
    if bios.get("SMBIOSBIOSVersion"):
        info["bios_version"] = bios["SMBIOSBIOSVersion"]
    if bios.get("ReleaseDate"):
        info["bios_date"] = bios["ReleaseDate"]
    if bios.get("SerialNumber"):
        info["board_serial"] = bios["SerialNumber"]

    board = (_wmic("baseboard", "get", "Manufacturer,Product,SerialNumber") or [{}])[0]
    if board.get("Manufacturer"):
        info["board_manufacturer"] = board["Manufacturer"]
    if board.get("Product"):
        info["board_model"] = board["Product"]
    if board.get("SerialNumber") and not info.get("board_serial"):
        info["board_serial"] = board["SerialNumber"]

    cs = (_wmic("computersystem", "get", "Manufacturer,Model") or [{}])[0]
    if cs.get("Manufacturer"):
        info["chassis_manufacturer"] = cs["Manufacturer"]
    if cs.get("Model"):
        info["chassis_model"] = cs["Model"]

    os_row = (_wmic("os", "get", "Caption,Version,BuildNumber") or [{}])[0]
    if os_row.get("Caption"):
        info["os_name"] = os_row["Caption"]
    if os_row.get("Version"):
        info["os_version"] = os_row["Version"]
    if os_row.get("BuildNumber"):
        info["os_build"] = os_row["BuildNumber"]

    cpu_rows = _wmic("cpu", "get", "Name,NumberOfCores,NumberOfLogicalProcessors")
    if cpu_rows:
        cpu = cpu_rows[0]
        if cpu.get("Name"):
            info["processor_marketing"] = cpu["Name"].strip()
        cores = cpu.get("NumberOfCores")
        threads = cpu.get("NumberOfLogicalProcessors")
        if cores and threads:
            info["cpu_cores"] = f"{cores} cores / {threads} threads"
        elif cores:
            info["cpu_cores"] = f"{cores} cores"

    try:
        r = subprocess.run(
            ["wmic", "memorychip", "get", "Capacity", "/format:list"],
            capture_output=True, text=True, timeout=15,
        )
        total = sum(
            int(line.partition("=")[2].strip())
            for line in r.stdout.splitlines()
            if line.strip().startswith("Capacity=") and line.partition("=")[2].strip().isdigit()
        )
        if total > 0:
            info["ram_total"] = f"{total / (1024 ** 3):.0f} GB"
    except Exception:
        pass

    gpu_rows = _wmic("path", "win32_videocontroller", "get", "Name,AdapterRAM")
    gpu_list = []
    for row in gpu_rows:
        name = row.get("Name", "").strip()
        if not name:
            continue
        try:
            vram_bytes = int(row.get("AdapterRAM", "0") or "0")
            entry = name + (f" ({vram_bytes // (1024 ** 3)} GB VRAM)" if vram_bytes > 0 else "")
        except (ValueError, TypeError):
            entry = name
        gpu_list.append(entry)
    if gpu_list:
        info["gpu_list"] = gpu_list

    disk_rows = _wmic("diskdrive", "get", "Model,Size")
    disk_list = []
    for row in disk_rows:
        model = row.get("Model", "").strip()
        if not model:
            continue
        try:
            size_gb = int(row.get("Size", "0") or "0") / (1024 ** 3)
            entry = model + (f" · {size_gb:.0f} GB" if size_gb > 0 else "")
        except (ValueError, TypeError):
            entry = model
        disk_list.append(entry)
    if disk_list:
        info["storage_list"] = disk_list

    return info


def _get_info_windows() -> dict:
    """Try PowerShell first, fall back to wmic CLI."""
    info = _get_info_windows_ps()
    # Consider PS successful if it returned any meaningful hardware field
    if info and not info.get("error") and any(
        info.get(k) for k in ("chassis_model", "board_model", "bios_version", "os_name")
    ):
        return info
    # Fallback: wmic
    wmic_info = _get_info_windows_wmic()
    if wmic_info:
        # Merge: keep any good PS values, fill gaps with wmic
        merged = {**wmic_info, **{k: v for k, v in info.items() if v and k != "error"}}
        return merged
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

    # CPU details — lscpu primary, /proc/cpuinfo fallback
    try:
        result = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            raise FileNotFoundError
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
        cps = info.pop("_linux_cores_per_socket", None)
        sockets = info.pop("_linux_sockets", None)
        if cps and sockets:
            physical = int(cps) * int(sockets)
            info["cpu_cores"] = f"{physical} cores"
    except Exception:
        # Fallback: parse /proc/cpuinfo directly
        try:
            with open("/proc/cpuinfo") as f:
                cpuinfo = f.read()
            for line in cpuinfo.splitlines():
                if "model name" in line and "processor_marketing" not in info:
                    info["processor_marketing"] = line.split(":", 1)[1].strip()
                    break
            physical_ids = set()
            core_ids: dict[str, set[str]] = {}
            current_physical = None
            for line in cpuinfo.splitlines():
                if line.startswith("physical id"):
                    current_physical = line.split(":", 1)[1].strip()
                    physical_ids.add(current_physical)
                elif line.startswith("core id") and current_physical is not None:
                    core_ids.setdefault(current_physical, set()).add(
                        line.split(":", 1)[1].strip()
                    )
            if physical_ids and core_ids:
                total_physical = sum(len(v) for v in core_ids.values())
                info["cpu_cores"] = f"{total_physical} cores"
        except Exception:
            pass

    # RAM total — psutil primary, /proc/meminfo fallback
    try:
        import psutil

        total_bytes = psutil.virtual_memory().total
        info["ram_total"] = f"{total_bytes / (1024**3):.0f} GB"
    except Exception:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        info["ram_total"] = f"{kb / (1024 ** 2):.0f} GB"
                        break
        except Exception:
            pass

    # GPU(s) — lspci primary, /sys/bus/pci/devices fallback
    try:
        result = subprocess.run(["lspci", "-mm"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            raise FileNotFoundError
        gpu_list = []
        for line in result.stdout.splitlines():
            lower = line.lower()
            if "vga" in lower or "display" in lower or "3d" in lower:
                parts = line.split('"')
                vendor = parts[3] if len(parts) > 3 else ""
                device = parts[5] if len(parts) > 5 else ""
                name = f"{vendor} {device}".strip()
                if name:
                    gpu_list.append(name)
        if gpu_list:
            info["gpu_list"] = gpu_list
    except Exception:
        # Fallback: read class/vendor/device from sysfs PCI tree
        try:
            from pathlib import Path

            gpu_list = []
            for dev in Path("/sys/bus/pci/devices").iterdir():
                try:
                    cls = (dev / "class").read_text().strip()
                    # PCI class 0x03xxxx = Display controller
                    if not cls.startswith("0x03"):
                        continue
                    vendor_id = (dev / "vendor").read_text().strip()
                    device_id = (dev / "device").read_text().strip()
                    gpu_list.append(f"PCI {vendor_id}:{device_id}")
                except Exception:
                    continue
            if gpu_list:
                info["gpu_list"] = gpu_list
        except Exception:
            pass

    # Storage — lsblk primary, /sys/block fallback
    try:
        result = subprocess.run(
            ["lsblk", "-d", "-o", "NAME,SIZE,MODEL,TYPE", "--noheadings"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise FileNotFoundError
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
        # Fallback: read model names from /sys/block
        try:
            from pathlib import Path

            storage_list = []
            for dev in sorted(Path("/sys/block").iterdir()):
                name = dev.name
                if name.startswith(("loop", "ram", "dm-")):
                    continue
                model_path = dev / "device" / "model"
                model = model_path.read_text().strip() if model_path.exists() else name
                size_path = dev / "size"
                try:
                    blocks = int(size_path.read_text().strip())
                    size_gb = (blocks * 512) / (1024 ** 3)
                    entry = f"{model} · {size_gb:.0f} GB"
                except Exception:
                    entry = model
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

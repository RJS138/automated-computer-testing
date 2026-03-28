"""Battery test: health %, design vs current capacity, cycle count."""

import asyncio
import platform
import subprocess

import psutil

from ..models.test_result import TestResult
from ..thresholds import (
    BATTERY_HEALTH_GOOD,
    BATTERY_HEALTH_WARN,
    get_battery_cycle_thresholds,
)
from .base import BaseTest


def _run_powershell(script: str, timeout: int = 20) -> str:
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


def _get_battery_details_windows_ps() -> dict:
    """Primary: PowerShell Get-CimInstance for detailed battery info."""
    import json

    details: dict = {}

    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$b  = Get-CimInstance Win32_Battery | Select-Object -First 1
$fc = Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity | Select-Object -First 1
$cc = Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount | Select-Object -First 1
$sd = Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData | Select-Object -First 1
$design = if ($sd.DesignedCapacity -and [int]$sd.DesignedCapacity -gt 0) { [int]$sd.DesignedCapacity } elseif ($b.DesignCapacity -and [int]$b.DesignCapacity -gt 0) { [int]$b.DesignCapacity } else { 0 }
$full   = if ($fc.FullChargedCapacity -and [int]$fc.FullChargedCapacity -gt 0) { [int]$fc.FullChargedCapacity } elseif ($b.FullChargeCapacity -and [int]$b.FullChargeCapacity -gt 0) { [int]$b.FullChargeCapacity } else { 0 }
$cycle  = if ($cc.CycleCount -and [int]$cc.CycleCount -gt 0) { [int]$cc.CycleCount } else { $null }
[PSCustomObject]@{
    design_mwh  = $design
    full_mwh    = $full
    cycle_count = $cycle
    chemistry   = if ($b.Chemistry -ne $null) { [int]$b.Chemistry } else { $null }
} | ConvertTo-Json
"""

    try:
        out = _run_powershell(script)
        if not out:
            return details

        d = json.loads(out)
        design = d.get("design_mwh") or 0
        full = d.get("full_mwh") or 0

        if design > 0:
            details["design_capacity_mwh"] = design
        if full > 0:
            details["full_charge_capacity_mwh"] = full

        # Cycle count 0 means the firmware doesn't report it — treat as unavailable
        cycle = d.get("cycle_count")
        if cycle is not None and int(cycle) > 0:
            details["cycle_count"] = int(cycle)

        chem = d.get("chemistry")
        if chem is not None:
            details["chemistry"] = int(chem)

        if design > 0 and full > 0:
            details["health_pct"] = round((full / design) * 100, 1)

    except Exception:
        pass

    return details


def _get_battery_details_windows_wmic() -> dict:
    """Fallback: wmic CLI for basic battery info."""
    details: dict = {}

    def _wmic_val(*args: str) -> str:
        try:
            r = subprocess.run(
                ["wmic"] + list(args) + ["/format:list"],
                capture_output=True, text=True, timeout=15,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if "=" in line:
                    _, _, v = line.partition("=")
                    if v.strip():
                        return v.strip()
        except Exception:
            pass
        return ""

    try:
        # Basic capacity from Win32_Battery
        r = subprocess.run(
            ["wmic", "path", "Win32_Battery", "get",
             "DesignCapacity,FullChargeCapacity,Chemistry", "/format:list"],
            capture_output=True, text=True, timeout=15,
        )
        row: dict[str, str] = {}
        for line in r.stdout.splitlines():
            line = line.strip()
            if "=" in line:
                k, _, v = line.partition("=")
                if v.strip():
                    row[k.strip()] = v.strip()

        design = int(row.get("DesignCapacity") or "0")
        full = int(row.get("FullChargeCapacity") or "0")
        if design > 0:
            details["design_capacity_mwh"] = design
        if full > 0:
            details["full_charge_capacity_mwh"] = full
        chem = row.get("Chemistry")
        if chem:
            details["chemistry"] = int(chem)

        # Better full-charge capacity from root\wmi
        try:
            fc_str = _wmic_val(
                "/namespace:\\\\root\\wmi", "path", "BatteryFullChargedCapacity",
                "get", "FullChargedCapacity",
            )
            fc = int(fc_str) if fc_str.isdigit() else 0
            if fc > 0:
                details["full_charge_capacity_mwh"] = fc
                full = fc
        except Exception:
            pass

        # Cycle count from root\wmi
        try:
            cc_str = _wmic_val(
                "/namespace:\\\\root\\wmi", "path", "BatteryCycleCount",
                "get", "CycleCount",
            )
            cc = int(cc_str) if cc_str.isdigit() else 0
            if cc > 0:
                details["cycle_count"] = cc
        except Exception:
            pass

        if design > 0 and full > 0:
            details["health_pct"] = round((full / design) * 100, 1)

    except Exception:
        pass

    return details


def _get_battery_details_lhm() -> dict:
    """
    Read design and full-charge capacity from LibreHardwareMonitor via SensorDump.

    LHM exposes battery Data sensors ("Designed Capacity", "Full Charged Capacity")
    in Wh on most OEM laptops where WMI DesignCapacity/FullChargeCapacity returns 0.
    """
    details: dict = {}
    try:
        from ..utils.lhm_sensor import get_all_sensors

        for s in get_all_sensors(timeout=10):
            if s.get("type") != "Data":
                continue
            name = (s.get("name") or "").lower()
            value = s.get("value")
            if not value or float(value) <= 0:
                continue
            # LHM reports battery capacity in Wh — convert to mWh
            if "design" in name and "capacity" in name:
                details["design_capacity_mwh"] = round(float(value) * 1000)
            elif "full" in name and "capacity" in name:
                details["full_charge_capacity_mwh"] = round(float(value) * 1000)
    except Exception:
        pass

    design = details.get("design_capacity_mwh", 0)
    full = details.get("full_charge_capacity_mwh", 0)
    if design > 0 and full > 0:
        details["health_pct"] = round((full / design) * 100, 1)

    return details


def _get_battery_details_powercfg() -> dict:
    """
    Parse powercfg /batteryreport XML for design and full-charge capacity.

    Reliable across virtually all Windows laptops including OEM models where
    WMI capacity fields return 0.
    """
    import os
    import tempfile
    import xml.etree.ElementTree as ET
    from pathlib import Path

    details: dict = {}
    tmp = Path(tempfile.gettempdir()) / f"touchstone_batteryreport_{os.getpid()}.xml"
    try:
        subprocess.run(
            ["powercfg", "/batteryreport", "/xml", "/output", str(tmp)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if not tmp.exists():
            return details

        tree = ET.parse(str(tmp))
        root = tree.getroot()

        # Strip XML namespaces so we can query tag names directly
        for elem in root.iter():
            elem.tag = elem.tag.split("}", 1)[-1]

        for bat in root.findall(".//Battery"):
            design_str = bat.findtext("DesignCapacity") or ""
            full_str = bat.findtext("FullChargeCapacity") or ""
            if design_str.isdigit() and int(design_str) > 0:
                details["design_capacity_mwh"] = int(design_str)
            if full_str.isdigit() and int(full_str) > 0:
                details["full_charge_capacity_mwh"] = int(full_str)
            break  # first battery only

    except Exception:
        pass
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    design = details.get("design_capacity_mwh", 0)
    full = details.get("full_charge_capacity_mwh", 0)
    if design > 0 and full > 0:
        details["health_pct"] = round((full / design) * 100, 1)

    return details


def _get_battery_details_windows_mfr() -> dict:
    """
    Manufacturer-specific WMI battery queries via PowerShell.

    Many OEM laptops expose proprietary WMI namespaces that return accurate
    capacity data even when standard Win32_Battery / BatteryStaticData return 0.
    Detects manufacturer from Win32_ComputerSystem and tries the known namespace
    for that vendor.

    Covered: Lenovo, Dell (Command Monitor), HP, ASUS, Samsung, Acer/Gateway,
             Toshiba/Dynabook, Panasonic.
    """
    import json

    details: dict = {}

    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$mfr = ((Get-CimInstance Win32_ComputerSystem).Manufacturer + '').ToLower()
$design = 0
$full   = 0
$cycle  = $null

if ($mfr -like '*lenovo*') {
    $b = Get-CimInstance -Namespace root\WMI -ClassName LENOVO_BATTERY_INFORMATION -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignCapacity   -gt 0) { $design = [int]$b.DesignCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
        if ([int]$b.CycleCount       -gt 0) { $cycle = [int]$b.CycleCount }
    }
} elseif ($mfr -like '*dell*') {
    # Requires Dell Command Monitor to be installed
    $b = Get-CimInstance -Namespace root\dcim\sysman -ClassName DCIM_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignCapacity    -gt 0) { $design = [int]$b.DesignCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
    }
} elseif ($mfr -like '*hp*' -or $mfr -like '*hewlett*') {
    $b = Get-CimInstance -Namespace root\WMI -ClassName HP_BatteryInformation -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignCapacity    -gt 0) { $design = [int]$b.DesignCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
    }
} elseif ($mfr -like '*asus*') {
    $b = Get-CimInstance -Namespace root\WMI -ClassName ASUS_BatteryHealth -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignedCapacity  -gt 0) { $design = [int]$b.DesignedCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
    }
} elseif ($mfr -like '*samsung*') {
    $b = Get-CimInstance -Namespace root\WMI -ClassName SamsungBattery -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignCapacity    -gt 0) { $design = [int]$b.DesignCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
    }
} elseif ($mfr -like '*acer*' -or $mfr -like '*gateway*') {
    $b = Get-CimInstance -Namespace root\WMI -ClassName Acer_WMI_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignCapacity    -gt 0) { $design = [int]$b.DesignCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
    }
} elseif ($mfr -like '*toshiba*' -or $mfr -like '*dynabook*') {
    $b = Get-CimInstance -Namespace root\WMI -ClassName Toshiba_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignCapacity    -gt 0) { $design = [int]$b.DesignCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
    }
} elseif ($mfr -like '*panasonic*') {
    $b = Get-CimInstance -Namespace root\WMI -ClassName Panasonic_BatteryInformation -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) {
        if ([int]$b.DesignCapacity    -gt 0) { $design = [int]$b.DesignCapacity }
        if ([int]$b.FullChargeCapacity -gt 0) { $full  = [int]$b.FullChargeCapacity }
    }
}

[PSCustomObject]@{
    design_mwh  = $design
    full_mwh    = $full
    cycle_count = $cycle
} | ConvertTo-Json
"""

    try:
        out = _run_powershell(script, timeout=15)
        if not out:
            return details

        d = json.loads(out)
        design = d.get("design_mwh") or 0
        full = d.get("full_mwh") or 0

        if design > 0:
            details["design_capacity_mwh"] = int(design)
        if full > 0:
            details["full_charge_capacity_mwh"] = int(full)

        cycle = d.get("cycle_count")
        if cycle is not None and int(cycle) > 0:
            details["cycle_count"] = int(cycle)

        if design > 0 and full > 0:
            details["health_pct"] = round((full / design) * 100, 1)

    except Exception:
        pass

    return details


def _get_battery_details_windows_ioctl() -> dict:
    """
    Read battery capacity via IOCTL_BATTERY_QUERY_INFORMATION (Windows kernel API).

    Uses SetupDi to enumerate battery device interfaces, then DeviceIoControl to
    query the BATTERY_INFORMATION struct directly from the battery miniclass driver.
    This is the most universal method — it works on any OEM laptop (MSI, Razer,
    Gigabyte, etc.) without proprietary WMI namespaces or third-party tools.
    Requires no elevation beyond what the process already has.
    """
    import ctypes
    import ctypes.wintypes as wintypes
    import struct as _struct

    details: dict = {}

    try:
        setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        # Battery device interface GUID: {72631e54-78a4-11d0-bcf7-00aa00b7b32a}
        BATTERY_GUID = GUID(
            0x72631E54,
            0x78A4,
            0x11D0,
            (ctypes.c_ubyte * 8)(0xBC, 0xF7, 0x00, 0xAA, 0x00, 0xB7, 0xB3, 0x2A),
        )

        DIGCF_PRESENT = 0x00000002
        DIGCF_DEVICEINTERFACE = 0x00000010
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        IOCTL_BATTERY_QUERY_TAG = 0x00294040
        IOCTL_BATTERY_QUERY_INFORMATION = 0x00294044
        BATTERY_INFORMATION_LEVEL = 1

        class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD),
                ("Reserved", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("DevicePath", ctypes.c_wchar * 1024),
            ]

        class BATTERY_QUERY_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BatteryTag", wintypes.ULONG),
                ("InformationLevel", wintypes.DWORD),
                ("AtRate", wintypes.LONG),
            ]

        class BATTERY_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("Capabilities", wintypes.ULONG),
                ("Technology", ctypes.c_ubyte),
                ("Reserved", ctypes.c_ubyte * 3),
                ("Chemistry", ctypes.c_ubyte * 4),
                ("DesignedCapacity", wintypes.ULONG),
                ("FullChargedCapacity", wintypes.ULONG),
                ("DefaultAlert1", wintypes.ULONG),
                ("DefaultAlert2", wintypes.ULONG),
                ("CriticalBias", wintypes.ULONG),
                ("CycleCount", wintypes.ULONG),
            ]

        setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
        setupapi.SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD,
        ]
        kernel32.CreateFileW.restype = ctypes.c_void_p

        INVALID_HANDLE = ctypes.c_void_p(-1).value

        hdev = setupapi.SetupDiGetClassDevsW(
            ctypes.byref(BATTERY_GUID),
            None,
            None,
            DIGCF_PRESENT | DIGCF_DEVICEINTERFACE,
        )
        if hdev == INVALID_HANDLE or hdev is None:
            return details

        try:
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            # cbSize for SP_DEVICE_INTERFACE_DETAIL_DATA_W: 8 on 64-bit, 6 on 32-bit
            detail_cb = 8 if _struct.calcsize("P") == 8 else 6

            index = 0
            while True:
                ok = setupapi.SetupDiEnumDeviceInterfaces(
                    hdev, None, ctypes.byref(BATTERY_GUID), index, ctypes.byref(iface),
                )
                if not ok:
                    break

                detail = SP_DEVICE_INTERFACE_DETAIL_DATA_W()
                detail.cbSize = detail_cb
                ok2 = setupapi.SetupDiGetDeviceInterfaceDetailW(
                    hdev,
                    ctypes.byref(iface),
                    ctypes.byref(detail),
                    ctypes.sizeof(detail),
                    None,
                    None,
                )
                if not ok2:
                    index += 1
                    continue

                hbat = kernel32.CreateFileW(
                    detail.DevicePath,
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    OPEN_EXISTING,
                    0,
                    None,
                )
                if hbat == INVALID_HANDLE or hbat is None:
                    index += 1
                    continue

                try:
                    bat_tag = wintypes.ULONG(0)
                    wait_timeout = wintypes.ULONG(0)
                    bytes_returned = wintypes.DWORD(0)

                    ok3 = kernel32.DeviceIoControl(
                        hbat,
                        IOCTL_BATTERY_QUERY_TAG,
                        ctypes.byref(wait_timeout),
                        ctypes.sizeof(wait_timeout),
                        ctypes.byref(bat_tag),
                        ctypes.sizeof(bat_tag),
                        ctypes.byref(bytes_returned),
                        None,
                    )
                    if not ok3 or bat_tag.value == 0:
                        index += 1
                        continue

                    bqi = BATTERY_QUERY_INFORMATION()
                    bqi.BatteryTag = bat_tag.value
                    bqi.InformationLevel = BATTERY_INFORMATION_LEVEL
                    bqi.AtRate = 0

                    bi = BATTERY_INFORMATION()
                    ok4 = kernel32.DeviceIoControl(
                        hbat,
                        IOCTL_BATTERY_QUERY_INFORMATION,
                        ctypes.byref(bqi),
                        ctypes.sizeof(bqi),
                        ctypes.byref(bi),
                        ctypes.sizeof(bi),
                        ctypes.byref(bytes_returned),
                        None,
                    )
                    if ok4:
                        if bi.DesignedCapacity > 0:
                            details["design_capacity_mwh"] = bi.DesignedCapacity
                        if bi.FullChargedCapacity > 0:
                            details["full_charge_capacity_mwh"] = bi.FullChargedCapacity
                        if bi.CycleCount > 0:
                            details.setdefault("cycle_count", bi.CycleCount)
                        if details.get("design_capacity_mwh") and details.get("full_charge_capacity_mwh"):
                            details["health_pct"] = round(
                                (details["full_charge_capacity_mwh"] / details["design_capacity_mwh"]) * 100, 1
                            )
                        break  # first battery is sufficient
                finally:
                    kernel32.CloseHandle(hbat)

                index += 1
        finally:
            setupapi.SetupDiDestroyDeviceInfoList(hdev)

    except Exception:
        pass

    return details


def _get_battery_details_windows() -> dict:
    """
    Collect battery capacity on Windows using a six-tier fallback chain:
      1. PowerShell WMI  (BatteryStaticData / BatteryFullChargedCapacity)
      2. Manufacturer WMI  (Lenovo, Dell, HP, ASUS, Samsung, Acer, Toshiba, Panasonic)
      3. IOCTL ctypes  (universal kernel-level driver query — works on MSI, Razer, etc.)
      4. LHM SensorDump  (LibreHardwareMonitor sensor bridge)
      5. powercfg /batteryreport XML  (reliable on all Windows laptops)
      6. wmic CLI fallback
    Tiers merge into the same result dict — non-capacity fields (chemistry,
    cycle count) collected in tier 1 are preserved regardless of which tier
    provides the capacity.
    """
    details = _get_battery_details_windows_ps()

    if not details.get("design_capacity_mwh") or not details.get("full_charge_capacity_mwh"):
        for tier_fn in (
            _get_battery_details_windows_mfr,
            _get_battery_details_windows_ioctl,
            _get_battery_details_lhm,
            _get_battery_details_powercfg,
        ):
            tier = tier_fn()
            if tier.get("design_capacity_mwh") and tier.get("full_charge_capacity_mwh"):
                details["design_capacity_mwh"] = tier["design_capacity_mwh"]
                details["full_charge_capacity_mwh"] = tier["full_charge_capacity_mwh"]
                details["health_pct"] = tier["health_pct"]
                # Merge cycle count from this tier if PS tier didn't get one
                if "cycle_count" in tier:
                    details.setdefault("cycle_count", tier["cycle_count"])
                break

    if not details.get("design_capacity_mwh") and not details.get("full_charge_capacity_mwh"):
        wmic = _get_battery_details_windows_wmic()
        for k, v in wmic.items():
            details.setdefault(k, v)

    return details


def _get_battery_details_linux() -> dict:
    """Read battery details from /sys/class/power_supply/ on Linux."""
    from pathlib import Path

    details: dict = {}

    power_supply_dir = Path("/sys/class/power_supply")
    if not power_supply_dir.exists():
        return details

    for bat_dir in power_supply_dir.iterdir():
        type_file = bat_dir / "type"
        if not type_file.exists():
            continue
        try:
            if type_file.read_text().strip() != "Battery":
                continue
        except Exception:
            continue

        def read_val(name: str, _d: Path = bat_dir) -> str | None:
            p = _d / name
            return p.read_text().strip() if p.exists() else None

        design = read_val("energy_full_design") or read_val("charge_full_design")
        full = read_val("energy_full") or read_val("charge_full")
        cycles = read_val("cycle_count")
        technology = read_val("technology")

        if design:
            details["design_capacity_mwh"] = int(design) // 1000  # µWh → mWh
        if full:
            details["full_charge_capacity_mwh"] = int(full) // 1000
        if cycles:
            details["cycle_count"] = int(cycles)
        if technology:
            details["chemistry"] = technology
        break  # Use first battery

    return details


def _get_battery_details_darwin() -> dict:
    """
    Read battery details on macOS.

    Primary:  system_profiler SPPowerDataType -json  (health %, condition,
              cycle count, charger info — no root needed)
    Secondary: ioreg -r -n AppleSmartBattery  (raw mAh, temperature, voltage,
              amperage — fills in capacity values)
    """
    import json as _json

    details: dict = {}

    # --- system_profiler (clean JSON, most reliable) ---
    try:
        r = subprocess.run(
            ["system_profiler", "SPPowerDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = _json.loads(r.stdout).get("SPPowerDataType", [])
        for entry in data:
            health = entry.get("sppower_battery_health_info", {})
            charge = entry.get("sppower_battery_charge_info", {})
            model = entry.get("sppower_battery_model_info", {})

            if health:
                # "97%" → 97.0
                cap_str = health.get("sppower_battery_health_maximum_capacity", "")
                if cap_str:
                    try:
                        details["health_pct"] = float(cap_str.strip("%"))
                    except ValueError:
                        pass
                cycles = health.get("sppower_battery_cycle_count")
                if cycles is not None:
                    details["cycle_count"] = int(cycles)
                condition = health.get("sppower_battery_health")
                if condition:
                    details["condition"] = condition  # "Good" / "Fair" / "Poor"

            if charge:
                soc = charge.get("sppower_battery_state_of_charge")
                if soc is not None:
                    details["state_of_charge"] = int(soc)

            if model:
                details["battery_serial"] = model.get("sppower_battery_serial_number")
                details["device_name"] = model.get("sppower_battery_device_name")

            # Charger info
            charger = entry.get("sppower_ac_charger_watts") or entry.get("_name")
            if isinstance(charger, str) and charger.isdigit():
                details["charger_watts"] = int(charger)

        # Charger wattage lives in a separate entry
        for entry in data:
            watts = entry.get("sppower_ac_charger_watts")
            if watts is not None:
                try:
                    details["charger_watts"] = int(watts)
                except (ValueError, TypeError):
                    pass
            connected = entry.get("sppower_battery_charger_connected")
            if connected is not None:
                details["charger_connected"] = connected == "TRUE"
    except Exception:
        pass

    # --- ioreg AppleSmartBattery (raw mAh, temperature, voltage, amperage) ---
    try:
        r = subprocess.run(
            ["ioreg", "-r", "-n", "AppleSmartBattery"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in r.stdout.splitlines():
            line = line.strip()

            def _int(line_str: str) -> int:
                return int(line_str.split("=")[-1].strip())

            if '"DesignCapacity"' in line and "=" in line and "{" not in line:
                details["design_capacity_mah"] = _int(line)
            elif '"AppleRawMaxCapacity"' in line and "=" in line:
                # This is the true full-charge capacity in mAh (NOT MaxCapacity which is %)
                details["full_charge_capacity_mah"] = _int(line)
            elif '"AppleRawCurrentCapacity"' in line and "=" in line:
                details["current_capacity_mah"] = _int(line)
            elif '"CycleCount"' in line and "=" in line and "{" not in line:
                if "cycle_count" not in details:
                    details["cycle_count"] = _int(line)
            elif '"Temperature"' in line and "=" in line and "{" not in line:
                # SBS spec: units are 0.1 K → subtract 273.15 for °C
                raw_k10 = _int(line)
                details["temp_c"] = round(raw_k10 / 10 - 273.15, 1)
            elif '"Voltage"' in line and "=" in line and "{" not in line:
                details["voltage_mv"] = _int(line)
            elif '"Amperage"' in line and "=" in line and "{" not in line:
                details["amperage_ma"] = _int(line)
            elif '"BatteryChemistry"' in line and "=" in line:
                details["chemistry"] = line.split("=")[-1].strip().strip('"')
    except Exception:
        pass

    # Compute health from raw mAh if system_profiler didn't give it
    if "health_pct" not in details:
        design = details.get("design_capacity_mah")
        full = details.get("full_charge_capacity_mah")
        if design and full and design > 0:
            details["health_pct"] = round((full / design) * 100, 1)

    return details


_CHEM_MAP = {
    1: "Other",
    2: "Unknown",
    3: "Lead Acid",
    4: "NiCd",
    5: "NiMH",
    6: "Li-ion",
    7: "NiZn",
    8: "AlZn",
}


class BatteryTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()

        battery = psutil.sensors_battery()

        if battery is None:
            self.result.mark_skip("No battery detected — desktop or battery not recognized")
            return self.result

        loop = asyncio.get_event_loop()
        sys = platform.system()

        details: dict = {}
        if sys == "Windows":
            details = await loop.run_in_executor(None, _get_battery_details_windows)
        elif sys == "Linux":
            details = await loop.run_in_executor(None, _get_battery_details_linux)
        elif sys == "Darwin":
            details = await loop.run_in_executor(None, _get_battery_details_darwin)

        # health_pct: prefer pre-computed (Darwin via system_profiler), fall back to mWh calc
        health_pct: float | None = details.get("health_pct")
        if health_pct is None:
            design_mwh = details.get("design_capacity_mwh")
            full_mwh = details.get("full_charge_capacity_mwh")
            if design_mwh and full_mwh and design_mwh > 0:
                health_pct = round((full_mwh / design_mwh) * 100, 1)

        # Windows chemistry: integer → human string
        chemistry = details.get("chemistry")
        if isinstance(chemistry, int):
            chemistry = _CHEM_MAP.get(chemistry, f"Code {chemistry}")

        data: dict = {
            "percent_charged": round(battery.percent, 1),
            "plugged_in": battery.power_plugged,
            "health_pct": health_pct,
            "cycle_count": details.get("cycle_count"),
            "chemistry": chemistry,
            "condition": details.get("condition"),
            "temp_c": details.get("temp_c"),
            "voltage_mv": details.get("voltage_mv"),
            "amperage_ma": details.get("amperage_ma"),
            "charger_watts": details.get("charger_watts"),
            "charger_connected": details.get("charger_connected"),
            "battery_serial": details.get("battery_serial"),
            "state_of_charge": details.get("state_of_charge"),
        }

        # Capacity units differ by platform
        if sys == "Darwin":
            data["design_capacity_mah"] = details.get("design_capacity_mah")
            data["full_charge_capacity_mah"] = details.get("full_charge_capacity_mah")
            data["current_capacity_mah"] = details.get("current_capacity_mah")
        else:
            data["design_capacity_mwh"] = details.get("design_capacity_mwh")
            data["full_charge_capacity_mwh"] = details.get("full_charge_capacity_mwh")

        # Cycle count thresholds
        cycle_thresh = get_battery_cycle_thresholds(sys, details.get("device_name", ""))
        data["cycle_warn_threshold"] = cycle_thresh["warn"]
        data["cycle_fail_threshold"] = cycle_thresh["fail"]

        cycle_count = data.get("cycle_count")
        cycle_issue: str | None = None
        if cycle_count is not None:
            if cycle_count >= cycle_thresh["fail"]:
                cycle_issue = "fail"
            elif cycle_count >= cycle_thresh["warn"]:
                cycle_issue = "warn"

        # Build shared display strings
        health_str = f"{health_pct:.0f}%" if health_pct is not None else "Cannot determine"
        cycle_str = f"{cycle_count} cycles" if cycle_count is not None else ""
        charged_str = f"{data['percent_charged']:.0f}% charged"
        charger_str = (
            f" · {data['charger_watts']}W"
            if data.get("charger_watts")
            else (" · plugged in" if data.get("plugged_in") else "")
        )
        condition_str = (
            f" · {data['condition']}"
            if data.get("condition") and data["condition"] != "Good"
            else ""
        )
        data["card_sub_detail"] = charged_str + charger_str + condition_str

        # Status — health_pct drives primary status; cycle count can escalate PASS→WARN
        if health_pct is not None and health_pct < BATTERY_HEALTH_WARN:
            self.result.mark_fail(
                summary=f"Health critical: {health_str} of design capacity",
                data=data,
            )
        elif health_pct is not None and health_pct < BATTERY_HEALTH_GOOD:
            self.result.mark_warn(
                summary=f"Degraded: {health_str} health",
                data=data,
            )
        elif cycle_issue == "fail":
            self.result.mark_warn(
                summary=f"Cycle count high: {cycle_count} (≥{cycle_thresh['fail']}) — replace soon",
                data=data,
            )
        elif cycle_issue == "warn":
            self.result.mark_warn(
                summary=f"Cycle count elevated: {cycle_count} (≥{cycle_thresh['warn']})",
                data=data,
            )
        else:
            if health_pct is not None:
                summary_parts = [f"Health {health_str}"]
            else:
                summary_parts = ["Health: Cannot determine"]
            if cycle_str:
                summary_parts.append(cycle_str)
            self.result.mark_pass(
                summary=" · ".join(summary_parts),
                data=data,
            )

        return self.result

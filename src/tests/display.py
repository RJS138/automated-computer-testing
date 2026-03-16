"""Automatic display information test.

Enumerates all connected displays (internal and external) and collects:
  - Name, manufacturer, model, serial number
  - Current resolution and refresh rate
  - Maximum resolution and refresh rate (from available modes)
  - Physical size in mm and diagonal in inches
  - Connection type (Internal / HDMI / DisplayPort / USB-C / …)
  - Primary / built-in flags

Platform coverage:
  macOS  — CoreGraphics (resolution, refresh, size) + system_profiler (name, serial)
  Linux  — xrandr (resolution, refresh, modes) + /sys/class/drm EDID (name, serial)
  Windows — WMI Win32_DesktopMonitor + ctypes EnumDisplaySettings
"""

import asyncio
import math
import platform
import subprocess
from typing import Any

from ..models.test_result import TestResult
from .base import BaseTest

# ---------------------------------------------------------------------------
# Helpers — macOS
# ---------------------------------------------------------------------------


def _sp_displays_macos() -> list[dict]:
    """Parse `system_profiler SPDisplaysDataType -json` into per-display dicts."""
    import json

    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        sp = json.loads(raw).get("SPDisplaysDataType", [])
    except Exception:
        return []

    displays: list[dict] = []
    for gpu_entry in sp:
        for disp in gpu_entry.get("spdisplays_ndrvs", []):
            d: dict[str, Any] = {}
            d["name"] = disp.get("_name", "Unknown Display")
            d["manufacturer"] = disp.get("spdisplays_vendor") or None
            d["serial"] = disp.get("spdisplays_serialnumber") or None

            conn = disp.get("spdisplays_connection_type", "")
            internal = (
                disp.get("spdisplays_displayport_isinternal") == "spdisplays_yes"
                or "internal" in conn.lower()
            )
            d["is_internal"] = internal
            d["is_primary"] = disp.get("spdisplays_main") == "spdisplays_yes"
            d["connection_type"] = "Internal" if internal else (conn or None)

            # Native pixel resolution  e.g. "3456 x 2234"
            pixels = disp.get("spdisplays_pixels", "") or disp.get("spdisplays_resolution", "")
            if pixels:
                parts = [p.strip() for p in pixels.split("x")]
                if len(parts) == 2:
                    try:
                        w = int(parts[0].split()[-1])
                        h = int(parts[1].split()[0])
                        d["current_resolution"] = f"{w}x{h}"
                    except (ValueError, IndexError):
                        pass

            # Refresh rate from system_profiler (present for some external displays)
            hz_raw = disp.get("spdisplays_refreshrate", "")
            if hz_raw:
                try:
                    d["current_refresh_hz"] = float(hz_raw.split()[0])
                except (ValueError, IndexError):
                    pass

            displays.append(d)
    return displays


def _panel_tech(display_type: str) -> str:
    """Map a macOS Display Type string to a technology label (with Apple branding)."""
    dt = display_type.lower()
    if "oled" in dt:
        return "OLED"
    if "liquid retina xdr" in dt:
        return "Mini-LED LCD (Liquid Retina XDR)"
    if "liquid retina" in dt:
        return "IPS LCD (Liquid Retina)"
    if "retina" in dt:
        return "IPS LCD (Retina)"
    if "qled" in dt:
        return "QLED"
    if "ips" in dt:
        return "IPS LCD"
    if "tn " in dt or dt.startswith("tn"):
        return "TN LCD"
    if "lcd" in dt or "led" in dt:
        return "LCD"
    return display_type


def _sp_text_macos() -> dict[str, dict]:
    """
    Parse `system_profiler SPDisplaysDataType` text output for fields not
    available in JSON mode: Display Type, native resolution, panel serial,
    and current UI resolution / refresh rate.

    Returns a dict keyed by display name as shown by system_profiler.
    """
    import re

    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception:
        return {}

    results: dict[str, dict] = {}
    current: str | None = None
    in_displays = False

    for line in raw.splitlines():
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip())
        content = line.strip()

        if content == "Displays:":
            in_displays = True
            continue

        # Exiting a Displays: block when indent drops back
        if in_displays and indent < 8 and not content.endswith(":"):
            in_displays = False

        # Display name: exactly 8 spaces, ends with ":", no ": " inside
        if in_displays and indent == 8 and content.endswith(":") and ": " not in content:
            current = content[:-1]
            results[current] = {}
            continue

        if current is None or not in_displays:
            continue

        if indent >= 10 and ": " in content:
            key, _, val = content.partition(": ")
            key = key.strip()
            val = val.strip()

            if key == "Display Type":
                results[current]["display_type"] = val
                results[current]["panel_technology"] = _panel_tech(val)

            elif key == "Resolution":
                # "3024 x 1964 Retina" → native pixel resolution
                m = re.match(r"(\d+)\s*[xX]\s*(\d+)", val)
                if m:
                    results[current]["native_resolution"] = f"{m.group(1)}x{m.group(2)}"

            elif key == "Display Serial Number":
                results[current]["panel_serial"] = val

            elif key == "UI Looks like":
                # "1512 x 982 @ 120.00Hz (Retina)"
                m = re.match(r"(\d+)\s*[xX]\s*(\d+)\s*@\s*([\d.]+)\s*[Hh]z", val)
                if m:
                    results[current]["ui_resolution"] = f"{m.group(1)}x{m.group(2)}"
                    results[current]["ui_refresh_hz"] = float(m.group(3))

    return results


def _cg_display_info() -> list[dict]:
    """
    Use CoreGraphics to get per-display current mode info and physical size.

    Note: CGDisplayCopyAllDisplayModes is intentionally omitted — its CFArray
    elements are typed incorrectly by ctypes on macOS Sequoia, causing crashes.
    Current mode only (resolution, refresh rate, physical size) is safe.
    """
    import ctypes

    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    except OSError:
        return []

    cg.CGGetActiveDisplayList.argtypes = [
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    cg.CGGetActiveDisplayList.restype = ctypes.c_int32
    cg.CGDisplayIsMain.restype = ctypes.c_bool
    cg.CGDisplayIsBuiltin.restype = ctypes.c_bool
    cg.CGDisplayCopyDisplayMode.restype = ctypes.c_void_p
    cg.CGDisplayModeRelease.argtypes = [ctypes.c_void_p]
    cg.CGDisplayModeGetRefreshRate.argtypes = [ctypes.c_void_p]
    cg.CGDisplayModeGetRefreshRate.restype = ctypes.c_double
    cg.CGDisplayModeGetWidth.argtypes = [ctypes.c_void_p]
    cg.CGDisplayModeGetWidth.restype = ctypes.c_size_t
    cg.CGDisplayModeGetHeight.argtypes = [ctypes.c_void_p]
    cg.CGDisplayModeGetHeight.restype = ctypes.c_size_t

    class _CGSize(ctypes.Structure):
        _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

    cg.CGDisplayScreenSize.argtypes = [ctypes.c_uint32]
    cg.CGDisplayScreenSize.restype = _CGSize

    max_disp = 16
    ids = (ctypes.c_uint32 * max_disp)()
    n = ctypes.c_uint32(0)
    try:
        cg.CGGetActiveDisplayList(max_disp, ids, ctypes.byref(n))
    except Exception:
        return []

    results: list[dict] = []
    for i in range(n.value):
        did = ids[i]
        d: dict[str, Any] = {}

        try:
            d["is_primary"] = bool(cg.CGDisplayIsMain(did))
            d["is_internal"] = bool(cg.CGDisplayIsBuiltin(did))
        except Exception:
            d["is_primary"] = False
            d["is_internal"] = False

        # Current mode (resolution + refresh rate)
        try:
            mode = cg.CGDisplayCopyDisplayMode(did)
            if mode:
                w = cg.CGDisplayModeGetWidth(mode)
                h = cg.CGDisplayModeGetHeight(mode)
                hz = cg.CGDisplayModeGetRefreshRate(mode)
                d["current_resolution"] = f"{w}x{h}"
                d["current_refresh_hz"] = hz if hz > 0 else None
                cg.CGDisplayModeRelease(mode)
        except Exception:
            pass

        # Physical size → diagonal in inches
        try:
            sz = cg.CGDisplayScreenSize(did)
            if sz.width > 0 and sz.height > 0:
                d["physical_width_mm"] = round(sz.width)
                d["physical_height_mm"] = round(sz.height)
                d["inches"] = round(math.sqrt(sz.width**2 + sz.height**2) / 25.4, 1)
        except Exception:
            pass

        results.append(d)

    return results


def _get_displays_macos() -> list[dict]:
    """Merge CoreGraphics and system_profiler (JSON + text) data into final display list."""
    cg_list = _cg_display_info()
    sp_list = _sp_displays_macos()
    sp_text = _sp_text_macos()

    def _overlay(cg: dict, sp: dict) -> None:
        for key in ("name", "manufacturer", "serial", "connection_type"):
            if sp.get(key) and not cg.get(key):
                cg[key] = sp[key]
        if not cg.get("current_refresh_hz") and sp.get("current_refresh_hz"):
            cg["current_refresh_hz"] = sp["current_refresh_hz"]

    used_sp: set[int] = set()

    # Pass 1: match by primary + internal flags
    for cg in cg_list:
        for j, sp in enumerate(sp_list):
            if j in used_sp:
                continue
            if cg.get("is_primary") == sp.get("is_primary") and cg.get("is_internal") == sp.get(
                "is_internal"
            ):
                _overlay(cg, sp)
                used_sp.add(j)
                break

    # Pass 2: match remaining by resolution
    for cg in cg_list:
        if cg.get("name"):
            continue
        for j, sp in enumerate(sp_list):
            if j in used_sp:
                continue
            if cg.get("current_resolution") == sp.get("current_resolution"):
                _overlay(cg, sp)
                used_sp.add(j)
                break

    # Fallback names
    for cg in cg_list:
        if not cg.get("name"):
            cg["name"] = "Display" if not cg.get("is_internal") else "Built-in Display"

    # Merge text-parsed data (panel type, native resolution, panel serial, UI resolution)
    for cg in cg_list:
        name = cg.get("name", "")
        txt = sp_text.get(name)
        if not txt:
            # Fuzzy match: try substring
            for k, v in sp_text.items():
                if name.lower() in k.lower() or k.lower() in name.lower():
                    txt = v
                    break
        if txt:
            for key in (
                "panel_technology",
                "panel_serial",
                "native_resolution",
                "ui_resolution",
                "ui_refresh_hz",
                "display_type",
            ):
                if txt.get(key) and not cg.get(key):
                    cg[key] = txt[key]
            # Fill in refresh rate from UI Looks like if CG didn't have it
            if not cg.get("current_refresh_hz") and txt.get("ui_refresh_hz"):
                cg["current_refresh_hz"] = txt["ui_refresh_hz"]

    return cg_list


# ---------------------------------------------------------------------------
# Helpers — Linux
# ---------------------------------------------------------------------------


def _parse_edid(data: bytes) -> dict:
    """Extract manufacturer, model, and serial from raw EDID bytes."""
    if len(data) < 128 or data[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return {}

    result: dict[str, Any] = {}

    # Manufacturer ID: 3 letters packed into bytes 8-9
    mid = (data[8] << 8) | data[9]
    c1 = chr(((mid >> 10) & 0x1F) + 64)
    c2 = chr(((mid >> 5) & 0x1F) + 64)
    c3 = chr((mid & 0x1F) + 64)
    result["manufacturer_id"] = c1 + c2 + c3

    # Product code (bytes 10-11, LE)
    result["product_code"] = f"{(data[11] << 8) | data[10]:04X}"

    # Descriptor blocks at offsets 54, 72, 90, 108
    for offset in (54, 72, 90, 108):
        if offset + 18 > len(data):
            break
        block = data[offset : offset + 18]
        if block[0] != 0 or block[1] != 0:
            continue  # Timing descriptor, not monitor descriptor
        tag = block[3]
        text = block[5:].decode("ascii", errors="ignore").rstrip("\n").strip()
        if tag == 0xFF:
            result["serial"] = text
        elif tag == 0xFC:
            result["model"] = text
        elif tag == 0xFE and "manufacturer" not in result:
            result["manufacturer"] = text

    # Physical size from bytes 21-22 (cm)
    w_cm, h_cm = data[21], data[22]
    if w_cm and h_cm:
        result["physical_width_mm"] = w_cm * 10
        result["physical_height_mm"] = h_cm * 10
        result["inches"] = round(math.sqrt((w_cm * 10) ** 2 + (h_cm * 10) ** 2) / 25.4, 1)

    return result


def _get_displays_linux() -> list[dict]:
    """Parse xrandr output + EDID sysfs for display info."""
    try:
        raw = subprocess.check_output(
            ["xrandr", "--verbose"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return []

    import re

    displays: list[dict] = []
    current: dict | None = None
    in_edid = False
    edid_hex = ""

    for line in raw.splitlines():
        # New connected output
        m = re.match(r"^(\S+) connected\s+(primary\s+)?(\d+x\d+\+\d+\+\d+)?", line)
        if m:
            if current is not None:
                if edid_hex:
                    current.update(_parse_edid(bytes.fromhex(edid_hex)))
                displays.append(current)
            name = m.group(1)
            is_primary = bool(m.group(2))
            res_match = m.group(3)
            current = {
                "name": name,
                "is_primary": is_primary,
                "is_internal": name.lower().startswith(("edp", "lvds", "dsi")),
                "connection_type": _linux_conn_type(name),
            }
            if res_match:
                current["current_resolution"] = res_match.split("+")[0]
            in_edid = False
            edid_hex = ""
            continue

        if current is None:
            continue

        # Current mode line: "   1920x1080     60.00*+  50.00"
        m = re.match(r"^\s+(\d+x\d+)\s+([\d.]+)\*", line)
        if m:
            current.setdefault("current_resolution", m.group(1))
            try:
                current["current_refresh_hz"] = float(m.group(2))
            except ValueError:
                pass

        # Collect all modes for max resolution/refresh
        m = re.match(r"^\s+(\d+x\d+)\s+([\d. *+]+)", line)
        if m:
            try:
                w, h = (int(x) for x in m.group(1).split("x"))
                prev_w, prev_h = (
                    (int(x) for x in current.get("max_resolution", "0x0").split("x"))
                    if "max_resolution" in current
                    else (0, 0)
                )
                if w * h >= prev_w * prev_h:
                    current["max_resolution"] = f"{w}x{h}"
            except (ValueError, AttributeError):
                pass
            for hz_str in re.findall(r"[\d]+\.[\d]+", m.group(2)):
                try:
                    hz = float(hz_str)
                    if hz > current.get("max_refresh_hz", 0.0):
                        current["max_refresh_hz"] = hz
                except ValueError:
                    pass

        # EDID block
        if "EDID:" in line:
            in_edid = True
            edid_hex = ""
            continue
        if in_edid:
            stripped = line.strip().replace(" ", "")
            if all(c in "0123456789abcdefABCDEF" for c in stripped) and stripped:
                edid_hex += stripped
            else:
                in_edid = False

    if current is not None:
        if edid_hex:
            current.update(_parse_edid(bytes.fromhex(edid_hex)))
        displays.append(current)

    return displays


def _linux_conn_type(name: str) -> str:
    n = name.lower()
    if n.startswith(("edp", "lvds", "dsi")):
        return "Internal"
    if "hdmi" in n:
        return "HDMI"
    if "dp" in n or "displayport" in n:
        return "DisplayPort"
    if "usb" in n:
        return "USB-C"
    if "vga" in n:
        return "VGA"
    if "dvi" in n:
        return "DVI"
    return "Unknown"


# ---------------------------------------------------------------------------
# Helpers — Windows
# ---------------------------------------------------------------------------


def _get_displays_windows() -> list[dict]:
    """Collect display info via WMI and ctypes EnumDisplaySettings."""

    displays: list[dict] = []

    try:
        import wmi

        c = wmi.WMI()

        # Map monitor instance names to WMI monitor objects
        monitors: dict[str, Any] = {}
        for m in c.Win32_DesktopMonitor():
            monitors[m.PNPDeviceID or ""] = m

        # Video controllers
        for vc in c.Win32_VideoController():
            d: dict[str, Any] = {
                "name": vc.Name or "Unknown",
                "manufacturer": vc.AdapterCompatibility or None,
                "is_internal": False,
                "is_primary": True,  # assume first is primary
            }
            try:
                d["current_resolution"] = (
                    f"{vc.CurrentHorizontalResolution}x{vc.CurrentVerticalResolution}"
                )
            except Exception:
                pass
            try:
                d["current_refresh_hz"] = float(vc.CurrentRefreshRate)
                d["max_refresh_hz"] = float(vc.MaxRefreshRate)
            except Exception:
                pass
            displays.append(d)

        # Add physical monitor details
        for _pnp, mon in monitors.items():
            d = {
                "name": mon.Caption or mon.Name or "Monitor",
                "manufacturer": mon.MonitorManufacturer or None,
                "is_internal": False,
                "is_primary": False,
                "connection_type": "Unknown",
            }
            try:
                d["current_resolution"] = f"{mon.ScreenWidth}x{mon.ScreenHeight}"
            except Exception:
                pass
            displays.append(d)

    except Exception:
        # WMI not available — try ctypes EnumDisplayDevices
        try:
            displays = _windows_enum_displays()
        except Exception:
            pass

    return displays


def _windows_enum_displays() -> list[dict]:
    import ctypes
    import ctypes.wintypes

    displays: list[dict] = []

    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("DeviceName", ctypes.c_wchar * 32),
            ("DeviceString", ctypes.c_wchar * 128),
            ("StateFlags", ctypes.c_ulong),
            ("DeviceID", ctypes.c_wchar * 128),
            ("DeviceKey", ctypes.c_wchar * 128),
        ]

    class DEVMODE(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", ctypes.c_wchar * 32),
            ("dmSpecVersion", ctypes.c_ushort),
            ("dmDriverVersion", ctypes.c_ushort),
            ("dmSize", ctypes.c_ushort),
            ("dmDriverExtra", ctypes.c_ushort),
            ("dmFields", ctypes.c_ulong),
            ("dmPositionX", ctypes.c_long),
            ("dmPositionY", ctypes.c_long),
            ("dmDisplayOrientation", ctypes.c_ulong),
            ("dmDisplayFixedOutput", ctypes.c_ulong),
            ("dmColor", ctypes.c_short),
            ("dmDuplex", ctypes.c_short),
            ("dmYResolution", ctypes.c_short),
            ("dmTTOption", ctypes.c_short),
            ("dmCollate", ctypes.c_short),
            ("dmFormName", ctypes.c_wchar * 32),
            ("dmLogPixels", ctypes.c_ushort),
            ("dmBitsPerPel", ctypes.c_ulong),
            ("dmPelsWidth", ctypes.c_ulong),
            ("dmPelsHeight", ctypes.c_ulong),
            ("dmDisplayFlags", ctypes.c_ulong),
            ("dmDisplayFrequency", ctypes.c_ulong),
            *[(f"_pad{i}", ctypes.c_char) for i in range(40)],
        ]

    DISPLAY_DEVICE_ACTIVE = 0x00000001

    i = 0
    while True:
        dd = DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(dd)
        if not ctypes.windll.user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not (dd.StateFlags & DISPLAY_DEVICE_ACTIVE):
            continue

        d: dict[str, Any] = {
            "name": dd.DeviceString.strip(),
            "is_primary": bool(dd.StateFlags & 0x00000004),
            "is_internal": False,
        }

        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(dm)
        if ctypes.windll.user32.EnumDisplaySettingsW(
            dd.DeviceName,
            -1,
            ctypes.byref(dm),  # ENUM_CURRENT_SETTINGS = -1
        ):
            d["current_resolution"] = f"{dm.dmPelsWidth}x{dm.dmPelsHeight}"
            if dm.dmDisplayFrequency:
                d["current_refresh_hz"] = float(dm.dmDisplayFrequency)

        displays.append(d)

    return displays


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class DisplayTest(BaseTest):
    """Automatic display information gathering test."""

    async def run(self) -> TestResult:
        self.result.mark_running()

        sys_name = platform.system()
        loop = asyncio.get_event_loop()

        if sys_name == "Darwin":
            displays = await loop.run_in_executor(None, _get_displays_macos)
        elif sys_name == "Linux":
            displays = await loop.run_in_executor(None, _get_displays_linux)
        elif sys_name == "Windows":
            displays = await loop.run_in_executor(None, _get_displays_windows)
        else:
            displays = []

        data: dict[str, Any] = {
            "displays": displays,
            "count": len(displays),
        }

        if not displays:
            self.result.mark_warn("No display information available", data)
            return self.result

        internal = [d for d in displays if d.get("is_internal")]
        external = [d for d in displays if not d.get("is_internal")]

        parts = []
        if internal:
            parts.append(f"{len(internal)} internal")
        if external:
            parts.append(f"{len(external)} external")
        summary = f"{len(displays)} display(s): {', '.join(parts)}"

        self.result.mark_pass(summary, data)
        return self.result

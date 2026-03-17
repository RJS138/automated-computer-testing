"""Network test: Wi-Fi (AP, Tx/Rx, speed), Bluetooth, adapter list."""

import asyncio
import json as _json
import platform
import re
import socket
import subprocess
import time
import urllib.request

import psutil

from ..config import PING_TARGET, PING_TIMEOUT
from ..models.test_result import TestResult
from .base import BaseTest

# macOS airport binary path
_AIRPORT = (
    "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
)

# BT HCI version → human version string (per Bluetooth Core Spec)
_BT_HCI_VERSION = {
    "0x06": "4.0",
    "0x07": "4.1",
    "0x08": "4.2",
    "0x09": "5.0",
    "0x0a": "5.1",
    "0x0b": "5.2",
    "0x0c": "5.3",
    "0x0d": "5.4",
}


# ---------------------------------------------------------------------------
# Ping
# ---------------------------------------------------------------------------


async def _ping(host: str, timeout: int) -> tuple[bool, float | None]:
    sys = platform.system()
    cmd = (
        ["ping", "-n", "1", "-w", str(timeout * 1000), host]
        if sys == "Windows"
        else ["ping", "-c", "1", "-W", str(timeout), host]
    )
    try:
        loop = asyncio.get_event_loop()
        start = time.monotonic()
        proc = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: subprocess.run(cmd, capture_output=True, text=True)),
            timeout=timeout + 2,
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "time=" in line or "time<" in line:
                    for part in line.split():
                        if part.startswith("time="):
                            try:
                                return True, round(float(part[5:].rstrip("ms")), 1)
                            except ValueError:
                                pass
            return True, round(elapsed_ms, 1)
        return False, None
    except Exception:
        return False, None


# ---------------------------------------------------------------------------
# Network adapters
# ---------------------------------------------------------------------------


def _get_adapters() -> list[dict]:
    adapters = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    for name, addr_list in addrs.items():
        stat = stats.get(name)
        is_up = stat.isup if stat else False
        speed = stat.speed if stat else 0
        mac = ipv4 = ipv6 = None
        for addr in addr_list:
            if addr.family == psutil.AF_LINK:
                mac = addr.address
            elif addr.family == socket.AF_INET:
                ipv4 = addr.address
            elif addr.family == socket.AF_INET6:
                ipv6 = addr.address
        adapters.append(
            {
                "name": name,
                "is_up": is_up,
                "speed_mbps": speed,
                "mac": mac,
                "ipv4": ipv4,
                "ipv6": ipv6,
            }
        )
    return adapters


# ---------------------------------------------------------------------------
# Speed test (download via Cloudflare)
# ---------------------------------------------------------------------------


def _speed_test_download(test_mb: int = 5) -> dict:
    """Download test_mb MB and return download_mbps."""
    url = f"https://speed.cloudflare.com/__down?bytes={test_mb * 1024 * 1024}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PCTester/1.0"})
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read()
        elapsed = time.monotonic() - start
        mbps = round((len(payload) * 8) / (elapsed * 1_000_000), 1)
        return {"download_mbps": mbps}
    except Exception as exc:
        return {"speed_error": str(exc)}


# ---------------------------------------------------------------------------
# Wi-Fi — macOS
# ---------------------------------------------------------------------------


def _clean_security(raw: str) -> str:
    """'spairport_security_mode_wpa2_personal_mixed' → 'WPA2 Personal Mixed'"""
    s = raw.replace("spairport_security_mode_", "").replace("_", " ").strip()
    if not s:
        return "Open"
    _CAPS = {"wpa", "wpa2", "wpa3", "wep", "wps", "pmf", "sae", "owe"}
    return " ".join(w.upper() if w.lower() in _CAPS else w.capitalize() for w in s.split())


def _get_wifi_macos() -> dict:
    """
    Parse SPAirPortDataType JSON.
    Note: macOS 13+ (Ventura/Sonoma/Sequoia) redacts SSID/BSSID for privacy.
    Signal is in 'spairport_signal_noise' as '-44 dBm / -93 dBm'.
    Link rate is in 'spairport_network_rate' (integer Mbps).
    """
    info: dict = {"connected": False, "available_networks": []}
    try:
        r = subprocess.run(
            ["system_profiler", "SPAirPortDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = _json.loads(r.stdout).get("SPAirPortDataType", [])
        for entry in data:
            for iface in entry.get("spairport_airport_interfaces", []):
                info["interface"] = iface.get("_name", "")
                current = iface.get("spairport_current_network_information", {})

                # Connected = type is 'station'
                if current.get("spairport_network_type") == "spairport_network_type_station":
                    info["connected"] = True
                    ssid = current.get("_name", "")
                    info["ssid"] = None if ssid == "<redacted>" else (ssid or None)

                    # Signal from "spairport_signal_noise": "-44 dBm / -93 dBm"
                    sig_noise = str(current.get("spairport_signal_noise", ""))
                    m = re.search(r"(-?\d+)\s*dBm", sig_noise)
                    if m:
                        info["signal_dbm"] = int(m.group(1))

                    info["channel"] = current.get("spairport_network_channel")
                    info["standard"] = current.get("spairport_network_phymode")
                    info["security"] = _clean_security(current.get("spairport_security_mode", ""))

                    # Link rate (integer Mbps)
                    rate = current.get("spairport_network_rate")
                    if rate:
                        info["tx_rate_mbps"] = int(rate)

                # Nearby networks — key varies by macOS version:
                # macOS 13+: spairport_airport_other_local_wireless_networks
                # older macOS / not connected: spairport_airport_local_wireless_networks
                nearby = (
                    iface.get("spairport_airport_other_local_wireless_networks")
                    or iface.get("spairport_airport_local_wireless_networks")
                    or []
                )
                for net in nearby:
                    ssid = net.get("_name", "")
                    sig_noise = str(net.get("spairport_signal_noise", ""))
                    m = re.search(r"(-?\d+)\s*dBm", sig_noise)
                    info["available_networks"].append(
                        {
                            "ssid": None if ssid == "<redacted>" else (ssid or "Hidden"),
                            "bssid": None,
                            "signal_dbm": int(m.group(1)) if m else None,
                            "channel": net.get("spairport_network_channel"),
                            "security": _clean_security(net.get("spairport_security_mode", "")),
                        }
                    )
                break  # first interface only
    except Exception:
        pass

    # Fallback: use airport -s for available networks if system_profiler returned none.
    # Works on Intel Macs / older macOS where the JSON key is absent or empty.
    if not info["available_networks"]:
        try:
            r = subprocess.run(
                [_AIRPORT, "-s"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            for line in r.stdout.splitlines()[1:]:  # skip header row
                # Columns: SSID  BSSID  RSSI  CHANNEL  HT  CC  SECURITY
                # SSID is right-aligned and may contain spaces; BSSID is a MAC address
                m = re.search(
                    r"^(.+?)\s+((?:[0-9a-f]{2}:){5}[0-9a-f]{2})\s+(-\d+)\s+(\S+)",
                    line.strip(),
                    re.IGNORECASE,
                )
                if m:
                    try:
                        channel = int(m.group(4).split(",")[0])
                    except ValueError:
                        channel = None
                    info["available_networks"].append(
                        {
                            "ssid": m.group(1).strip() or "Hidden",
                            "bssid": m.group(2),
                            "signal_dbm": int(m.group(3)),
                            "channel": channel,
                            "security": None,
                        }
                    )
        except Exception:
            pass

    # Fallback: try networksetup for SSID (works on older macOS)
    if info.get("connected") and not info.get("ssid"):
        try:
            iface = info.get("interface", "en0")
            r = subprocess.run(
                ["networksetup", "-getairportnetwork", iface],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "Current Wi-Fi Network:" in r.stdout:
                info["ssid"] = r.stdout.split("Current Wi-Fi Network:", 1)[1].strip()
        except Exception:
            pass

    return info


# ---------------------------------------------------------------------------
# Wi-Fi — Windows
# ---------------------------------------------------------------------------


def _get_wifi_windows() -> dict:
    info: dict = {"connected": False, "available_networks": []}
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in r.stdout.splitlines():
            line = line.strip()
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.strip()
            if k == "name":
                info["interface"] = v
            elif k == "ssid" and "bssid" not in k:
                info["ssid"] = v
                info["connected"] = True
            elif k == "bssid":
                info["bssid"] = v
            elif k == "signal":
                try:
                    info["signal_pct"] = int(v.rstrip("%"))
                except ValueError:
                    pass
            elif k == "channel":
                try:
                    info["channel"] = int(v)
                except ValueError:
                    pass
            elif k == "transmit rate (mbps)":
                try:
                    info["tx_rate_mbps"] = float(v)
                except ValueError:
                    pass
            elif k == "receive rate (mbps)":
                try:
                    info["rx_rate_mbps"] = float(v)
                except ValueError:
                    pass
            elif k == "radio type":
                info["standard"] = v
            elif k == "authentication":
                info["security"] = v
    except Exception:
        pass

    # Available networks
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        current: dict = {}
        for line in r.stdout.splitlines():
            line = line.strip()
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.strip()
            if k == "ssid" and "bssid" not in k:
                if current.get("ssid"):
                    info["available_networks"].append(current)
                current = {"ssid": v}
            elif "authentication" in k:
                current["security"] = v
            elif k == "signal":
                try:
                    current["signal_pct"] = int(v.rstrip("%"))
                except ValueError:
                    pass
            elif k.startswith("bssid"):
                current.setdefault("bssid", v)
        if current.get("ssid"):
            info["available_networks"].append(current)
    except Exception:
        pass

    return info


# ---------------------------------------------------------------------------
# Wi-Fi — Linux
# ---------------------------------------------------------------------------


def _get_wifi_linux() -> dict:
    info: dict = {"connected": False, "available_networks": []}
    wifi_iface = None

    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in r.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                wifi_iface = parts[0]
                info["connected"] = True
                info["interface"] = wifi_iface
                info["ssid"] = parts[3] if len(parts) > 3 else None
                break
    except Exception:
        pass

    if wifi_iface:
        try:
            r = subprocess.run(
                ["iw", "dev", wifi_iface, "link"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if "SSID:" in line:
                    info["ssid"] = line.split("SSID:")[-1].strip()
                elif "signal:" in line:
                    m = re.search(r"signal:\s*(-?\d+)", line)
                    if m:
                        info["signal_dbm"] = int(m.group(1))
                elif "tx bitrate:" in line:
                    m = re.search(r"([\d.]+)\s*MBit", line)
                    if m:
                        info["tx_rate_mbps"] = float(m.group(1))
                elif "freq:" in line:
                    m = re.search(r"freq:\s*(\d+)", line)
                    if m:
                        info["frequency_mhz"] = int(m.group(1))
        except Exception:
            pass

    # Available networks via nmcli (multiline mode avoids BSSID colon conflict)
    try:
        r = subprocess.run(
            [
                "nmcli",
                "-m",
                "multiline",
                "-f",
                "SSID,BSSID,SIGNAL,CHAN,SECURITY",
                "dev",
                "wifi",
                "list",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        nets: list[dict] = []
        cur: dict = {}
        for line in r.stdout.splitlines():
            if line.startswith("SSID:"):
                if cur:
                    nets.append(cur)
                cur = {"ssid": line[5:].strip()}
            elif line.startswith("BSSID:") and cur:
                cur["bssid"] = line[6:].strip()
            elif line.startswith("SIGNAL:") and cur:
                try:
                    cur["signal_pct"] = int(line[7:].strip())
                except ValueError:
                    pass
            elif line.startswith("CHAN:") and cur:
                try:
                    cur["channel"] = int(line[5:].strip())
                except ValueError:
                    pass
            elif line.startswith("SECURITY:") and cur:
                cur["security"] = line[9:].strip()
        if cur:
            nets.append(cur)
        info["available_networks"] = [n for n in nets if n.get("ssid")]
    except Exception:
        pass

    return info


# ---------------------------------------------------------------------------
# Bluetooth — macOS
# ---------------------------------------------------------------------------


def _get_bluetooth_macos() -> dict:
    """
    Parse SPBluetoothDataType JSON.
    Modern macOS uses 'controller_properties' dict + 'device_connected'/'device_not_connected' lists.
    Older macOS used 'spbluetooth_local_device_title' dict.
    """
    bt: dict = {"available": False}
    try:
        r = subprocess.run(
            ["system_profiler", "SPBluetoothDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = _json.loads(r.stdout).get("SPBluetoothDataType", [])
        for entry in data:
            # Modern macOS (Ventura+): controller_properties dict
            ctrl = entry.get("controller_properties", {})
            if ctrl:
                bt["available"] = True
                state = str(ctrl.get("controller_state", "")).lower()
                bt["enabled"] = "on" in state
                bt["address"] = ctrl.get("controller_address")
                bt["chipset"] = ctrl.get("controller_chipset")
                bt["transport"] = ctrl.get("controller_transport")
                # Parse supported services for display
                svc_str = ctrl.get("controller_supportedServices", "")
                m = re.search(r"<(.+?)>", svc_str)
                bt["services"] = m.group(1).strip() if m else None
                # Connected / paired device counts
                connected = entry.get("device_connected", [])
                not_connected = entry.get("device_not_connected", [])
                bt["devices_connected"] = len(connected) if isinstance(connected, list) else 0
                bt["devices_paired"] = (len(connected) if isinstance(connected, list) else 0) + (
                    len(not_connected) if isinstance(not_connected, list) else 0
                )
                break

            # Older macOS: spbluetooth_local_device_title
            local = entry.get("spbluetooth_local_device_title", {})
            if local:
                bt["available"] = True
                state = str(local.get("spbluetooth_state", "")).lower()
                bt["enabled"] = state not in (
                    "off",
                    "disabled",
                    "spbluetooth_state_off",
                )
                bt["address"] = local.get("spbluetooth_local_address")
                bt["name"] = local.get("spbluetooth_local_name")
                bt["chipset"] = local.get("spbluetooth_chipset")
                hci = local.get("spbluetooth_hci_version", "")
                bt["version"] = _BT_HCI_VERSION.get(hci, hci) if hci else None
                break
    except Exception:
        pass
    return bt


# ---------------------------------------------------------------------------
# Bluetooth — Windows
# ---------------------------------------------------------------------------


def _get_bluetooth_windows() -> dict:
    bt: dict = {"available": False}
    try:
        import wmi  # type: ignore

        c = wmi.WMI()
        bt_guid = "{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}"
        for dev in c.Win32_PnPEntity():
            if getattr(dev, "ClassGuid", "") == bt_guid:
                bt["available"] = True
                bt["name"] = dev.Name
                bt["enabled"] = getattr(dev, "Status", "") == "OK"
                break
    except Exception:
        pass
    return bt


# ---------------------------------------------------------------------------
# Physical NIC enumeration
# ---------------------------------------------------------------------------


def _get_physical_nics_macos() -> dict:
    """Count physical NICs via networksetup -listallhardwareports."""
    nics: dict[str, int] = {"wifi": 0, "ethernet": 0, "thunderbolt": 0, "usb": 0, "other": 0}
    try:
        r = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        current_port: str | None = None
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("Hardware Port:"):
                current_port = line.split(":", 1)[1].strip().lower()
            elif line.startswith("Device:") and current_port is not None:
                if "wi-fi" in current_port or "airport" in current_port:
                    nics["wifi"] += 1
                elif "thunderbolt" in current_port:
                    nics["thunderbolt"] += 1
                elif "usb" in current_port:
                    nics["usb"] += 1
                elif "ethernet" in current_port:
                    nics["ethernet"] += 1
                else:
                    nics["other"] += 1
                current_port = None
    except Exception:
        pass
    nics["total"] = sum(nics.values())
    return nics


def _get_physical_nics_windows() -> dict:
    """Count physical NICs via WMI Win32_NetworkAdapter(PhysicalAdapter=True)."""
    nics: dict[str, int] = {"wifi": 0, "ethernet": 0, "other": 0}
    try:
        import wmi  # type: ignore

        c = wmi.WMI()
        for nic in c.Win32_NetworkAdapter(PhysicalAdapter=True):
            name = (nic.Name or "").lower()
            if any(k in name for k in ("wireless", "wi-fi", "wifi", "802.11", "wlan")):
                nics["wifi"] += 1
            elif any(k in name for k in ("ethernet", "gigabit", "lan", "realtek", "intel")):
                nics["ethernet"] += 1
            else:
                nics["other"] += 1
    except Exception:
        pass
    nics["total"] = sum(nics.values())
    return nics


def _get_physical_nics_linux() -> dict:
    """Count physical NICs via /sys/class/net (device symlink = physical)."""
    from pathlib import Path

    nics: dict[str, int] = {"wifi": 0, "ethernet": 0, "other": 0}
    try:
        for iface in Path("/sys/class/net").iterdir():
            if not (iface / "device").exists():
                continue  # skip virtual (lo, docker0, veth*, etc.)
            if (iface / "wireless").exists() or (iface / "phy80211").exists():
                nics["wifi"] += 1
            else:
                nics["ethernet"] += 1
    except Exception:
        pass
    nics["total"] = sum(nics.values())
    return nics


def _format_nics(nics: dict) -> str:
    total = nics.get("total", 0)
    if total == 0:
        return ""
    parts = []
    for key, label in [
        ("wifi", "Wi-Fi"),
        ("ethernet", "Ethernet"),
        ("thunderbolt", "Thunderbolt"),
        ("usb", "USB LAN"),
        ("other", "Other"),
    ]:
        n = nics.get(key, 0)
        if n == 1:
            parts.append(label)
        elif n > 1:
            parts.append(f"{n}x {label}")
    label_str = ", ".join(parts)
    return (
        f"{total} NIC{'s' if total != 1 else ''}: {label_str}"
        if label_str
        else f"{total} NIC{'s' if total != 1 else ''}"
    )


# ---------------------------------------------------------------------------
# Bluetooth — Linux
# ---------------------------------------------------------------------------


def _get_bluetooth_linux() -> dict:
    bt: dict = {"available": False}
    try:
        r = subprocess.run(
            ["rfkill", "list", "bluetooth"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.stdout.strip():
            bt["available"] = True
            bt["soft_blocked"] = "Soft blocked: yes" in r.stdout
            bt["hard_blocked"] = "Hard blocked: yes" in r.stdout
            bt["enabled"] = not bt["soft_blocked"] and not bt["hard_blocked"]
    except Exception:
        pass

    if bt.get("available"):
        try:
            r = subprocess.run(
                ["bluetoothctl", "show"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("Name:"):
                    bt["name"] = line.split(":", 1)[1].strip()
                elif line.startswith("Powered:"):
                    bt["powered"] = "yes" in line.lower()
                elif line.startswith("Address:"):
                    bt["address"] = line.split(":", 1)[1].strip()
        except Exception:
            pass

    return bt


# ---------------------------------------------------------------------------
# Main test class
# ---------------------------------------------------------------------------


class NetworkTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()
        loop = asyncio.get_event_loop()
        sys = platform.system()

        # Adapters + physical NIC count
        adapters = await loop.run_in_executor(None, _get_adapters)
        if sys == "Darwin":
            nics = await loop.run_in_executor(None, _get_physical_nics_macos)
        elif sys == "Windows":
            nics = await loop.run_in_executor(None, _get_physical_nics_windows)
        else:
            nics = await loop.run_in_executor(None, _get_physical_nics_linux)

        # Wi-Fi
        if sys == "Darwin":
            wifi = await loop.run_in_executor(None, _get_wifi_macos)
        elif sys == "Windows":
            wifi = await loop.run_in_executor(None, _get_wifi_windows)
        else:
            wifi = await loop.run_in_executor(None, _get_wifi_linux)

        # Bluetooth
        if sys == "Darwin":
            bluetooth = await loop.run_in_executor(None, _get_bluetooth_macos)
        elif sys == "Windows":
            bluetooth = await loop.run_in_executor(None, _get_bluetooth_windows)
        else:
            bluetooth = await loop.run_in_executor(None, _get_bluetooth_linux)

        # Ping (Tx/Rx check)
        reachable, rtt_ms = await _ping(PING_TARGET, PING_TIMEOUT)
        wifi["ping_ok"] = reachable
        wifi["ping_rtt_ms"] = rtt_ms

        # Download speed test (only if internet reachable)
        if reachable:
            speed = await loop.run_in_executor(None, _speed_test_download)
            wifi.update(speed)

        data: dict = {
            "adapters": adapters,
            "nics": nics,
            "wifi": wifi,
            "bluetooth": bluetooth,
            "ping_target": PING_TARGET,
            "ping_reachable": reachable,
            "ping_rtt_ms": rtt_ms,
        }

        # Build display strings
        ssid = wifi.get("ssid") or ("Connected" if wifi.get("connected") else None)
        dl = wifi.get("download_mbps")
        bt_available = bluetooth.get("available", False)
        bt_enabled = bluetooth.get("enabled", False)
        bt_devs = bluetooth.get("devices_connected", 0)

        # Bluetooth — primary label for summary line
        if bt_available and bt_enabled and bt_devs:
            bt_label = f"BT On · {bt_devs} device{'s' if bt_devs != 1 else ''} connected"
        elif bt_available and bt_enabled:
            bt_label = "BT On"
        elif bt_available:
            bt_label = "BT Off"
        else:
            bt_label = "No Bluetooth"

        # Sub-detail: SSID, download speed, NIC inventory
        sub_parts = []
        if ssid:
            sub_parts.append(f"'{ssid}'")
        if dl:
            sub_parts.append(f"{dl} Mbps ↓")
        nic_str = _format_nics(nics)
        if nic_str:
            sub_parts.append(nic_str)
        data["card_sub_detail"] = " · ".join(sub_parts)

        # Overall status — BT promoted into summary
        active = [a for a in adapters if a["is_up"]]
        if not active:
            self.result.mark_fail(
                summary=f"No active network adapters · {bt_label}",
                data=data,
            )
        elif not wifi.get("connected"):
            nets = wifi.get("available_networks", [])
            self.result.mark_warn(
                summary=f"Wi-Fi not connected · {len(nets)} networks visible · {bt_label}",
                data=data,
            )
        elif not reachable:
            self.result.mark_warn(
                summary=f"No internet — ping {PING_TARGET} failed · {bt_label}",
                data=data,
            )
        else:
            rtt_str = f"{rtt_ms} ms" if rtt_ms else "OK"
            self.result.mark_pass(
                summary=f"Wi-Fi · ping {rtt_str} · {bt_label}",
                data=data,
            )

        return self.result

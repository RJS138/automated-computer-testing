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


def _get_battery_details_windows() -> dict:
    """Use WMI for detailed battery info on Windows."""
    details: dict = {}
    try:
        import pythoncom  # type: ignore
        import wmi  # type: ignore

        pythoncom.CoInitialize()
        try:
            c = wmi.WMI()

            # Basic info from root\cimv2
            for batt in c.Win32_Battery():
                if batt.DesignCapacity:
                    details["design_capacity_mwh"] = int(batt.DesignCapacity)
                if batt.FullChargeCapacity:
                    details["full_charge_capacity_mwh"] = int(batt.FullChargeCapacity)
                details["chemistry"] = batt.Chemistry

            # BatteryFullChargedCapacity and BatteryCycleCount live in root\wmi
            c_wmi = wmi.WMI(namespace="root\\wmi")

            try:
                for b in c_wmi.BatteryFullChargedCapacity():
                    if b.FullChargedCapacity:
                        details["full_charge_capacity_mwh"] = int(b.FullChargedCapacity)
            except Exception:
                pass

            try:
                for b in c_wmi.BatteryCycleCount():
                    if b.CycleCount is not None:
                        details["cycle_count"] = int(b.CycleCount)
            except Exception:
                pass

            # Compute health_pct if we have both capacities
            design = details.get("design_capacity_mwh")
            full = details.get("full_charge_capacity_mwh")
            if design and full and design > 0:
                details["health_pct"] = round((full / design) * 100, 1)

        finally:
            pythoncom.CoUninitialize()
    except Exception:
        pass
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
        health_str = f"{health_pct:.0f}%" if health_pct is not None else "?"
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
            summary_parts = [f"Health {health_str}"]
            if cycle_str:
                summary_parts.append(cycle_str)
            self.result.mark_pass(
                summary=" · ".join(summary_parts),
                data=data,
            )

        return self.result

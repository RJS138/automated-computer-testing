"""Storage test: physical drives, SMART health, capacity, power-on hours, speed."""

import asyncio
import json as _json
import os
import platform
import random as _random
import subprocess
import sys as _sys
import tempfile
import time
from pathlib import Path

import psutil

from ..config import STORAGE_TEST_SIZE_FULL, STORAGE_TEST_SIZE_QUICK
from ..models.test_result import TestResult
from ..thresholds import get_storage_thresholds
from .base import BaseTest


# ---------------------------------------------------------------------------
# smartctl JSON helper
# ---------------------------------------------------------------------------

def _get_smartctl_bin() -> str:
    """Return path to smartctl: bundled copy inside PyInstaller _MEIPASS, or system PATH."""
    if getattr(_sys, "frozen", False) and hasattr(_sys, "_MEIPASS"):
        bundled = os.path.join(_sys._MEIPASS, "smartctl")
        if os.path.isfile(bundled):
            return bundled
    return "smartctl"


def _smartctl_json(device: str) -> dict:
    """Run `smartctl -a --json <device>` and return parsed output or {}."""
    try:
        r = subprocess.run(
            [_get_smartctl_bin(), "-a", "--json", device],
            capture_output=True, text=True, timeout=15,
        )
        return _json.loads(r.stdout)
    except Exception:
        return {}


def _enrich_with_smartctl(drive: dict) -> None:
    """Add SMART fields to *drive* dict in-place using smartctl JSON output."""
    d = _smartctl_json(drive.get("device", ""))
    if not d:
        return

    # Overall SMART health
    smart = d.get("smart_status", {})
    if isinstance(smart.get("passed"), bool):
        drive["smart_status"] = "PASSED" if smart["passed"] else "FAILED"

    # NVMe health log (applies to NVMe drives on all platforms)
    nvme = d.get("nvme_smart_health_information_log", {})
    if nvme:
        if nvme.get("power_on_hours") is not None:
            drive["power_on_hours"] = nvme["power_on_hours"]
        if nvme.get("temperature") is not None:
            drive["temp_c"] = nvme["temperature"]
        if nvme.get("percentage_used") is not None:
            drive["percentage_used"] = nvme["percentage_used"]
        if nvme.get("available_spare") is not None:
            drive["available_spare_pct"] = nvme["available_spare"]
        if nvme.get("unsafe_shutdowns") is not None:
            drive["unsafe_shutdowns"] = nvme["unsafe_shutdowns"]
        if nvme.get("power_cycles") is not None:
            drive["power_cycles"] = nvme["power_cycles"]

    # Traditional ATA SMART attributes (HDD / SATA SSD)
    for attr in d.get("ata_smart_attributes", {}).get("table", []):
        aid = attr.get("id")
        raw = attr.get("raw", {}).get("value")
        if aid == 9 and drive.get("power_on_hours") is None:
            drive["power_on_hours"] = raw
        elif aid == 5:
            drive["reallocated_sectors"] = raw
        elif aid in (190, 194) and drive.get("temp_c") is None:
            drive["temp_c"] = raw

    # Top-level temperature fallback
    if drive.get("temp_c") is None:
        t = d.get("temperature", {}).get("current")
        if t is not None:
            drive["temp_c"] = t


# ---------------------------------------------------------------------------
# Physical drive enumeration — per platform
# ---------------------------------------------------------------------------

def _drives_macos() -> list[dict]:
    """
    Enumerate physical drives on macOS.

    Uses SPNVMeDataType + SPSerialATADataType for drive metadata, then
    SPStorageDataType for used/free space (APFS-container aware).
    """
    drives: list[dict] = []
    seen: set[str] = set()

    # --- Physical drive metadata ---
    for sp_type, iface in (("SPNVMeDataType", "NVMe"), ("SPSerialATADataType", "SATA")):
        try:
            r = subprocess.run(
                ["system_profiler", sp_type, "-json"],
                capture_output=True, text=True, timeout=15,
            )
            data = _json.loads(r.stdout).get(sp_type, [])
            for ctrl in data:
                items = ctrl.get("_items", [ctrl])
                for item in items:
                    bsd = item.get("bsd_name", "")
                    if not bsd or bsd in seen:
                        continue
                    seen.add(bsd)
                    cap = item.get("size_in_bytes")
                    drives.append({
                        "device": f"/dev/{bsd}",
                        "model": item.get("device_model") or item.get("_name", "Unknown"),
                        "serial": item.get("device_serial") or "Unknown",
                        "firmware": item.get("device_revision") or "Unknown",
                        "capacity_bytes": cap,
                        "total_gb": round(cap / 1e9, 1) if cap else None,
                        "used_gb": None,
                        "free_gb": None,
                        "interface": iface,
                        "medium_type": "SSD",
                        "smart_status": item.get("smart_status", "Unknown"),
                        "power_on_hours": None,
                        "temp_c": None,
                        "reallocated_sectors": None,
                        "percentage_used": None,
                    })
        except Exception:
            pass

    # --- Used / free from SPStorageDataType (APFS-container-aware) ---
    # Each physical disk maps to one container; all volumes in the container
    # share the same pool, so free_space_in_bytes is the same for all.
    # We take the first entry per physical device to avoid duplicates.
    try:
        r = subprocess.run(
            ["system_profiler", "SPStorageDataType", "-json"],
            capture_output=True, text=True, timeout=15,
        )
        storage = _json.loads(r.stdout).get("SPStorageDataType", [])
        matched_devices: set[str] = set()
        for vol in storage:
            phys = vol.get("physical_drive", {})
            # Match the volume back to a physical drive bsd_name
            # The bsd_name in SPStorageDataType is the APFS volume (disk3s1),
            # so map it by looking for our physical drives (disk0, disk1, ...)
            free = vol.get("free_space_in_bytes")
            size = vol.get("size_in_bytes")
            if free is None or size is None:
                continue
            # Heuristic: match by size — find the drive whose capacity matches
            # the volume's container size (within 5%)
            for drv in drives:
                cap = drv.get("capacity_bytes")
                if cap and drv["device"] not in matched_devices:
                    # Container size ≈ physical size minus overhead partitions
                    ratio = size / cap if cap > 0 else 0
                    if 0.85 <= ratio <= 1.05:
                        drv["used_gb"] = round((size - free) / 1e9, 1)
                        drv["free_gb"] = round(free / 1e9, 1)
                        matched_devices.add(drv["device"])
                        break
    except Exception:
        pass

    return drives


def _drives_windows() -> list[dict]:
    """Enumerate physical drives on Windows via WMI."""
    drives: list[dict] = []
    try:
        import wmi  # type: ignore
        c = wmi.WMI()
        for disk in c.Win32_DiskDrive():
            cap = int(disk.Size) if disk.Size else None
            drives.append({
                "device": disk.DeviceID,
                "model": disk.Model or "Unknown",
                "serial": (disk.SerialNumber or "").strip() or "Unknown",
                "firmware": disk.FirmwareRevision or "Unknown",
                "capacity_bytes": cap,
                "total_gb": round(cap / 1e9, 1) if cap else None,
                "used_gb": None,
                "free_gb": None,
                "interface": disk.InterfaceType or "Unknown",
                "medium_type": "Unknown",
                "smart_status": "Unknown",
                "power_on_hours": None,
                "temp_c": None,
                "reallocated_sectors": None,
                "percentage_used": None,
            })
    except Exception:
        pass

    # Add used/free from psutil — match by size
    _fill_usage_from_psutil(drives)
    return drives


def _drives_linux() -> list[dict]:
    """Enumerate physical drives on Linux via /sys/block + lsblk."""
    drives: list[dict] = []
    try:
        r = subprocess.run(
            ["lsblk", "-d", "-o", "NAME,MODEL,SERIAL,SIZE,ROTA,TRAN", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        data = _json.loads(r.stdout)
        for dev in data.get("blockdevices", []):
            name = dev.get("name", "")
            if not name or name.startswith("loop"):
                continue
            rota = dev.get("rota", "1")
            tran = dev.get("tran") or "Unknown"
            size_str = dev.get("size", "")
            drives.append({
                "device": f"/dev/{name}",
                "model": dev.get("model") or "Unknown",
                "serial": dev.get("serial") or "Unknown",
                "firmware": "Unknown",
                "capacity_bytes": None,
                "total_gb": None,
                "used_gb": None,
                "free_gb": None,
                "interface": tran.upper(),
                "medium_type": "HDD" if rota == "1" else "SSD",
                "smart_status": "Unknown",
                "power_on_hours": None,
                "temp_c": None,
                "reallocated_sectors": None,
                "percentage_used": None,
            })
    except Exception:
        pass

    _fill_usage_from_psutil(drives)
    return drives


def _fill_usage_from_psutil(drives: list[dict]) -> None:
    """Best-effort: fill used/free on the first physical-drive entry from psutil."""
    try:
        for part in psutil.disk_partitions(all=False):
            if not part.mountpoint:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            # Assign to the drive whose device path is a prefix of the partition
            for drv in drives:
                dev = drv["device"]
                if part.device.startswith(dev) and drv["used_gb"] is None:
                    drv["total_gb"] = round(usage.total / 1e9, 1)
                    drv["used_gb"] = round(usage.used / 1e9, 1)
                    drv["free_gb"] = round(usage.free / 1e9, 1)
                    drv["capacity_bytes"] = drv["capacity_bytes"] or usage.total
                    break
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Speed test
# ---------------------------------------------------------------------------

def _nocache_fd(fd: int, plat: str) -> None:
    """Best-effort: disable OS read cache for file descriptor fd."""
    if plat == "Darwin":
        try:
            import fcntl as _fcntl
            _fcntl.fcntl(fd, 48, 1)  # F_NOCACHE = 48
        except Exception:
            pass


def _disk_speed_test(size_mb: int, full: bool = False) -> dict:
    """
    Measure storage speed using a temp file.

    Quick mode: sequential write (fsync) + sequential read (cache-bypassed).
    Full mode: same + random 4 KiB reads for up to 5 seconds to measure IOPS.

    macOS: F_NOCACHE (fcntl 48) bypasses page cache on reads — no alignment needed.
    """
    block_size = 1024 * 1024          # 1 MiB sequential blocks
    rand_block = 4096                  # 4 KiB random reads
    rand_duration = 5.0                # seconds to run random IO phase
    total_bytes = size_mb * 1024 * 1024
    results: dict = {}
    tmp_path: str | None = None
    _plat = platform.system()

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
            tmp_path = f.name

        # --- Sequential write (fsync to flush write cache) ---
        buf = b"\xFF" * block_size
        start = time.monotonic()
        with open(tmp_path, "wb", buffering=0) as f:
            written = 0
            while written < total_bytes:
                chunk = min(block_size, total_bytes - written)
                f.write(buf[:chunk])
                written += chunk
            f.flush()
            os.fsync(f.fileno())
        results["write_mb_s"] = round(size_mb / (time.monotonic() - start), 1)

        # --- Sequential read (bypass page cache for honest measurement) ---
        start = time.monotonic()
        with open(tmp_path, "rb", buffering=0) as f:
            _nocache_fd(f.fileno(), _plat)
            while f.read(block_size):
                pass
        results["read_mb_s"] = round(size_mb / (time.monotonic() - start), 1)

        # --- Full mode: random 4 KiB read IOPS ---
        if full:
            max_offset = (total_bytes - rand_block) // rand_block  # in blocks
            rng = _random.Random()
            ops = 0
            rand_start = time.monotonic()
            with open(tmp_path, "rb", buffering=0) as f:
                _nocache_fd(f.fileno(), _plat)
                while time.monotonic() - rand_start < rand_duration:
                    f.seek(rng.randrange(0, max_offset) * rand_block)
                    f.read(rand_block)
                    ops += 1
            elapsed = time.monotonic() - rand_start
            if elapsed > 0 and ops > 0:
                results["rand_read_iops"] = round(ops / elapsed)
                results["rand_read_mb_s"] = round(
                    (ops * rand_block / (1024 ** 2)) / elapsed, 1
                )
                results["rand_read_ops"] = ops
                results["rand_read_duration_s"] = round(elapsed, 1)

    except Exception as exc:
        results["speed_error"] = str(exc)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return results


# ---------------------------------------------------------------------------
# Main test class
# ---------------------------------------------------------------------------

class StorageTest(BaseTest):
    async def run(self) -> TestResult:
        self.result.mark_running()
        loop = asyncio.get_event_loop()
        sys = platform.system()

        # 1. Enumerate physical drives
        if sys == "Darwin":
            drives = await loop.run_in_executor(None, _drives_macos)
        elif sys == "Windows":
            drives = await loop.run_in_executor(None, _drives_windows)
        else:
            drives = await loop.run_in_executor(None, _drives_linux)

        # 2. Enrich each drive with smartctl SMART data
        for drv in drives:
            await loop.run_in_executor(None, _enrich_with_smartctl, drv)

        # 3. Speed test
        size_mb = STORAGE_TEST_SIZE_QUICK if self.is_quick() else STORAGE_TEST_SIZE_FULL
        import functools as _functools
        speed_fn = _functools.partial(_disk_speed_test, full=not self.is_quick())
        speed = await loop.run_in_executor(None, speed_fn, size_mb)

        # 4. Evaluate drive temperatures against thresholds
        drive_temp_fail = False
        drive_temp_warn = False
        for drv in drives:
            temp_thresh, _ = get_storage_thresholds(
                drv.get("interface", "Unknown"),
                drv.get("medium_type", "Unknown"),
            )
            drv["temp_warn_threshold"] = temp_thresh["warn"]
            drv["temp_fail_threshold"] = temp_thresh["fail"]
            if temp_thresh.get("note"):
                drv["temp_note"] = temp_thresh["note"]
            temp = drv.get("temp_c")
            if temp is not None:
                if temp >= temp_thresh["fail"]:
                    drive_temp_fail = True
                elif temp >= temp_thresh["warn"]:
                    drive_temp_warn = True

        # 5. Evaluate speed against thresholds for the boot drive
        read_mb_s = speed.get("read_mb_s")
        write_mb_s = speed.get("write_mb_s")
        speed_status = "pass"
        speed_note = ""
        if drives:
            boot = drives[0]
            _, speed_thresh = get_storage_thresholds(
                boot.get("interface", "Unknown"),
                boot.get("medium_type", "Unknown"),
                read_mb_s,
            )
            speed["speed_warn_read"] = speed_thresh["warn_read"]
            speed["speed_fail_read"] = speed_thresh["fail_read"]
            speed["speed_warn_write"] = speed_thresh["warn_write"]
            speed["speed_fail_write"] = speed_thresh["fail_write"]
            speed["speed_expected_read"] = speed_thresh["expected_read"]
            speed["speed_expected_write"] = speed_thresh["expected_write"]
            if read_mb_s and read_mb_s < speed_thresh["fail_read"]:
                speed_status = "fail"
                speed_note = f"Read {read_mb_s} MB/s — expected ≥{speed_thresh['expected_read']} MB/s"
            elif write_mb_s and write_mb_s < speed_thresh["fail_write"]:
                speed_status = "fail"
                speed_note = f"Write {write_mb_s} MB/s — expected ≥{speed_thresh['expected_write']} MB/s"
            elif read_mb_s and read_mb_s < speed_thresh["warn_read"]:
                speed_status = "warn"
                speed_note = f"Read {read_mb_s} MB/s below expected {speed_thresh['expected_read']} MB/s"
            elif write_mb_s and write_mb_s < speed_thresh["warn_write"]:
                speed_status = "warn"
                speed_note = f"Write {write_mb_s} MB/s below expected {speed_thresh['expected_write']} MB/s"

        data: dict = {
            "drives": drives,
            "speed_test_mb": size_mb,
            **speed,
        }

        # 6. Determine overall status — priority: SMART fail > temp fail > speed fail >
        #    reallocated > temp warn > speed warn > no SMART > PASS
        failed = any(d.get("smart_status") == "FAILED" for d in drives)
        reallocated = any(
            d.get("reallocated_sectors") not in (None, 0, "0")
            for d in drives
        )
        no_smart = not drives or all(d.get("smart_status") in (None, "Unknown") for d in drives)

        if failed:
            self.result.mark_fail(
                summary="SMART reports drive FAILURE — immediate backup recommended!",
                data=data,
            )
        elif drive_temp_fail:
            self.result.mark_fail(
                summary="Drive overheating — check cooling immediately",
                data=data,
            )
        elif speed_status == "fail":
            self.result.mark_fail(
                summary=f"Storage performance critical: {speed_note}",
                data=data,
            )
        elif reallocated:
            self.result.mark_warn(
                summary="Reallocated sectors detected — drive may be failing",
                data=data,
            )
        elif drive_temp_warn:
            self.result.mark_warn(
                summary="Drive temperature elevated — check airflow",
                data=data,
            )
        elif speed_status == "warn":
            self.result.mark_warn(
                summary=f"Storage underperforming: {speed_note}",
                data=data,
            )
        elif no_smart:
            self.result.mark_warn(
                summary="Could not read SMART data (smartctl missing or permission denied)",
                data=data,
            )
        else:
            write = speed.get("write_mb_s", "?")
            read = speed.get("read_mb_s", "?")
            poh = drives[0].get("power_on_hours") if drives else None
            poh_str = f" — {poh}h power-on" if poh is not None else ""
            self.result.mark_pass(
                summary=f"{len(drives)} drive(s) SMART OK{poh_str} — Read {read} MB/s / Write {write} MB/s",
                data=data,
            )

        return self.result

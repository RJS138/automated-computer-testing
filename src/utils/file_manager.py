"""Find USB drive, create report output folders."""

import platform
import string
from pathlib import Path

from ..config import REPORTS_DIR_NAME, USB_MARKER
from ..models.job import JobInfo
from .platform_detect import get_exe_dir


def find_usb_drive() -> Path | None:
    """
    Attempt to find the USB drive that PC Tester is running from.
    Strategy:
      1. Look for USB_MARKER file on removable drives (Windows).
      2. Walk /media and /mnt on Linux.
      3. Fall back to the executable directory.
    """
    sys = platform.system()

    if sys == "Windows":
        return _find_usb_windows()
    elif sys == "Linux":
        return _find_usb_linux()
    elif sys == "Darwin":
        return _find_usb_darwin()
    return None


def _find_usb_windows() -> Path | None:
    try:
        import ctypes
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1

        # DRIVE_REMOVABLE = 2
        for drive in drives:
            if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                marker = Path(drive) / USB_MARKER
                if marker.exists():
                    return Path(drive)
        # If marker not found, return first removable drive
        for drive in drives:
            if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                return Path(drive)
    except Exception:
        pass
    return None


def _find_usb_linux() -> Path | None:
    for mount_root in (Path("/media"), Path("/mnt"), Path("/run/media")):
        if not mount_root.exists():
            continue
        for candidate in mount_root.rglob(USB_MARKER):
            return candidate.parent
    return None


def _find_usb_darwin() -> Path | None:
    """Check /Volumes for a drive containing the USB marker file."""
    volumes = Path("/Volumes")
    if not volumes.exists():
        return None
    for vol in volumes.iterdir():
        if (vol / USB_MARKER).exists():
            return vol
    return None


def get_report_dir(job: JobInfo) -> Path:
    """
    Determine the output directory for this job's reports.

    Priority:
      1. USB drive /reports/{folder_name}/
      2. Executable directory /reports/{folder_name}/
    """
    usb = find_usb_drive()
    base = usb if usb else get_exe_dir()
    return base / REPORTS_DIR_NAME / job.folder_name()


def ensure_usb_marker(usb_path: Path) -> None:
    """Write the USB marker file so PC Tester can find the drive."""
    marker = usb_path / USB_MARKER
    if not marker.exists():
        marker.write_text(
            "PC Tester USB Drive — do not delete this file.\n",
            encoding="utf-8",
        )

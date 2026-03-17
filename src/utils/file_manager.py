"""Find USB drive, create report output folders."""

import json
import platform
import re
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


def get_job_dir(job: JobInfo) -> Path:
    """
    Return the top-level job folder: .../reports/{CustomerName_WO#}/

    This is the stable per-job root that holds before/, after/, and comparison files.
    """
    usb = find_usb_drive()
    base = usb if usb else get_exe_dir()
    return base / REPORTS_DIR_NAME / job.folder_name()


def get_report_dir(job: JobInfo) -> Path:
    """
    Return the type-specific subfolder for the current report:
      .../reports/{CustomerName_WO#}/before/   or
      .../reports/{CustomerName_WO#}/after/
    """
    return get_job_dir(job) / job.report_type.value


def scan_existing_jobs() -> list[dict]:
    """Scan the reports directory and return metadata for every known job.

    Each returned dict has:
        customer_name     str   — original customer name (from report JSON)
        job_number        str   — original job number
        device_description str  — device model string
        has_before        bool  — before/before.html exists
        has_after         bool  — after/after.html exists
        folder_path       Path  — absolute path to the job folder
    """
    usb = find_usb_drive()
    base = usb if usb else get_exe_dir()
    reports_dir = base / REPORTS_DIR_NAME

    if not reports_dir.exists():
        return []

    jobs: list[dict] = []
    for job_dir in sorted(reports_dir.iterdir()):
        if not job_dir.is_dir():
            continue

        has_before = (job_dir / "before" / "before.html").exists()
        has_after = (job_dir / "after" / "after.html").exists()

        if not has_before and not has_after:
            continue  # empty or non-job folder

        info = _parse_job_html(job_dir, has_before, has_after)
        if info is None:
            # Fall back to folder name — can't recover original text, skip
            continue

        info["has_before"] = has_before
        info["has_after"] = has_after
        info["folder_path"] = job_dir
        jobs.append(info)

    return jobs


def _parse_job_html(job_dir: Path, has_before: bool, has_after: bool) -> dict | None:
    """Extract job metadata from the embedded JSON in a report HTML file."""
    _SCRIPT_RE = re.compile(
        r'<script[^>]+id=["\']report-data["\'][^>]*>(.*?)</script>',
        re.DOTALL,
    )
    # Prefer the most recent report type
    for report_type, exists in (("after", has_after), ("before", has_before)):
        if not exists:
            continue
        html_path = job_dir / report_type / f"{report_type}.html"
        try:
            content = html_path.read_text(encoding="utf-8", errors="ignore")
            m = _SCRIPT_RE.search(content)
            if not m:
                continue
            data = json.loads(m.group(1))
            job = data.get("job", {})
            return {
                "customer_name": job.get("customer_name", ""),
                "job_number": job.get("job_number", ""),
                "device_description": job.get("device_description", ""),
            }
        except Exception:
            continue
    return None


def ensure_usb_marker(usb_path: Path) -> None:
    """Write the USB marker file so PC Tester can find the drive."""
    marker = usb_path / USB_MARKER
    if not marker.exists():
        marker.write_text(
            "Touchstone USB Drive — do not delete this file.\n",
            encoding="utf-8",
        )

"""Application-wide constants and configuration."""

import sys
from pathlib import Path

APP_NAME = "PC Tester"
APP_VERSION = "1.0.0"
BUSINESS_NAME = "Your PC Repair Business"  # Change to your business name

# Test durations (seconds)
CPU_STRESS_QUICK = 30
CPU_STRESS_FULL = 180
RAM_SCAN_QUICK = 20
RAM_SCAN_FULL = 120
STORAGE_SPEED_QUICK = 10
STORAGE_SPEED_FULL = 30

# CPU stress: MB of data to crunch per worker
CPU_STRESS_WORK_MB_QUICK = 50
CPU_STRESS_WORK_MB_FULL = 500

# RAM pattern scan: MB to test in quick/full mode
RAM_SCAN_MB_QUICK = 256
RAM_SCAN_MB_FULL = 2048  # capped at 50% available RAM at runtime

# Storage speed test file size (MB)
STORAGE_TEST_SIZE_QUICK = 128
STORAGE_TEST_SIZE_FULL = 512

# Connectivity test
PING_TARGET = "8.8.8.8"
PING_TIMEOUT = 3  # seconds

# Temperature thresholds (°C)
CPU_TEMP_WARN = 85
CPU_TEMP_FAIL = 95

# Report output folder name format
REPORT_FOLDER_FORMAT = "{customer}_{job}_{date}"

# USB drive detection: look for this marker file on removable drives
USB_MARKER = "pctester_usb.marker"

# Base directory for reports (relative to where the exe lives or USB root)
REPORTS_DIR_NAME = "reports"

# Paths resolved at runtime by file_manager.py
# In a PyInstaller --onefile bundle, data files added with --add-data are
# extracted to sys._MEIPASS at runtime.  __file__ inside a frozen bundle is
# not a reliable filesystem path, so we detect frozen execution explicitly.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _BUNDLE_DIR = Path(sys._MEIPASS)
    SRC_DIR = _BUNDLE_DIR / "src"
else:
    SRC_DIR = Path(__file__).parent          # pc-tester/src/

BASE_DIR = SRC_DIR.parent                    # pc-tester/
TEMPLATES_DIR = SRC_DIR / "report" / "templates"

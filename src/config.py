"""Application-wide constants and configuration."""

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
RAM_SCAN_MB_FULL = 1024

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
BASE_DIR = Path(__file__).parent.parent  # pc-tester/
SRC_DIR = Path(__file__).parent          # pc-tester/src/
TEMPLATES_DIR = SRC_DIR / "report" / "templates"

# Manual test checklist items
MANUAL_TEST_ITEMS = [
    {
        "id": "lcd",
        "label": "LCD / Display",
        "instructions": (
            "Inspect the screen carefully:\n"
            "  • Look for dead pixels (permanent black/bright dots)\n"
            "  • Check for backlight bleed (bright patches at edges in a dark room)\n"
            "  • Verify the display is bright and colours look correct\n"
            "  • Check for cracks or pressure marks"
        ),
    },
    {
        "id": "speakers",
        "label": "Speakers / Audio",
        "instructions": (
            "Test audio output:\n"
            "  • Play a short audio clip or use the system sound test\n"
            "  • Verify both left and right channels work\n"
            "  • Check for distortion, buzzing, or static\n"
            "  • Test headphone jack if present"
        ),
    },
    {
        "id": "keyboard",
        "label": "Keyboard",
        "instructions": (
            "Test the keyboard:\n"
            "  • Open a text editor and press every key\n"
            "  • Check for stuck, missing, or non-registering keys\n"
            "  • Test function keys (Fn row)\n"
            "  • Test special keys: Caps Lock, Num Lock, Insert, Delete"
        ),
    },
    {
        "id": "touchpad",
        "label": "Touchpad / Trackpad",
        "instructions": (
            "Test the touchpad:\n"
            "  • Move cursor across the full surface\n"
            "  • Test left and right click buttons (physical or tap)\n"
            "  • Test two-finger scroll\n"
            "  • Check for dead zones or erratic movement"
        ),
    },
    {
        "id": "usb_a",
        "label": "USB-A Ports",
        "instructions": (
            "Test each USB-A port:\n"
            "  • Plug a known-good USB device into each port\n"
            "  • Verify the device is detected in the OS\n"
            "  • Check for loose or damaged connectors\n"
            "  • Note: test USB 2.0 and USB 3.0 ports separately if present"
        ),
    },
    {
        "id": "usb_c",
        "label": "USB-C Ports",
        "instructions": (
            "Test each USB-C port:\n"
            "  • Plug a known-good USB-C device into each port\n"
            "  • Verify the device is detected\n"
            "  • If Thunderbolt, test with a TB device if available\n"
            "  • Check for charging functionality if applicable"
        ),
    },
    {
        "id": "hdmi",
        "label": "HDMI / Video Out",
        "instructions": (
            "Test video output:\n"
            "  • Connect an external monitor via HDMI (or DisplayPort/VGA if present)\n"
            "  • Verify image displays correctly on the external monitor\n"
            "  • Test switching between display modes (mirror/extend)\n"
            "  • Check connector is not loose or damaged"
        ),
    },
    {
        "id": "webcam",
        "label": "Webcam",
        "instructions": (
            "Test the built-in webcam:\n"
            "  • Open Camera app or use a video call app\n"
            "  • Verify live video feed is clear and not distorted\n"
            "  • Check microphone input while testing camera\n"
            "  • Verify privacy shutter works (if present)"
        ),
    },
]

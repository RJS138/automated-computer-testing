"""USB-A Ports manual test item."""

ITEM: dict = {
    "id": "usb_a",
    "label": "USB-A Ports",
    "test_type": "usb_test_a",
    "instructions": (
        "Click 'Start USB-A Test' to open the interactive USB port test.\n\n"
        "The test lists currently connected USB devices, then lets you plug in\n"
        "a device and click Scan to verify it is detected (shown in green).\n\n"
        "Test each USB-A port individually:\n"
        "  • USB 2.0 and USB 3.0 ports separately if present\n"
        "  • Check for loose or damaged connectors"
    ),
}

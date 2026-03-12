"""USB-C Ports manual test item."""

ITEM: dict = {
    "id": "usb_c",
    "label": "USB-C Ports",
    "test_type": "usb_test_c",
    "instructions": (
        "Click 'Start USB-C Test' to open the interactive USB port test.\n\n"
        "The test lists currently connected USB devices, then lets you plug in\n"
        "a device and click Scan to verify it is detected (shown in green).\n\n"
        "Test each USB-C port individually:\n"
        "  • Thunderbolt ports if present\n"
        "  • Check charging functionality if applicable\n"
        "  • Check for loose or damaged connectors"
    ),
}

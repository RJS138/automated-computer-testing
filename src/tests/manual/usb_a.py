"""USB-A Ports manual test item."""

ITEM: dict = {
    "id": "usb_a",
    "label": "USB-A Ports",
    "instructions": (
        "Test each USB-A port:\n"
        "  • Plug a known-good USB device into each port\n"
        "  • Verify the device is detected in the OS\n"
        "  • Check for loose or damaged connectors\n"
        "  • Note: test USB 2.0 and USB 3.0 ports separately if present"
    ),
}

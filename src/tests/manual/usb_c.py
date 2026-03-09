"""USB-C Ports manual test item."""

ITEM: dict = {
    "id": "usb_c",
    "label": "USB-C Ports",
    "instructions": (
        "Test each USB-C port:\n"
        "  • Plug a known-good USB-C device into each port\n"
        "  • Verify the device is detected\n"
        "  • If Thunderbolt, test with a TB device if available\n"
        "  • Check for charging functionality if applicable"
    ),
}

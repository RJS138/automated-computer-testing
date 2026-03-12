"""Touchpad / Trackpad manual test item."""

ITEM: dict = {
    "id": "touchpad",
    "label": "Touchpad / Trackpad",
    "test_type": "touchpad_test",
    "instructions": (
        "Click 'Start Touchpad Test' to open the interactive trackpad test.\n\n"
        "You will need to:\n"
        "  • Draw across the entire pad surface (coverage tracker shows progress)\n"
        "  • Left-click in the left-click zone\n"
        "  • Right-click in the right-click zone\n"
        "  • Scroll (two-finger or scroll wheel) in the scroll zone\n\n"
        "Check for dead zones, erratic movement, or unresponsive areas."
    ),
}

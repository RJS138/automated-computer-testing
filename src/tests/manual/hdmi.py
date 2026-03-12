"""HDMI / Video Out manual test item."""

ITEM: dict = {
    "id": "hdmi",
    "label": "HDMI / Video Out",
    "test_type": "hdmi_test",
    "instructions": (
        "Click 'Start HDMI Test' to open the interactive display output test.\n\n"
        "The test detects connected displays and highlights newly connected ones.\n"
        "Use the 'Colour Test' button to run a colour cycle on the external monitor.\n\n"
        "Verify:\n"
        "  • External monitor is detected after connecting\n"
        "  • Image is clear with no artefacts\n"
        "  • Connector is not loose or damaged"
    ),
}

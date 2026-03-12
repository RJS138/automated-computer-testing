"""Webcam manual test item."""

ITEM: dict = {
    "id": "webcam",
    "label": "Webcam",
    "test_type": "webcam_test",
    "instructions": (
        "Click 'Start Webcam Test' to open the live camera preview.\n\n"
        "The test shows a real-time preview from the selected camera.\n"
        "Use the dropdown to switch between cameras if multiple are detected.\n\n"
        "Verify:\n"
        "  • Live feed is clear and not distorted\n"
        "  • Correct camera is selected (front/rear if both present)\n"
        "  • Privacy shutter works if present (blocks feed when closed)"
    ),
}

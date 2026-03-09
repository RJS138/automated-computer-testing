"""LCD / Display manual test item."""

ITEM: dict = {
    "id": "lcd",
    "label": "LCD / Display",
    "test_type": "display_color",
    "instructions": (
        "Click 'Start Display Test' to run the full-screen colour cycle.\n\n"
        "The screen will show 8 solid colours. On each colour, check for:\n"
        "  • Dead pixels — dots stuck at the wrong colour\n"
        "  • Backlight bleed — bright patches at screen edges (visible on black)\n"
        "  • Colour uniformity — even brightness, no dark or bright patches\n"
        "  • Screen damage — cracks or pressure marks visible on white/light screens\n\n"
        "Press any key or click to advance through colours.\n"
        "Press ESC to end the cycle early."
    ),
}

"""Speakers / Audio manual test item."""

ITEM: dict = {
    "id": "speakers",
    "label": "Speakers / Audio",
    "test_type": "speakers_test",
    "instructions": (
        "Click 'Start Speaker Test' to open the interactive audio test.\n\n"
        "The test will play tones through both speakers, then each speaker individually,\n"
        "then a frequency sweep, and finally speak a short code aloud that you must type\n"
        "to confirm audio is actually being heard.\n\n"
        "Listen for:\n"
        "  • Both channels producing sound\n"
        "  • No distortion, buzzing, or static\n"
        "  • Clear, balanced audio across the frequency range"
    ),
}

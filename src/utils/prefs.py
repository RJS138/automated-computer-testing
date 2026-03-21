"""User preferences — persisted to ~/.touchstone/prefs.json."""

from __future__ import annotations

import json
from pathlib import Path

_PREFS_PATH = Path.home() / ".touchstone" / "prefs.json"

_DEFAULTS: dict[str, str] = {
    "theme": "dark",
    "output_format": "html_pdf",
    "save_path": "",
}


def load_prefs() -> dict[str, str]:
    """Return persisted prefs with safe defaults for all missing keys.

    Never raises — any error returns full defaults.
    Backwards compatible with files that only contain {"theme": "..."}.
    """
    try:
        data = json.loads(_PREFS_PATH.read_text())
        result = {k: data.get(k, v) for k, v in _DEFAULTS.items()}
        result["theme"] = "light" if result["theme"] == "light" else "dark"
        return result
    except Exception:
        return dict(_DEFAULTS)


def save_prefs(*, theme: str, output_format: str, save_path: str) -> None:
    """Persist all prefs to ~/.touchstone/prefs.json. All args keyword-only."""
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_PATH.write_text(
        json.dumps({"theme": theme, "output_format": output_format, "save_path": save_path})
    )

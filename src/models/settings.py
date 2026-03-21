"""Settings — ephemeral app-level settings (reset each launch)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    """Report settings. output_format and save_path persist across sessions
via ~/.touchstone/prefs.json. notes is ephemeral (reset each launch).
"""

    output_format: str = "html_pdf"  # "html_pdf" | "html_only" | "pdf_only"
    save_path: str = ""
    notes: str = ""

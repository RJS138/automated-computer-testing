"""Settings — ephemeral app-level settings (reset each launch)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    """Ephemeral report settings. Not persisted to disk."""

    output_format: str = "html_pdf"  # "html_pdf" | "html_only" | "pdf_only"
    save_path: str = ""
    notes: str = ""

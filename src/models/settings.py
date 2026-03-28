"""Settings — ephemeral app-level settings (reset each launch)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    """Report settings. output_format, save_path, company_name, and
company_logo_path persist across sessions via ~/.touchstone/prefs.json.
notes is ephemeral (reset each launch).
"""

    output_format: str = "html_pdf"  # "html_pdf" | "html_only" | "pdf_only"
    save_path: str = ""
    notes: str = ""
    company_name: str = ""       # shown in report header; replaces "Touchstone" when set
    company_logo_path: str = ""  # absolute path to PNG/JPG logo; embedded as base64 in reports

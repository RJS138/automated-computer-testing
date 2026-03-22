"""Shared background worker threads for MainDashboard.

TestWorker  — runs a single BaseTest subclass in a background thread.
ReportWorker — generates HTML/PDF report in a background thread.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.models.job import TestMode
from src.models.test_result import TestResult

# ── Test Worker ───────────────────────────────────────────────────────────────


class TestWorker(QThread):
    """Runs a single BaseTest in a background thread."""

    finished = Signal(str)  # emits test name on completion
    progress = Signal(str, object)  # (test_name, data_dict) — live progress updates

    def __init__(
        self,
        name: str,
        module: str,
        cls_name: str,
        result: TestResult,
        mode: TestMode,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._module = module
        self._cls_name = cls_name
        self._result = result
        self._mode = mode
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        """Public read-only access to the test name."""
        return self._name

    def run(self) -> None:
        import importlib

        mod = importlib.import_module(f"src.tests.{self._module}")
        TestClass = getattr(mod, self._cls_name)
        test = TestClass(result=self._result, mode=self._mode)
        test.on_progress = lambda data: self.progress.emit(self._name, data)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _run() -> None:
            # Capture the running Task so cancel() can reach it.
            self._task = asyncio.current_task()
            await test.safe_run()

        try:
            self._loop.run_until_complete(_run())
        except Exception as exc:
            self._result.mark_error(str(exc))
        finally:
            self._loop.close()
        self.finished.emit(self._name)

    def cancel(self) -> None:
        """Cancel the running async task. Thread-safe; safe to call multiple times."""
        if self._loop and self._task and not self._task.done():
            self._loop.call_soon_threadsafe(self._task.cancel)


# ── Report Worker ─────────────────────────────────────────────────────────────


class ReportWorker(QThread):
    """Generates HTML/PDF report in a background thread."""

    done = Signal(str, str)  # (html_path, pdf_path) — pdf_path is "" if PDF was skipped
    error = Signal(str)  # error message if generation failed
    status = Signal(str)  # progress messages ("Rendering HTML…", etc.)

    def __init__(self, job, results: list, settings, parent=None) -> None:
        super().__init__(parent)
        self._job = job
        self._results = results
        self._settings = settings

    def run(self) -> None:
        try:
            from pathlib import Path

            from src.config import REPORTS_DIR_NAME
            from src.report.diff import generate_comparison
            from src.report.generator import assemble_report
            from src.report.html_render import render_html
            from src.report.pdf_render import render_pdf

            job = self._job
            results = self._results
            fmt = self._settings.output_format  # "html_pdf" | "html_only" | "pdf_only"
            report_type = job.report_type.value

            # Build report object
            report = assemble_report(job, results)

            # Derive save directory from settings.save_path
            base = Path(self._settings.save_path)
            report_dir = base / REPORTS_DIR_NAME / job.folder_name() / report_type
            job_dir = base / REPORTS_DIR_NAME / job.folder_name()
            report_dir.mkdir(parents=True, exist_ok=True)

            html_path = report_dir / f"{report_type}.html"
            pdf_path = report_dir / f"{report_type}.pdf"

            html_content: str = ""

            if fmt in ("html_pdf", "html_only"):
                self.status.emit("Rendering HTML…")
                html_content = render_html(report)
                html_path.write_text(html_content, encoding="utf-8")

            if fmt in ("html_pdf", "pdf_only"):
                self.status.emit("Rendering PDF…")
                if not html_content:
                    # pdf_only: render HTML in-memory to feed to PDF renderer
                    html_content = render_html(report)
                render_pdf(html_content, pdf_path)

            # open_path: prefer HTML when available, fall back to PDF
            open_path: Path = html_path if html_path.exists() else pdf_path

            # Comparison report (only when both before and after exist)
            other_type = "after" if report_type == "before" else "before"
            other_html = job_dir / other_type / f"{other_type}.html"
            if other_html.exists() and html_content:
                self.status.emit("Generating comparison report…")
                comparison_html = generate_comparison(job_dir, job)
                if comparison_html:
                    comp_html_path = job_dir / "comparison.html"
                    comp_html_path.write_text(comparison_html, encoding="utf-8")
                    if fmt in ("html_pdf", "pdf_only"):
                        render_pdf(comparison_html, job_dir / "comparison.pdf")
                    open_path = comp_html_path

            self.status.emit("Reports saved.")
            self.done.emit(open_path.as_uri(), str(pdf_path) if pdf_path.exists() else "")

        except Exception as exc:
            self.error.emit(str(exc))

"""Shared background worker threads for MainDashboard.

TestWorker  — runs a single BaseTest subclass in a background thread.
ReportWorker — generates HTML/PDF report in a background thread.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.models.job import TestMode
from src.models.test_result import TestResult

# ── Test Worker ───────────────────────────────────────────────────────────────


class TestWorker(QThread):
    """Runs a single BaseTest in a background thread."""

    finished = Signal(str)  # emits test name on completion

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

    def run(self) -> None:
        import asyncio
        import importlib

        mod = importlib.import_module(f"src.tests.{self._module}")
        TestClass = getattr(mod, self._cls_name)
        test = TestClass(result=self._result, mode=self._mode)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test.safe_run())
        except Exception as exc:
            self._result.mark_error(str(exc))
        finally:
            loop.close()
        self.finished.emit(self._name)


# ── Report Worker ─────────────────────────────────────────────────────────────


class ReportWorker(QThread):
    """Generates HTML/PDF report in a background thread."""

    done = Signal(str, str)  # (html_path, pdf_path) — pdf_path is "" if PDF was skipped
    error = Signal(str)  # error message if generation failed
    status = Signal(str)  # progress messages ("Rendering HTML…", etc.)

    def __init__(self, job, results: list, parent=None) -> None:
        super().__init__(parent)
        self._job = job
        self._results = results

    def run(self) -> None:
        try:
            from src.report.diff import generate_comparison
            from src.report.generator import assemble_report
            from src.report.html_render import render_html
            from src.report.pdf_render import render_pdf
            from src.utils.file_manager import get_job_dir, get_report_dir

            job = self._job
            results = self._results
            report_type = job.report_type.value

            # Build report object
            report = assemble_report(job, results)

            report_dir = get_report_dir(job)
            job_dir = get_job_dir(job)
            report_dir.mkdir(parents=True, exist_ok=True)

            self.status.emit("Rendering HTML…")
            html_content = render_html(report)
            html_path = report_dir / f"{report_type}.html"
            html_path.write_text(html_content, encoding="utf-8")

            self.status.emit("Rendering PDF…")
            pdf_path = report_dir / f"{report_type}.pdf"
            pdf_ok = render_pdf(html_content, pdf_path)

            # Check for the other report type for comparison
            other_type = "after" if report_type == "before" else "before"
            other_html = job_dir / other_type / f"{other_type}.html"
            open_path: Path = html_path

            if other_html.exists():
                self.status.emit("Generating comparison report…")
                comparison_html = generate_comparison(job_dir, job)
                if comparison_html:
                    comp_html_path = job_dir / "comparison.html"
                    comp_html_path.write_text(comparison_html, encoding="utf-8")
                    comp_pdf_path = job_dir / "comparison.pdf"
                    render_pdf(comparison_html, comp_pdf_path)
                    open_path = comp_html_path

            # Determine PDF path for the done signal
            if pdf_ok:
                self.status.emit("Reports saved (HTML + PDF)")
                pdf_path_str = str(pdf_path)
            else:
                self.status.emit("HTML report saved (PDF skipped — check logs)")
                pdf_path_str = ""

            # Emit done with paths
            self.done.emit(open_path.as_uri(), pdf_path_str)

        except Exception as exc:
            self.error.emit(str(exc))

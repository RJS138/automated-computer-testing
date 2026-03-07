"""Report done screen — shows save location and triggers report generation."""

import asyncio
import webbrowser
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Label, Static


class ReportDoneScreen(Screen):
    DEFAULT_CSS = """
    ReportDoneScreen {
        align: center middle;
    }
    #done-panel {
        width: 70;
        height: auto;
        border: solid $success;
        padding: 1 2;
    }
    #done-title {
        text-align: center;
        text-style: bold;
        color: $success;
        margin: 0 0 1 0;
    }
    #status-msg {
        margin: 0 0 1 0;
    }
    #report-path {
        background: $surface;
        padding: 0 1;
        color: $text;
        margin: 0 0 1 0;
    }
    #summary-line {
        margin: 0 0 1 0;
    }
    #btn-row {
        layout: horizontal;
        margin: 1 0 0 0;
    }
    #btn-quit {
        width: 1fr;
        margin: 0 1 0 0;
    }
    #btn-new-job {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        with Static(id="done-panel"):
            yield Label("Report Complete", id="done-title")
            yield Label("Generating report...", id="status-msg")
            yield Label("", id="report-path")
            yield Label("", id="summary-line")
            with Static(id="btn-row"):
                yield Button("Quit", variant="default", id="btn-quit")
                yield Button("New Job →", variant="primary", id="btn-new-job")

    def on_mount(self) -> None:
        self.call_after_refresh(self._generate_report)

    async def _generate_report(self) -> None:
        status = self.query_one("#status-msg", Label)
        path_label = self.query_one("#report-path", Label)
        summary_label = self.query_one("#summary-line", Label)

        try:
            job = self.app.job_info  # type: ignore[attr-defined]
            results = self.app.test_results  # type: ignore[attr-defined]

            from ...report.generator import assemble_report
            from ...report.html_render import render_html
            from ...report.pdf_render import render_pdf
            from ...report.diff import generate_comparison
            from ...utils.file_manager import get_job_dir, get_report_dir

            # Build report object
            report = assemble_report(job, results)

            # report_dir  = .../Name_WO#/before/  (or /after/)
            # job_dir     = .../Name_WO#/          (stable per-job root)
            report_dir = get_report_dir(job)
            job_dir = get_job_dir(job)
            report_dir.mkdir(parents=True, exist_ok=True)

            status.update("Rendering HTML...")
            await asyncio.sleep(0)

            loop = asyncio.get_event_loop()
            report_type = job.report_type.value
            html_path = report_dir / f"{report_type}.html"
            html_content = await loop.run_in_executor(None, render_html, report)
            html_path.write_text(html_content, encoding="utf-8")

            status.update("Rendering PDF...")
            await asyncio.sleep(0)

            pdf_path = report_dir / f"{report_type}.pdf"
            pdf_ok = await loop.run_in_executor(None, render_pdf, html_content, pdf_path)

            # Check for the other type in its subfolder
            other_type = "after" if report_type == "before" else "before"
            other_html = job_dir / other_type / f"{other_type}.html"
            open_path: Path = html_path  # default: open the individual report
            if other_html.exists():
                status.update("Generating comparison report...")
                await asyncio.sleep(0)
                comparison_html = await loop.run_in_executor(
                    None, generate_comparison, job_dir, job
                )
                if comparison_html:
                    comp_html_path = job_dir / "comparison.html"
                    comp_html_path.write_text(comparison_html, encoding="utf-8")
                    comp_pdf_path = job_dir / "comparison.pdf"
                    await loop.run_in_executor(None, render_pdf, comparison_html, comp_pdf_path)
                    open_path = comp_html_path  # comparison is the main view

            if pdf_ok:
                status.update("[bold green]Reports saved (HTML + PDF)[/bold green]")
            else:
                status.update("[bold green]HTML report saved[/bold green] [dim](PDF skipped — check logs)[/dim]")
            # Show the job root so the user sees the main folder, not the subfolder
            path_label.update(str(job_dir))

            # Open the best available report in the default browser
            webbrowser.open(open_path.as_uri())

            overall = report.overall_status()
            pass_c = report.pass_count()
            warn_c = report.warn_count()
            fail_c = report.fail_count()
            summary_label.update(
                f"Overall: {overall.value.upper()} — "
                f"{pass_c} passed, {warn_c} warnings, {fail_c} failed"
            )

        except Exception as exc:
            status.update(f"[bold red]Error generating report:[/bold red] {exc}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-quit":
            self.app.exit()
        elif event.button.id == "btn-new-job":
            from ...ui.screens.readiness import ReadinessScreen

            # Reset shared state
            self.app.job_info = None  # type: ignore[attr-defined]
            self.app.test_results = []  # type: ignore[attr-defined]
            self.app.manual_items = []  # type: ignore[attr-defined]
            # Replace entire stack with a fresh readiness screen
            self.app.switch_screen(ReadinessScreen())

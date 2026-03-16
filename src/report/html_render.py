"""Render a FullReport to HTML using Jinja2."""

import json

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import TEMPLATES_DIR
from ..models.report import FullReport


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _report_to_json(report: FullReport) -> str:
    """
    Serialize report data to a JSON string for embedding in the HTML.
    Used by the comparison diff parser — keeps Jinja2 templates simple.
    """
    data = {
        "job": {
            "customer_name": report.job.customer_name,
            "device_description": report.job.device_description,
            "job_number": report.job.job_number,
            "report_type": report.job.report_type.value,
            "test_mode": report.job.test_mode.value,
            "generated_at": report.generated_at.isoformat(),
        },
        "results": {
            r.name: {
                "display_name": r.display_name,
                "status": r.status.value,
                "summary": r.summary,
                "data": r.data,
            }
            for r in report.results
        },
    }
    return json.dumps(data, indent=2, default=str)


def render_html(report: FullReport) -> str:
    """Render a single report (before or after) to HTML string."""
    env = _get_jinja_env()
    template = env.get_template("report.html.j2")
    return template.render(report=report, report_json=_report_to_json(report))

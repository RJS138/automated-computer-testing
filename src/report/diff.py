"""Generate a before/after comparison report."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import APP_VERSION, TEMPLATES_DIR
from ..models.job import JobInfo
from ..models.test_result import TestStatus


def _parse_html_report(html_path: Path) -> dict:
    """
    Extract embedded JSON data from an HTML report.
    The template embeds <script id="report-data" type="application/json">...</script>.
    """
    import re

    content = html_path.read_text(encoding="utf-8")
    match = re.search(
        r'<script[^>]+id="report-data"[^>]*>(.*?)</script>',
        content,
        re.DOTALL,
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


def _diff_results(before: dict, after: dict) -> list[dict]:
    """
    Compare per-test result data between before and after reports.
    Returns a list of comparison rows.
    """
    all_test_names = list(
        {
            *before.get("results", {}).keys(),
            *after.get("results", {}).keys(),
        }
    )

    rows = []
    for name in all_test_names:
        b = before.get("results", {}).get(name, {})
        a = after.get("results", {}).get(name, {})

        b_status = b.get("status", "—")
        a_status = a.get("status", "—")
        b_summary = b.get("summary", "—")
        a_summary = a.get("summary", "—")

        # Determine change direction
        good_statuses = {TestStatus.PASS.value}
        bad_statuses = {TestStatus.FAIL.value, TestStatus.ERROR.value}

        if b_status in bad_statuses and a_status in good_statuses:
            change = "improved"
        elif b_status in good_statuses and a_status in bad_statuses:
            change = "worsened"
        elif b_status == a_status:
            change = "unchanged"
        else:
            change = "changed"

        rows.append(
            {
                "name": name,
                "display_name": b.get("display_name") or a.get("display_name") or name,
                "before_status": b_status,
                "after_status": a_status,
                "before_summary": b_summary,
                "after_summary": a_summary,
                "change": change,
            }
        )

    return rows


def generate_comparison(job_dir: Path, job: JobInfo) -> str | None:
    """
    Read before/before.html and after/after.html from job_dir, generate comparison HTML.
    Returns the HTML string, or None if either file is missing.
    """
    before_path = job_dir / "before" / "before.html"
    after_path = job_dir / "after" / "after.html"

    if not before_path.exists() or not after_path.exists():
        return None

    before_data = _parse_html_report(before_path)
    after_data = _parse_html_report(after_path)

    diff_rows = _diff_results(before_data, after_data)

    improved = sum(1 for r in diff_rows if r["change"] == "improved")
    worsened = sum(1 for r in diff_rows if r["change"] == "worsened")
    unchanged = sum(1 for r in diff_rows if r["change"] == "unchanged")

    comparison_json = json.dumps(
        {
            "type": "comparison",
            "job": {
                "customer_name": job.customer_name,
                "device_description": job.device_description,
                "job_number": job.job_number,
            },
            "rows": diff_rows,
            "improved": improved,
            "worsened": worsened,
            "unchanged": unchanged,
        },
        indent=2,
        default=str,
    )

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("comparison.html.j2")

    from .html_render import _load_branding
    branding_name, branding_logo = _load_branding()

    return template.render(
        job=job,
        rows=diff_rows,
        improved=improved,
        worsened=worsened,
        unchanged=unchanged,
        before_data=before_data,
        after_data=after_data,
        comparison_json=comparison_json,
        branding_name=branding_name,
        branding_logo=branding_logo,
        app_version=APP_VERSION,
    )

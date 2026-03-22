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


def _cpu_temp_svg(
    samples: list[dict],
    temp_warn: float | None,
    temp_fail: float | None,
    width: int = 560,
    height: int = 110,
) -> str:
    """Generate an inline SVG area chart for CPU temperature over time."""
    if not samples or len(samples) < 2:
        return ""

    temps = [s["c"] for s in samples]
    times = [s["t"] for s in samples]

    pad_l, pad_r, pad_t, pad_b = 38, 8, 10, 20
    cw = width - pad_l - pad_r
    ch = height - pad_t - pad_b

    y_max = (temp_fail + 5) if temp_fail is not None else (max(temps) + 8)
    y_min = min(temps) - 5
    y_range = max(y_max - y_min, 1.0)

    x_min, x_max = times[0], max(times[-1], 1.0)
    x_range = max(x_max - x_min, 1.0)

    def tx(t: float) -> float:
        return pad_l + (t - x_min) / x_range * cw

    def ty(temp: float) -> float:
        return pad_t + ch - (temp - y_min) / y_range * ch

    pts = [(tx(s["t"]), ty(s["c"])) for s in samples]
    bottom_y = pad_t + ch

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"'
        f' viewBox="0 0 {width} {height}" style="display:block;width:100%;max-width:{width}px">',
        '<defs><linearGradient id="tcg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#3b82f6" stop-opacity="0.25"/>'
        '<stop offset="100%" stop-color="#3b82f6" stop-opacity="0.02"/>'
        '</linearGradient></defs>',
    ]

    # Grid lines + Y labels (4 ticks)
    for i in range(4):
        tick = y_min + i * y_range / 3
        y = ty(tick)
        if pad_t <= y <= bottom_y:
            parts.append(
                f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}"'
                f' stroke="#1f1f23" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="0" y="{y + 4:.1f}" fill="#52525b" font-size="9"'
                f' font-family="monospace">{tick:.0f}°</text>'
            )

    # Threshold lines
    if temp_warn is not None:
        wy = ty(temp_warn)
        parts.append(
            f'<line x1="{pad_l}" y1="{wy:.1f}" x2="{width - pad_r}" y2="{wy:.1f}"'
            f' stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,4" stroke-opacity="0.7"/>'
        )
        parts.append(
            f'<text x="{width - 90}" y="{wy - 3:.1f}" fill="#f59e0b"'
            f' font-size="8" fill-opacity="0.8">warn {temp_warn:.0f}°C</text>'
        )
    if temp_fail is not None:
        fy = ty(temp_fail)
        parts.append(
            f'<line x1="{pad_l}" y1="{fy:.1f}" x2="{width - pad_r}" y2="{fy:.1f}"'
            f' stroke="#ef4444" stroke-width="1" stroke-dasharray="4,4" stroke-opacity="0.5"/>'
        )

    # Area fill
    area_pts = f"{pts[0][0]:.1f},{bottom_y:.1f}"
    for x, y in pts:
        area_pts += f" {x:.1f},{y:.1f}"
    area_pts += f" {pts[-1][0]:.1f},{bottom_y:.1f}"
    parts.append(f'<polygon points="{area_pts}" fill="url(#tcg)"/>')

    # Line
    line_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(
        f'<polyline points="{line_pts}" fill="none" stroke="#3b82f6"'
        f' stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Idle marker
    x0, y0 = pts[0]
    parts.append(f'<circle cx="{x0:.1f}" cy="{y0:.1f}" r="3" fill="#71717a"/>')
    parts.append(
        f'<text x="{x0 + 5:.1f}" y="{y0 - 3:.1f}" fill="#71717a" font-size="8">'
        f'idle {temps[0]:.0f}°C</text>'
    )

    # Peak marker
    peak_i = temps.index(max(temps))
    xp, yp = pts[peak_i]
    parts.append(
        f'<circle cx="{xp:.1f}" cy="{yp:.1f}" r="4" fill="#f59e0b"'
        f' stroke="#f5f5f5" stroke-width="1.5"/>'
    )
    parts.append(
        f'<text x="{xp + 6:.1f}" y="{yp - 3:.1f}" fill="#f59e0b"'
        f' font-size="9" font-weight="600">{max(temps):.0f}°C peak</text>'
    )
    parts.append(
        f'<text x="{xp + 6:.1f}" y="{yp + 9:.1f}" fill="#888"'
        f' font-size="8">at {times[peak_i]:.0f}s</text>'
    )

    # X axis
    parts.append(
        f'<line x1="{pad_l}" y1="{bottom_y:.1f}" x2="{width - pad_r}" y2="{bottom_y:.1f}"'
        f' stroke="#3f3f46" stroke-width="1"/>'
    )
    for t_label in [x_min, (x_min + x_max) / 2, x_max]:
        lx = tx(t_label)
        parts.append(
            f'<text x="{lx - 6:.1f}" y="{bottom_y + 12:.1f}" fill="#52525b"'
            f' font-size="9" font-family="monospace">{t_label:.0f}s</text>'
        )

    parts.append('</svg>')
    return "\n".join(parts)


def render_html(report: FullReport) -> str:
    """Render a single report (before or after) to HTML string."""
    env = _get_jinja_env()
    template = env.get_template("report.html.j2")

    # Pre-compute SVG charts keyed by test name.
    # Always pass temp_svgs (even as {}) to avoid Jinja2 UndefinedError.
    temp_svgs: dict[str, str] = {}
    for r in report.results:
        if r.name == "cpu" and r.data and r.data.get("temp_samples"):
            temp_svgs["cpu"] = _cpu_temp_svg(
                r.data["temp_samples"],
                r.data.get("temp_thresh_load_warn"),
                r.data.get("temp_thresh_fail"),
            )

    return template.render(
        report=report,
        report_json=_report_to_json(report),
        temp_svgs=temp_svgs,
    )

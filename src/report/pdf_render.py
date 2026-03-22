"""
Generate PDF reports using ReportLab — pure Python, no system libraries required.

Parses the JSON data block embedded in the HTML report by the Jinja2 template,
then builds a structured PDF directly.  Works on all platforms without Pango/Cairo.
"""

import json
import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import (
    Circle,
    Drawing,
    Line,
    PolyLine,
    Polygon,
    String,
)

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
_C = {
    "header": HexColor("#1e3a5f"),
    "pass": HexColor("#43a047"),
    "pass_bg": HexColor("#e8f5e9"),
    "pass_txt": HexColor("#2e7d32"),
    "warn": HexColor("#ffb300"),
    "warn_bg": HexColor("#fff8e1"),
    "warn_txt": HexColor("#f57f17"),
    "fail": HexColor("#e53935"),
    "fail_bg": HexColor("#ffebee"),
    "fail_txt": HexColor("#c62828"),
    "skip": HexColor("#bdbdbd"),
    "skip_bg": HexColor("#f5f5f5"),
    "skip_txt": HexColor("#757575"),
    "tbl_hdr": HexColor("#eeeeee"),
    "tbl_alt": HexColor("#f9f9f9"),
    "border": HexColor("#e0e0e0"),
    "muted": HexColor("#888888"),
    "improved": HexColor("#e8f5e9"),
    "worsened": HexColor("#ffebee"),
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


def _style(name: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


_S = {
    "body": _style("body", fontName="Helvetica", fontSize=9, leading=12, textColor=black),
    "small": _style("small", fontName="Helvetica", fontSize=8, leading=10, textColor=_C["muted"]),
    "bold": _style("bold", fontName="Helvetica-Bold", fontSize=9, leading=12),
    "h1": _style("h1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=white),
    "h2": _style("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=_C["header"]),
    "meta": _style(
        "meta",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=HexColor("#cccccc"),
    ),
    "badge_w": _style("badgew", fontName="Helvetica-Bold", fontSize=8, textColor=white),
    "badge_b": _style("badgeb", fontName="Helvetica-Bold", fontSize=8, textColor=black),
    "summary": _style("summ", fontName="Helvetica-Bold", fontSize=11, leading=14),
    "data_key": _style(
        "dkey",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=HexColor("#444444"),
    ),
    "data_val": _style("dval", fontName="Helvetica", fontSize=8, leading=10),
    "mono": _style("mono", fontName="Courier", fontSize=8, leading=10),
}


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _v(data: dict, key: str, suffix: str = "") -> str:
    v = data.get(key)
    if v is None:
        return "—"
    return f"{v}{suffix}"


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


# ---------------------------------------------------------------------------
# Test-specific data row extraction
# ---------------------------------------------------------------------------


def _rows_cpu(d: dict) -> list[tuple[str, str]]:
    r = [
        ("CPU Model", _v(d, "brand")),
        ("Architecture", _v(d, "arch")),
        (
            "Cores / Threads",
            f"{d.get('physical_cores', '—')} / {d.get('logical_cores', '—')}",
        ),
        ("Clock Speed", _v(d, "hz_advertised")),
        ("Idle Temp", f"{d['temp_idle']}°C" if d.get("temp_idle") else "—"),
        ("Peak Temp (stress)", f"{d['temp_peak']}°C" if d.get("temp_peak") else "—"),
        ("Stress Duration", _v(d, "stress_duration_s", "s")),
    ]
    if d.get("gpu_temp"):
        r.append(("GPU Temp (post-stress)", f"{d['gpu_temp']}°C"))
    if d.get("cpu_power_w"):
        r.append(("CPU Power", f"{d['cpu_power_w']} W"))
    return r


def _rows_ram(d: dict) -> list[tuple[str, str]]:
    return [
        ("Total RAM", _v(d, "total_gb", " GB")),
        ("Available", _v(d, "available_gb", " GB")),
        ("Used", _v(d, "used_percent", "%")),
        ("Speed", _v(d, "speed_mhz")),
        ("Swap Total", _v(d, "swap_total_gb", " GB")),
        ("Pattern Scan", f"{d.get('scan_mb', '—')} MB — {d.get('scan_message', '—')}"),
    ]


def _rows_storage(d: dict) -> list[tuple[str, str]]:
    rows = []
    for i, drv in enumerate(d.get("drives", []), 1):
        cap = drv.get("total_gb")
        used = drv.get("used_gb")
        free = drv.get("free_gb")
        cap_str = f"{cap} GB total / {used or '—'} GB used / {free or '—'} GB free" if cap else "—"
        rows += [
            (f"Drive {i} — {drv.get('model', 'Unknown')}", ""),
            (
                "  Serial / Interface",
                f"{drv.get('serial', '—')} / {drv.get('interface', '—')} {drv.get('medium_type', '')}",
            ),
            ("  Capacity", cap_str),
            ("  SMART Status", drv.get("smart_status", "Unknown")),
        ]
        if drv.get("power_on_hours") is not None:
            rows.append(("  Power-On Hours", f"{drv['power_on_hours']}h"))
        if drv.get("temp_c") is not None:
            rows.append(("  Temperature", f"{drv['temp_c']}°C"))
        if drv.get("percentage_used") is not None:
            rows.append(
                (
                    "  NVMe Wear / Spare",
                    f"{drv['percentage_used']}% used / {drv.get('available_spare_pct', '—')}% spare",
                )
            )
    rows += [
        ("Read Speed", _v(d, "read_mb_s", " MB/s")),
        ("Write Speed", _v(d, "write_mb_s", " MB/s")),
    ]
    return rows


def _rows_gpu(d: dict) -> list[tuple[str, str]]:
    rows = []
    for gpu in d.get("gpus", []):
        rows.append((f"GPU — {gpu.get('name', 'Unknown')}", _v(gpu, "vendor")))
        if gpu.get("vram_total_mb"):
            used = f" ({gpu['vram_used_mb']} MB used)" if gpu.get("vram_used_mb") else ""
            rows.append(("  VRAM", f"{gpu['vram_total_mb']} MB{used}"))
        elif gpu.get("vram_note"):
            rows.append(("  Memory", gpu["vram_note"]))
        if gpu.get("gpu_cores"):
            rows.append(("  GPU Cores", str(gpu["gpu_cores"])))
        if gpu.get("metal_support"):
            rows.append(("  Metal", gpu["metal_support"]))
        if gpu.get("temp_c") is not None:
            rows.append(("  Temperature", f"{gpu['temp_c']}°C"))
    return rows


def _rows_network(d: dict) -> list[tuple[str, str]]:
    wifi = d.get("wifi", {})
    bt = d.get("bluetooth", {})
    rows = [
        ("Wi-Fi", "Connected" if wifi.get("connected") else "Not Connected"),
    ]
    if wifi.get("ssid"):
        rows.append(("  SSID", wifi["ssid"]))
    if wifi.get("signal_dbm") is not None:
        rows.append(("  Signal", f"{wifi['signal_dbm']} dBm"))
    if wifi.get("standard"):
        rows.append(("  Standard", wifi["standard"]))
    if wifi.get("security"):
        rows.append(("  Security", wifi["security"]))
    if wifi.get("tx_rate_mbps"):
        rows.append(("  Link Rate", f"{wifi['tx_rate_mbps']} Mbps"))
    if wifi.get("download_mbps"):
        rows.append(("  Download Speed", f"{wifi['download_mbps']} Mbps"))
    rtt = d.get("ping_rtt_ms")
    rows.append(
        (
            "Internet (ping)",
            f"{rtt} ms" if d.get("ping_reachable") and rtt else "Failed",
        )
    )
    rows.append(("Bluetooth", "Available" if bt.get("available") else "Not detected"))
    if bt.get("chipset"):
        rows.append(("  Chipset", bt["chipset"]))
    if bt.get("version"):
        rows.append(("  Version", f"Bluetooth {bt['version']}"))
    if bt.get("devices_paired") is not None:
        rows.append(("  Devices Paired", str(bt["devices_paired"])))
    active = sum(1 for a in d.get("adapters", []) if a.get("is_up"))
    rows.append(("Active Adapters", str(active)))
    nets = wifi.get("available_networks", [])
    if nets:
        rows.append(
            (
                f"Networks Visible ({len(nets)})",
                ", ".join(n.get("ssid") or "(hidden)" for n in nets[:6]),
            )
        )
    return rows


def _rows_battery(d: dict) -> list[tuple[str, str]]:
    rows = [
        ("Charge Level", _v(d, "percent_charged", "%")),
        ("Plugged In", "Yes" if d.get("plugged_in") else "No"),
    ]
    hp = d.get("health_pct")
    rows.append(("Health", f"{hp}%" if hp is not None else "Unknown"))
    if d.get("condition"):
        rows.append(("Condition", d["condition"]))
    rows.append(
        (
            "Cycle Count",
            _fmt(d.get("cycle_count")) if d.get("cycle_count") is not None else "Unknown",
        )
    )
    if d.get("design_capacity_mah"):
        rows.append(("Design Capacity", f"{d['design_capacity_mah']} mAh"))
    elif d.get("design_capacity_mwh"):
        rows.append(("Design Capacity", f"{d['design_capacity_mwh']} mWh"))
    if d.get("full_charge_capacity_mah"):
        rows.append(("Full Charge", f"{d['full_charge_capacity_mah']} mAh"))
    if d.get("chemistry"):
        rows.append(("Chemistry", str(d["chemistry"])))
    if d.get("temp_c") is not None:
        rows.append(("Battery Temp", f"{d['temp_c']}°C"))
    if d.get("voltage_mv"):
        rows.append(("Voltage", f"{d['voltage_mv'] / 1000:.2f} V"))
    if d.get("charger_watts"):
        rows.append(("Charger", f"{d['charger_watts']}W"))
    return rows


def _rows_system_info(d: dict) -> list[tuple[str, str]]:
    return [
        ("OS", _v(d, "os_name")),
        ("OS Version", _v(d, "os_version")),
        ("Hostname", _v(d, "hostname")),
        ("Architecture", _v(d, "machine_arch")),
        ("Board Model", d.get("chassis_model") or d.get("board_model") or "—"),
        ("Board Serial", _v(d, "board_serial")),
        ("BIOS Version", _v(d, "bios_version")),
        ("BIOS Date", _v(d, "bios_date")),
        ("BIOS Vendor", _v(d, "bios_vendor")),
    ]


def _rows_manual(d: dict) -> list[tuple[str, str]]:
    rows = []
    for item_id, item in d.get("items", {}).items():
        status = item.get("status", "—").upper()
        notes = item.get("notes", "") or ""
        rows.append((item.get("label", item_id), f"{status}{' — ' + notes if notes else ''}"))
    return rows


def _rows_display(d: dict) -> list[tuple[str, str]]:
    rows = []
    for i, disp in enumerate(d.get("displays", []), 1):
        label = disp.get("name", "Unknown Display")
        tags = []
        if disp.get("is_primary"):
            tags.append("Primary")
        if disp.get("is_internal"):
            tags.append("Built-in")
        if tags:
            label += f" ({', '.join(tags)})"
        rows.append((f"Display {i} — {label}", ""))
        rows.append(("  Connection", disp.get("connection_type") or "—"))
        if disp.get("panel_technology"):
            rows.append(("  Panel Type", disp["panel_technology"]))
        if disp.get("native_resolution"):
            rows.append(("  Native Resolution", disp["native_resolution"]))
        if disp.get("max_resolution") and disp.get("max_resolution") != disp.get(
            "native_resolution"
        ):
            rows.append(("  Max Resolution", disp["max_resolution"]))
        if disp.get("ui_resolution"):
            hz = (
                f" @ {int(disp['ui_refresh_hz'])} Hz"
                if disp.get("ui_refresh_hz") is not None
                else ""
            )
            rows.append(("  UI Resolution", f"{disp['ui_resolution']}{hz}"))
        elif disp.get("current_resolution"):
            hz = (
                f" @ {int(disp['current_refresh_hz'])} Hz"
                if disp.get("current_refresh_hz") is not None
                else ""
            )
            rows.append(("  Resolution", f"{disp['current_resolution']}{hz}"))
        if disp.get("max_refresh_hz") and disp.get("max_refresh_hz") not in (
            disp.get("ui_refresh_hz"),
            disp.get("current_refresh_hz"),
        ):
            rows.append(("  Max Refresh Rate", f"{int(disp['max_refresh_hz'])} Hz"))
        if disp.get("inches"):
            rows.append(("  Screen Size", f'{disp["inches"]}"'))
        if disp.get("physical_width_mm"):
            rows.append(
                (
                    "  Physical Size",
                    f"{disp['physical_width_mm']} × {disp['physical_height_mm']} mm",
                )
            )
        if disp.get("manufacturer"):
            rows.append(("  Manufacturer", disp["manufacturer"]))
        if disp.get("model"):
            rows.append(("  Model", disp["model"]))
        if disp.get("manufacturer_id"):
            rows.append(("  Manufacturer ID", disp["manufacturer_id"]))
        if disp.get("panel_serial"):
            rows.append(("  Panel Serial", disp["panel_serial"]))
        if disp.get("serial") and disp.get("serial") != disp.get("panel_serial"):
            rows.append(("  Serial", disp["serial"]))
    return rows


def _rows_generic(d: dict) -> list[tuple[str, str]]:
    rows = []
    for k, v in d.items():
        if isinstance(v, (dict, list)):
            continue
        rows.append((k.replace("_", " ").title(), _fmt(v)))
    return rows[:20]


def _cpu_temp_drawing(
    samples: list[dict],
    temp_warn: float | None,
    temp_fail: float | None,
    width: float = 460,
    height: float = 80,
) -> Drawing:
    """Build a ReportLab Drawing of the CPU temperature area chart."""
    d = Drawing(width, height)

    temps = [s["c"] for s in samples]
    times = [s["t"] for s in samples]

    pad_l, pad_r, pad_t, pad_b = 30.0, 8.0, 8.0, 14.0
    cw = width - pad_l - pad_r
    ch = height - pad_t - pad_b

    y_max = max(temps) + 8
    y_min = min(temps) - 5
    y_range = max(float(y_max - y_min), 1.0)

    x_min, x_max = float(times[0]), max(float(times[-1]), 1.0)
    x_range = max(x_max - x_min, 1.0)

    # ReportLab Y-axis is bottom-up; pad_b is the baseline
    def tx(t: float) -> float:
        return pad_l + (t - x_min) / x_range * cw

    def ty(temp: float) -> float:
        return pad_b + (temp - y_min) / y_range * ch

    pts = [(tx(s["t"]), ty(s["c"])) for s in samples]

    # Threshold lines
    if temp_warn is not None and y_min <= temp_warn <= y_max:
        wy = ty(temp_warn)
        line = Line(pad_l, wy, width - pad_r, wy)
        line.strokeColor = HexColor("#f59e0b")
        line.strokeDashArray = [3, 3]
        line.strokeWidth = 0.5
        d.add(line)

    if temp_fail is not None and y_min <= temp_fail <= y_max:
        fy = ty(temp_fail)
        line = Line(pad_l, fy, width - pad_r, fy)
        line.strokeColor = HexColor("#ef4444")
        line.strokeDashArray = [3, 3]
        line.strokeWidth = 0.5
        d.add(line)

    # Area polygon (filled, semi-transparent approximated by light blue)
    poly_pts: list[float] = [pad_l, pad_b]
    for x, y in pts:
        poly_pts += [x, y]
    poly_pts += [pts[-1][0], pad_b]
    poly = Polygon(poly_pts)
    poly.fillColor = HexColor("#dbeafe")  # light blue stand-in for 15% opacity #3b82f6
    poly.strokeColor = None
    d.add(poly)

    # Line
    line_pts: list[float] = []
    for x, y in pts:
        line_pts += [x, y]
    pl = PolyLine(line_pts)
    pl.strokeColor = HexColor("#3b82f6")
    pl.strokeWidth = 1.5
    d.add(pl)

    # Idle dot + label (always to the right — it's at the leftmost position)
    x0, y0 = pts[0]
    c0 = Circle(x0, y0, 2.5)
    c0.fillColor = HexColor("#888888")
    c0.strokeColor = None
    d.add(c0)
    idle_lbl = String(x0 + 5, y0 + 2, f"idle {temps[0]:.0f}\u00b0C")
    idle_lbl.fontSize = 7
    idle_lbl.fillColor = HexColor("#888888")
    idle_lbl.textAnchor = "start"
    d.add(idle_lbl)

    # Peak dot + label — flip to left when peak is on the right half of the chart
    peak_i = temps.index(max(temps))
    xp, yp = pts[peak_i]
    cp = Circle(xp, yp, 3.5)
    cp.fillColor = HexColor("#f59e0b")
    cp.strokeColor = None
    d.add(cp)
    if xp > width / 2:
        peak_lbl = String(xp - 6, yp + 2, f"{max(temps):.0f}\u00b0C peak")
        peak_lbl.textAnchor = "end"
    else:
        peak_lbl = String(xp + 6, yp + 2, f"{max(temps):.0f}\u00b0C peak")
        peak_lbl.textAnchor = "start"
    peak_lbl.fontSize = 7
    peak_lbl.fillColor = HexColor("#f57f17")
    d.add(peak_lbl)

    # X axis baseline
    ax = Line(pad_l, pad_b, width - pad_r, pad_b)
    ax.strokeColor = HexColor("#bbbbbb")
    ax.strokeWidth = 0.5
    d.add(ax)

    # X axis labels
    for t_val in [x_min, (x_min + x_max) / 2, x_max]:
        lbl = String(tx(t_val) - 6, 2, f"{t_val:.0f}s")
        lbl.fontSize = 7
        lbl.fillColor = HexColor("#888888")
        d.add(lbl)

    return d


_ROW_EXTRACTORS = {
    "cpu": _rows_cpu,
    "ram": _rows_ram,
    "storage": _rows_storage,
    "gpu": _rows_gpu,
    "display": _rows_display,
    "network": _rows_network,
    "battery": _rows_battery,
    "system_info": _rows_system_info,
    "manual": _rows_manual,
}


def _get_rows(name: str, data: dict) -> list[tuple[str, str]]:
    extractor = _ROW_EXTRACTORS.get(name, _rows_generic)
    return [(k, v) for k, v in extractor(data) if v != ""]


# ---------------------------------------------------------------------------
# Flowable builders
# ---------------------------------------------------------------------------


def _status_colors(status: str) -> tuple:
    """Return (border_color, bg_color, text_color) for a status string."""
    s = status.lower()
    if s == "pass":
        return _C["pass"], _C["pass_bg"], _C["pass_txt"]
    if s == "warn":
        return _C["warn"], _C["warn_bg"], _C["warn_txt"]
    if s == "fail":
        return _C["fail"], _C["fail_bg"], _C["fail_txt"]
    return _C["skip"], _C["skip_bg"], _C["skip_txt"]


def _header_band(job: dict, report_type: str, generated_at: str) -> Table:
    left = [
        Paragraph("PC Diagnostic Report", _S["h1"]),
        Paragraph(
            f"Customer: {job.get('customer_name', '—')}  ·  "
            f"Device: {job.get('device_description', '—')}  ·  "
            f"Job #{job.get('job_number', '—')}",
            _S["meta"],
        ),
        Paragraph(
            f"Generated: {generated_at}  ·  Mode: {job.get('test_mode', '').upper()}",
            _S["meta"],
        ),
    ]
    right = Paragraph(
        f"<b>{report_type.upper()} REPAIR</b>",
        _style("rt", fontName="Helvetica-Bold", fontSize=10, textColor=white, alignment=2),
    )
    t = Table([[left, right]], colWidths=[CONTENT_W * 0.75, CONTENT_W * 0.25])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _C["header"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (0, -1), 12),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 12),
            ]
        )
    )
    return t


def _summary_band(overall: str, pass_c: int, warn_c: int, fail_c: int) -> Table:
    border, bg, _txt = _status_colors(overall)
    label = Paragraph(f"<b>Overall: {overall.upper()}</b>", _S["summary"])
    counts = Paragraph(
        f"<font color='#2e7d32'>{pass_c} passed</font>  "
        f"<font color='#f57f17'>{warn_c} warnings</font>  "
        f"<font color='#c62828'>{fail_c} failed</font>",
        _style("cnt", fontName="Helvetica", fontSize=9, alignment=2),
    )
    t = Table([[label, counts]], colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.5])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LEFTBORDER", (0, 0), (0, -1), 4),
                ("LINEAFTER", (0, 0), (0, -1), 0, colors.transparent),
                ("BOX", (0, 0), (-1, -1), 0, colors.transparent),
                ("LINEBEFORE", (0, 0), (0, -1), 4, border),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (0, -1), 12),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def _test_result_block(result: dict) -> list:
    name = result.get("name", "")
    dname = result.get("display_name", name)
    status = result.get("status", "waiting")
    summary = result.get("summary", "")
    data = result.get("data") or {}

    border, bg, txt = _status_colors(status)

    # Header row: [BADGE]  Test Name  —  Summary
    badge = Paragraph(
        f"<b>{status.upper()}</b>",
        _style(f"b{status}", fontName="Helvetica-Bold", fontSize=7, textColor=txt),
    )
    header_table = Table(
        [
            [
                badge,
                Paragraph(f"<b>{dname}</b>", _S["bold"]),
                Paragraph(summary, _S["small"]),
            ]
        ],
        colWidths=[45, 120, CONTENT_W - 165],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), bg),
                ("BACKGROUND", (1, 0), (-1, -1), bg),
                ("LINEBEFORE", (0, 0), (0, -1), 4, border),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (0, -1), 8),
                ("LEFTPADDING", (1, 0), (1, -1), 6),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, _C["border"]),
            ]
        )
    )

    items = [header_table]

    if data:
        rows = _get_rows(name, data)
        if rows:
            tdata = [
                [
                    Paragraph(k, _S["data_key"]),
                    Paragraph(_fmt(v) if not isinstance(v, str) else v, _S["data_val"]),
                ]
                for k, v in rows
            ]
            dt = Table(tdata, colWidths=[CONTENT_W * 0.38, CONTENT_W * 0.62])
            dt.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#fafafa")),
                        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [white, _C["tbl_alt"]]),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (0, -1), 12),
                        ("LEFTPADDING", (1, 0), (1, -1), 8),
                        ("RIGHTPADDING", (-1, 0), (-1, -1), 8),
                        ("LINEBELOW", (0, -1), (-1, -1), 0.5, _C["border"]),
                        ("GRID", (0, 0), (-1, -1), 0.25, HexColor("#eeeeee")),
                    ]
                )
            )
            items.append(dt)

    # For CPU test with temp samples, add chart as standalone flowable before
    # KeepTogether to avoid page overflow from the combined header+chart+table block.
    result_flowables: list = []
    if name == "cpu" and data.get("temp_samples") and len(data["temp_samples"]) >= 2:
        result_flowables.append(_cpu_temp_drawing(
            data["temp_samples"],
            data.get("temp_thresh_load_warn"),
            data.get("temp_thresh_fail"),
        ))
        result_flowables.append(Spacer(1, 2 * mm))
    result_flowables += [KeepTogether(items), Spacer(1, 3 * mm)]
    return result_flowables


# ---------------------------------------------------------------------------
# HTML → JSON extraction
# ---------------------------------------------------------------------------


def _extract_json(html: str, script_id: str) -> dict | None:
    m = re.search(
        rf'<script[^>]+id="{re.escape(script_id)}"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# PDF renderers
# ---------------------------------------------------------------------------


def _build_report_pdf(data: dict, output_path: Path) -> bool:
    job = data.get("job", {})
    results_dict = data.get("results", {})
    gen = job.get("generated_at", "")[:19].replace("T", " ")
    report_type = job.get("report_type", "report")

    # Overall counts
    statuses = [r.get("status", "waiting") for r in results_dict.values()]
    pass_c = statuses.count("pass")
    warn_c = sum(1 for s in statuses if s in ("warn", "error"))
    fail_c = statuses.count("fail")
    overall = "fail" if fail_c else "warn" if warn_c else "pass"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"PC Diagnostic Report — {job.get('customer_name', '')}",
    )

    story = [
        _header_band(job, report_type, gen),
        Spacer(1, 3 * mm),
        _summary_band(overall, pass_c, warn_c, fail_c),
        Spacer(1, 5 * mm),
        Paragraph("Test Results", _S["h2"]),
        HRFlowable(width=CONTENT_W, thickness=1, color=_C["border"], spaceAfter=4),
    ]

    if job.get("notes"):
        story += [
            Paragraph("<b>Notes:</b>", _S["bold"]),
            Paragraph(job["notes"], _S["body"]),
            Spacer(1, 4 * mm),
        ]

    for result in results_dict.values():
        story += _test_result_block(result)

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=_C["border"]))
    story.append(
        Paragraph(
            f"PC Tester — Automated Diagnostic Report  ·  {gen}",
            _style("foot", fontName="Helvetica", fontSize=7, textColor=_C["muted"]),
        )
    )

    doc.build(story)
    return True


def _build_comparison_pdf(data: dict, output_path: Path) -> bool:
    job = data.get("job", {})
    rows = data.get("rows", [])
    imp = data.get("improved", 0)
    wors = data.get("worsened", 0)
    unch = data.get("unchanged", 0)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"Before/After Comparison — {job.get('customer_name', '')}",
    )

    header_t = Table(
        [
            [
                Paragraph("Before / After Comparison Report", _S["h1"]),
                Paragraph(
                    f"{job.get('customer_name', '—')}  ·  Job #{job.get('job_number', '—')}",
                    _style(
                        "chm",
                        fontName="Helvetica",
                        fontSize=9,
                        textColor=HexColor("#cccccc"),
                        alignment=2,
                    ),
                ),
            ]
        ],
        colWidths=[CONTENT_W * 0.65, CONTENT_W * 0.35],
    )
    header_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _C["header"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (0, -1), 12),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 12),
            ]
        )
    )

    summary_t = Table(
        [
            [
                Paragraph(
                    f"<b>Changes:</b>  "
                    f"<font color='#2e7d32'>{imp} improved</font>  "
                    f"<font color='#c62828'>{wors} worsened</font>  "
                    f"<font color='#555555'>{unch} unchanged</font>",
                    _S["body"],
                )
            ]
        ],
        colWidths=[CONTENT_W],
    )
    summary_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#fafafa")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, _C["border"]),
            ]
        )
    )

    col_w = [CONTENT_W * 0.20, CONTENT_W * 0.36, CONTENT_W * 0.08, CONTENT_W * 0.36]
    thead = Table(
        [
            [
                Paragraph(
                    "<b>Test</b>",
                    _style("th", fontName="Helvetica-Bold", fontSize=8, textColor=white),
                ),
                Paragraph(
                    "<b>Before</b>",
                    _style("th2", fontName="Helvetica-Bold", fontSize=8, textColor=white),
                ),
                Paragraph(
                    "→",
                    _style(
                        "arr",
                        fontName="Helvetica-Bold",
                        fontSize=10,
                        textColor=white,
                        alignment=1,
                    ),
                ),
                Paragraph(
                    "<b>After</b>",
                    _style("th3", fontName="Helvetica-Bold", fontSize=8, textColor=white),
                ),
            ]
        ],
        colWidths=col_w,
    )
    thead.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _C["header"]),
                ("BACKGROUND", (1, 0), (1, -1), HexColor("#2a5298")),
                ("BACKGROUND", (3, 0), (3, -1), HexColor("#1b4a2a")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    tbody_data = []
    tbody_style = [
        ("GRID", (0, 0), (-1, -1), 0.25, _C["border"]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    # Hex strings for use inside Paragraph markup (hexval() is unreliable)
    _STATUS_HEX = {
        "pass": "#2e7d32",
        "warn": "#f57f17",
        "fail": "#c62828",
        "skip": "#757575",
        "error": "#c62828",
        "waiting": "#757575",
    }
    _ARROWS = {"improved": "^", "worsened": "v", "changed": "~", "unchanged": "-"}
    _ARROW_COLORS = {
        "improved": _C["pass_txt"],
        "worsened": _C["fail_txt"],
        "changed": _C["warn_txt"],
        "unchanged": _C["muted"],
    }

    for i, row in enumerate(rows):
        change = row.get("change", "unchanged")
        b_stat = row.get("before_status", "—")
        a_stat = row.get("after_status", "—")
        _, _b_bg, _ = _status_colors(b_stat)
        _, _a_bg, _ = _status_colors(a_stat)
        b_hex = _STATUS_HEX.get(b_stat, "#444444")
        a_hex = _STATUS_HEX.get(a_stat, "#444444")

        b_summary = (row.get("before_summary") or "").replace("<", "&lt;").replace(">", "&gt;")
        a_summary = (row.get("after_summary") or "").replace("<", "&lt;").replace(">", "&gt;")

        arrow_col = Paragraph(
            _ARROWS.get(change, "-"),
            _style(
                f"arr{i}",
                fontName="Helvetica-Bold",
                fontSize=12,
                textColor=_ARROW_COLORS.get(change, _C["muted"]),
                alignment=1,
            ),
        )
        tbody_data.append(
            [
                Paragraph(
                    f"<b>{row.get('display_name', row.get('name', ''))}</b>",
                    _S["data_key"],
                ),
                Paragraph(
                    f"<font color='{b_hex}'><b>{b_stat.upper()}</b></font><br/>"
                    f"<font size='7'>{b_summary}</font>",
                    _S["data_val"],
                ),
                arrow_col,
                Paragraph(
                    f"<font color='{a_hex}'><b>{a_stat.upper()}</b></font><br/>"
                    f"<font size='7'>{a_summary}</font>",
                    _S["data_val"],
                ),
            ]
        )

        if change == "improved":
            tbody_style.append(("BACKGROUND", (0, i), (-1, i), _C["improved"]))
        elif change == "worsened":
            tbody_style.append(("BACKGROUND", (0, i), (-1, i), _C["worsened"]))
        elif i % 2 == 1:
            tbody_style.append(("BACKGROUND", (0, i), (-1, i), _C["tbl_alt"]))

    tbody = Table(tbody_data, colWidths=col_w)
    tbody.setStyle(TableStyle(tbody_style))

    story = [
        header_t,
        Spacer(1, 3 * mm),
        summary_t,
        Spacer(1, 5 * mm),
        Paragraph("Test-by-Test Comparison", _S["h2"]),
        HRFlowable(width=CONTENT_W, thickness=1, color=_C["border"], spaceAfter=4),
        thead,
        tbody,
        Spacer(1, 6 * mm),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=_C["border"]),
        Paragraph(
            f"PC Tester — Before/After Comparison  ·  "
            f"{job.get('customer_name', '—')} / Job #{job.get('job_number', '—')}",
            _style("cfoot", fontName="Helvetica", fontSize=7, textColor=_C["muted"]),
        ),
    ]

    doc.build(story)
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_pdf(html_content: str, output_path: Path) -> bool:
    """
    Generate a PDF from an HTML report string.

    Parses the JSON data embedded in the HTML by the Jinja2 template
    (<script id="report-data"> or <script id="comparison-data">),
    then builds a professional PDF using ReportLab — no system libraries needed.

    Returns True if the PDF was written, False on failure.
    """
    try:
        data = _extract_json(html_content, "report-data")
        if data:
            return _build_report_pdf(data, output_path)

        data = _extract_json(html_content, "comparison-data")
        if data:
            return _build_comparison_pdf(data, output_path)

        _write_skipped(output_path, "Could not find embedded report data in HTML")
        return False

    except ImportError as exc:
        _write_skipped(output_path, f"ReportLab not installed: {exc} — run: uv sync")
        return False
    except Exception as exc:
        _write_skipped(output_path, f"PDF error: {exc}")
        return False


def _write_skipped(output_path: Path, reason: str) -> None:
    note = output_path.with_name(output_path.stem + "_pdf_skipped.txt")
    note.write_text(
        f"PDF generation was skipped — the HTML report is still available.\n\nReason: {reason}\n",
        encoding="utf-8",
    )

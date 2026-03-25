"""CategorySection — collapsible hardware-category block with flat test rows."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.test_result import TestResult
from src.ui.stylesheet import get_colors
from src.ui.widgets.dashboard_card import DashboardCard


def _build_expanded_detail(result: TestResult) -> str:
    """Build a comprehensive multi-line detail string from test result data."""
    data = result.data or {}
    test_name = result.name
    parts: list[str] = []

    if test_name == "cpu":
        if data.get("brand"):
            parts.append(data["brand"])
        cores = data.get("physical_cores")
        threads = data.get("logical_cores")
        if cores and threads:
            parts.append(f"{cores} cores  ·  {threads} threads")
        elif threads:
            parts.append(f"{threads} threads")
        temp_parts = []
        if data.get("temp_idle") is not None:
            temp_parts.append(f"Idle: {data['temp_idle']}°C")
        if data.get("temp_peak") is not None:
            temp_parts.append(f"Peak: {data['temp_peak']}°C")
        if data.get("stress_duration_s"):
            temp_parts.append(f"{data['stress_duration_s']}s stress")
        if temp_parts:
            parts.append("  ·  ".join(temp_parts))

    elif test_name == "ram":
        size_parts = []
        if data.get("total_gb"):
            size_parts.append(f"{data['total_gb']} GB total")
        if data.get("available_gb"):
            size_parts.append(f"{data['available_gb']} GB free")
        if data.get("speed_mhz"):
            size_parts.append(f"{data['speed_mhz']} MHz")
        if size_parts:
            parts.append("  ·  ".join(size_parts))
        bw = []
        if data.get("ram_read_mb_s"):
            bw.append(f"R {data['ram_read_mb_s']:,} MB/s")
        if data.get("ram_write_mb_s"):
            bw.append(f"W {data['ram_write_mb_s']:,} MB/s")
        if bw:
            parts.append("  ·  ".join(bw))
        if data.get("scan_message"):
            mb = data.get("scan_mb", "")
            n = data.get("patterns_tested", "")
            prefix = "  ·  ".join(filter(None, [
                f"{mb} MB" if mb else "",
                f"{n} pattern{'s' if n and n != 1 else ''}" if n else "",
            ]))
            parts.append(f"Scan: {prefix}  ·  {data['scan_message']}" if prefix else f"Scan: {data['scan_message']}")

    elif test_name == "storage":
        for d in data.get("drives") or []:
            model = d.get("model") or "Drive"
            header = model
            size_gb = int(d["total_gb"]) if d.get("total_gb") else None
            medium = d.get("medium_type") or d.get("interface") or ""
            if size_gb:
                header += f"  —  {size_gb} GB"
            if medium:
                header += f"  ({medium})"
            parts.append(header)
            detail = []
            if d.get("smart_status"):
                detail.append(f"SMART: {d['smart_status']}")
            if d.get("temp_c") is not None:
                detail.append(f"Temp: {d['temp_c']}°C")
            if d.get("power_on_hours") is not None:
                detail.append(f"{d['power_on_hours']:,}h on")
            if d.get("percentage_used") is not None:
                detail.append(f"{d['percentage_used']}% wear")
            if detail:
                parts.append("  ·  ".join(detail))
        read = data.get("read_mb_s")
        write = data.get("write_mb_s")
        if read or write:
            sp = []
            if read:
                sp.append(f"R {read} MB/s")
            if write:
                sp.append(f"W {write} MB/s")
            parts.append("Speed: " + "  ·  ".join(sp))

    elif test_name == "network":
        wifi = data.get("wifi") or {}
        if wifi.get("ssid"):
            w = [f"Wi-Fi: {wifi['ssid']}"]
            if wifi.get("signal_pct") is not None:
                w[0] += f" ({wifi['signal_pct']}%)"
            elif wifi.get("signal_dbm") is not None:
                w[0] += f" ({wifi['signal_dbm']} dBm)"
            if wifi.get("standard"):
                w.append(wifi["standard"])
            parts.append("  ·  ".join(w))
        conn = []
        if data.get("ping_rtt_ms") is not None:
            conn.append(f"Ping: {data['ping_rtt_ms']} ms")
        if wifi.get("download_mbps"):
            conn.append(f"↓ {wifi['download_mbps']} Mbps")
        if conn:
            parts.append("  ·  ".join(conn))
        for a in data.get("adapters") or []:
            if not a.get("is_up"):
                continue
            ap = [a["name"]]
            if a.get("speed_mbps"):
                ap.append(f"{a['speed_mbps']} Mbps")
            if a.get("ipv4"):
                ap.append(a["ipv4"])
            parts.append("  ·  ".join(ap))

    elif test_name == "gpu":
        for g in data.get("gpus") or []:
            gpu_name = g.get("name", "GPU")
            name_line = [gpu_name]
            if g.get("vram_total_mb"):
                name_line.append(f"{round(g['vram_total_mb'] / 1024)} GB VRAM")
            elif g.get("vram_note"):
                name_line.append(g["vram_note"])
            parts.append("  ·  ".join(name_line))
            gd = []
            if g.get("temp_c") is not None:
                gd.append(f"Temp: {g['temp_c']}°C")
            if g.get("utilization_pct") is not None:
                gd.append(f"Util: {g['utilization_pct']:.0f}%")
            if g.get("power_w") is not None:
                gd.append(f"Power: {g['power_w']}W")
            if g.get("driver_version"):
                gd.append(f"Driver: {g['driver_version']}")
            if gd:
                parts.append("  ·  ".join(gd))

    elif test_name == "battery":
        hp = data.get("health_pct")
        cc = data.get("cycle_count")
        pct = data.get("percent_charged")
        chem = data.get("chemistry")
        row1 = []
        if hp is not None:
            row1.append(f"Health: {hp:.0f}%")
        if cc is not None:
            row1.append(f"Cycles: {cc}")
        if pct is not None:
            row1.append(f"Charged: {pct:.0f}%")
        if row1:
            parts.append("  ·  ".join(row1))
        if chem:
            parts.append(f"Chemistry: {chem}")
        unit = "mWh" if data.get("design_capacity_mwh") else "mAh"
        design = data.get("design_capacity_mwh") or data.get("design_capacity_mah")
        full = data.get("full_charge_capacity_mwh") or data.get("full_charge_capacity_mah")
        cap = []
        if design:
            cap.append(f"Design: {design:,} {unit}")
        if full:
            cap.append(f"Full: {full:,} {unit}")
        if cap:
            parts.append("  ·  ".join(cap))
        extra = []
        if data.get("temp_c") is not None:
            extra.append(f"Temp: {data['temp_c']}°C")
        if data.get("voltage_mv") is not None:
            extra.append(f"Voltage: {data['voltage_mv'] / 1000:.2f}V")
        if data.get("charger_watts"):
            extra.append(f"Charger: {data['charger_watts']}W")
        if extra:
            parts.append("  ·  ".join(extra))

    return "\n".join(parts)


class CategorySection(QFrame):
    """Collapsible section: plain category header + flat test rows.

    Parameters
    ----------
    title : str
        Display title, e.g. ``"Performance"``.
    tests : list of (name, display_name, advanced_only) tuples
    col_count : int
        Ignored — kept for API compatibility.
    short_names : dict, optional
        Unused — kept for API compatibility.
    """

    def __init__(
        self,
        title: str,
        tests: list[tuple[str, str, bool]],
        col_count: int,
        short_names: dict[str, str] | None = None,
        theme: str = "dark",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet("QFrame { border: none; background: transparent; }")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._title = title
        self._tests = tests
        self._advanced = False
        self._expanded = True
        self._theme = theme
        self._cards: dict[str, DashboardCard] = {}
        self._adv_names: frozenset[str] = frozenset(n for n, _, adv in tests if adv)

        self._build_ui()
        self.apply_theme(theme)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Section header ────────────────────────────────────────────────────
        self._header_widget = QWidget()
        self._header_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header_widget.setStyleSheet("background: transparent;")
        self._header_widget.setFixedHeight(36)
        h_layout = QHBoxLayout(self._header_widget)
        h_layout.setContentsMargins(4, 0, 4, 0)
        h_layout.setSpacing(6)

        self._title_lbl = QLabel(self._title.upper())
        self._title_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #71717a; "
            "letter-spacing: 0.06em; background: transparent;"
        )
        h_layout.addWidget(self._title_lbl)
        h_layout.addStretch()

        # "all · none" mini controls — visible only in advanced mode
        self._sel_all_btn = QPushButton("all")
        self._sel_all_btn.setFlat(True)
        self._sel_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sel_all_btn.hide()
        self._sel_all_btn.clicked.connect(self.select_all)
        h_layout.addWidget(self._sel_all_btn)

        self._sel_sep_lbl = QLabel("·")
        self._sel_sep_lbl.setStyleSheet("color: #52525b; font-size: 11px; background: transparent;")
        self._sel_sep_lbl.hide()
        h_layout.addWidget(self._sel_sep_lbl)

        self._sel_none_btn = QPushButton("none")
        self._sel_none_btn.setFlat(True)
        self._sel_none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sel_none_btn.hide()
        self._sel_none_btn.clicked.connect(self.deselect_all)
        h_layout.addWidget(self._sel_none_btn)

        self._arrow_lbl = QLabel("▾")
        self._arrow_lbl.setStyleSheet("color: #52525b; font-size: 11px; background: transparent;")
        h_layout.addWidget(self._arrow_lbl)

        outer.addWidget(self._header_widget)

        # Thin rule below header
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.HLine)
        self._sep.setStyleSheet("background: #27272a; border: none; max-height: 1px; min-height: 1px;")
        outer.addWidget(self._sep)

        # ── Collapsible rows ──────────────────────────────────────────────────
        self._collapsible = QWidget()
        self._collapsible.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(self._collapsible)
        self._rows_layout.setContentsMargins(0, 4, 0, 0)
        self._rows_layout.setSpacing(5)
        outer.addWidget(self._collapsible)

        # Bottom spacing after section
        spacer = QWidget()
        spacer.setFixedHeight(12)
        spacer.setStyleSheet("background: transparent;")
        outer.addWidget(spacer)

        self._rebuild_rows()

        # Collapse/expand animation
        self._anim = QPropertyAnimation(self._collapsible, b"maximumHeight")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        self._header_widget.mousePressEvent = lambda _e: self._toggle_expanded()

    def _rebuild_rows(self) -> None:
        """Clear and repopulate rows based on current simple/advanced state."""
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)  # type: ignore[arg-type]

        for name, display_name, adv_only in self._tests:
            if adv_only and not self._advanced:
                continue
            if name not in self._cards:
                card = DashboardCard(name, display_name, theme=self._theme)
                self._cards[name] = card
            self._rows_layout.addWidget(self._cards[name])

    # ── Public API ────────────────────────────────────────────────────────────

    def set_advanced(self, enabled: bool) -> None:
        """Show/hide advanced-only tests and toggle checkboxes on all cards."""
        self._advanced = enabled
        self._rebuild_rows()
        for card in self._cards.values():
            card.set_advanced(enabled)
        self._sel_all_btn.setVisible(enabled)
        self._sel_sep_lbl.setVisible(enabled)
        self._sel_none_btn.setVisible(enabled)
        if self._expanded:
            self._collapsible.setMaximumHeight(16777215)

    def select_all(self) -> None:
        """Check all visible cards in this section."""
        for name, _, adv_only in self._tests:
            if adv_only and not self._advanced:
                continue
            card = self._cards.get(name)
            if card:
                card.set_checked(True)

    def deselect_all(self) -> None:
        """Uncheck all visible cards in this section."""
        for name, _, adv_only in self._tests:
            if adv_only and not self._advanced:
                continue
            card = self._cards.get(name)
            if card:
                card.set_checked(False)

    def update_card(self, result: TestResult) -> None:
        """Update the row for the given test result."""
        card = self._cards.get(result.name)
        if card is None:
            return
        sub = _build_expanded_detail(result)
        if not sub:
            sub = result.data.get("card_sub_detail", "") if result.data else ""
        if not sub and result.error_message:
            sub = result.error_message
        card.set_status(result.status.value, result.summary or "", sub)

    def card(self, name: str) -> DashboardCard | None:
        """Return the DashboardCard row for the given test name, or None."""
        return self._cards.get(name)

    def apply_theme(self, theme: str) -> None:
        """Re-apply all inline styles and propagate to child cards."""
        self._theme = theme
        c = get_colors(theme)
        self._title_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {c['text_muted']};"
            f" letter-spacing: 0.06em; background: transparent;"
        )
        self._sep.setStyleSheet(
            f"background: {c['border_subtle']}; border: none; max-height: 1px; min-height: 1px;"
        )
        self._arrow_lbl.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 11px; background: transparent;"
        )
        _mini_btn_style = (
            f"QPushButton {{ color: {c['text_muted']}; font-size: 11px; background: transparent;"
            f" padding: 0 2px; }}"
            f"QPushButton:hover {{ color: {c['accent']}; }}"
        )
        self._sel_all_btn.setStyleSheet(_mini_btn_style)
        self._sel_none_btn.setStyleSheet(_mini_btn_style)
        self._sel_sep_lbl.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 11px; background: transparent;"
        )
        for card in self._cards.values():
            card.apply_theme(theme)

    # ── Collapse/expand ───────────────────────────────────────────────────────

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self._arrow_lbl.setText("▾" if self._expanded else "▸")
        self._anim.stop()
        if self._expanded:
            self._collapsible.show()
            self._anim.setStartValue(0)
            self._anim.setEndValue(16777215)
            self._anim.start()
        else:
            current = self._collapsible.height()
            self._anim.setStartValue(current)
            self._anim.setEndValue(0)
            self._anim.start()

    def _on_anim_finished(self) -> None:
        if not self._expanded:
            self._collapsible.hide()

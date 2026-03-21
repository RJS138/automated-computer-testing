"""JobSetupPage — startup screen for job entry with collapsible recent jobs."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.job import JobInfo, ReportType
from src.ui.stylesheet import build_seg_styles, get_colors
from src.utils.file_manager import scan_existing_jobs


class JobSetupPage(QWidget):
    """Centered job-entry form with collapsible recent jobs.

    Signals
    -------
    start_testing(JobInfo)
        Emitted when Start Testing is clicked with valid Customer Name + Job #.
    """

    start_testing = Signal(object)  # JobInfo

    def __init__(self, theme: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._report_type = ReportType.BEFORE
        self._recent_expanded = False
        self._build_ui()
        self._build_recent_panel(self._inner_layout)
        self.apply_theme(theme)

    def _build_ui(self) -> None:
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        inner = QWidget()
        inner.setMaximumWidth(520)
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 32, 16, 32)
        inner_layout.setSpacing(12)
        self._inner_layout = inner_layout

        self._title_lbl = QLabel("New Job")
        inner_layout.addWidget(self._title_lbl)

        self._sub_lbl = QLabel("Fill in the details below, then start testing.")
        inner_layout.addWidget(self._sub_lbl)

        # Form card
        self._form_card = QFrame()
        form_layout = QVBoxLayout(self._form_card)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(12)

        # Row 1: Customer Name + Job #
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        cust_col = QVBoxLayout()
        cust_col.setSpacing(5)
        self._cust_lbl = QLabel("CUSTOMER NAME")
        cust_col.addWidget(self._cust_lbl)
        self._customer_field = QLineEdit()
        self._customer_field.setPlaceholderText("e.g. Smith Repair")
        self._customer_field.textChanged.connect(self._update_start_btn)
        cust_col.addWidget(self._customer_field)
        row1.addLayout(cust_col, stretch=1)

        job_col = QVBoxLayout()
        job_col.setSpacing(5)
        self._job_lbl = QLabel("JOB #")
        job_col.addWidget(self._job_lbl)
        self._job_field = QLineEdit()
        self._job_field.setPlaceholderText("WO#")
        self._job_field.setFixedWidth(120)
        self._job_field.textChanged.connect(self._update_start_btn)
        job_col.addWidget(self._job_field)
        row1.addLayout(job_col)
        form_layout.addLayout(row1)

        # Row 2: Device Description
        dev_col = QVBoxLayout()
        dev_col.setSpacing(5)
        self._dev_lbl = QLabel("DEVICE DESCRIPTION")
        dev_col.addWidget(self._dev_lbl)
        self._device_field = QLineEdit()
        self._device_field.setPlaceholderText('e.g. MacBook Pro 14" M3')
        dev_col.addWidget(self._device_field)
        form_layout.addLayout(dev_col)

        # Separator + Report Type
        self._form_sep = QFrame()
        self._form_sep.setFrameShape(QFrame.Shape.HLine)
        form_layout.addWidget(self._form_sep)

        type_col = QVBoxLayout()
        type_col.setSpacing(6)
        self._type_lbl = QLabel("REPORT TYPE")
        type_col.addWidget(self._type_lbl)

        seg_row = QHBoxLayout()
        seg_row.setSpacing(0)
        self._before_btn = QPushButton("Before")
        self._before_btn.setFixedHeight(30)
        self._before_btn.clicked.connect(lambda: self._set_report_type(ReportType.BEFORE))
        seg_row.addWidget(self._before_btn)

        self._after_btn = QPushButton("After")
        self._after_btn.setFixedHeight(30)
        self._after_btn.clicked.connect(lambda: self._set_report_type(ReportType.AFTER))
        seg_row.addWidget(self._after_btn)
        seg_row.addStretch()
        type_col.addLayout(seg_row)
        form_layout.addLayout(type_col)

        inner_layout.addWidget(self._form_card)

        # Start Testing button
        self._start_btn = QPushButton("▶ Start Testing")
        self._start_btn.setFixedHeight(40)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start_clicked)
        inner_layout.addWidget(self._start_btn)

        content_layout.addStretch()
        content_layout.addWidget(inner)
        content_layout.addStretch()

        scroll.setWidget(content)
        page_layout.addWidget(scroll)

    def _build_recent_panel(self, parent_layout: QVBoxLayout) -> None:
        self._recent_panel = QFrame()
        panel_layout = QVBoxLayout(self._recent_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QWidget()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 10, 16, 10)

        self._recent_title_lbl = QLabel("Recent Jobs")
        h_layout.addWidget(self._recent_title_lbl)
        h_layout.addStretch()

        self._recent_toggle_lbl = QLabel("▾ show")
        h_layout.addWidget(self._recent_toggle_lbl)
        panel_layout.addWidget(header)

        self._recent_content = QWidget()
        self._recent_content.setStyleSheet("background: transparent;")
        self._recent_content_layout = QVBoxLayout(self._recent_content)
        self._recent_content_layout.setContentsMargins(4, 0, 4, 4)
        self._recent_content_layout.setSpacing(0)
        self._recent_content.hide()
        panel_layout.addWidget(self._recent_content)

        header.mousePressEvent = lambda _e: self._toggle_recent()
        parent_layout.addWidget(self._recent_panel)
        parent_layout.addStretch()

    def _toggle_recent(self) -> None:
        self._recent_expanded = not self._recent_expanded
        if self._recent_expanded:
            self._recent_toggle_lbl.setText("▴ hide")
            self._recent_content.show()
        else:
            self._recent_toggle_lbl.setText("▾ show")
            self._recent_content.hide()

    def reload_recent_jobs(self) -> None:
        """Clear and repopulate recent jobs list. Call on page entry and after New Job."""
        while self._recent_content_layout.count():
            item = self._recent_content_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        jobs = scan_existing_jobs()
        for j in jobs:
            try:
                j["_mtime"] = j["folder_path"].stat().st_mtime
            except OSError:
                j["_mtime"] = 0.0
        jobs.sort(key=lambda j: j["_mtime"], reverse=True)
        jobs = jobs[:10]

        if not jobs:
            empty = QLabel("No recent jobs.")
            c = get_colors(self._theme)
            empty.setStyleSheet(
                f"color: {c['text_muted']}; font-size: 12px; padding: 12px; background: transparent;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._recent_content_layout.addWidget(empty)
            return

        for i, job in enumerate(jobs):
            row = self._make_recent_row(job)
            self._recent_content_layout.addWidget(row)
            if i < len(jobs) - 1:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.HLine)
                c = get_colors(self._theme)
                div.setStyleSheet(
                    f"background: {c['border_subtle']}; border: none; max-height: 1px; min-height: 1px;"
                )
                self._recent_content_layout.addWidget(div)

    def _make_recent_row(self, job: dict) -> QWidget:
        c = get_colors(self._theme)
        row = QWidget()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(
            f"QWidget {{ background: transparent; }} QWidget:hover {{ background: {c['bg_elevated']}; }}"
        )
        layout = QGridLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.setColumnStretch(0, 1)

        desc = job.get("device_description") or ""
        name_text = f"{job['customer_name']} — {desc}" if desc else job["customer_name"]
        name_lbl = QLabel(name_text)
        name_lbl.setStyleSheet(
            f"font-size: 12px; color: {c['text_primary']}; font-weight: 500; background: transparent;"
        )
        layout.addWidget(name_lbl, 0, 0)

        mtime = job.get("_mtime", 0.0)
        dt = datetime.fromtimestamp(mtime)
        date_str = f"{dt.strftime('%b')} {dt.day}"
        meta_lbl = QLabel(f"{job['job_number']}  ·  {date_str}")
        meta_lbl.setStyleSheet(f"font-size: 11px; color: {c['text_muted']}; background: transparent;")
        layout.addWidget(meta_lbl, 1, 0)

        for col, (has_it, label) in enumerate(
            [(job["has_before"], "Before"), (job["has_after"], "After")], start=1
        ):
            color = "#22c55e" if has_it else "#52525b"
            mark = "✓" if has_it else "—"
            badge = QLabel(f"{label} {mark}")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;"
            )
            layout.addWidget(badge, 0, col, 2, 1, Qt.AlignmentFlag.AlignVCenter)

        row.mousePressEvent = lambda _e, j=job: self._on_recent_clicked(j)
        return row

    def _on_recent_clicked(self, job: dict) -> None:
        self._customer_field.setText(job["customer_name"])
        self._job_field.setText(job["job_number"])
        self._device_field.setText(job.get("device_description") or "")
        if job["has_before"] and not job["has_after"]:
            self._set_report_type(ReportType.AFTER)
        elif not job["has_before"]:
            self._set_report_type(ReportType.BEFORE)

    def _set_report_type(self, rt: ReportType) -> None:
        self._report_type = rt
        seg = build_seg_styles(self._theme)
        self._before_btn.setStyleSheet(seg["L_ON"] if rt == ReportType.BEFORE else seg["L_OFF"])
        self._after_btn.setStyleSheet(seg["R_ON"] if rt == ReportType.AFTER else seg["R_OFF"])

    def _update_start_btn(self) -> None:
        enabled = bool(
            self._customer_field.text().strip() and self._job_field.text().strip()
        )
        self._start_btn.setEnabled(enabled)

    def _on_start_clicked(self) -> None:
        job_info = JobInfo(
            customer_name=self._customer_field.text().strip(),
            device_description=self._device_field.text().strip(),
            job_number=self._job_field.text().strip(),
            report_type=self._report_type,
        )
        self.start_testing.emit(job_info)

    def apply_theme(self, theme: str) -> None:
        """Re-apply all inline styles for the given theme and regenerate dynamic rows."""
        self._theme = theme
        c = get_colors(theme)
        field_lbl_style = (
            f"font-size: 10px; font-weight: 700; color: {c['text_muted']};"
            f" letter-spacing: 0.05em;"
        )
        self._title_lbl.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: {c['text_primary']};"
        )
        self._sub_lbl.setStyleSheet(
            f"font-size: 13px; color: {c['text_muted']}; margin-bottom: 4px;"
        )
        self._form_card.setStyleSheet(
            f"QFrame {{ background: {c['bg_surface']}; border: none; border-radius: 8px; }}"
        )
        self._cust_lbl.setStyleSheet(field_lbl_style)
        self._job_lbl.setStyleSheet(field_lbl_style)
        self._dev_lbl.setStyleSheet(field_lbl_style)
        self._type_lbl.setStyleSheet(field_lbl_style)
        self._form_sep.setStyleSheet(
            f"background: {c['border_subtle']}; border: none; max-height: 1px;"
        )
        # Report type buttons (preserve current selection)
        self._set_report_type(self._report_type)
        # Start Testing button
        self._start_btn.setStyleSheet(
            f"QPushButton {{ background: {c['accent']}; color: #ffffff; border: none;"
            f" border-radius: 6px; padding: 5px 14px; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
            f"QPushButton:pressed {{ background: {c['accent_hover']}; }}"
            f"QPushButton:disabled {{ background: {c['accent']}; color: #ffffff; }}"
        )
        # Recent Jobs panel
        self._recent_panel.setStyleSheet(
            f"QFrame {{ background: {c['bg_surface']}; border: none; border-radius: 8px; }}"
        )
        self._recent_title_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {c['text_secondary']}; background: transparent;"
        )
        self._recent_toggle_lbl.setStyleSheet(
            f"font-size: 10px; color: {c['accent']}; background: transparent;"
        )
        # Regenerate recent rows with updated theme colors
        self.reload_recent_jobs()

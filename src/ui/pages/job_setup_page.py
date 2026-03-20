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
from src.ui.stylesheet import refresh_style
from src.utils.file_manager import scan_existing_jobs


class JobSetupPage(QWidget):
    """Centered job-entry form with collapsible recent jobs.

    Signals
    -------
    start_testing(JobInfo)
        Emitted when Start Testing is clicked with valid Customer Name + Job #.
    """

    start_testing = Signal(object)  # JobInfo

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._report_type = ReportType.BEFORE
        self._recent_expanded = False
        self._build_ui()

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

        title_lbl = QLabel("New Job")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 600; color: #fafafa;")
        inner_layout.addWidget(title_lbl)

        sub_lbl = QLabel("Fill in the details below, then start testing.")
        sub_lbl.setStyleSheet("font-size: 13px; color: #71717a; margin-bottom: 4px;")
        inner_layout.addWidget(sub_lbl)

        # Form card
        form_card = QFrame()
        form_card.setStyleSheet(
            "QFrame { background: #18181b; border: 1px solid #3f3f46; border-radius: 8px; }"
        )
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(12)

        # Row 1: Customer Name + Job #
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        cust_col = QVBoxLayout()
        cust_col.setSpacing(5)
        cust_lbl = QLabel("CUSTOMER NAME")
        cust_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #71717a; letter-spacing: 0.05em;"
        )
        cust_col.addWidget(cust_lbl)
        self._customer_field = QLineEdit()
        self._customer_field.setPlaceholderText("e.g. Smith Repair")
        self._customer_field.textChanged.connect(self._update_start_btn)
        cust_col.addWidget(self._customer_field)
        row1.addLayout(cust_col, stretch=1)

        job_col = QVBoxLayout()
        job_col.setSpacing(5)
        job_lbl = QLabel("JOB #")
        job_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #71717a; letter-spacing: 0.05em;"
        )
        job_col.addWidget(job_lbl)
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
        dev_lbl = QLabel("DEVICE DESCRIPTION")
        dev_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #71717a; letter-spacing: 0.05em;"
        )
        dev_col.addWidget(dev_lbl)
        self._device_field = QLineEdit()
        self._device_field.setPlaceholderText('e.g. MacBook Pro 14" M3')
        dev_col.addWidget(self._device_field)
        form_layout.addLayout(dev_col)

        # Separator + Report Type
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #27272a; border: none; max-height: 1px;")
        form_layout.addWidget(sep)

        type_col = QVBoxLayout()
        type_col.setSpacing(6)
        type_lbl = QLabel("REPORT TYPE")
        type_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #71717a; letter-spacing: 0.05em;"
        )
        type_col.addWidget(type_lbl)

        seg_row = QHBoxLayout()
        seg_row.setSpacing(0)
        self._before_btn = QPushButton("Before")
        self._before_btn.setProperty("class", "seg-left")
        self._before_btn.setProperty("checked", "true")
        self._before_btn.setFixedHeight(30)
        self._before_btn.clicked.connect(lambda: self._set_report_type(ReportType.BEFORE))
        seg_row.addWidget(self._before_btn)

        self._after_btn = QPushButton("After")
        self._after_btn.setProperty("class", "seg-right")
        self._after_btn.setProperty("checked", "false")
        self._after_btn.setFixedHeight(30)
        self._after_btn.clicked.connect(lambda: self._set_report_type(ReportType.AFTER))
        seg_row.addWidget(self._after_btn)
        seg_row.addStretch()
        type_col.addLayout(seg_row)
        form_layout.addLayout(type_col)

        inner_layout.addWidget(form_card)

        # Start Testing button
        self._start_btn = QPushButton("▶ Start Testing")
        self._start_btn.setProperty("class", "primary")
        self._start_btn.setFixedHeight(40)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start_clicked)
        inner_layout.addWidget(self._start_btn)

        # Recent Jobs panel
        self._build_recent_panel(inner_layout)

        inner_layout.addStretch()

        content_layout.addStretch()
        content_layout.addWidget(inner)
        content_layout.addStretch()

        scroll.setWidget(content)
        page_layout.addWidget(scroll)

        # Apply initial seg button styles
        refresh_style(self._before_btn)
        refresh_style(self._after_btn)

    def _build_recent_panel(self, parent_layout: QVBoxLayout) -> None:
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame { background: #18181b; border: 1px solid #27272a; border-radius: 8px; }"
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QWidget()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 10, 16, 10)

        title_lbl = QLabel("Recent Jobs")
        title_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #a1a1aa; background: transparent;"
        )
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()

        self._recent_toggle_lbl = QLabel("▾ show")
        self._recent_toggle_lbl.setStyleSheet(
            "font-size: 10px; color: #3b82f6; background: transparent;"
        )
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
        parent_layout.addWidget(panel)

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
        jobs.sort(key=lambda j: j["folder_path"].stat().st_mtime, reverse=True)
        jobs = jobs[:10]

        if not jobs:
            empty = QLabel("No recent jobs.")
            empty.setStyleSheet(
                "color: #71717a; font-size: 12px; padding: 12px; background: transparent;"
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
                div.setStyleSheet(
                    "background: #27272a; border: none; max-height: 1px; min-height: 1px;"
                )
                self._recent_content_layout.addWidget(div)

    def _make_recent_row(self, job: dict) -> QWidget:
        row = QWidget()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(
            "QWidget { background: transparent; } QWidget:hover { background: #27272a; }"
        )
        layout = QGridLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.setColumnStretch(0, 1)

        desc = job.get("device_description") or ""
        name_text = f"{job['customer_name']} — {desc}" if desc else job["customer_name"]
        name_lbl = QLabel(name_text)
        name_lbl.setStyleSheet(
            "font-size: 12px; color: #fafafa; font-weight: 500; background: transparent;"
        )
        layout.addWidget(name_lbl, 0, 0)

        mtime = job["folder_path"].stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        date_str = f"{dt.strftime('%b')} {dt.day}"
        meta_lbl = QLabel(f"{job['job_number']}  ·  {date_str}")
        meta_lbl.setStyleSheet("font-size: 11px; color: #71717a; background: transparent;")
        layout.addWidget(meta_lbl, 1, 0)

        for col, (has_it, label) in enumerate(
            [(job["has_before"], "Before"), (job["has_after"], "After")], start=1
        ):
            bg = "#1a2e20" if has_it else "#27272a"
            color = "#22c55e" if has_it else "#71717a"
            mark = "✓" if has_it else "—"
            badge = QLabel(f"{label} {mark}")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {bg}; color: {color}; "
                f"font-size: 10px; font-weight: 700; "
                f"padding: 2px 6px; border-radius: 4px; border: none;"
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
        self._before_btn.setProperty("checked", "true" if rt == ReportType.BEFORE else "false")
        self._after_btn.setProperty("checked", "true" if rt == ReportType.AFTER else "false")
        refresh_style(self._before_btn)
        refresh_style(self._after_btn)

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

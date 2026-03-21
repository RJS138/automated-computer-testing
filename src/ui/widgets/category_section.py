"""CategorySection — collapsible hardware-category block with flat test rows."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.test_result import TestResult
from src.ui.stylesheet import get_colors
from src.ui.widgets.dashboard_card import DashboardCard


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
        if self._expanded:
            self._collapsible.setMaximumHeight(16777215)

    def update_card(self, result: TestResult) -> None:
        """Update the row for the given test result."""
        card = self._cards.get(result.name)
        if card is None:
            return
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

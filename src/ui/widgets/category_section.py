"""CategorySection — collapsible hardware-category block with mini badges and DashboardCard grid."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.test_result import TestResult
from src.ui.widgets.dashboard_card import DashboardCard

_BADGE_STYLES: dict[str, tuple[str, str]] = {
    "pass":    ("#1a2e20", "#22c55e"),
    "warn":    ("#2d2006", "#f59e0b"),
    "fail":    ("#2e1414", "#ef4444"),
    "error":   ("#2e1414", "#ef4444"),
    "running": ("#1e3a5f", "#60a5fa"),
    "waiting": ("#27272a", "#71717a"),
    "skip":    ("#27272a", "#71717a"),
}


class _MiniBadge(QLabel):
    def __init__(self, short_name: str, parent=None) -> None:
        super().__init__(parent)
        self._short = short_name.upper()
        self._apply("waiting")

    def update_status(self, status: str) -> None:
        self._apply(status)

    def _apply(self, status: str) -> None:
        bg, color = _BADGE_STYLES.get(status, _BADGE_STYLES["waiting"])
        label = f"{self._short} —" if status == "waiting" else f"{self._short} {status.upper()}"
        self.setText(label)
        self.setStyleSheet(
            f"background: {bg}; color: {color}; "
            f"font-size: 10px; font-weight: 700; "
            f"padding: 1px 7px; border-radius: 4px; border: none;"
        )


class CategorySection(QFrame):
    """Collapsible section: header badges + DashboardCard grid.

    Parameters
    ----------
    title : str
        Display title including emoji, e.g. ``"⚡ Performance"``.
    tests : list of (name, display_name, advanced_only) tuples
        All tests for this category, including advanced-only ones.
    col_count : int
        Fixed number of grid columns.
    short_names : dict, optional
        name → short badge label. Defaults to display_name.
    """

    def __init__(
        self,
        title: str,
        tests: list[tuple[str, str, bool]],
        col_count: int,
        short_names: dict[str, str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: #18181b; border: 1px solid #3f3f46; border-radius: 8px; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._title = title
        self._tests = tests
        self._col_count = col_count
        self._short_names = short_names or {}
        self._advanced = False
        self._expanded = True
        self._cards: dict[str, DashboardCard] = {}
        self._badges: dict[str, _MiniBadge] = {}
        self._adv_names: frozenset[str] = frozenset(n for n, _, adv in tests if adv)

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header row
        self._header_widget = QWidget()
        self._header_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header_widget.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(self._header_widget)
        h_layout.setContentsMargins(14, 8, 14, 8)
        h_layout.setSpacing(8)

        title_lbl = QLabel(self._title)
        title_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #a1a1aa; "
            "text-transform: uppercase; letter-spacing: 0.08em; background: transparent;"
        )
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()

        self._badges_layout = QHBoxLayout()
        self._badges_layout.setSpacing(4)
        self._badges_layout.setContentsMargins(0, 0, 0, 0)
        for name, display_name, adv_only in self._tests:
            if not adv_only:
                short = self._short_names.get(name, display_name)
                badge = _MiniBadge(short)
                self._badges[name] = badge
                self._badges_layout.addWidget(badge)
        h_layout.addLayout(self._badges_layout)

        self._arrow_lbl = QLabel("▾")
        self._arrow_lbl.setStyleSheet(
            "color: #71717a; font-size: 12px; background: transparent;"
        )
        h_layout.addWidget(self._arrow_lbl)

        outer.addWidget(self._header_widget)

        # Collapsible container: separator + card grid
        self._collapsible = QWidget()
        self._collapsible.setStyleSheet("background: #18181b;")
        coll_layout = QVBoxLayout(self._collapsible)
        coll_layout.setContentsMargins(0, 0, 0, 0)
        coll_layout.setSpacing(0)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            "background: #27272a; border: none; max-height: 1px; min-height: 1px;"
        )
        coll_layout.addWidget(sep)

        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background: #18181b;")
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)
        self._grid_layout.setSpacing(6)
        coll_layout.addWidget(self._grid_widget)

        outer.addWidget(self._collapsible)

        self._rebuild_grid()

        # Collapse/expand animation on maximumHeight
        self._anim = QPropertyAnimation(self._collapsible, b"maximumHeight")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._header_widget.mousePressEvent = lambda _e: self._toggle_expanded()

    def _rebuild_grid(self) -> None:
        """Clear and repopulate card grid based on current simple/advanced state."""
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)  # type: ignore[arg-type]

        col = row = 0
        for name, display_name, adv_only in self._tests:
            if adv_only and not self._advanced:
                continue
            if name not in self._cards:
                card = DashboardCard(name, display_name)
                self._cards[name] = card
            self._grid_layout.addWidget(self._cards[name], row, col)
            col += 1
            if col >= self._col_count:
                col = 0
                row += 1

    # ── Public API ────────────────────────────────────────────────────────────

    def set_advanced(self, enabled: bool) -> None:
        """Show/hide advanced-only tests and toggle checkboxes on all cards."""
        self._advanced = enabled
        self._rebuild_grid()

        # Show/hide advanced-only badges
        for name in self._adv_names:
            if name in self._badges:
                self._badges[name].setVisible(enabled)
            elif enabled:
                short = self._short_names.get(name, name)
                badge = _MiniBadge(short)
                self._badges[name] = badge
                self._badges_layout.addWidget(badge)

        for card in self._cards.values():
            card.set_advanced(enabled)

        if self._expanded:
            self._collapsible.setMaximumHeight(16777215)

    def update_card(self, result: TestResult) -> None:
        """Update card status and header mini badge."""
        card = self._cards.get(result.name)
        if card is None:
            return
        sub = result.data.get("card_sub_detail", "") if result.data else ""
        if not sub and result.error_message:
            sub = result.error_message
        card.set_status(result.status.value, result.summary or "", sub)

        badge = self._badges.get(result.name)
        if badge is not None:
            badge.update_status(result.status.value)

    def card(self, name: str) -> DashboardCard | None:
        """Return the DashboardCard for the given test name, or None."""
        return self._cards.get(name)

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

# CPU Temperature Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** During the CPU stress test, collect temperature samples every 2 seconds, show a live sparkline on the dashboard card while running, a full expandable area chart when done, and an inline SVG area chart in both the HTML and PDF reports.

**Architecture:** Bottom-up: data model (cpu.py) → progress signal (workers.py) → chart widget (new TempChartWidget) → dashboard card integration → page wiring → report pipeline. No external chart libraries — QPainter in Qt, inline SVG strings in HTML, ReportLab Drawing in PDF.

**Tech Stack:** PySide6 (QPainter, QWidget, Signal), Python stdlib (time.monotonic), ReportLab graphics.shapes, Jinja2

---

## File Structure

| File | What changes |
|------|-------------|
| `src/tests/base.py` | Add `on_progress` attribute |
| `src/tests/cpu.py` | Collect `temp_samples`, call `on_progress` on each tick |
| `src/ui/workers.py` | Add `progress = Signal(str, object)`, wire `on_progress` callback |
| `src/ui/widgets/temp_chart_widget.py` | **New** — `TempChartWidget` with compact (sparkline) and full (area chart) modes |
| `src/ui/widgets/dashboard_card.py` | Add sparkline to main row, chart panel to expandable area |
| `src/ui/pages/test_dashboard_page.py` | Connect `progress` signal, call `set_chart_data` in `_apply_result` |
| `src/report/html_render.py` | Add `_cpu_temp_svg()` helper, pass `temp_svgs` dict to template |
| `src/report/templates/report.html.j2` | Insert chart block before CPU data table |
| `src/report/pdf_render.py` | Add `_cpu_temp_drawing()`, insert before CPU data table in `_test_result_block` |

**Manual verification throughout:** `uv run touchstone --dev-manual`

---

### Task 1: Data collection — temp_samples + on_progress callback

**Files:**
- Modify: `src/tests/base.py:22-24`
- Modify: `src/tests/cpu.py:249-275`

- [ ] **Step 1: Add `on_progress` attribute to `BaseTest.__init__`**

  Open `src/tests/base.py`. In `__init__` (after `self.mode = mode` at line 24), add:

  ```python
          self.on_progress = None  # Callable[[dict], None] | None
  ```

- [ ] **Step 2: Declare `temp_samples` and `_stress_start` alongside `peak_temp`**

  Open `src/tests/cpu.py`. At line 249 (where `peak_temp: list[float] = []` is declared before `monitor_temps`), add two more declarations:

  ```python
          peak_temp: list[float] = []
          temp_samples: list[dict] = []
          _stress_start = time.monotonic()
  ```

- [ ] **Step 3: Update `monitor_temps` to record samples and fire the callback**

  Replace the `monitor_temps` coroutine body (lines 251-256):

  ```python
          async def monitor_temps(stop_event: asyncio.Event) -> None:
              while not stop_event.is_set():
                  temps = await loop.run_in_executor(None, _get_cpu_temps)
                  if temps:
                      current = max(temps)
                      peak_temp.append(current)
                      elapsed = round(time.monotonic() - _stress_start, 1)
                      temp_samples.append({"t": elapsed, "c": round(current, 1)})
                      if self.on_progress:
                          self.on_progress({"temp_c": round(current, 1), "time_s": elapsed})
                  await asyncio.sleep(2)
  ```

- [ ] **Step 4: Store `temp_samples` in result data**

  After line 275 (`data["temp_peak"] = round(max(peak_temp), 1) if peak_temp else None`), add:

  ```python
          if temp_samples:
              data["temp_samples"] = temp_samples
  ```

- [ ] **Step 5: Verify data collection works**

  ```bash
  cd "/Users/robertsaunders/Code/Automated PC Testing/pc-tester"
  python -c "
  import asyncio, platform
  from src.models.test_result import TestResult
  from src.models.job import TestMode
  from src.tests.cpu import CpuTest

  async def main():
      r = TestResult('cpu', 'CPU Stress')
      t = CpuTest(result=r, mode=TestMode.QUICK)
      samples = []
      t.on_progress = lambda d: samples.append(d)
      await t.run()
      print('temp_samples in data:', len(r.data.get('temp_samples', [])))
      print('on_progress callbacks:', len(samples))
      print('first sample:', samples[0] if samples else 'none')
  asyncio.run(main())
  "
  ```
  Expected: `temp_samples in data: N` (N > 0), `on_progress callbacks: N`, `first sample: {'temp_c': ..., 'time_s': ...}`

- [ ] **Step 6: Commit**

  ```bash
  git add src/tests/base.py src/tests/cpu.py
  git commit -m "feat: collect CPU temp_samples time-series and fire on_progress callback"
  ```

---

### Task 2: TestWorker progress signal

**Files:**
- Modify: `src/ui/workers.py:20-68`

- [ ] **Step 1: Add `progress` signal to `TestWorker`**

  Open `src/ui/workers.py`. After `finished = Signal(str)` (line 23), add:

  ```python
      progress = Signal(str, object)  # (test_name, data_dict) — live progress updates
  ```

- [ ] **Step 2: Wire `on_progress` callback in `run()`**

  In `run()`, after `test = TestClass(result=self._result, mode=self._mode)` (line 53), add:

  ```python
          test.on_progress = lambda data: self.progress.emit(self._name, data)
  ```

  The `data` dict passed from the CPU test is always a fresh literal `{"temp_c": ..., "time_s": ...}`, so Qt's cross-thread queued signal delivery safely copies it to the main thread.

- [ ] **Step 3: Verify the app launches without errors**

  ```bash
  uv run touchstone --dev-manual
  ```
  App opens normally. Close it. No errors in terminal.

- [ ] **Step 4: Commit**

  ```bash
  git add src/ui/workers.py
  git commit -m "feat: add TestWorker.progress signal for live test data updates"
  ```

---

### Task 3: TempChartWidget

**Files:**
- Create: `src/ui/widgets/temp_chart_widget.py`

- [ ] **Step 1: Create the file**

  Create `src/ui/widgets/temp_chart_widget.py` with the full content below:

  ```python
  """TempChartWidget — compact sparkline or full area chart for CPU temperature."""

  from __future__ import annotations

  from PySide6.QtCore import Qt
  from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
  from PySide6.QtWidgets import QSizePolicy, QWidget

  from ..stylesheet import get_colors


  class TempChartWidget(QWidget):
      """Renders CPU temperature samples as an area chart.

      compact=True  — 80×22 px sparkline for the dashboard card main row.
      compact=False — 100 px tall full chart for the expandable detail panel.
      """

      def __init__(self, compact: bool = False, theme: str = "dark", parent=None) -> None:
          super().__init__(parent)
          self._compact = compact
          self._theme = theme
          self._samples: list[tuple[float, float]] = []  # (time_s, temp_c)
          self._warn: float | None = None
          self._fail: float | None = None
          self.setStyleSheet("background: transparent;")
          if compact:
              self.setFixedSize(80, 22)
          else:
              self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
              self.setFixedHeight(100)

      def push_sample(self, time_s: float, temp_c: float) -> None:
          """Append one sample and repaint."""
          self._samples.append((time_s, temp_c))
          self.update()

      def set_samples(self, samples: list[dict]) -> None:
          """Bulk-load samples from result.data['temp_samples']."""
          self._samples = [(s["t"], s["c"]) for s in samples]
          self.update()

      def set_thresholds(self, warn: float | None, fail: float | None) -> None:
          self._warn = warn
          self._fail = fail
          self.update()

      def apply_theme(self, theme: str) -> None:
          self._theme = theme
          self.update()

      def reset(self) -> None:
          """Clear all samples — call before a fresh test run."""
          self._samples.clear()
          self.update()

      def paintEvent(self, event) -> None:  # noqa: N802
          if len(self._samples) < 2:
              return

          painter = QPainter(self)
          painter.setRenderHint(QPainter.RenderHint.Antialiasing)

          w, h = self.width(), self.height()
          c = get_colors(self._theme)
          temps = [s[1] for s in self._samples]
          times = [s[0] for s in self._samples]

          # Y range
          y_max = (self._fail + 5) if self._fail else (max(temps) + 8)
          y_min = min(temps) - 5
          y_range = max(y_max - y_min, 1.0)

          # X range
          x_min, x_max = times[0], max(times[-1], 1.0)
          x_range = max(x_max - x_min, 1.0)

          # Padding
          if self._compact:
              pad_l, pad_r, pad_t, pad_b = 0, 0, 2, 2
          else:
              pad_l, pad_r, pad_t, pad_b = 32, 8, 14, 18

          cw = w - pad_l - pad_r
          ch = h - pad_t - pad_b

          def to_x(t: float) -> float:
              return pad_l + (t - x_min) / x_range * cw

          def to_y(temp: float) -> float:
              return pad_t + ch - (temp - y_min) / y_range * ch

          pts = [(to_x(t), to_y(temp)) for t, temp in self._samples]

          accent = QColor(c["accent"])

          # Threshold lines (full mode only)
          if not self._compact:
              if self._warn is not None:
                  wy = to_y(self._warn)
                  if pad_t <= wy <= pad_t + ch:
                      pen = QPen(QColor(c["warn_text"]))
                      pen.setStyle(Qt.PenStyle.DashLine)
                      pen.setWidthF(1.0)
                      painter.setPen(pen)
                      painter.drawLine(int(pad_l), int(wy), int(w - pad_r), int(wy))
              if self._fail is not None:
                  fy = to_y(self._fail)
                  if pad_t <= fy <= pad_t + ch:
                      pen = QPen(QColor(c["danger_text"]))
                      pen.setStyle(Qt.PenStyle.DashLine)
                      pen.setWidthF(1.0)
                      painter.setPen(pen)
                      painter.drawLine(int(pad_l), int(fy), int(w - pad_r), int(fy))

          # Area fill
          area = QPainterPath()
          bottom_y = float(pad_t + ch)
          area.moveTo(pts[0][0], bottom_y)
          area.lineTo(pts[0][0], pts[0][1])
          for x, y in pts[1:]:
              area.lineTo(x, y)
          area.lineTo(pts[-1][0], bottom_y)
          area.closeSubpath()
          fill = QColor(accent)
          fill.setAlphaF(0.15)
          painter.fillPath(area, fill)

          # Line
          line_pen = QPen(accent)
          line_pen.setWidthF(1.5 if self._compact else 2.0)
          line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
          line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
          painter.setPen(line_pen)
          path = QPainterPath()
          path.moveTo(pts[0][0], pts[0][1])
          for x, y in pts[1:]:
              path.lineTo(x, y)
          painter.drawPath(path)

          # Markers (full mode only)
          if not self._compact:
              # Idle dot — first sample, grey
              painter.setPen(Qt.PenStyle.NoPen)
              painter.setBrush(QColor(c["text_muted"]))
              x0, y0 = pts[0]
              painter.drawEllipse(int(x0) - 3, int(y0) - 3, 6, 6)

              # Peak dot — amber
              peak_i = temps.index(max(temps))
              xp, yp = pts[peak_i]
              painter.setBrush(QColor(c["warn_text"]))
              painter.drawEllipse(int(xp) - 4, int(yp) - 4, 8, 8)

          painter.end()
  ```

- [ ] **Step 2: Verify the file imports without errors**

  ```bash
  cd "/Users/robertsaunders/Code/Automated PC Testing/pc-tester"
  python -c "from src.ui.widgets.temp_chart_widget import TempChartWidget; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 3: Commit**

  ```bash
  git add src/ui/widgets/temp_chart_widget.py
  git commit -m "feat: add TempChartWidget — compact sparkline and full area chart modes"
  ```

---

### Task 4: DashboardCard — sparkline + chart panel

**Files:**
- Modify: `src/ui/widgets/dashboard_card.py:1-233`

Read the full file before editing. Key reference points:
- Line 1-17: imports
- Line 43-58: `__init__` — `self._expanded = False` is at line 48
- Line 60-124: `_build_ui()` — main row layout built at lines 72-116; `_detail_lbl` added at line 93; `_expand_arrow` at line 96; `_detail_panel` added at line 121-124
- Line 128-178: `set_status()` — running branch sets `_stop_mode=True`, else branch sets `_stop_mode=False`
- Line 169-195: `apply_theme()`
- Line 197-206: `_set_sub_detail()`
- Line 208-220: `_on_row_clicked()`

- [ ] **Step 1: Add import for `TempChartWidget`**

  At the top of `dashboard_card.py`, after the existing local import `from ..stylesheet import get_colors, refresh_style`, add:

  ```python
  from .temp_chart_widget import TempChartWidget
  ```

- [ ] **Step 2: Add `_has_chart_data` in `__init__`**

  In `__init__`, after `self._expanded = False` (line 48), add:

  ```python
          self._has_chart_data: bool = False
  ```

- [ ] **Step 3: Add `_sparkline` to the main row in `_build_ui()`**

  In `_build_ui()`, find where `_expand_arrow` is added to the row (around line 96-99):
  ```python
          self._expand_arrow = QLabel("▾")
          self._expand_arrow.setFixedWidth(18)
          self._expand_arrow.hide()
          row.addWidget(self._expand_arrow, 0, vc)
  ```

  Insert the sparkline widget **before** `_expand_arrow`:
  ```python
          # Compact sparkline — shown while temp samples are arriving
          self._sparkline = TempChartWidget(compact=True, theme="dark")
          self._sparkline.hide()
          row.addWidget(self._sparkline, 0, vc)

          self._expand_arrow = QLabel("▾")
          self._expand_arrow.setFixedWidth(18)
          self._expand_arrow.hide()
          row.addWidget(self._expand_arrow, 0, vc)
  ```

- [ ] **Step 4: Add `_chart_panel` to outer layout in `_build_ui()`**

  After the line `outer.addWidget(self._detail_panel)` (line 124), add:

  ```python
          # Full area chart panel — shown in expandable area after test completes
          self._chart_panel = TempChartWidget(compact=False, theme="dark")
          self._chart_panel.hide()
          outer.addWidget(self._chart_panel)
  ```

- [ ] **Step 5: Add `push_temp_sample()` public method**

  Add after `set_advanced()` (around line 158):

  ```python
      def push_temp_sample(self, time_s: float, temp_c: float) -> None:
          """Called while test is running. Grows the sparkline and updates the detail label."""
          # Guard against late-arriving queued signals after test completes.
          # _stop_mode is True only while the test is running.
          if not self._stop_mode:
              return
          self._sparkline.push_sample(time_s, temp_c)
          if not self._sparkline.isVisible():
              self._sparkline.show()
              # Stop the plain elapsed ticker — sparkline label takes over
              self._ticker.stop()
          self._detail_lbl.setText(f"{int(time_s)}s · {int(temp_c)}°C")
  ```

- [ ] **Step 6: Add `set_chart_data()` public method**

  Add after `push_temp_sample()`:

  ```python
      def set_chart_data(
          self,
          samples: list[dict],
          warn: float | None = None,
          fail: float | None = None,
      ) -> None:
          """Load completed temp_samples into the full chart panel."""
          self._chart_panel.set_samples(samples)
          self._chart_panel.set_thresholds(warn, fail)
          self._has_chart_data = True
          self._expand_arrow.show()
          if self._expanded:
              self._chart_panel.show()
  ```

- [ ] **Step 7: Reset chart data when test re-starts in `set_status()`**

  In `set_status()`, find the `if status == "running":` branch (where `self._stop_mode = True` is set). Add these lines after `self._stop_mode = True`:

  ```python
              # Reset chart widgets for a fresh run (handles Re-run button)
              self._sparkline.reset()
              self._chart_panel.reset()
              self._has_chart_data = False
              self._expand_arrow.hide()
  ```

  This ensures that clicking Re-run clears old temperature data instead of accumulating new samples on top of the previous run's data.

- [ ] **Step 8: Hide sparkline when test exits running state**

  In `set_status()`, in the `else` branch (when status is not `"running"`), after `self._stop_mode = False`, add:

  ```python
              self._sparkline.hide()
  ```

- [ ] **Step 9: Update `_set_sub_detail()` to respect `_has_chart_data`**

  The current `_set_sub_detail()` collapses the panel when text is empty. Change the collapse guard:

  ```python
      def _set_sub_detail(self, text: str) -> None:
          self._sub_detail_text = text.strip()
          has = bool(self._sub_detail_text)
          # Show expand arrow if either sub-detail text OR chart data is present
          self._expand_arrow.setVisible(has or self._has_chart_data)
          self._detail_panel.setText(self._sub_detail_text)
          if not has and self._expanded and not self._has_chart_data:
              self._expanded = False
              self._detail_panel.hide()
  ```

- [ ] **Step 10: Update `_on_row_clicked()` to expand/collapse chart panel**

  Replace `_on_row_clicked()`:

  ```python
      def _on_row_clicked(self, event) -> None:
          if not self._sub_detail_text and not self._has_chart_data:
              return
          self._expanded = not self._expanded
          self._expand_arrow.setText("▴" if self._expanded else "▾")
          if self._expanded:
              if self._sub_detail_text:
                  self._detail_panel.show()
              if self._has_chart_data:
                  self._chart_panel.show()
          else:
              self._detail_panel.hide()
              self._chart_panel.hide()
          self.adjustSize()
          if self.parent():
              self.parent().adjustSize()  # type: ignore[union-attr]
  ```

- [ ] **Step 11: Propagate theme to chart widgets in `apply_theme()`**

  In `apply_theme()`, add at the end (before or after the `_detail_panel.setStyleSheet` call):

  ```python
          self._sparkline.apply_theme(theme)
          self._chart_panel.apply_theme(theme)
  ```

- [ ] **Step 12: Verify the app launches and card layout looks correct**

  ```bash
  uv run touchstone --dev-manual
  ```
  Cards should look identical to before (sparkline and chart panel are hidden). No layout shift.

- [ ] **Step 13: Commit**

  ```bash
  git add src/ui/widgets/dashboard_card.py
  git commit -m "feat: DashboardCard — live sparkline and expandable temp chart panel"
  ```

---

### Task 5: TestDashboardPage — wire progress signal and set_chart_data

**Files:**
- Modify: `src/ui/pages/test_dashboard_page.py:409-471`

Read `_make_worker()` (line 409), `_get_card()` (line 423), and `_apply_result()` (line 460) before editing.

- [ ] **Step 1: Connect `progress` signal in `_make_worker()`**

  In `_make_worker()` (line 409), after `worker.finished.connect(on_done)` (line 420), add:

  ```python
          worker.progress.connect(self._on_test_progress)
  ```

- [ ] **Step 2: Add `_on_test_progress()` handler**

  Add this method in the `# ── Worker helpers` section, after `_make_worker()`:

  ```python
      def _on_test_progress(self, name: str, data: dict) -> None:
          """Route live progress data from a running test to its dashboard card."""
          temp_c = data.get("temp_c")
          time_s = data.get("time_s")
          if temp_c is None or time_s is None:
              return
          card = self._get_card(name)
          if card:
              card.push_temp_sample(time_s, temp_c)
  ```

- [ ] **Step 3: Call `set_chart_data` in `_apply_result()` for CPU test**

  In `_apply_result()` (line 460), after the `section.update_card(result)` / `break` block (lines 464-467), and reusing the already-declared `result` variable, add:

  ```python
          # Load temperature chart data into the card (CPU test only)
          if result and result.name == "cpu":
              samples = (result.data or {}).get("temp_samples")
              if samples:
                  card = self._get_card(name)
                  if card:
                      card.set_chart_data(
                          samples,
                          warn=(result.data or {}).get("temp_thresh_load_warn"),
                          fail=(result.data or {}).get("temp_thresh_fail"),
                      )
  ```

  Insert this block **outside** the `for` loop — after the entire `for section in self._category_sections:` loop ends (after the `break` at line 467 exits the loop), and before the next statement `if result not in self._window.test_results:` (line 468). The `break` is inside the loop body; this new code goes after the loop, at the same indentation level as the `for` statement.

- [ ] **Step 4: Verify live sparkline during CPU Stress**

  ```bash
  uv run touchstone --dev-manual
  ```
  Click **▶ Run All**. Within the first few seconds of the CPU Stress test card: the detail area should show a small growing line (sparkline) alongside the elapsed time and current temperature (e.g., `4s · 58°C`). After the test completes, click the CPU Stress card row — the expandable panel should show a full area chart with threshold lines and peak marker.

- [ ] **Step 5: Commit**

  ```bash
  git add src/ui/pages/test_dashboard_page.py
  git commit -m "feat: wire TestWorker.progress to dashboard card sparkline; load chart data on result"
  ```

---

### Task 6: HTML report — inline SVG chart

**Files:**
- Modify: `src/report/html_render.py:1-49`
- Modify: `src/report/templates/report.html.j2:211-234`

- [ ] **Step 1: Add `_cpu_temp_svg()` helper to `html_render.py`**

  Add after `_report_to_json()` (line 42) and before `render_html()` (line 45):

  ```python
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

      y_max = (temp_fail + 5) if temp_fail else (max(temps) + 8)
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
      if temp_warn:
          wy = ty(temp_warn)
          parts.append(
              f'<line x1="{pad_l}" y1="{wy:.1f}" x2="{width - pad_r}" y2="{wy:.1f}"'
              f' stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,4" stroke-opacity="0.7"/>'
          )
          parts.append(
              f'<text x="{width - 90}" y="{wy - 3:.1f}" fill="#f59e0b"'
              f' font-size="8" fill-opacity="0.8">warn {temp_warn:.0f}°C</text>'
          )
      if temp_fail:
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
  ```

- [ ] **Step 2: Update `render_html()` to build and pass `temp_svgs`**

  Replace the `render_html()` function (lines 45-49):

  ```python
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
  ```

- [ ] **Step 3: Add chart block to `report.html.j2` before the CPU table**

  Open `src/report/templates/report.html.j2`. Find line 211-212:
  ```
          {% if result.name == 'cpu' %}
            <table class="data-table">
  ```

  Replace with:
  ```
          {% if result.name == 'cpu' %}
            {% if temp_svgs.get('cpu') %}
            <div style="margin-bottom:12px;">
              <div style="font-size:10px;font-weight:600;color:#888;letter-spacing:0.07em;text-transform:uppercase;margin-bottom:6px;">Temperature Over Stress Duration</div>
              {{ temp_svgs['cpu'] | safe }}
            </div>
            {% endif %}
            <table class="data-table">
  ```

- [ ] **Step 4: Verify the HTML report includes the chart**

  ```bash
  uv run touchstone --dev-manual
  ```
  Run all tests. Then click **Generate Report**. Open the HTML file. The CPU Stress section should show the temperature area chart above the data table. If temp collection isn't available on this machine, the chart block is simply absent (the guard `temp_svgs.get('cpu')` handles it).

- [ ] **Step 5: Commit**

  ```bash
  git add src/report/html_render.py src/report/templates/report.html.j2
  git commit -m "feat: add CPU temperature SVG chart to HTML report"
  ```

---

### Task 7: PDF report — ReportLab temperature chart

**Files:**
- Modify: `src/report/pdf_render.py:1-545`

Read `_test_result_block()` (lines 474-545) and the imports (lines 13-26) before editing.

- [ ] **Step 1: Add ReportLab graphics imports**

  At the top of `pdf_render.py`, after the existing `from reportlab.platypus import (...)` block (line 26), add:

  ```python
  from reportlab.graphics.shapes import (
      Circle,
      Drawing,
      Line,
      PolyLine,
      Polygon,
      String,
  )
  ```

  **Note:** `HexColor` is already imported at line 14 (`from reportlab.lib.colors import HexColor, black, white`) — do not re-import it. The `_cpu_temp_drawing()` function uses it via the existing import.

- [ ] **Step 2: Add `_cpu_temp_drawing()` helper function**

  Add after `_rows_generic()` (around line 373) and before `_ROW_EXTRACTORS` (line 376):

  ```python
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

      y_max = (temp_fail + 5) if temp_fail else (max(temps) + 8)
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

      # Idle dot
      x0, y0 = pts[0]
      c0 = Circle(x0, y0, 2.5)
      c0.fillColor = HexColor("#888888")
      c0.strokeColor = None
      d.add(c0)

      # Peak dot + label
      peak_i = temps.index(max(temps))
      xp, yp = pts[peak_i]
      cp = Circle(xp, yp, 3.5)
      cp.fillColor = HexColor("#f59e0b")
      cp.strokeColor = None
      d.add(cp)
      peak_lbl = String(xp + 5, yp + 2, f"{max(temps):.0f}\u00b0C peak")
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
  ```

- [ ] **Step 3: Insert drawing before CPU data table in `_test_result_block()`**

  In `_test_result_block()` (line 474), find the closing `return` statement (line 545):
  ```python
      return [KeepTogether(items), Spacer(1, 3 * mm)]
  ```

  Replace it with:
  ```python
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
  ```

- [ ] **Step 4: Verify the PDF report includes the chart**

  ```bash
  uv run touchstone --dev-manual
  ```
  Run all tests. Generate a report. Open the PDF. The CPU Stress section should show the temperature chart above the data table. If temp samples aren't available, the chart is absent and the PDF is unchanged.

- [ ] **Step 5: Commit**

  ```bash
  git add src/report/pdf_render.py
  git commit -m "feat: add CPU temperature chart to PDF report via ReportLab Drawing"
  ```

---

## Acceptance Checklist

- [ ] During CPU Stress (Run All): sparkline grows in the card detail area; label shows `Xs · Y°C`
- [ ] After CPU Stress completes: clicking the card row reveals a full area chart with idle dot, peak marker, and threshold lines
- [ ] HTML report: CPU section shows temperature chart above the data table
- [ ] PDF report: CPU section shows temperature chart above the data table
- [ ] When temperature data is unavailable (no mactop / no root): chart is absent from dashboard, HTML, and PDF — no errors
- [ ] Other test cards are unaffected (no sparkline, no chart panel)
- [ ] Theme switch (dark ↔ light) updates chart colours correctly
- [ ] Re-running a CPU test (Re-run button): sparkline resets and grows fresh; chart updates on completion

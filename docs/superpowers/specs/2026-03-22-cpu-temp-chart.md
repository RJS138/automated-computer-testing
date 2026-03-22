# CPU Temperature Chart — Design Spec

**Date:** 2026-03-22
**Goal:** During the CPU stress test, collect temperature samples over time. Show a live sparkline on the dashboard card while running, a full expandable area chart after the test completes, and an inline SVG area chart in both the HTML and PDF reports.

---

## Scope

- CPU test only. GPU temperature charting is a future feature that follows the same pattern.
- No new external dependencies (chart uses QPainter in Qt, inline SVG in HTML, ReportLab Drawing in PDF).

---

## Data Model

**`result.data["temp_samples"]`** — new key added by the CPU test.

Format: `list[dict]` where each entry is `{"t": float, "c": float}`.
- `t` — elapsed seconds since stress phase start (0.0, 2.0, 4.0, …)
- `c` — temperature in °C (max across all cores at that moment)

Sampled every 2 seconds by the existing `monitor_temps` coroutine (same interval as before).
For 60s quick test: ~30 samples. For 180s extended test: ~90 samples.

**Existing keys unchanged:** `temp_idle`, `temp_peak`, `temp_thresh_load_warn`, `temp_thresh_fail`, and all other keys. No breaking changes to the data model.

If temperature collection is unavailable on a platform (returns `None`), `temp_samples` is not set (key absent). All consumers must guard with `.get("temp_samples")`.

---

## Layer 1: CPU Test (`src/tests/cpu.py`)

**Changes to `monitor_temps` coroutine:**

1. Declare `temp_samples: list[dict] = []` alongside the existing `peak_temp: list[float] = []`.
2. On each 2-second tick, after appending to `peak_temp`, also append `{"t": round(elapsed_s, 1), "c": round(max(temps), 1)}` to `temp_samples`.
3. Track `elapsed_s` from the moment the stress loop starts (use `time.monotonic()` — already likely imported via `asyncio` or add directly).
4. After the stress phase completes, set `data["temp_samples"] = temp_samples` (only if `temp_samples` is non-empty).
5. Also call the `on_progress` callback on each tick (see Layer 2): `if self.on_progress: self.on_progress({"temp_c": current_temp, "time_s": elapsed_s})`.

`on_progress` is called with the same sample that gets appended to `temp_samples` — no double-computation needed.

---

## Layer 2: Progress Signal (`src/tests/base.py`, `src/ui/workers.py`)

### `src/tests/base.py`

Add one attribute to `BaseTest.__init__`:
```python
self.on_progress: "Callable[[dict], None] | None" = None
```

No changes to `safe_run()`. The CPU test accesses `self.on_progress` directly; the base class just declares it so type checkers don't complain.

### `src/ui/workers.py`

Add to `TestWorker`:
```python
progress = Signal(str, object)  # (test_name, data_dict)
```

In `run()`, after creating `test = TestClass(...)` and before calling `self._loop.run_until_complete(_run())`, set:
```python
test.on_progress = lambda data: self.progress.emit(self._name, data)
```

Qt's cross-thread signal delivery handles thread safety — no `call_soon_threadsafe` needed for the signal emit itself. The lambda captures `self._name` at setup time.

---

## Layer 3: Dashboard Card

### New file: `src/ui/widgets/temp_chart_widget.py`

A single `TempChartWidget(QWidget)` class that renders in two modes based on the `compact: bool` constructor parameter.

**Constructor:**
```python
TempChartWidget(compact: bool = False, theme: str = "dark", parent=None)
```

**Public API:**
- `push_sample(time_s: float, temp_c: float)` — appends sample, calls `update()` to trigger repaint
- `set_samples(samples: list[dict])` — bulk-load (used when setting chart after test completes)
- `set_thresholds(warn: float | None, fail: float | None)` — sets reference lines
- `apply_theme(theme: str)` — re-applies colours

**Compact mode** (`compact=True`):
- Fixed size: 80×22 px
- Renders only the blue line, no axes, no labels, no threshold lines
- Auto-scales Y to the sample range
- Used in the `_main_row` of `DashboardCard` while running

**Full mode** (`compact=False`):
- Height: ~100 px, expands to available width
- Renders: area fill under the line, Y-axis labels (4 ticks), X-axis time labels, dashed threshold lines (warn=amber, fail=red), idle marker (grey dot at first sample), peak marker (amber dot at max sample with "XX°C peak" label)
- Used in the expandable panel of `DashboardCard` after test completes

**`paintEvent` implementation:**
- Compute `y_min = min(samples.c) - 5`, `y_max = max(samples.c) + 5` (or fixed to include thresholds if provided)
- Map `(time_s, temp_c)` → pixel coordinates
- Draw area polygon first (filled with accent blue at low opacity), then polyline on top, then markers
- Use `get_colors(theme)` for colour tokens: `accent` for line, `text_muted` for axes, `warn_text` for warn line, `fail_text`/`danger_text` for fail line

### Changes to `src/ui/widgets/dashboard_card.py`

**New instance variables (in `__init__`):**
```python
self._sparkline: TempChartWidget  # compact mode, in main row
self._chart_panel: TempChartWidget  # full mode, in expandable area
self._has_chart_data: bool = False
```

**`_build_ui()` changes:**
- Add `self._sparkline = TempChartWidget(compact=True, theme=theme)` to the main row `QHBoxLayout`, inserted between `_detail_lbl` and `_expand_arrow`. Initially hidden.
- Add `self._chart_panel = TempChartWidget(compact=False, theme=theme)` to the outer `QVBoxLayout`, below `_detail_panel`. Initially hidden.

**New public methods:**
```python
def push_temp_sample(self, time_s: float, temp_c: float) -> None:
    """Called while test is running. Shows sparkline, updates current temp text."""
    self._sparkline.push_sample(time_s, temp_c)
    if not self._sparkline.isVisible():
        self._sparkline.show()
    # Update detail label to show current temp instead of plain elapsed
    self._detail_lbl.setText(f"{int(time_s)}s · {int(temp_c)}°C")

def set_chart_data(
    self,
    samples: list[dict],
    warn: float | None = None,
    fail: float | None = None,
) -> None:
    """Called after test completes with temp_samples from result.data."""
    self._chart_panel.set_samples(samples)
    self._chart_panel.set_thresholds(warn, fail)
    self._has_chart_data = True
    self._expand_arrow.show()
    if self._expanded:
        self._chart_panel.show()
```

**`set_status()` changes:**
- When status transitions away from `"running"`: hide `_sparkline`, restore `_detail_lbl` to normal (idle→peak text or detail string as set by caller).
- No other changes to the existing stop/run button logic.

**`_on_row_clicked()` changes:**
- Expand/collapse `_chart_panel` alongside `_detail_panel`. Show the expand arrow if `self._has_chart_data` (even if `_sub_detail_text` is empty).

**`apply_theme()` changes:**
- Call `self._sparkline.apply_theme(theme)` and `self._chart_panel.apply_theme(theme)`.

---

## Layer 4: Dashboard Page (`src/ui/pages/test_dashboard_page.py`)

### Connect progress signal

In the same place where workers are created and `finished` is connected, also connect:
```python
worker.progress.connect(self._on_test_progress)
```

Add handler:
```python
def _on_test_progress(self, name: str, data: dict) -> None:
    """Route live progress data to the appropriate card."""
    temp_c = data.get("temp_c")
    time_s = data.get("time_s")
    if temp_c is None or time_s is None:
        return
    card = self._find_card(name)
    if card:
        card.push_temp_sample(time_s, temp_c)
```

`_find_card(name)` iterates `self._category_sections` to find the card (same pattern as existing card lookups).

### Call set_chart_data after test completes

In `_apply_result(name)`, after updating the card status (the existing `section.update_card(result)` call), add:
```python
result = self._results.get(name)
if result and result.name == "cpu":
    samples = (result.data or {}).get("temp_samples")
    if samples:
        card = self._find_card(name)
        if card:
            card.set_chart_data(
                samples,
                warn=(result.data or {}).get("temp_thresh_load_warn"),
                fail=(result.data or {}).get("temp_thresh_fail"),
            )
```

---

## Layer 5: HTML Report (`src/report/html_render.py`, `src/report/templates/report.html.j2`)

### `src/report/html_render.py`

Add a private helper function:
```python
def _cpu_temp_svg(
    samples: list[dict],
    temp_warn: float | None,
    temp_fail: float | None,
    width: int = 560,
    height: int = 110,
) -> str:
```

This function:
1. Normalises the sample data to pixel coordinates (fixed canvas, Y-axis from `min(c)-5` to `max(c)+5`, or to `temp_fail+5` if thresholds are present)
2. Builds an SVG string with: gradient definition, grid lines, dashed threshold lines (if warn/fail provided), area polygon, polyline, idle/peak marker dots and labels, X/Y axis labels
3. Returns the full `<svg>...</svg>` string

In `render_html()`, build a `temp_svgs: dict[str, str]` by iterating results:
```python
temp_svgs = {}
for r in report.results:
    if r.name == "cpu" and r.data and r.data.get("temp_samples"):
        temp_svgs["cpu"] = _cpu_temp_svg(
            r.data["temp_samples"],
            r.data.get("temp_thresh_load_warn"),
            r.data.get("temp_thresh_fail"),
        )
```

Pass `temp_svgs=temp_svgs` to `template.render(...)`.

### `src/report/templates/report.html.j2`

In the `{% if result.name == 'cpu' %}` block, before the existing `<table class="data-table">`, add:
```html
{% if temp_svgs.get('cpu') %}
<div class="chart-block">
  <div class="chart-label">Temperature Over Stress Duration</div>
  {{ temp_svgs['cpu'] | safe }}
</div>
{% endif %}
```

Add `.chart-block` and `.chart-label` styles to the template's `<style>` block (minimal — just spacing and the uppercase label style consistent with the rest of the report).

---

## Layer 6: PDF Report (`src/report/pdf_render.py`)

Add a private helper function:
```python
def _cpu_temp_drawing(
    samples: list[dict],
    temp_warn: float | None,
    temp_fail: float | None,
    width: float = 460,
    height: float = 90,
) -> Drawing:
```

This function mirrors the SVG logic but uses ReportLab's `Drawing`, `PolyLine`, `Circle`, `String`, and `Line` shapes from `reportlab.graphics.shapes`. Returns a `Drawing` object.

In `_test_result_block()` (or equivalent function that builds the flowable list for each test), after detecting `name == "cpu"` and finding `data.get("temp_samples")`, insert the drawing as a flowable using `shapes.Drawing` → wrap in a `Flowable` via `reportlab.graphics.renderPDF` (standard ReportLab pattern for inline drawings).

The drawing is inserted **before** the data table.

---

## File Summary

| File | Change |
|------|--------|
| `src/tests/cpu.py` | Collect `temp_samples`, call `on_progress` callback |
| `src/tests/base.py` | Add `on_progress: Callable | None = None` attribute |
| `src/ui/workers.py` | Add `progress = Signal(str, object)`, wire `on_progress` callback |
| `src/ui/widgets/temp_chart_widget.py` | **New** — `TempChartWidget` with compact/full modes |
| `src/ui/widgets/dashboard_card.py` | Add sparkline + chart panel, `push_temp_sample()`, `set_chart_data()` |
| `src/ui/pages/test_dashboard_page.py` | Connect `progress` signal, call `set_chart_data` in `_apply_result` |
| `src/report/html_render.py` | Add `_cpu_temp_svg()` helper, pass `temp_svgs` to template |
| `src/report/templates/report.html.j2` | Insert chart SVG before CPU data table |
| `src/report/pdf_render.py` | Add `_cpu_temp_drawing()` helper, insert before CPU data table |

---

## Out of Scope

- GPU temperature chart (same pattern, separate feature)
- Interactive hover tooltips in HTML (static SVG only)
- Charting any other test's data
- Changing the 2-second sample interval

---

## Manual Verification

```bash
uv run touchstone --dev-manual
```

1. Click **▶ Run All** — during CPU Stress, the card's detail area shows a growing sparkline with current temp
2. After CPU Stress completes, click the card row — expandable panel shows the full area chart
3. Generate a report — HTML report shows the temperature chart above the CPU data table
4. Open the PDF — same chart rendered via ReportLab

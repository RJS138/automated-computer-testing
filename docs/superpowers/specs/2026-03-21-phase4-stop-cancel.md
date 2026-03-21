# Phase 4 — Stop / Cancel Running Tests

## 1. Goal

Allow technicians to stop a running test suite (global) or a single running test (per-card) at any time. Interrupted tests show a distinct CANCEL status. Tests that were queued but never started are also marked CANCEL immediately.

---

## 2. Scope

**In scope:**
- Global stop: Run All button becomes ◼ Stop while the suite is running
- Per-card stop: each card's Run button becomes ◼ Stop while that card's test is running
- New `CANCEL` terminal status (orange) in `TestStatus` and `TestResult`
- asyncio Task cancellation mechanism in `TestWorker`

**Out of scope:**
- Stopping `system_info` (runs independently at page entry, short-lived)
- Stopping `ReportWorker`
- Partial result saving after cancel
- Report diff / before-after comparison (backend already complete — opens automatically)

---

## 3. Status: CANCEL

### 3.1 `TestStatus` enum (`src/models/test_result.py`)

Add `CANCEL = "cancel"` to `TestStatus`. CANCEL is a terminal state — it is NOT in the `incomplete` set `{WAITING, RUNNING}`, so `_recalculate_overall()` and `all_done` checks work without modification.

### 3.2 `TestResult.mark_cancel()`

```python
def mark_cancel(self) -> None:
    self.status = TestStatus.CANCEL
    self.summary = "Cancelled"
    self.completed_at = datetime.now()
```

`completed_at` is set for consistency with all other terminal `mark_*()` methods.

### 3.3 Colour tokens

**`src/ui/stylesheet.py`** — add `cancel_text` and `cancel_bg` to both `DARK` and `LIGHT` dicts in `get_colors()`:

| Token | Dark | Light |
|-------|------|-------|
| `cancel_text` | `#fb923c` | `#ea580c` |
| `cancel_bg` | `#1c1107` | `#ffedd5` |

Also add the card border rule to `QSS_DARK` and `QSS_LIGHT` alongside the existing pass/warn/fail/error/skip rules, using the `cancel_bg` hex directly.

**`src/ui/widgets/dashboard_card.py`** — `_STATUS_COLORS` is a module-level dict of hardcoded dark-mode hex values for the status label text colour. Add the cancel entry the same way:

```python
_STATUS_COLORS: dict[str, str] = {
    ...
    "cancel": "#fb923c",   # orange — dark mode
}
```

Add a parallel `_STATUS_COLORS_LIGHT` dict (matching the pattern used in `device_banner.py` for `_OVERALL_STYLES_LIGHT`) for light-mode overrides:

```python
_STATUS_COLORS_LIGHT: dict[str, str] = {
    "cancel": "#ea580c",
}
```

In `set_status()`, when applying the status label colour, use the light override when available:

```python
colors = _STATUS_COLORS_LIGHT if self._theme == "light" else _STATUS_COLORS
color = colors.get(status) or _STATUS_COLORS.get(status, "#52525b")
```

The card border still uses `setProperty("status", "cancel")` + `refresh_style()` for the border highlight, matching the existing pass/warn/fail/error/skip border rule pattern.

---

## 4. Cancellation Mechanism

### 4.1 `BaseTest.safe_run()` (`src/tests/base.py`)

Add `CancelledError` handling:

```python
async def safe_run(self) -> TestResult:
    try:
        return await self.run()
    except asyncio.CancelledError:
        self.result.mark_cancel()
        return self.result
    except Exception as exc:
        self.result.mark_error(f"Unexpected error: {exc}")
        return self.result
```

### 4.2 CPU test `finally` block (`src/tests/cpu.py`)

The CPU test creates an inner `monitor_task`. When `CancelledError` propagates during cancellation, the existing `finally` block does `stop_event.set(); await monitor_task`. An `await` inside a cancelled coroutine re-raises `CancelledError`, leaving `monitor_task` orphaned.

**Fix the `finally` block in `cpu.py`:**
```python
finally:
    stop_event.set()
    monitor_task.cancel()
    await asyncio.gather(monitor_task, return_exceptions=True)
```

This cleanly cancels the monitor task and suppresses its `CancelledError` via `return_exceptions=True`.

### 4.3 `TestWorker` (`src/ui/workers.py`)

Use an inner `async def _run()` shim so `self._task` is set to the running task (via `asyncio.current_task()`) while the loop is already executing — avoiding `create_task` on a stopped loop:

```python
class TestWorker(QThread):
    finished = Signal(str)

    def __init__(self, name, module, cls_name, result, mode, parent=None):
        super().__init__(parent)
        self._name = name
        self._module = module
        self._cls_name = cls_name
        self._result = result
        self._mode = mode
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None

    def run(self) -> None:
        import asyncio, importlib
        mod = importlib.import_module(f"src.tests.{self._module}")
        TestClass = getattr(mod, self._cls_name)
        test = TestClass(result=self._result, mode=self._mode)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _run():
            self._task = asyncio.current_task()
            return await test.safe_run()

        try:
            self._loop.run_until_complete(_run())
        except Exception as exc:
            self._result.mark_error(str(exc))
        finally:
            self._loop.close()
        self.finished.emit(self._name)

    def cancel(self) -> None:
        """Cancel the running async task. Thread-safe."""
        if self._loop and self._task and not self._task.done():
            self._loop.call_soon_threadsafe(self._task.cancel)

    @property
    def name(self) -> str:
        return self._name
```

**Behaviour:** `cancel()` raises `CancelledError` at the next `await` in `safe_run()`. For `run_in_executor` calls the executor finishes its current blocking call then cancels. For `asyncio.sleep()` calls (CPU test) cancellation is immediate. `finished` always fires — the queue advances as usual.

---

## 5. UI Changes

### 5.1 `DashboardCard` (`src/ui/widgets/dashboard_card.py`)

**New signal:**
```python
stop_requested = Signal(str)  # carries test name
```

**Button mode tracking:** Add `self._stop_mode: bool = False`.

**`set_status()` changes:**
- `status == "running"`: set `_stop_mode = True`, button text → `"◼ Stop"`, style with `danger_bg`/`danger_text` colours
- any other status: set `_stop_mode = False`, button text → `"Run"` (waiting) or `"Re-run"` (other terminal states), restore normal button style

**`_on_run_clicked()` changes:**
```python
def _on_run_clicked(self) -> None:
    if self._stop_mode:
        self.stop_requested.emit(self._name)
    else:
        self.run_requested.emit(self._name)
```

**`apply_theme()`:** Re-applies button style respecting current `_stop_mode`.

**`set_status()` for CANCEL:** Display `"CANCEL"` label in `cancel_text` colour; detail label shows `"cancelled"` in muted colour. Use the inline `_STATUS_COLORS` dict approach (matching pass/warn/fail pattern).

### 5.2 `CategorySection` (`src/ui/widgets/category_section.py`)

**New signal forwarded:** `stop_requested = Signal(str)` — forward from each card's `stop_requested` up to `TestDashboardPage`. Matches existing `run_requested` forwarding pattern.

### 5.3 `HeaderBar` (`src/ui/widgets/header_bar.py`)

**New signal:**
```python
stop_all_clicked = Signal()
```

**New method: `set_running_all(active: bool)`**
- `True`: Run All button text → `"◼ Stop"`, styled with danger colours, disconnects `run_all_clicked`, connects `stop_all_clicked`
- `False`: Run All button text → `"▶ Run All"`, restores normal primary style, disconnects `stop_all_clicked`, connects `run_all_clicked`

`apply_theme()` respects the current running state when re-styling the Run All button.

### 5.4 `TestDashboardPage` (`src/ui/pages/test_dashboard_page.py`)

**New connections:**
```python
self._header.stop_all_clicked.connect(self._on_stop_all)
# per-section (when building sections):
section.stop_requested.connect(self._on_stop_card)
```

**`_on_run_all()` update:** After setting `_running_all = True`, call `self._header.set_running_all(True)`.

**New handler: `_on_stop_all()`**
```python
def _on_stop_all(self) -> None:
    # 0. Clear running_all FIRST so _recalculate_overall() (called inside
    #    _apply_result() below) doesn't find `all_done and _running_all`
    #    and bypass the header reset in step 4.
    self._running_all = False

    # 1. Mark all actively-running tests as CANCEL immediately so cards
    #    exit stop-mode before set_running_all(False) re-enables buttons.
    #    Cancel the workers and clear the list — the early-return guards on
    #    finished callbacks mean _apply_result() won't be called from those
    #    callbacks, so the list must be pruned here instead.
    for w in list(self._active_workers):
        result = self._results.get(w.name)
        if result and result.status == TestStatus.RUNNING:
            result.mark_cancel()
            self._apply_result(w.name)
        w.cancel()
    self._active_workers.clear()

    # 2. Mark all queued (WAITING) results as CANCEL immediately.
    for entry in self._sequential_queue:
        result = self._results.get(entry["name"])
        if result and result.status == TestStatus.WAITING:
            result.mark_cancel()
            self._apply_result(entry["name"])
    self._sequential_queue.clear()

    # 3. Reset parallel counters so any stale callbacks that slip through
    #    don't call _next_sequential() / _run_manual_queue().
    self._parallel_done_count = 0
    self._parallel_total = 0

    # 4. Reset UI state — header button back to "▶ Run All", re-enable cards.
    self._header.set_running_all(False)
    for section in self._category_sections:
        for card in section._cards.values():
            card.set_running_all(False)

    # 5. Do NOT call _on_automated_done / _run_manual_queue.
```

**Guards in `_on_parallel_test_done()` and `_on_sequential_test_done()`:** Both need an early return if `_running_all` is False, so stale finished callbacks from cancelled workers don't advance the queue or trigger `_run_manual_queue()`:

```python
def _on_parallel_test_done(self, name: str) -> None:
    if not self._running_all:
        return
    self._apply_result(name)
    self._parallel_done_count += 1
    if self._parallel_done_count >= self._parallel_total:
        self._next_sequential()

def _on_sequential_test_done(self, name: str) -> None:
    if not self._running_all:
        return
    self._apply_result(name)
    self._next_sequential()
```

**New handler: `_on_stop_card(name: str)`**
```python
def _on_stop_card(self, name: str) -> None:
    for w in self._active_workers:
        if w.name == name:
            w.cancel()
            break
```

When a per-card cancel completes, the worker's `finished` signal fires normally — `_on_parallel_test_done` or `_on_sequential_test_done` runs, sees a CANCEL result, and advances the queue as usual. The Run All suite continues for other tests.

---

## 6. Files Changed

| File | Change |
|------|--------|
| `src/models/test_result.py` | Add `CANCEL` to `TestStatus`, add `mark_cancel()` with `completed_at` |
| `src/tests/base.py` | Catch `CancelledError` in `safe_run()` |
| `src/tests/cpu.py` | Fix `monitor_task` finally block to use `cancel()` + `gather(return_exceptions=True)` |
| `src/ui/workers.py` | `_run()` shim, store loop/task refs, add `cancel()` method, add `name` property |
| `src/ui/stylesheet.py` | Add `cancel_text`/`cancel_bg` tokens; add `QFrame[status="cancel"]` border rule |
| `src/ui/widgets/dashboard_card.py` | `stop_requested` signal, `_stop_mode` flag, button toggle, CANCEL inline colours |
| `src/ui/widgets/category_section.py` | Forward `stop_requested` signal |
| `src/ui/widgets/header_bar.py` | `stop_all_clicked` signal, `set_running_all()` method |
| `src/ui/pages/test_dashboard_page.py` | `_on_stop_all()`, `_on_stop_card()`, guard in `_on_parallel_test_done`, wire signals |

---

## 7. Acceptance Criteria

- [ ] Run All button becomes `"◼ Stop"` while suite is running; clicking cancels all active tests and marks all queued tests CANCEL
- [ ] Each card's Run button becomes `"◼ Stop"` while that card's test is running; clicking cancels only that test
- [ ] Cancelled tests show `CANCEL` in orange; queued tests that never ran also show `CANCEL`
- [ ] After Stop All, the manual test queue does NOT run
- [ ] After per-card stop during Run All, the suite continues normally for other tests
- [ ] Re-running a CANCEL card works (Re-run button appears, `run_requested` fires)
- [ ] `all_done` check treats CANCEL as terminal — dashboard reaches done state correctly after stop
- [ ] Both dark and light themes apply correct orange cancel colours
- [ ] `system_info` worker is unaffected by stop actions
- [ ] CPU test monitor task does not orphan after cancellation

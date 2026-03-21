# Phase 4 — Stop / Cancel Running Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let technicians stop a running test suite (global) or a single test (per-card) at any time; interrupted and queued tests show a new orange CANCEL status.

**Architecture:** Seven independent layers built bottom-up: data model → test cancellation → UI widgets → page wiring. `TestWorker` gains a `cancel()` method using an asyncio shim; `DashboardCard`'s Run button morphs into ◼ Stop while a test is running; `HeaderBar`'s Run All button does the same; `TestDashboardPage` ties it all together with `_on_stop_all()` and `_on_stop_card()` handlers.

**Tech Stack:** PySide6 (Signals, QThread), Python asyncio (task cancellation via `asyncio.current_task()`), existing `TestWorker`/`BaseTest` patterns.

---

## File Structure

| File | What changes |
|------|-------------|
| `src/models/test_result.py` | Add `CANCEL` status + `mark_cancel()` |
| `src/tests/base.py` | Catch `CancelledError` in `safe_run()` |
| `src/tests/cpu.py` | Fix `monitor_task` finally block |
| `src/ui/workers.py` | `_run()` shim, `_loop`/`_task` refs, `cancel()`, `name` property |
| `src/ui/stylesheet.py` | `cancel_text`/`cancel_bg` tokens in `DARK`/`LIGHT` |
| `src/ui/widgets/dashboard_card.py` | `stop_requested` signal, `_stop_mode` flag, button toggle, `_STATUS_COLORS_LIGHT` |
| `src/ui/widgets/header_bar.py` | `stop_all_clicked` signal, `set_running_all()` method |
| `src/ui/pages/test_dashboard_page.py` | Wire stop signals, `_on_stop_all()`, `_on_stop_card()`, callback guards |

**Architectural note — CategorySection:** The spec listed `category_section.py` as a changed file, suggesting a forwarded `stop_requested` signal. However, examining `test_dashboard_page.py`, `run_requested` is also wired **per-card** inside `_wire_section_run_buttons()` (not via a section-level forwarded signal). Following this existing pattern, `stop_requested` is wired the same way — directly per-card in `_wire_section_run_buttons()`. No changes to `category_section.py` are needed.

**Manual verification:** `uv run touchstone --dev-manual` (skips job-setup screen, goes straight to test dashboard). No automated tests exist.

---

### Task 1: TestStatus.CANCEL + mark_cancel()

**Files:**
- Modify: `src/models/test_result.py:9-72`

- [ ] **Step 1: Add CANCEL to TestStatus and add mark_cancel()**

  Open `src/models/test_result.py`. After line 16 (`ERROR = "error"`), add:

  ```python
      CANCEL = "cancel"
  ```

  After `mark_skip()` (line 66-69), add:

  ```python
      def mark_cancel(self) -> None:
          self.status = TestStatus.CANCEL
          self.summary = "Cancelled"
          self.completed_at = datetime.now()
  ```

  The `is_done()` method at line 72 returns `True` for any status not in `{WAITING, RUNNING}`. CANCEL is terminal so it works without changes.

- [ ] **Step 2: Verify the file looks correct**

  Run:
  ```bash
  cd "/Users/robertsaunders/Code/Automated PC Testing/pc-tester"
  python -c "from src.models.test_result import TestResult, TestStatus; r = TestResult('x','X'); r.mark_cancel(); print(r.status, r.summary, r.completed_at)"
  ```
  Expected output: `cancel Cancelled <datetime>`

- [ ] **Step 3: Commit**

  ```bash
  git add src/models/test_result.py
  git commit -m "feat: add TestStatus.CANCEL and mark_cancel()"
  ```

---

### Task 2: BaseTest.safe_run() catches CancelledError

**Files:**
- Modify: `src/tests/base.py:30-36`

- [ ] **Step 1: Add asyncio import and CancelledError handler**

  Open `src/tests/base.py`. Add `import asyncio` at the top (after `import abc`):

  ```python
  import asyncio
  import abc
  ```

  Replace the `safe_run()` method body so it reads:

  ```python
      async def safe_run(self) -> TestResult:
          """Wrapper that catches unexpected exceptions and marks the result as ERROR."""
          try:
              return await self.run()
          except asyncio.CancelledError:
              self.result.mark_cancel()
              return self.result
          except Exception as exc:
              self.result.mark_error(f"Unexpected error: {exc}")
              return self.result
  ```

  **Why the explicit `CancelledError` catch is required:** In Python 3.8+, `asyncio.CancelledError` is a subclass of `BaseException`, NOT `Exception`. The existing `except Exception` clause would NOT catch it — cancellation would silently propagate up and the result would never be marked. The explicit handler is mandatory, not optional.

- [ ] **Step 2: Verify**

  ```bash
  python -c "
  import asyncio
  from src.tests.base import BaseTest
  from src.models.test_result import TestResult, TestStatus
  from src.models.job import TestMode

  class Dummy(BaseTest):
      async def run(self):
          await asyncio.sleep(10)
          return self.result

  async def main():
      r = TestResult('t', 'T')
      t = Dummy(result=r, mode=TestMode.QUICK)
      task = asyncio.create_task(t.safe_run())
      await asyncio.sleep(0)
      task.cancel()
      await task
      print(r.status)  # should print: cancel

  asyncio.run(main())
  "
  ```
  Expected: `cancel`

- [ ] **Step 3: Commit**

  ```bash
  git add src/tests/base.py
  git commit -m "feat: catch CancelledError in BaseTest.safe_run() -> mark_cancel"
  ```

---

### Task 3: Fix CPU test monitor_task finally block

**Files:**
- Modify: `src/tests/cpu.py:268-270`

- [ ] **Step 1: Replace finally block**

  Open `src/tests/cpu.py`. Find the `finally` block at lines 268-270:

  ```python
          finally:
              stop_event.set()
              await monitor_task
  ```

  Replace with:

  ```python
          finally:
              stop_event.set()
              monitor_task.cancel()
              await asyncio.gather(monitor_task, return_exceptions=True)
  ```

  **Why:** When the outer coroutine is cancelled, a bare `await monitor_task` inside a `finally` block re-raises `CancelledError` immediately, leaving `monitor_task` running as an orphan in a closing loop. `monitor_task.cancel()` + `gather(return_exceptions=True)` cleanly cancels the monitor task and suppresses its `CancelledError`.

  When the test runs normally (not cancelled), `stop_event.set()` causes `monitor_temps` to exit its `while not stop_event.is_set()` loop, so `monitor_task.cancel()` is a no-op harmless call, and `gather` just awaits a task that's already finishing.

- [ ] **Step 2: Verify the app still launches**

  ```bash
  uv run touchstone --dev-manual
  ```
  App should open on the test dashboard. Close it. No errors in terminal.

- [ ] **Step 3: Commit**

  ```bash
  git add src/tests/cpu.py
  git commit -m "fix: cancel monitor_task in CPU test finally block to prevent orphan on cancel"
  ```

---

### Task 4: TestWorker cancel mechanism

**Files:**
- Modify: `src/ui/workers.py:19-55`

- [ ] **Step 1: Rewrite TestWorker**

  Open `src/ui/workers.py`. Replace the entire `TestWorker` class (lines 19-55) with:

  ```python
  class TestWorker(QThread):
      """Runs a single BaseTest in a background thread."""

      finished = Signal(str)  # emits test name on completion

      def __init__(
          self,
          name: str,
          module: str,
          cls_name: str,
          result: TestResult,
          mode: TestMode,
          parent=None,
      ) -> None:
          super().__init__(parent)
          self._name = name
          self._module = module
          self._cls_name = cls_name
          self._result = result
          self._mode = mode
          self._loop: "asyncio.AbstractEventLoop | None" = None
          self._task: "asyncio.Task | None" = None

      @property
      def name(self) -> str:
          """Public read-only access to the test name."""
          return self._name

      def run(self) -> None:
          import asyncio
          import importlib

          mod = importlib.import_module(f"src.tests.{self._module}")
          TestClass = getattr(mod, self._cls_name)
          test = TestClass(result=self._result, mode=self._mode)
          self._loop = asyncio.new_event_loop()
          asyncio.set_event_loop(self._loop)

          async def _run() -> None:
              # Capture the running Task so cancel() can reach it.
              self._task = asyncio.current_task()
              await test.safe_run()

          try:
              self._loop.run_until_complete(_run())
          except Exception as exc:
              self._result.mark_error(str(exc))
          finally:
              self._loop.close()
          self.finished.emit(self._name)

      def cancel(self) -> None:
          """Cancel the running async task. Thread-safe; safe to call multiple times."""
          if self._loop and self._task and not self._task.done():
              self._loop.call_soon_threadsafe(self._task.cancel)
  ```

  Also add `import asyncio` annotation at the top of the file. Since `asyncio` is imported locally inside `run()`, the type hints `"asyncio.AbstractEventLoop | None"` are string-quoted to avoid a top-level import. Alternatively, add `import asyncio` at the top of `workers.py` alongside the existing imports — either is fine.

- [ ] **Step 2: Verify the app runs tests correctly**

  ```bash
  uv run touchstone --dev-manual
  ```
  Click **▶ Run All**. Tests should start running (cards show RUNNING status, elapsed timers tick). Wait a few seconds, then close the app. No errors in terminal.

- [ ] **Step 3: Commit**

  ```bash
  git add src/ui/workers.py
  git commit -m "feat: add TestWorker.cancel() via asyncio task cancellation"
  ```

---

### Task 5: Cancel colour tokens

**Files:**
- Modify: `src/ui/stylesheet.py:51-95`

- [ ] **Step 1: Add cancel_text and cancel_bg to DARK and LIGHT dicts**

  Open `src/ui/stylesheet.py`.

  In the `DARK` dict (around line 70-72), add after `"danger_text"`:

  ```python
      "cancel_text":    "#fb923c",
      "cancel_bg":      "#1c1107",
  ```

  In the `LIGHT` dict (around line 93-95), add after `"danger_text"`:

  ```python
      "cancel_text":    "#ea580c",
      "cancel_bg":      "#ffedd5",
  ```

  **Note — no QSS border rule needed:** The spec mentioned adding a `QFrame[class="test-card"][status="cancel"]` border rule, but `DashboardCard` never calls `setProperty("class", "test-card")` or `setProperty("status", ...)`, so QSS property selectors have no effect on it. The card's status colour is applied via `set_status()` using direct `setStyleSheet()` on the label — the orange status text is sufficient visual feedback for CANCEL.

- [ ] **Step 2: Commit**

  ```bash
  git add src/ui/stylesheet.py
  git commit -m "feat: add cancel_text / cancel_bg colour tokens to DARK and LIGHT"
  ```

---

### Task 6: DashboardCard stop button

**Files:**
- Modify: `src/ui/widgets/dashboard_card.py:19-232`

- [ ] **Step 1: Add _STATUS_COLORS_LIGHT and stop_requested signal; init _stop_mode**

  Open `src/ui/widgets/dashboard_card.py`.

  After the `_STATUS_COLORS` dict (line 27), add:

  ```python
  # Light-mode overrides for statuses whose dark hex doesn't work on light bg.
  _STATUS_COLORS_LIGHT: dict[str, str] = {
      "cancel": "#ea580c",
  }
  ```

  In `_STATUS_COLORS`, add the cancel entry:

  ```python
  _STATUS_COLORS: dict[str, str] = {
      "waiting": "#52525b",
      "running": "#60a5fa",
      "pass":    "#22c55e",
      "warn":    "#f59e0b",
      "fail":    "#ef4444",
      "error":   "#ef4444",
      "skip":    "#52525b",
      "cancel":  "#fb923c",
  }
  ```

  In `DashboardCard.__init__()`, add after `self._expanded = False`:

  ```python
          self._stop_mode: bool = False
  ```

  After `run_requested = Signal(str)`, add:

  ```python
      stop_requested = Signal(str)
  ```

- [ ] **Step 2: Update set_status() for running → stop button, and cancel display**

  Replace the `set_status()` method body. Key changes:
  - Resolve colour via theme-aware lookup
  - `running`: set `_stop_mode=True`, button → "◼ Stop" in danger colours
  - other: set `_stop_mode=False`, button → "Run"/"Re-run", restore normal style
  - `cancel`: show "cancelled" in detail label

  ```python
      def set_status(self, status: str, detail: str = "", sub_detail: str = "") -> None:
          """Update inline summary, status colour, expandable panel, and button label."""
          status = status.lower()
          c = get_colors(self._theme)

          # Theme-aware status label colour
          light_overrides = _STATUS_COLORS_LIGHT if self._theme == "light" else {}
          color = light_overrides.get(status) or _STATUS_COLORS.get(status, "#52525b")

          self._status_lbl.setText(status.upper())
          self._status_lbl.setStyleSheet(
              f"color: {color}; font-size: 12px; font-weight: 600; background: transparent;"
          )

          if status == "running":
              self._stop_mode = True
              self._elapsed_s = 0
              self._detail_lbl.setText("running…")
              self._detail_lbl.setStyleSheet(
                  f"color: {c['badge_accent_text']}; font-size: 13px; background: transparent;"
              )
              if not self._ticker.isActive():
                  self._ticker.start()
              self._set_sub_detail("")
              # Morph Run button into ◼ Stop
              self._run_btn.setText("◼ Stop")
              self._run_btn.setStyleSheet(
                  f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                  f" border: none; border-radius: 6px; font-size: 12px; font-weight: 600; }}"
                  f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
              )
          else:
              self._stop_mode = False
              self._ticker.stop()
              detail_text = "cancelled" if status == "cancel" else detail
              self._detail_lbl.setText(detail_text)
              self._detail_lbl.setStyleSheet(
                  f"color: {c['text_muted']}; font-size: 13px; background: transparent;"
              )
              self._set_sub_detail(sub_detail)
              # Restore normal Run/Re-run button
              self._run_btn.setText("Run" if status == "waiting" else "Re-run")
              self._apply_run_btn_normal_style()
  ```

- [ ] **Step 3: Add _apply_run_btn_normal_style() helper and update apply_theme()**

  Add a private helper (call it from both `set_status()` non-running branch and `apply_theme()`):

  ```python
      def _apply_run_btn_normal_style(self) -> None:
          c = get_colors(self._theme)
          self._run_btn.setStyleSheet(
              f"QPushButton {{ background: {c['bg_elevated']}; color: {c['text_secondary']};"
              f" border: none; border-radius: 6px; font-size: 12px; font-weight: 500; }}"
              f"QPushButton:hover {{ background: {c['bg_hover']}; color: {c['text_primary']}; }}"
              f"QPushButton:pressed {{ background: {c['text_muted']}; }}"
              f"QPushButton:disabled {{ background: {c['bg_elevated']}; color: {c['text_muted']}; }}"
          )
  ```

  In `apply_theme()`, replace the `self._run_btn.setStyleSheet(...)` block with:

  ```python
          if self._stop_mode:
              self._run_btn.setText("◼ Stop")
              self._run_btn.setStyleSheet(
                  f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                  f" border: none; border-radius: 6px; font-size: 12px; font-weight: 600; }}"
                  f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
              )
          else:
              self._apply_run_btn_normal_style()
  ```

- [ ] **Step 4: Update _on_run_clicked() to emit stop_requested when in stop mode**

  Replace `_on_run_clicked()`:

  ```python
      def _on_run_clicked(self) -> None:
          if self._stop_mode:
              self.stop_requested.emit(self._name)
          else:
              self.run_requested.emit(self._name)
  ```

- [ ] **Step 5: Run the app and verify button morphs**

  ```bash
  uv run touchstone --dev-manual
  ```
  Click **▶ Run All**. While tests are running, each card's button should read "◼ Stop" in red/orange. After tests complete, buttons should revert to "Re-run".

- [ ] **Step 6: Commit**

  ```bash
  git add src/ui/widgets/dashboard_card.py
  git commit -m "feat: DashboardCard Run button morphs to stop while running; stop_requested signal"
  ```

---

### Task 7: HeaderBar set_running_all() + stop_all_clicked

**Files:**
- Modify: `src/ui/widgets/header_bar.py:30-34`, `:132-134`, `:156-164`

- [ ] **Step 1: Add stop_all_clicked signal**

  Open `src/ui/widgets/header_bar.py`. After `run_all_clicked = Signal()` (line 30), add:

  ```python
      stop_all_clicked = Signal()
  ```

  Also add `self._running_all: bool = False` in `__init__` after `self._mode = "simple"`:

  ```python
          self._running_all: bool = False
  ```

- [ ] **Step 2: Add set_running_all() method**

  After `set_run_all_enabled()` (line 132-133), add:

  ```python
      def set_running_all(self, active: bool) -> None:
          """Toggle Run All button between ▶ Run All and ◼ Stop."""
          self._running_all = active
          c = get_colors(self._theme)
          if active:
              self._run_all_btn.setText("◼ Stop")
              self._run_all_btn.clicked.disconnect()
              self._run_all_btn.clicked.connect(self.stop_all_clicked)
              self._run_all_btn.setStyleSheet(
                  f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                  f" border: none; border-radius: 6px; padding: 5px 14px; font-size: 12px;"
                  f" font-weight: 600; min-height: 30px; }}"
                  f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
              )
          else:
              self._run_all_btn.setText("▶ Run All")
              self._run_all_btn.clicked.disconnect()
              self._run_all_btn.clicked.connect(self.run_all_clicked)
              self._apply_run_all_normal_style()
  ```

- [ ] **Step 3: Extract _apply_run_all_normal_style() helper; update apply_theme()**

  Add a private helper (call from both `set_running_all(False)` and `apply_theme()`):

  ```python
      def _apply_run_all_normal_style(self) -> None:
          c = get_colors(self._theme)
          self._run_all_btn.setStyleSheet(
              f"QPushButton {{ background: {c['accent']}; color: #ffffff; border: none;"
              f" border-radius: 6px; padding: 5px 14px; font-size: 12px;"
              f" font-weight: 600; min-height: 30px; }}"
              f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
              f"QPushButton:pressed {{ background: {c['accent_hover']}; }}"
              f"QPushButton:disabled {{ background: {c['accent']}; color: #ffffff; }}"
          )
  ```

  In `apply_theme()`, replace the `# Run All button` block with:

  ```python
          # Run All / Stop button — preserve current running state
          if self._running_all:
              self._run_all_btn.setText("◼ Stop")
              self._run_all_btn.setStyleSheet(
                  f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                  f" border: none; border-radius: 6px; padding: 5px 14px; font-size: 12px;"
                  f" font-weight: 600; min-height: 30px; }}"
                  f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
              )
          else:
              self._apply_run_all_normal_style()
  ```

- [ ] **Step 4: Run the app and verify**

  ```bash
  uv run touchstone --dev-manual
  ```
  Click **▶ Run All**. The button should immediately change to "◼ Stop" in danger styling. (It won't do anything yet — that's wired in Task 8.)

- [ ] **Step 5: Commit**

  ```bash
  git add src/ui/widgets/header_bar.py
  git commit -m "feat: HeaderBar.set_running_all() toggles Run All <-> Stop button"
  ```

---

### Task 8: TestDashboardPage — wire stop signals and handlers

**Files:**
- Modify: `src/ui/pages/test_dashboard_page.py`

This is the final integration task. Read the full `_on_run_all`, `_on_parallel_test_done`, `_on_sequential_test_done`, `_wire_section_run_buttons`, and `_recalculate_overall` methods carefully before editing.

- [ ] **Step 1: Wire stop_requested per-card in _wire_section_run_buttons()**

  Open `src/ui/pages/test_dashboard_page.py`. Find `_wire_section_run_buttons()` (line 213). After the `card.run_requested.connect(self._on_run_requested)` block, add stop_requested wiring in the same pattern:

  ```python
      def _wire_section_run_buttons(self, section: CategorySection) -> None:
          """Connect run_requested and stop_requested for all cards in a section."""
          for name, _, _ in section._tests:
              card = section.card(name)
              if card is not None:
                  try:
                      card.run_requested.disconnect(self._on_run_requested)
                  except RuntimeError:
                      pass
                  card.run_requested.connect(self._on_run_requested)
                  try:
                      card.stop_requested.disconnect(self._on_stop_card)
                  except RuntimeError:
                      pass
                  card.stop_requested.connect(self._on_stop_card)
  ```

- [ ] **Step 2: Wire stop_all_clicked alongside run_all_clicked**

  Open `src/ui/pages/test_dashboard_page.py`. At line 165, `run_all_clicked` is connected:

  ```python
  self._header.run_all_clicked.connect(self._on_run_all)
  ```

  Add immediately after it:

  ```python
  self._header.stop_all_clicked.connect(self._on_stop_all)
  ```

- [ ] **Step 3: Update _on_run_all() to call set_running_all(True)**

  In `_on_run_all()` (line 284), after `self._running_all = True`, add:

  ```python
          self._header.set_running_all(True)
  ```

- [ ] **Step 4: Update _recalculate_overall() to call set_running_all(False) on header**

  In `_recalculate_overall()` (line 431-435), the existing block:

  ```python
          if all_done and self._running_all:
              self._running_all = False
              for section in self._category_sections:
                  for card in section._cards.values():
                      card.set_running_all(False)
  ```

  Add `self._header.set_running_all(False)` inside that block:

  ```python
          if all_done and self._running_all:
              self._running_all = False
              self._header.set_running_all(False)
              for section in self._category_sections:
                  for card in section._cards.values():
                      card.set_running_all(False)
  ```

- [ ] **Step 5: Add early-return guards to _on_parallel_test_done and _on_sequential_test_done**

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

- [ ] **Step 6: Add _on_stop_all() handler**

  Add this method in the `# ── Run All` section, after `_on_run_all()`:

  ```python
      def _on_stop_all(self) -> None:
          """Cancel all running tests and mark queued tests CANCEL. Does not run manual queue."""
          # Clear running_all FIRST so _recalculate_overall() inside _apply_result()
          # doesn't find `all_done and _running_all` and bypass the header reset below.
          self._running_all = False

          # Mark actively-running tests CANCEL now so cards exit stop-mode before
          # set_running_all(False) re-enables buttons. Then cancel + clear the list —
          # the early-return guards mean _apply_result() won't be called from callbacks.
          for w in list(self._active_workers):
              result = self._results.get(w.name)
              if result and result.status == TestStatus.RUNNING:
                  result.mark_cancel()
                  self._apply_result(w.name)
              w.cancel()
          self._active_workers.clear()

          # Mark all queued (WAITING) results CANCEL immediately.
          for entry in self._sequential_queue:
              result = self._results.get(entry["name"])
              if result and result.status == TestStatus.WAITING:
                  result.mark_cancel()
                  self._apply_result(entry["name"])
          self._sequential_queue.clear()

          # Reset parallel counters so any stale callbacks don't start more tests.
          self._parallel_done_count = 0
          self._parallel_total = 0

          # Reset UI — header button back to ▶ Run All, re-enable cards.
          self._header.set_running_all(False)
          for section in self._category_sections:
              for card in section._cards.values():
                  card.set_running_all(False)

          # Do NOT call _on_automated_done() / _run_manual_queue().
  ```

- [ ] **Step 7: Add _on_stop_card() handler**

  Add after `_on_stop_all()`:

  ```python
      def _on_stop_card(self, name: str) -> None:
          """Cancel a single running test. The suite continues for other tests."""
          for w in self._active_workers:
              if w.name == name:
                  w.cancel()
                  break
  ```

  **How this works:** `w.cancel()` raises `CancelledError` at the next `await` in the test. `safe_run()` catches it and calls `mark_cancel()`. The worker's `finished` signal fires normally, calling `_on_parallel_test_done` or `_on_sequential_test_done`. Since `_running_all` is still `True` (only a single card was stopped), the guard doesn't trigger — `_apply_result()` runs, the card updates to CANCEL, and the queue advances normally.

- [ ] **Step 8: Run the app and verify the full stop flow**

  ```bash
  uv run touchstone --dev-manual
  ```

  **Verify global stop:**
  1. Click **▶ Run All** — button changes to "◼ Stop", card buttons change to "◼ Stop"
  2. Wait ~2 seconds, click **◼ Stop**
  3. All running tests should show CANCEL in orange; queued tests should also show CANCEL
  4. Manual test queue should NOT appear (no dialog opens)
  5. Header button should return to "▶ Run All"

  **Verify per-card stop:**
  1. Click **▶ Run All** again
  2. While CPU Stress is running, click its "◼ Stop" button
  3. Only CPU Stress should show CANCEL; other tests continue running
  4. Suite should complete normally (manual queue runs after)

  **Verify re-run:**
  1. Click "Re-run" on a CANCEL card — it should run and show a new result

- [ ] **Step 9: Commit**

  ```bash
  git add src/ui/pages/test_dashboard_page.py
  git commit -m "feat: wire stop/cancel — _on_stop_all, _on_stop_card, callback guards"
  ```

---

## Acceptance Checklist

- [ ] Run All button becomes `"◼ Stop"` while suite is running; clicking it cancels all active tests and marks all queued tests CANCEL
- [ ] Each card's Run button becomes `"◼ Stop"` while that card's test is running; clicking cancels only that test
- [ ] Cancelled tests show `CANCEL` in orange; queued tests that never ran also show `CANCEL`
- [ ] After Stop All, the manual test queue does NOT run
- [ ] After per-card stop during Run All, the suite continues normally for other tests
- [ ] Re-running a CANCEL card works (Re-run button appears, test reruns)
- [ ] `all_done` treats CANCEL as terminal — dashboard reaches done state after stop
- [ ] Both dark and light themes show correct orange cancel colour
- [ ] `system_info` worker is unaffected by stop actions
- [ ] CPU test monitor task does not orphan after cancellation

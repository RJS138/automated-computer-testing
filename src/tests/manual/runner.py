"""Manual test runner — stores guided checklist results."""

from ...models.test_result import TestResult, TestStatus
from .hdmi import ITEM as _HDMI
from .keyboard import ITEM as _KEYBOARD
from .lcd import ITEM as _LCD
from .speakers import ITEM as _SPEAKERS
from .touchpad import ITEM as _TOUCHPAD
from .usb_a import ITEM as _USB_A
from .usb_c import ITEM as _USB_C
from .webcam import ITEM as _WEBCAM

MANUAL_TEST_ITEMS: list[dict] = [
    _LCD,
    _SPEAKERS,
    _KEYBOARD,
    _TOUCHPAD,
    _USB_A,
    _USB_C,
    _HDMI,
    _WEBCAM,
]


class ManualTestRunner:
    """
    Manages the state of manual pass/fail checklist items.
    The UI screens interact with this class directly.
    """

    def __init__(self) -> None:
        self.items: list[dict] = [
            {
                **item,
                "status": TestStatus.WAITING,
                "notes": "",
            }
            for item in MANUAL_TEST_ITEMS
        ]
        self._index = 0

    @property
    def current_item(self) -> dict | None:
        if self._index < len(self.items):
            return self.items[self._index]
        return None

    @property
    def is_complete(self) -> bool:
        return self._index >= len(self.items)

    def seek_to(self, item_id: str) -> None:
        """Advance the index to the item with the given id (no-op if not found)."""
        for i, item in enumerate(self.items):
            if item["id"] == item_id:
                self._index = i
                return

    def pass_current(self, notes: str = "") -> None:
        if self.current_item:
            self.current_item["status"] = TestStatus.PASS
            self.current_item["notes"] = notes
            self._index += 1

    def fail_current(self, notes: str = "") -> None:
        if self.current_item:
            self.current_item["status"] = TestStatus.FAIL
            self.current_item["notes"] = notes
            self._index += 1

    def skip_current(self, notes: str = "Not applicable") -> None:
        if self.current_item:
            self.current_item["status"] = TestStatus.SKIP
            self.current_item["notes"] = notes
            self._index += 1

    def to_test_results(self) -> list[TestResult]:
        """Convert manual checklist items to TestResult objects."""
        results = []
        for item in self.items:
            r = TestResult(
                name=f"manual_{item['id']}",
                display_name=f"Manual: {item['label']}",
                status=item["status"],
                summary=item["notes"] or item["status"].value.upper(),
                data={"instructions": item["instructions"]},
            )
            results.append(r)
        return results

    def summary_result(self) -> TestResult:
        """Return a single aggregated TestResult for the manual checklist."""
        result = TestResult(
            name="manual",
            display_name="Manual Checks",
        )
        fail_items = [i for i in self.items if i["status"] == TestStatus.FAIL]
        pass_items = [i for i in self.items if i["status"] == TestStatus.PASS]
        skip_items = [i for i in self.items if i["status"] == TestStatus.SKIP]

        item_details = {
            item["id"]: {
                "label": item["label"],
                "status": item["status"].value,
                "notes": item["notes"],
            }
            for item in self.items
        }

        data = {
            "items": item_details,
            "pass_count": len(pass_items),
            "fail_count": len(fail_items),
            "skip_count": len(skip_items),
        }

        if fail_items:
            failed_labels = ", ".join(i["label"] for i in fail_items)
            result.mark_fail(
                summary=f"{len(fail_items)} issue(s): {failed_labels}",
                data=data,
            )
        else:
            result.mark_pass(
                summary=f"All {len(pass_items)} checked item(s) passed ({len(skip_items)} skipped)",
                data=data,
            )

        return result

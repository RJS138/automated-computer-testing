"""Abstract base class for all hardware tests."""

import abc
import asyncio
from typing import TYPE_CHECKING

from ..models.job import TestMode
from ..models.test_result import TestResult

if TYPE_CHECKING:
    pass


class BaseTest(abc.ABC):
    """
    Abstract base for all hardware test modules.

    Each subclass must implement `run()` which populates and returns a TestResult.
    Tests update their own TestResult in-place so the UI can observe progress.
    """

    def __init__(self, result: TestResult, mode: TestMode) -> None:
        self.result = result
        self.mode = mode

    @abc.abstractmethod
    async def run(self) -> TestResult:
        """Execute the test. Must call result.mark_running() at start."""
        ...

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

    def is_quick(self) -> bool:
        return self.mode == TestMode.QUICK

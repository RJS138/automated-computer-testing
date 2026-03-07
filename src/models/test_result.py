"""Test result dataclass."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TestStatus(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class TestResult:
    name: str
    display_name: str
    status: TestStatus = TestStatus.WAITING
    data: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error_message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def mark_running(self) -> None:
        self.status = TestStatus.RUNNING
        self.started_at = datetime.now()

    def mark_pass(self, summary: str = "", data: dict | None = None) -> None:
        self.status = TestStatus.PASS
        self.summary = summary
        if data:
            self.data.update(data)
        self.completed_at = datetime.now()

    def mark_warn(self, summary: str = "", data: dict | None = None) -> None:
        self.status = TestStatus.WARN
        self.summary = summary
        if data:
            self.data.update(data)
        self.completed_at = datetime.now()

    def mark_fail(self, summary: str = "", data: dict | None = None) -> None:
        self.status = TestStatus.FAIL
        self.summary = summary
        if data:
            self.data.update(data)
        self.completed_at = datetime.now()

    def mark_error(self, message: str) -> None:
        self.status = TestStatus.ERROR
        self.error_message = message
        self.completed_at = datetime.now()

    def mark_skip(self, reason: str = "") -> None:
        self.status = TestStatus.SKIP
        self.summary = reason
        self.completed_at = datetime.now()

    def is_done(self) -> bool:
        return self.status not in (TestStatus.WAITING, TestStatus.RUNNING)

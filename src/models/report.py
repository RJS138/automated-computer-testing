"""Full report dataclass combining job info and all test results."""

from dataclasses import dataclass, field
from datetime import datetime

from .job import JobInfo
from .test_result import TestResult, TestStatus


@dataclass
class FullReport:
    job: JobInfo
    results: list[TestResult] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def overall_status(self) -> TestStatus:
        statuses = [r.status for r in self.results if r.is_done()]
        if not statuses:
            return TestStatus.WAITING
        if any(s == TestStatus.FAIL for s in statuses):
            return TestStatus.FAIL
        if any(s in (TestStatus.WARN, TestStatus.ERROR) for s in statuses):
            return TestStatus.WARN
        return TestStatus.PASS

    def result_by_name(self, name: str) -> TestResult | None:
        return next((r for r in self.results if r.name == name), None)

    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASS)

    def warn_count(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.WARN)

    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.FAIL)

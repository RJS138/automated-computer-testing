"""Job information dataclass."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ReportType(StrEnum):
    BEFORE = "before"
    AFTER = "after"


class TestMode(StrEnum):
    QUICK = "quick"
    FULL = "full"


@dataclass
class JobInfo:
    customer_name: str = ""
    device_description: str = ""
    job_number: str = ""
    notes: str = ""
    report_type: ReportType = ReportType.BEFORE
    test_mode: TestMode = TestMode.QUICK
    created_at: datetime = field(default_factory=datetime.now)

    def folder_name(self) -> str:
        """Stable folder name for this job: CustomerName_WO#."""
        safe_customer = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in self.customer_name
        )
        safe_job = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in self.job_number)
        return f"{safe_customer}_{safe_job}"

    def display_name(self) -> str:
        return f"{self.customer_name} — {self.device_description} (Job #{self.job_number})"

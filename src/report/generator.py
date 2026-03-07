"""Assembles a FullReport from job info and test results."""

import copy

from ..models.job import JobInfo
from ..models.report import FullReport
from ..models.test_result import TestResult


def assemble_report(job: JobInfo, results: list[TestResult]) -> FullReport:
    """Build a FullReport from job info and the list of completed TestResults.

    If system_info discovered the device model, it overrides the manually
    entered device_description so the report reflects the real hardware.
    """
    job = copy.copy(job)

    si = next((r for r in results if r.name == "system_info"), None)
    if si and si.data:
        d = si.data
        model = d.get("chassis_model") or d.get("board_model")
        a_num = d.get("apple_model_number", "")
        if model:
            job.device_description = f"{model} ({a_num})" if a_num else model

    return FullReport(job=job, results=results)

"""SMART Deep extended test stub."""

from .base import BaseTest


class SmartDeepTest(BaseTest):
    name = "smart_deep"

    async def run(self) -> None:
        self.result.mark_skip("SMART Deep not yet implemented")

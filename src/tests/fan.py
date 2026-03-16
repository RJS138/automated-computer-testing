"""Fan Test stub."""

from .base import BaseTest


class FanTest(BaseTest):
    name = "fan"

    async def run(self) -> None:
        self.result.mark_skip("Fan Test not yet implemented")

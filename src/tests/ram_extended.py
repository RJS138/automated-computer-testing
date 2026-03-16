"""RAM Extended pattern sweep stub."""

from .base import BaseTest


class RamExtendedTest(BaseTest):
    name = "ram_extended"

    async def run(self) -> None:
        self.result.mark_skip("RAM Extended not yet implemented")

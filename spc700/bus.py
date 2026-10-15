from __future__ import annotations

from collections.abc import Callable

READ = "read"
WRITE = "write"
WAIT = "wait"

ADDRESS_MASK = 0xFFFF


class Bus:
    __slots__ = ("cycles", "log", "on_spend", "recording")

    def __init__(self, recording: bool = False) -> None:
        self.recording = recording
        self.log: list[tuple[int | None, int | None, str]] = []
        self.cycles = 0
        self.on_spend: Callable[[int], None] | None = None

    def spend(self, count: int = 1) -> None:
        self.cycles += count
        if self.on_spend is not None:
            self.on_spend(count)

    def restart(self) -> None:
        self.log = []
        self.cycles = 0

    def read(self, address: int, value: int) -> None:
        if self.recording:
            self.log.append((address & ADDRESS_MASK, value & 0xFF, READ))
        self.spend()

    def write(self, address: int, value: int) -> None:
        if self.recording:
            self.log.append((address & ADDRESS_MASK, value & 0xFF, WRITE))
        self.spend()

    def idle(self, count: int = 1) -> None:
        if self.recording:
            self.log.extend([(None, None, WAIT)] * count)
        self.spend(count)

"""The cycle, which is the unit the SPC700 is actually specified in.

Nintendo's command tables give a cycle count per instruction and nothing about
what happens inside one, so a count on its own cannot be checked against
anything: two cores can agree on every total and touch different addresses in a
different order. A recording of the bus can be checked, cycle by cycle, and that
is what this records.

Three things can happen in a cycle. The processor reads an address, writes an
address, or does neither because the work is internal to it. A read that the
core discards still drives the address, so it is a read like any other: the
distinction is in what the core does with the value afterwards, never in what
the bus did.

Nothing here decides how many cycles an instruction takes. That belongs to the
instruction, which asks for what it needs. This is the ledger.
"""

from __future__ import annotations

from collections.abc import Callable

READ = "read"
WRITE = "write"
WAIT = "wait"

ADDRESS_MASK = 0xFFFF


class Bus:
    """A log of what happened on the bus, and a count of how long it took.

    Recording is off by default. The count costs one addition per cycle and is
    always wanted; the log costs a tuple and an append, and is wanted only by
    something that is going to read it back.
    """

    __slots__ = ("cycles", "log", "on_spend", "recording")

    def __init__(self, recording: bool = False) -> None:
        self.recording = recording
        self.log: list[tuple[int | None, int | None, str]] = []
        self.cycles = 0
        self.on_spend: Callable[[int], None] | None = None
        """What the part hangs here so its own tally moves with this one.

        Every cycle this bus counts passes through `spend`, and `spend` is the
        only place that touches the count. A second place that added a cycle
        without telling the part would drift from it the first time somebody
        wrote one, and nothing would catch it.
        """

    def spend(self, count: int = 1) -> None:
        """Charge cycles, once, in the one place that charges them.

        Called after the cycle's bus activity is recorded rather than before,
        because a clock blocks in here. Charging first would stop the part with
        the access it just performed still missing from the log, and a board
        reading the log to decide what to do next would be reading it one cycle
        stale.
        """
        self.cycles += count
        if self.on_spend is not None:
            self.on_spend(count)

    def restart(self) -> None:
        """Begin a fresh instruction, forgetting the one before it."""
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
        """Cycles the processor spends on itself, driving no address."""
        if self.recording:
            self.log.extend([(None, None, WAIT)] * count)
        self.spend(count)

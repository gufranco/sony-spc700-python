"""How fast the processor runs, and a floor it must not fall through.

Not a benchmark for its own sake. The conformance walk executes a quarter of a
million cases and compares more than a million cycles, so every instruction this
core gets slower at costs that run directly. The way it stops being usable is
gradual: a lookup grows an allocation, a fetch becomes a comprehension, and a
year later a run nobody changed takes an hour. A floor that fails loudly is
cheaper than noticing.

The floor is deliberately far below what the chip does today. It is there to
catch something several times slower, not to police the noise between one runner
and another, because a shared runner's variance is larger than any change worth
arguing about.

Every figure is a median across repeats rather than a mean, because one
scheduling hiccup moves a mean and moves a median much less, and the runtime
version is printed beside it because it is the single thing that changes these
numbers most.

Run it outside the coverage step. A tracer costs about ten times what this does,
so a floor measured under one measures the tracer.
"""

from __future__ import annotations

import statistics
import sys
import time
from typing import TYPE_CHECKING

import spc700

if TYPE_CHECKING:
    from collections.abc import Sequence

FLOOR = 150_000
"""Instructions per second this must beat, an order of magnitude below what it does."""

CALLS = 20_000
"""Steps per repeat. Enough that the clock's resolution does not decide."""

REPEATS = 5
"""How many repeats the median is taken across."""

PROGRAM = bytes([0xE8, 0x00, 0xBC, 0x3D, 0x5D, 0xDD, 0x2F, 0xF8])
"""A short loop the part runs forever: load, increment, move, and branch back.

Chosen rather than left to scrambled memory, because a part left in rubbish
reaches a stop instruction within a few dozen steps and the run measures how
quickly it stopped.
"""


class Timed:
    """One measured run, and what it is allowed to say about itself."""

    __slots__ = ("calls", "seconds", "what")

    def __init__(self, what: str, calls: int, seconds: Sequence[float]) -> None:
        self.what = what
        self.calls = calls
        self.seconds = list(seconds)

    def median(self) -> float:
        return statistics.median(self.seconds)

    def rate(self) -> float:
        """Calls per second, or zero when the clock could not see the work.

        A run that measured zero seconds is a reading about the clock rather
        than about the code, and reporting it as unbounded speed would let a
        machine with a coarse timer pass a floor it never met.
        """
        taken = self.median()
        return self.calls / taken if taken > 0 else 0.0

    def beats(self, floor: int) -> bool:
        return self.rate() >= floor


def measure(calls: int = CALLS, repeats: int = REPEATS) -> Timed:
    """Run the loop and time it, rebuilding the part for each repeat."""
    seconds = []
    for _ in range(repeats):
        part = spc700.Cpu(memory=spc700.Memory(image=PROGRAM, fill=0), step_limit=calls * 2)
        part.pc = 0x0000
        started = time.perf_counter()
        for _ in range(calls):
            part.step()
        seconds.append(time.perf_counter() - started)
    return Timed("step", calls, seconds)


def lines_for(found: Timed, floor: int = FLOOR) -> list[str]:
    """What the run reports, whether it passed or not."""
    runtime = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    lines = [
        f"  {found.what}: {found.rate():,.0f} per second"
        f" (median of {len(found.seconds)}) on Python {runtime}",
        f"  floor: {floor:,} per second",
    ]
    if not found.beats(floor):
        lines.append(f"  below the floor: {found.rate():,.0f} is under {floor:,}")
    return lines


def main(calls: int = CALLS, repeats: int = REPEATS, floor: int = FLOOR) -> int:
    found = measure(calls, repeats)
    for line in lines_for(found, floor):
        print(line)
    return 0 if found.beats(floor) else 1


if __name__ == "__main__":
    raise SystemExit(main())

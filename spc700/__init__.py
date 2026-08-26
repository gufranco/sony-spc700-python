"""An interpreter for the SPC700, the processor inside the SNES audio unit.

    from spc700 import Cpu

    cpu = Cpu("spc700")
    cpu.reset()

Nothing starts clean. Memory is scrambled unless a caller asks otherwise, and a
reset sets only what the hardware itself defines, leaving the rest holding what
it held.
"""

from typing import Any

from . import models as models
from .clock import Clock
from .core import (
    FLAG_B,
    FLAG_C,
    FLAG_H,
    FLAG_I,
    FLAG_N,
    FLAG_P,
    FLAG_V,
    FLAG_Z,
    STEP_LIMIT,
)
from .errors import ClockClosed, RunLimit, Truncated, UnknownModelError
from .memory import UNSET_SEED, Memory, SparseMemory, scramble
from .models import MODELS
from .opcodes import OPCODES, disassemble
from .version import VERSION

__version__ = VERSION


def Cpu(  # noqa: N802
    model: str | None = None,
    memory: Any = None,
    fill: int | None = None,
    **options: Any,
) -> Any:
    """A processor of the named model, sharing one interface across the family.

    The model comes first because it is the thing a caller always knows and
    memory is the thing they often do not care about yet. Omitting it hands back
    a part with memory of its own, scrambled rather than cleared, which is what a
    board holds before anything has written to it.

    `fill` is the one way across this family to ask for a store holding one byte
    everywhere. It is not what a board hands over and it is not the default: a
    caller asking for zeroes is asking for something no machine does, so they
    have to say so. What it is for is a run that has to get through a few dozen
    instructions without meeting an opcode that stops the part, which is what
    every check of a cycle budget needs and what scrambled memory cannot give.
    """
    if fill is not None and memory is None:
        memory = Memory(fill=fill)
    return models.lookup(model).build(SparseMemory() if memory is None else memory, **options)


__all__ = [
    "FLAG_B",
    "FLAG_C",
    "FLAG_H",
    "FLAG_I",
    "FLAG_N",
    "FLAG_P",
    "FLAG_V",
    "FLAG_Z",
    "MODELS",
    "OPCODES",
    "STEP_LIMIT",
    "UNSET_SEED",
    "Clock",
    "ClockClosed",
    "Cpu",
    "Memory",
    "RunLimit",
    "SparseMemory",
    "Truncated",
    "UnknownModelError",
    "__version__",
    "disassemble",
    "scramble",
]

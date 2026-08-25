"""An interpreter for the SPC700, the processor inside the SNES audio unit.

    from spc700 import Cpu

    cpu = Cpu("spc700")
    cpu.reset()

Nothing starts clean. Memory is scrambled unless a caller asks otherwise, and a
reset sets only what the hardware itself defines, leaving the rest holding what
it held.
"""

from typing import Any

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
from .models import MODELS, describe
from .opcodes import OPCODES, disassemble
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "spc700"


def Cpu(  # noqa: N802
    model: str = DEFAULT_MODEL, memory: Any = None, **options: Any
) -> Any:
    """A processor of the named model, sharing one interface across the family.

    The model comes first because it is the thing a caller always knows and
    memory is the thing they often do not care about yet. Omitting it hands back
    a part with memory of its own, scrambled rather than cleared, which is what a
    board holds before anything has written to it.
    """
    return describe(model).build(SparseMemory() if memory is None else memory, **options)


__all__ = [
    "DEFAULT_MODEL",
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
    "describe",
    "disassemble",
    "scramble",
]

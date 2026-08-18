"""An interpreter for the SPC700, the processor inside the SNES audio unit.

    from spc700 import Cpu, SparseMemory

    cpu = Cpu(SparseMemory(), model="spc700")

Nothing starts clean. Memory is scrambled unless a caller asks otherwise, and a
reset sets only what the hardware itself defines, leaving the rest holding what
it held.
"""

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
    StepLimit,
)
from .core import Cpu as Spc700
from .memory import UNSET_SEED, Memory, SparseMemory, scramble
from .models import MODELS, UnknownModelError, describe
from .opcodes import OPCODES, Truncated, disassemble
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "spc700"


def Cpu(memory, model=DEFAULT_MODEL, **options):  # noqa: N802
    """A processor of the named model, sharing one interface across the family."""
    return describe(model).build(memory, **options)


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
    "Cpu",
    "Memory",
    "SparseMemory",
    "Spc700",
    "StepLimit",
    "Truncated",
    "UnknownModelError",
    "__version__",
    "describe",
    "disassemble",
    "scramble",
]

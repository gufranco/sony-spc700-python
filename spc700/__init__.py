from typing import Any

from . import models as models
from .bus import Bus
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
from .opcodes import OPCODES, decode, disassemble
from .version import VERSION

__version__ = VERSION


def Cpu(  # noqa: N802
    model: str | None = None,
    memory: Any = None,
    fill: int | None = None,
    **options: Any,
) -> Any:
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
    "Bus",
    "Clock",
    "ClockClosed",
    "Cpu",
    "Memory",
    "RunLimit",
    "SparseMemory",
    "Truncated",
    "UnknownModelError",
    "__version__",
    "decode",
    "disassemble",
    "scramble",
]

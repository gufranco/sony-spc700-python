from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import spc700  # noqa: E402

FAMILY = (ROOT / "FAMILY.md").read_text()

KIND = "Clocked part"

CLOCKED = KIND == "Clocked part"

PACKAGE: Any = spc700

TOOL_MODULES = {"doctor", "environment"}

A_MODEL = sorted(PACKAGE.MODELS)[0] if hasattr(PACKAGE, "MODELS") else ""


def why_it_cannot_build_here() -> str | None:
    asked = getattr(PACKAGE, "why_not", None)
    return asked() if callable(asked) else None


BUILDABLE = why_it_cannot_build_here() is None


A_PART = KIND == "Part"


SOLD_AS_A_COMPONENT = False

INTERFACE = (
    "step",
    "run_for",
    "run_until",
    "reset",
    "held",
)

INTERRUPT_LINES: tuple[str, ...] = ()

COUNTERS = ("cycles", "steps")


class Part(Protocol):
    cycles: int
    steps: int

    def step(self) -> int: ...

    def run_for(self, cycles: int) -> int: ...

    def run_until(self, predicate: Any, limit: int | None = None) -> Any: ...

    def reset(self) -> Any: ...

    def held(self) -> bool: ...


def a_part() -> Part:
    part: Part = PACKAGE.Cpu(A_MODEL)
    return part


def store_attribute() -> str:
    part = PACKAGE.Cpu(A_MODEL)
    found = [name for name in ("memory", "stores") if getattr(part, name, None) is not None]
    assert found, "a clocked part keeps its store on `memory` or on `stores`"
    return found[0]


def accounts_for_one_interrupt(node: Any) -> bool:
    if isinstance(node, dict):
        if any("interrupt" in str(key).lower() for key in node):
            return True
        return any(accounts_for_one_interrupt(one) for one in node.values())
    if isinstance(node, list):
        return any(accounts_for_one_interrupt(one) for one in node)
    return "interrupt" in str(node).lower()


def at_the_start(part: Any) -> None:
    held = getattr(part, "registers", part)
    held.pc = 0x0000


def a_running_part() -> Part:
    part = PACKAGE.Cpu(A_MODEL, fill=0)
    at_the_start(part)
    checked: Part = part
    return checked


TESTED_DIRECTORIES = ("spc700", "conformance")

LONG_FILES: dict[str, str] = {
    "spc700/core.py": (
        "A single calculation engine sharing intermediate state: one Cpu whose 256 opcode"
        " handlers read and write the same registers, flags and bus"
    ),
}

MACHINES: dict[str, tuple[str, ...]] = {}

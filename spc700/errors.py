"""Everything this package raises, in one place.

One module so a caller can see the whole set at once, and so `except` has
somewhere to import from. It imports nothing from the rest of the package, which
is what keeps it from ever closing a cycle: everything here raises, so everything
here imports this, and an import running the other way would make the order
modules happen to load in decide whether the package works at all.

Three of these were defined in the three modules that raise them, which works
until a second module wants to raise the same name. A sibling package shipped
exactly that: two classes under one name, the package exporting one of them, and
`except` written against it sailing straight past every case the other raised.
"""

from __future__ import annotations


class RunLimit(Exception):
    """A bounded run gave up rather than running forever.

    Raised by `run_until` when the condition it was given has not come true
    within the step budget. The budget exists because a caller's condition can be
    one the program never satisfies, and a model that hangs is worse than one
    that refuses: a hang has to be diagnosed, a refusal names itself.
    """


class ClockClosed(Exception):
    """The clock was used after it was closed.

    A clock hands the part back when it closes, so anything still holding one is
    holding something that no longer drives anything. Raising says so rather than
    letting a caller step a part the clock has released.
    """


class Truncated(Exception):
    """The bytes ran out in the middle of an instruction.

    Raised by the disassembler rather than by the core: a program that runs off
    the end of memory wraps, which is what the hardware does, but a reader handed
    a short buffer has simply not been handed enough.
    """


class UnknownModelError(Exception):
    """No model goes by that name.

    The message names the models that would have worked, because a refusal that
    does not costs the caller a search through the source.
    """

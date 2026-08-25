"""Memory that holds what it held, because hardware never hands over a clean one.

The SPC700 sees a flat sixty four kilobyte space. On a console most of it is the
audio RAM, and that RAM is not cleared at power on: it holds whatever pattern the
parts settle into. Code that reads a byte it never wrote reads that pattern, and
on real hardware that read is a bug waiting for the day the pattern changes.
Memory that begins at zero hides every one of those reads, so nothing here begins
at zero unless a caller asks for it in writing.

Two shapes are offered because the cost of being unclean differs. `Memory` fills
a real buffer, which suits a machine that will touch most of its address space.
`SparseMemory` derives an unwritten byte from its address, which suits a test that
touches a dozen and should not pay for the whole space to do it.
"""

import random
from collections.abc import Sequence

UNSET_SEED = 0x5A5A5A5A

ADDRESS_MASK = 0xFFFF

SPACE_SIZE = 0x10000

_GOLDEN = 2654435761
_MIX = 2246822519
_SEED_STRIDE = 40503
_WORD = 0xFFFFFFFF


def scramble(size: int, seed: int = UNSET_SEED) -> bytearray:
    """A deterministic fill that is nothing like a cleared machine.

    Reproducible from the seed, so a differential run stays comparable, and
    obviously not clean, so a read of something never written shows up.
    """
    return bytearray(random.Random(seed).randbytes(size))


class SparseMemory:
    """Unclean everywhere without being allocated anywhere.

    Holds only what has been written and derives the rest from the address, so an
    unwritten byte still reads as something arbitrary, still differs from zero,
    and still reads the same twice, at no setup cost.
    """

    __slots__ = ("cells", "seed")
    """Without them a name this class does not have is accepted in silence.

    The caller sets a stray attribute, the one they meant keeps whatever it held,
    and nothing reports that the write went nowhere. A sibling package shipped
    exactly that, where two parts spell a flag differently and reaching for the
    wrong one did nothing at all.
    """

    def __init__(self, seed: int = UNSET_SEED) -> None:
        self.cells: dict[int, int] = {}
        self.seed = seed & _WORD

    def _unwritten(self, address: int) -> int:
        mixed = (address * _GOLDEN + self.seed * _SEED_STRIDE) & _WORD
        mixed ^= mixed >> 15
        mixed = (mixed * _MIX) & _WORD
        mixed ^= mixed >> 13
        return mixed & 0xFF

    def read8(self, address: int) -> int:
        address &= ADDRESS_MASK
        found = self.cells.get(address)
        return self._unwritten(address) if found is None else found

    def write8(self, address: int, value: int) -> None:
        self.cells[address & ADDRESS_MASK] = value & 0xFF


class Memory:
    """Flat memory, filled rather than cleared.

    Two ways to say what is in it, and they are separate parameters because they
    are separate ideas. `image` is what a board genuinely knows at power on: the
    bytes a mask ROM holds, loaded at the bottom, with everything it does not
    cover left as it was. `fill` is one byte repeated across the whole space,
    which no board ever hands over and which a test asks for deliberately.

    One parameter carrying both was how this was written, and it made the two
    behave differently in a way nothing said out loud: an image zeroed the space
    it did not reach, so a read of a byte nothing wrote answered zero, which is
    the defect the scrambled default exists to expose.

    Neither given, the space comes up scrambled, because that is what a machine
    hands over and a test that wants otherwise should have to say so.
    """

    __slots__ = ("data",)
    """Without them a name this class does not have is accepted in silence.

    The caller sets a stray attribute, the one they meant keeps whatever it held,
    and nothing reports that the write went nowhere. A sibling package shipped
    exactly that, where two parts spell a flag differently and reaching for the
    wrong one did nothing at all.
    """

    def __init__(
        self,
        size: int = SPACE_SIZE,
        image: Sequence[int] | None = None,
        seed: int = UNSET_SEED,
        fill: int | None = None,
    ) -> None:
        self.data = scramble(size, seed) if fill is None else bytearray([fill & 0xFF]) * size
        if image is not None:
            self.data[: len(image)] = image

    def read8(self, address: int) -> int:
        return self.data[address & ADDRESS_MASK]

    def write8(self, address: int, value: int) -> None:
        self.data[address & ADDRESS_MASK] = value & 0xFF

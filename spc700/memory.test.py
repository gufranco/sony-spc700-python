import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import UNSET_SEED, Memory, SparseMemory, scramble

SPACE = 0x10000


class ScrambleTest(unittest.TestCase):
    def test_gives_the_requested_length(self) -> None:
        # Arrange
        size = 64

        # Act
        pattern = scramble(size)

        # Assert
        self.assertEqual(len(pattern), 64)

    def test_repeats_for_one_seed(self) -> None:
        # Arrange
        first = scramble(256, seed=7)

        # Act
        second = scramble(256, seed=7)

        # Assert
        self.assertEqual(second, first)

    def test_differs_between_seeds(self) -> None:
        # Arrange
        first = scramble(256, seed=7)

        # Act
        second = scramble(256, seed=8)

        # Assert
        self.assertNotEqual(second, first)

    def test_is_not_a_cleared_machine(self) -> None:
        # Arrange
        size = 4096

        # Act
        pattern = scramble(size)

        # Assert
        self.assertNotEqual(pattern, bytearray(4096))

    def test_covers_most_of_the_byte_range(self) -> None:
        # Arrange
        size = 4096

        # Act
        pattern = scramble(size)

        # Assert
        self.assertGreater(len(set(pattern)), 200)

    def test_gives_nothing_for_no_length(self) -> None:
        # Arrange
        size = 0

        # Act
        pattern = scramble(size)

        # Assert
        self.assertEqual(pattern, bytearray())


class AddressSpaceTest(unittest.TestCase):
    def test_the_space_is_sixty_four_kilobytes_in_a_flat_store(self) -> None:
        # Arrange
        memory = Memory(fill=0)
        memory.write8(SPACE - 1, 0x5A)

        # Act
        wrapped = memory.read8(SPACE + SPACE - 1)

        # Assert
        self.assertEqual((wrapped, len(memory.data)), (0x5A, 65536))

    def test_and_in_a_sparse_one(self) -> None:
        # Arrange
        memory = SparseMemory()
        memory.write8(SPACE - 1, 0x5A)

        # Act
        wrapped = memory.read8(SPACE + SPACE - 1)

        # Assert
        self.assertEqual((wrapped, memory.read8(SPACE)), (0x5A, memory.read8(0x0000)))


class SparseMemoryTest(unittest.TestCase):
    def test_reads_back_what_was_written(self) -> None:
        # Arrange
        memory = SparseMemory()
        memory.write8(0x1234, 0x9C)

        # Act
        held = memory.read8(0x1234)

        # Assert
        self.assertEqual(held, 0x9C)

    def test_keeps_only_the_low_byte(self) -> None:
        # Arrange
        memory = SparseMemory()
        memory.write8(0x0010, 0x1FF)

        # Act
        held = memory.read8(0x0010)

        # Assert
        self.assertEqual(held, 0xFF)

    def test_wraps_the_address_into_the_space(self) -> None:
        # Arrange
        memory = SparseMemory()
        memory.write8(0x10010, 0x42)

        # Act
        held = memory.read8(0x0010)

        # Assert
        self.assertEqual(held, 0x42)

    def test_reads_something_it_never_held(self) -> None:
        # Arrange
        memory = SparseMemory()

        # Act
        unwritten = {memory.read8(address) for address in range(0, 0x4000, 7)}

        # Assert
        self.assertGreater(len(unwritten), 1)

    def test_repeats_an_unwritten_read(self) -> None:
        # Arrange
        memory = SparseMemory(seed=99)
        first = memory.read8(0xABCD)

        # Act
        second = memory.read8(0xABCD)

        # Assert
        self.assertEqual(second, first)

    def test_differs_between_seeds(self) -> None:
        # Arrange
        one = SparseMemory(seed=1)
        other = SparseMemory(seed=2)

        # Act
        differing = [
            address for address in range(0x400) if one.read8(address) != other.read8(address)
        ]

        # Assert
        self.assertGreater(len(differing), 0x200)

    def test_allocates_only_what_was_written(self) -> None:
        # Arrange
        memory = SparseMemory()
        memory.read8(0x1000)

        # Act
        memory.write8(0x2000, 1)

        # Assert
        self.assertEqual(memory.cells, {0x2000: 1})

    def test_a_written_zero_stays_zero(self) -> None:
        # Arrange
        memory = SparseMemory()
        address = next(a for a in range(0x1000) if memory.read8(a) != 0)
        memory.write8(address, 0)

        # Act
        held = memory.read8(address)

        # Assert
        self.assertEqual(held, 0)


class MemoryTest(unittest.TestCase):
    def test_is_scrambled_when_nothing_is_asked_for(self) -> None:
        # Arrange
        size = 0x1000

        # Act
        memory = Memory(size=size)

        # Assert
        self.assertNotEqual(memory.data, bytearray(0x1000))

    def test_fills_with_a_byte(self) -> None:
        # Arrange
        fill = 0xAA

        # Act
        memory = Memory(size=0x100, fill=fill)

        # Assert
        self.assertEqual(set(memory.data), {0xAA})

    def test_keeps_only_the_low_byte_of_the_fill(self) -> None:
        # Arrange
        fill = 0x1BB

        # Act
        memory = Memory(size=0x10, fill=fill)

        # Assert
        self.assertEqual(set(memory.data), {0xBB})

    def test_zero_is_a_decision_a_caller_can_make(self) -> None:
        # Arrange
        fill = 0

        # Act
        memory = Memory(size=0x100, fill=fill)

        # Assert
        self.assertEqual(memory.data, bytearray(0x100))

    def test_takes_an_image_at_the_bottom(self) -> None:
        # Arrange
        image = b"\x01\x02\x03"

        # Act
        memory = Memory(size=0x100, image=image)

        # Assert
        self.assertEqual(bytes(memory.data[:3]), b"\x01\x02\x03")

    def test_pads_the_rest_of_an_image(self) -> None:
        # Arrange
        image = b"\xff"

        # Act
        memory = Memory(size=0x10, image=image, fill=0)

        # Assert
        self.assertEqual(memory.data[1:], bytearray(0x0F))

    def test_repeats_for_one_seed(self) -> None:
        # Arrange
        first = Memory(size=0x100, seed=3)

        # Act
        second = Memory(size=0x100, seed=3)

        # Assert
        self.assertEqual(second.data, first.data)

    def test_reads_back_what_was_written(self) -> None:
        # Arrange
        memory = Memory(fill=0)
        memory.write8(0x1234, 0x5A)

        # Act
        held = memory.read8(0x1234)

        # Assert
        self.assertEqual(held, 0x5A)

    def test_defaults_to_the_whole_address_space(self) -> None:
        # Arrange
        expected = 0x10000

        # Act
        memory = Memory()

        # Assert
        self.assertEqual(len(memory.data), expected)

    def test_wraps_the_address_into_the_space(self) -> None:
        # Arrange
        memory = Memory(fill=0)
        memory.write8(0x10020, 0x77)

        # Act
        held = memory.read8(0x0020)

        # Assert
        self.assertEqual(held, 0x77)


class SeedTest(unittest.TestCase):
    def test_the_default_seed_is_shared(self) -> None:
        # Arrange
        named = scramble(16, seed=UNSET_SEED)

        # Act
        defaulted = scramble(16)

        # Assert
        self.assertEqual(defaulted, named)


if __name__ == "__main__":
    unittest.main()

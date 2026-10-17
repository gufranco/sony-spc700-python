import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import Cpu, Memory


def built(memory: Memory, **options: Any) -> Any:
    return Cpu("spc700", memory, **options)


def machine(
    code: Sequence[int], base: int = 0x0200, fill: int = 0, **registers: int
) -> tuple[Any, Memory]:
    memory = Memory(fill=fill)
    for offset, byte in enumerate(code):
        memory.write8(base + offset, byte)
    cpu = built(memory)
    cpu.psw = 0x00
    cpu.a = cpu.x = cpu.y = 0x00
    cpu.pc = base
    cpu.sp = 0xEF
    for name, value in registers.items():
        setattr(cpu, name, value)
    return cpu, memory


def run(code: Sequence[int], steps: int = 1, **registers: int) -> tuple[Any, Memory]:
    cpu, memory = machine(code, **registers)
    for _ in range(steps):
        cpu.step()
    return cpu, memory


class ArithmeticTest(unittest.TestCase):
    def test_addition_carries_out_of_eight_bits(self) -> None:
        # Arrange
        program = [0x60, 0x88, 0x01]

        # Act
        cpu, _ = run(program, steps=2, a=0xFF)

        # Assert
        self.assertEqual(cpu.a, 0x00)
        self.assertTrue(cpu.c)

    def test_addition_brings_the_carry_in(self) -> None:
        # Arrange
        program = [0x80, 0x88, 0x01]

        # Act
        cpu, _ = run(program, steps=2, a=0x00)

        # Assert
        self.assertEqual(cpu.a, 0x02)

    def test_addition_sets_overflow_when_the_sign_is_wrong(self) -> None:
        # Arrange
        program = [0x60, 0x88, 0x01]

        # Act
        cpu, _ = run(program, steps=2, a=0x7F)

        # Assert
        self.assertTrue(cpu.v)

    def test_addition_sets_the_half_carry_at_the_nibble(self) -> None:
        # Arrange
        program = [0x60, 0x88, 0x01]

        # Act
        cpu, _ = run(program, steps=2, a=0x0F)

        # Assert
        self.assertTrue(cpu.h)

    def test_subtraction_borrows_when_the_carry_is_clear(self) -> None:
        # Arrange
        program = [0x60, 0xA8, 0x01]

        # Act
        cpu, _ = run(program, steps=2, a=0x10)

        # Assert
        self.assertEqual(cpu.a, 0x0E)

    def test_subtraction_below_zero_clears_the_carry(self) -> None:
        # Arrange
        program = [0x80, 0xA8, 0x02]

        # Act
        cpu, _ = run(program, steps=2, a=0x01)

        # Assert
        self.assertFalse(cpu.c)

    def test_a_comparison_leaves_the_accumulator_alone(self) -> None:
        # Arrange
        program = [0x68, 0x10]

        # Act
        cpu, _ = run(program, a=0x20)

        # Assert
        self.assertEqual(cpu.a, 0x20)
        self.assertTrue(cpu.c)

    def test_a_comparison_of_equals_sets_zero(self) -> None:
        # Arrange
        program = [0x68, 0x20]

        # Act
        cpu, _ = run(program, a=0x20)

        # Assert
        self.assertTrue(cpu.z)

    def test_a_bitwise_and_keeps_the_common_bits(self) -> None:
        # Arrange
        program = [0x28, 0x0F]

        # Act
        cpu, _ = run(program, a=0x3C)

        # Assert
        self.assertEqual(cpu.a, 0x0C)

    def test_a_bitwise_or_keeps_every_bit(self) -> None:
        # Arrange
        program = [0x08, 0x0F]

        # Act
        cpu, _ = run(program, a=0x30)

        # Assert
        self.assertEqual(cpu.a, 0x3F)

    def test_an_exclusive_or_drops_the_common_bits(self) -> None:
        # Arrange
        program = [0x48, 0x0F]

        # Act
        cpu, _ = run(program, a=0x3C)

        # Assert
        self.assertEqual(cpu.a, 0x33)

    def test_incrementing_wraps_at_the_top(self) -> None:
        # Arrange
        program = [0xBC]

        # Act
        cpu, _ = run(program, a=0xFF)

        # Assert
        self.assertEqual(cpu.a, 0x00)
        self.assertTrue(cpu.z)

    def test_decrementing_wraps_at_the_bottom(self) -> None:
        # Arrange
        program = [0x9C]

        # Act
        cpu, _ = run(program, a=0x00)

        # Assert
        self.assertEqual(cpu.a, 0xFF)
        self.assertTrue(cpu.n)

    def test_a_nibble_exchange_swaps_the_halves(self) -> None:
        # Arrange
        program = [0x9F]

        # Act
        cpu, _ = run(program, a=0x3C)

        # Assert
        self.assertEqual(cpu.a, 0xC3)


class ShiftTest(unittest.TestCase):
    def test_a_shift_left_moves_the_top_bit_into_the_carry(self) -> None:
        # Arrange
        program = [0x1C]

        # Act
        cpu, _ = run(program, a=0x81)

        # Assert
        self.assertEqual(cpu.a, 0x02)
        self.assertTrue(cpu.c)

    def test_a_shift_right_moves_the_bottom_bit_into_the_carry(self) -> None:
        # Arrange
        program = [0x5C]

        # Act
        cpu, _ = run(program, a=0x03)

        # Assert
        self.assertEqual(cpu.a, 0x01)
        self.assertTrue(cpu.c)

    def test_a_rotate_left_brings_the_carry_in(self) -> None:
        # Arrange
        program = [0x80, 0x3C]

        # Act
        cpu, _ = run(program, steps=2, a=0x00)

        # Assert
        self.assertEqual(cpu.a, 0x01)

    def test_a_rotate_right_brings_the_carry_into_the_top(self) -> None:
        # Arrange
        program = [0x80, 0x7C]

        # Act
        cpu, _ = run(program, steps=2, a=0x00)

        # Assert
        self.assertEqual(cpu.a, 0x80)

    def test_a_shift_in_memory_writes_the_result_back(self) -> None:
        # Arrange
        cpu, memory = machine([0x0B, 0x10])
        memory.write8(0x0010, 0x40)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x80)


class WordTest(unittest.TestCase):
    def test_a_word_load_takes_two_bytes(self) -> None:
        # Arrange
        cpu, memory = machine([0xBA, 0x10])
        memory.write8(0x0010, 0x34)
        memory.write8(0x0011, 0x12)

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.y << 8) | cpu.a, 0x1234)

    def test_a_word_store_writes_two_bytes(self) -> None:
        # Arrange
        program = [0xDA, 0x10]

        # Act
        _, memory = run(program, a=0x34, y=0x12)

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x34)
        self.assertEqual(memory.read8(0x0011), 0x12)

    def test_a_word_addition_carries_between_the_bytes(self) -> None:
        # Arrange
        cpu, memory = machine([0x7A, 0x10], a=0xFF, y=0x00)
        memory.write8(0x0010, 0x01)
        memory.write8(0x0011, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.y << 8) | cpu.a, 0x0100)

    def test_a_word_subtraction_borrows_between_the_bytes(self) -> None:
        # Arrange
        cpu, memory = machine([0x9A, 0x10], a=0x00, y=0x01)
        memory.write8(0x0010, 0x01)
        memory.write8(0x0011, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.y << 8) | cpu.a, 0x00FF)

    def test_a_word_comparison_leaves_the_pair_alone(self) -> None:
        # Arrange
        cpu, memory = machine([0x5A, 0x10], a=0x34, y=0x12)
        memory.write8(0x0010, 0x34)
        memory.write8(0x0011, 0x12)

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.y << 8) | cpu.a, 0x1234)
        self.assertTrue(cpu.z)

    def test_a_word_increment_carries_into_the_high_byte(self) -> None:
        # Arrange
        cpu, memory = machine([0x3A, 0x10])
        memory.write8(0x0010, 0xFF)
        memory.write8(0x0011, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x00)
        self.assertEqual(memory.read8(0x0011), 0x01)

    def test_a_word_decrement_borrows_from_the_high_byte(self) -> None:
        # Arrange
        cpu, memory = machine([0x1A, 0x10])
        memory.write8(0x0010, 0x00)
        memory.write8(0x0011, 0x01)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0010), 0xFF)
        self.assertEqual(memory.read8(0x0011), 0x00)


class MultiplyDivideTest(unittest.TestCase):
    def test_a_multiply_fills_the_register_pair(self) -> None:
        # Arrange
        program = [0xCF]

        # Act
        cpu, _ = run(program, y=0x10, a=0x10)

        # Assert
        self.assertEqual((cpu.y << 8) | cpu.a, 0x0100)

    def test_a_multiply_sets_flags_from_the_high_byte(self) -> None:
        # Arrange
        program = [0xCF]

        # Act
        cpu, _ = run(program, y=0x00, a=0x00)

        # Assert
        self.assertTrue(cpu.z)

    def test_a_divide_gives_a_quotient_and_a_remainder(self) -> None:
        # Arrange
        program = [0x9E]

        # Act
        cpu, _ = run(program, y=0x00, a=0x0A, x=0x03)

        # Assert
        self.assertEqual(cpu.a, 0x03)
        self.assertEqual(cpu.y, 0x01)

    def test_a_divide_by_zero_does_not_raise(self) -> None:
        # Arrange
        program = [0x9E]

        # Act
        cpu, _ = run(program, y=0x01, a=0x00, x=0x00)

        # Assert
        self.assertIsInstance(cpu.a, int)


class IndexComparisonTest(unittest.TestCase):
    def test_an_index_comparison_leaves_the_index_alone(self) -> None:
        # Arrange
        program = [0xC8, 0x10]

        # Act
        cpu, _ = run(program, x=0x20)

        # Assert
        self.assertEqual(cpu.x, 0x20)
        self.assertTrue(cpu.c)

    def test_an_index_comparison_of_equals_sets_zero(self) -> None:
        # Arrange
        program = [0xC8, 0x20]

        # Act
        cpu, _ = run(program, x=0x20)

        # Assert
        self.assertTrue(cpu.z)

    def test_the_other_index_compares_the_same_way(self) -> None:
        # Arrange
        program = [0xAD, 0x20]

        # Act
        cpu, _ = run(program, y=0x20)

        # Assert
        self.assertTrue(cpu.z)
        self.assertEqual(cpu.y, 0x20)

    def test_an_index_comparison_below_clears_the_carry(self) -> None:
        # Arrange
        program = [0xAD, 0x30]

        # Act
        cpu, _ = run(program, y=0x20)

        # Assert
        self.assertFalse(cpu.c)


if __name__ == "__main__":
    unittest.main()

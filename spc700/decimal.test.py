import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import FLAG_C, FLAG_H, Cpu, Memory


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


class DecimalTest(unittest.TestCase):
    def test_a_decimal_adjust_after_add_carries_at_nine(self) -> None:
        # Arrange
        program = [0x60, 0x88, 0x01, 0xDF]

        # Act
        cpu, _ = run(program, steps=3, a=0x09)

        # Assert
        self.assertEqual(cpu.a, 0x10)

    def test_a_decimal_adjust_after_subtract_borrows_at_zero(self) -> None:
        # Arrange
        program = [0x80, 0xA8, 0x01, 0xBE]

        # Act
        cpu, _ = run(program, steps=3, a=0x10)

        # Assert
        self.assertEqual(cpu.a, 0x09)

    def test_a_decimal_adjust_above_ninety_nine_adds_sixty_and_carries(self) -> None:
        # Arrange
        program = [0xDF]

        # Act
        cpu, _ = run(program, a=0xAA, psw=0x00)

        # Assert
        self.assertEqual(cpu.a, 0x10)
        self.assertTrue(cpu.c)

    def test_a_decimal_adjust_with_the_carry_already_set_adds_sixty(self) -> None:
        # Arrange
        cpu, _ = machine([0xDF], a=0x11, psw=FLAG_C)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.a, 0x71)

    def test_a_decimal_adjust_reads_the_accumulator_it_just_changed(self) -> None:
        # Arrange
        program = [0xDF]

        # Act
        cpu, _ = run(program, a=0x9A, psw=0x00)

        # Assert
        self.assertEqual(cpu.a, 0x00)
        self.assertTrue(cpu.c)

    def test_a_decimal_adjust_leaves_a_valid_pair_alone(self) -> None:
        # Arrange
        program = [0xDF]

        # Act
        cpu, _ = run(program, a=0x42, psw=0x00)

        # Assert
        self.assertEqual(cpu.a, 0x42)

    def test_a_decimal_subtract_above_ninety_nine_takes_sixty_off(self) -> None:
        # Arrange
        cpu, _ = machine([0xBE], a=0xAA, psw=FLAG_C | FLAG_H)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.a, 0x44)
        self.assertFalse(cpu.c)

    def test_a_decimal_subtract_with_the_half_carry_set_leaves_the_nibble(self) -> None:
        # Arrange
        cpu, _ = machine([0xBE], a=0x42, psw=FLAG_C | FLAG_H)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.a, 0x42)

    def test_a_decimal_subtract_without_the_half_carry_takes_six_off(self) -> None:
        # Arrange
        cpu, _ = machine([0xBE], a=0x42, psw=FLAG_C)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.a, 0x3C)


if __name__ == "__main__":
    unittest.main()

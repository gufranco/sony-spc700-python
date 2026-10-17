import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import FLAG_C, FLAG_H, FLAG_V, Cpu, Memory


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


class BitTest(unittest.TestCase):
    def test_setting_a_bit_leaves_the_others_alone(self) -> None:
        # Arrange
        cpu, memory = machine([0x02, 0x10])
        memory.write8(0x0010, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x01)

    def test_setting_the_top_bit_uses_the_opcode_index(self) -> None:
        # Arrange
        cpu, memory = machine([0xE2, 0x10])
        memory.write8(0x0010, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x80)

    def test_clearing_a_bit_leaves_the_others_alone(self) -> None:
        # Arrange
        cpu, memory = machine([0x12, 0x10])
        memory.write8(0x0010, 0xFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0010), 0xFE)

    def test_a_test_and_set_leaves_the_bits_of_the_accumulator(self) -> None:
        # Arrange
        cpu, memory = machine([0x0E, 0x00, 0x03], a=0x0F)
        memory.write8(0x0300, 0xF0)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0300), 0xFF)

    def test_a_test_and_clear_removes_the_bits_of_the_accumulator(self) -> None:
        # Arrange
        cpu, memory = machine([0x4E, 0x00, 0x03], a=0x0F)
        memory.write8(0x0300, 0xFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0300), 0xF0)

    def test_a_carry_load_takes_the_addressed_bit(self) -> None:
        # Arrange
        cpu, memory = machine([0xAA, 0x00, 0xE0])
        memory.write8(0x0000, 0x80)

        # Act
        cpu.step()

        # Assert
        self.assertTrue(cpu.c)

    def test_a_carry_store_writes_the_addressed_bit(self) -> None:
        # Arrange
        cpu, memory = machine([0xCA, 0x00, 0xE0], psw=FLAG_C)
        memory.write8(0x0000, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0000), 0x80)

    def test_an_inverted_carry_load_takes_the_complement(self) -> None:
        # Arrange
        cpu, memory = machine([0x6A, 0x00, 0xE0], psw=FLAG_C)
        memory.write8(0x0000, 0x80)

        # Act
        cpu.step()

        # Assert
        self.assertFalse(cpu.c)

    def test_a_bit_complement_flips_the_addressed_bit(self) -> None:
        # Arrange
        cpu, memory = machine([0xEA, 0x00, 0xE0])
        memory.write8(0x0000, 0x80)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0000), 0x00)


class FlagTest(unittest.TestCase):
    def test_the_carry_can_be_set_and_cleared(self) -> None:
        # Arrange
        program = [0x80, 0x60]

        # Act
        cpu, _ = run(program, steps=2)

        # Assert
        self.assertFalse(cpu.c)

    def test_the_carry_can_be_complemented(self) -> None:
        # Arrange
        program = [0xED]

        # Act
        cpu, _ = run(program, psw=0x00)

        # Assert
        self.assertTrue(cpu.c)

    def test_the_overflow_flag_clears_the_half_carry_with_it(self) -> None:
        # Arrange
        cpu, _ = machine([0xE0], psw=FLAG_V | FLAG_H)

        # Act
        cpu.step()

        # Assert
        self.assertFalse(cpu.v)
        self.assertFalse(cpu.h)

    def test_the_page_flag_can_be_set_and_cleared(self) -> None:
        # Arrange
        program = [0x40, 0x20]

        # Act
        cpu, _ = run(program, steps=2)

        # Assert
        self.assertEqual(cpu.direct_page, 0x0000)

    def test_the_interrupt_flag_can_be_set_and_cleared(self) -> None:
        # Arrange
        program = [0xA0, 0xC0]

        # Act
        cpu, _ = run(program, steps=2)

        # Assert
        self.assertFalse(cpu.i)


if __name__ == "__main__":
    unittest.main()

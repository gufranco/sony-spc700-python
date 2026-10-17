import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import Cpu, Memory

BREAK_VECTOR = 0xFFDE


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


class BranchTest(unittest.TestCase):
    def test_an_unconditional_branch_moves_the_program_counter(self) -> None:
        # Arrange
        program = [0x2F, 0x02]

        # Act
        cpu, _ = run(program)

        # Assert
        self.assertEqual(cpu.pc, 0x0204)

    def test_a_branch_taken_on_zero_moves(self) -> None:
        # Arrange
        program = [0xE8, 0x00, 0xF0, 0x02]

        # Act
        cpu, _ = run(program, steps=2)

        # Assert
        self.assertEqual(cpu.pc, 0x0206)

    def test_a_branch_not_taken_falls_through(self) -> None:
        # Arrange
        program = [0xE8, 0x01, 0xF0, 0x02]

        # Act
        cpu, _ = run(program, steps=2)

        # Assert
        self.assertEqual(cpu.pc, 0x0204)

    def test_a_branch_on_bit_set_is_taken(self) -> None:
        # Arrange
        cpu, memory = machine([0x03, 0x10, 0x02])
        memory.write8(0x0010, 0x01)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.pc, 0x0205)

    def test_a_branch_on_bit_clear_is_taken(self) -> None:
        # Arrange
        cpu, memory = machine([0x13, 0x10, 0x02])
        memory.write8(0x0010, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.pc, 0x0205)

    def test_a_compare_and_branch_is_taken_when_they_differ(self) -> None:
        # Arrange
        cpu, memory = machine([0x2E, 0x10, 0x02], a=0x01)
        memory.write8(0x0010, 0x02)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.pc, 0x0205)

    def test_a_decrement_and_branch_is_taken_until_zero(self) -> None:
        # Arrange
        cpu, memory = machine([0x6E, 0x10, 0x02])
        memory.write8(0x0010, 0x02)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x01)
        self.assertEqual(cpu.pc, 0x0205)

    def test_a_decrement_and_branch_on_the_index_stops_at_zero(self) -> None:
        # Arrange
        program = [0xFE, 0x02]

        # Act
        cpu, _ = run(program, y=0x01)

        # Assert
        self.assertEqual(cpu.y, 0x00)
        self.assertEqual(cpu.pc, 0x0202)


class ControlTest(unittest.TestCase):
    def test_a_jump_moves_the_program_counter(self) -> None:
        # Arrange
        program = [0x5F, 0x00, 0x03]

        # Act
        cpu, _ = run(program)

        # Assert
        self.assertEqual(cpu.pc, 0x0300)

    def test_an_indexed_indirect_jump_reads_its_target(self) -> None:
        # Arrange
        cpu, memory = machine([0x1F, 0x00, 0x03], x=0x02)
        memory.write8(0x0302, 0x00)
        memory.write8(0x0303, 0x04)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.pc, 0x0400)

    def test_a_call_pushes_the_return_address(self) -> None:
        # Arrange
        program = [0x3F, 0x00, 0x03]

        # Act
        cpu, memory = run(program)

        # Assert
        self.assertEqual(cpu.pc, 0x0300)
        self.assertEqual(memory.read8(0x01EF), 0x02)
        self.assertEqual(memory.read8(0x01EE), 0x03)

    def test_a_return_takes_the_address_back_off(self) -> None:
        # Arrange
        program = [0x3F, 0x05, 0x02, 0x00, 0x00, 0x6F]

        # Act
        cpu, _ = run(program, steps=2)

        # Assert
        self.assertEqual(cpu.pc, 0x0203)

    def test_a_page_call_jumps_into_the_top_page(self) -> None:
        # Arrange
        program = [0x4F, 0x40]

        # Act
        cpu, _ = run(program)

        # Assert
        self.assertEqual(cpu.pc, 0xFF40)

    def test_a_table_call_reads_its_vector(self) -> None:
        # Arrange
        cpu, memory = machine([0x01])
        memory.write8(0xFFDE, 0x00)
        memory.write8(0xFFDF, 0x05)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.pc, 0x0500)

    def test_a_break_takes_its_vector_and_sets_the_break_flag(self) -> None:
        # Arrange
        cpu, memory = machine([0x0F])
        memory.write8(BREAK_VECTOR, 0x00)
        memory.write8(BREAK_VECTOR + 1, 0x06)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.pc, 0x0600)
        self.assertTrue(cpu.b)
        self.assertFalse(cpu.i)

    def test_a_return_from_interrupt_restores_the_status(self) -> None:
        # Arrange
        cpu, memory = machine([0x7F])
        memory.write8(0x01F0, 0xAA)
        memory.write8(0x01F1, 0x34)
        memory.write8(0x01F2, 0x12)
        cpu.sp = 0xEF

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.psw, 0xAA)
        self.assertEqual(cpu.pc, 0x1234)


if __name__ == "__main__":
    unittest.main()

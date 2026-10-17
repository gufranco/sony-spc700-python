import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import FLAG_P, Cpu, Memory


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


class MoveTest(unittest.TestCase):
    def test_an_immediate_load_sets_the_accumulator(self) -> None:
        # Arrange
        program = [0xE8, 0x42]

        # Act
        cpu, _ = run(program)

        # Assert
        self.assertEqual(cpu.a, 0x42)

    def test_a_load_sets_the_negative_flag(self) -> None:
        # Arrange
        program = [0xE8, 0x80]

        # Act
        cpu, _ = run(program)

        # Assert
        self.assertTrue(cpu.n)

    def test_a_load_sets_the_zero_flag(self) -> None:
        # Arrange
        program = [0xE8, 0x00]

        # Act
        cpu, _ = run(program)

        # Assert
        self.assertTrue(cpu.z)

    def test_a_store_leaves_the_flags_alone(self) -> None:
        # Arrange
        program = [0xC4, 0x10]

        # Act
        cpu, memory = run(program, a=0x00)

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x00)
        self.assertFalse(cpu.z)

    def test_a_direct_page_store_follows_the_page_flag(self) -> None:
        # Arrange
        cpu, memory = machine([0xC4, 0x10], a=0x5A, psw=FLAG_P)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0110), 0x5A)

    def test_an_indirect_store_uses_the_index_register(self) -> None:
        # Arrange
        program = [0xC6]

        # Act
        _, memory = run(program, a=0x77, x=0x30)

        # Assert
        self.assertEqual(memory.read8(0x0030), 0x77)

    def test_a_post_increment_store_advances_the_index(self) -> None:
        # Arrange
        program = [0xAF]

        # Act
        cpu, memory = run(program, a=0x99, x=0x40)

        # Assert
        self.assertEqual(memory.read8(0x0040), 0x99)
        self.assertEqual(cpu.x, 0x41)

    def test_a_post_increment_load_advances_the_index(self) -> None:
        # Arrange
        cpu, memory = machine([0xBF], x=0x40)
        memory.write8(0x0040, 0x3C)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.a, 0x3C)
        self.assertEqual(cpu.x, 0x41)

    def test_a_direct_to_direct_move_leaves_the_flags_alone(self) -> None:
        # Arrange
        cpu, memory = machine([0xFA, 0x10, 0x20])
        memory.write8(0x0010, 0x00)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(memory.read8(0x0020), 0x00)
        self.assertFalse(cpu.z)

    def test_transferring_the_stack_pointer_into_the_index_sets_flags(self) -> None:
        # Arrange
        program = [0x9D]

        # Act
        cpu, _ = run(program, sp=0x00)

        # Assert
        self.assertTrue(cpu.z)

    def test_transferring_the_index_into_the_stack_pointer_leaves_flags(self) -> None:
        # Arrange
        program = [0xBD]

        # Act
        cpu, _ = run(program, x=0x00)

        # Assert
        self.assertEqual(cpu.sp, 0x00)
        self.assertFalse(cpu.z)


class StackTest(unittest.TestCase):
    def test_a_push_lowers_the_stack_pointer(self) -> None:
        # Arrange
        program = [0x2D]

        # Act
        cpu, memory = run(program, a=0x5A)

        # Assert
        self.assertEqual(cpu.sp, 0xEE)
        self.assertEqual(memory.read8(0x01EF), 0x5A)

    def test_a_pull_raises_the_stack_pointer(self) -> None:
        # Arrange
        cpu, memory = machine([0xAE])
        memory.write8(0x01F0, 0x3C)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.a, 0x3C)
        self.assertEqual(cpu.sp, 0xF0)

    def test_a_pushed_value_comes_back(self) -> None:
        # Arrange
        program = [0x2D, 0xE8, 0x00, 0xAE]

        # Act
        cpu, _ = run(program, steps=3, a=0x77)

        # Assert
        self.assertEqual(cpu.a, 0x77)

    def test_the_stack_pointer_wraps_inside_its_page(self) -> None:
        # Arrange
        program = [0x2D]

        # Act
        cpu, memory = run(program, sp=0x00, a=0x11)

        # Assert
        self.assertEqual(cpu.sp, 0xFF)
        self.assertEqual(memory.read8(0x0100), 0x11)

    def test_the_status_register_survives_a_push_and_pull(self) -> None:
        # Arrange
        program = [0x0D, 0x8E]

        # Act
        cpu, _ = run(program, steps=2, psw=0xC5)

        # Assert
        self.assertEqual(cpu.psw, 0xC5)


class AddressingGuardTest(unittest.TestCase):
    def test_a_mode_that_names_no_address_is_refused(self) -> None:
        # Arrange
        cpu, _ = machine([0x00])

        # Act
        with self.assertRaises(KeyError) as raised:
            cpu.operand_address("implied", 0x00)

        # Assert
        self.assertEqual(raised.exception.args, ("implied does not name an address",))


if __name__ == "__main__":
    unittest.main()

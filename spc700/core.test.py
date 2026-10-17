import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import FLAG_P, OPCODES, Cpu, Memory, RunLimit

RESET_VECTOR = 0xFFFE


def built(memory: Memory, **options: Any) -> Any:
    return Cpu("spc700", memory, **options)


def machine(code: Sequence[int], base: int = 0x0200, fill: int = 0) -> tuple[Any, Memory]:
    memory = Memory(fill=fill)
    for offset, byte in enumerate(code):
        memory.write8(base + offset, byte)
    cpu = built(memory)
    cpu.psw = 0x00
    cpu.a = cpu.x = cpu.y = 0x00
    cpu.pc = base
    cpu.sp = 0xEF
    return cpu, memory


def run(code: Sequence[int], steps: int = 1) -> tuple[Any, Memory]:
    cpu, memory = machine(code)
    for _ in range(steps):
        cpu.step()
    return cpu, memory


def ready(opcode: int) -> Any:
    memory = Memory(seed=opcode)
    memory.write8(0x0200, opcode)
    cpu = built(memory)
    cpu.pc = 0x0200
    return cpu


class ResetTest(unittest.TestCase):
    def test_the_program_counter_comes_from_the_reset_vector(self) -> None:
        # Arrange
        memory = Memory(fill=0)
        memory.write8(RESET_VECTOR, 0x00)
        memory.write8(RESET_VECTOR + 1, 0xFF)
        cpu = built(memory)

        # Act
        cpu.reset()

        # Assert
        self.assertEqual(cpu.pc, 0xFF00)

    def test_the_part_is_handed_back_so_the_call_chains(self) -> None:
        # Arrange
        cpu = built(Memory(fill=0))

        # Act
        back = cpu.reset()

        # Assert
        self.assertIs(back, cpu)

    def test_but_only_once_a_caller_drives_the_pin(self) -> None:
        # Arrange
        memory = Memory(fill=0)
        memory.write8(RESET_VECTOR, 0x00)
        memory.write8(RESET_VECTOR + 1, 0xFF)

        # Act
        cpu = built(memory)

        # Assert
        self.assertNotEqual(cpu.pc, 0xFF00)

    def test_and_the_program_counter_comes_up_holding_something(self) -> None:
        # Arrange
        seeds = range(8)

        # Act
        held = {built(Memory(fill=0), seed=one).pc for one in seeds}

        # Assert
        self.assertGreater(len(held), 1)

    def test_the_registers_are_not_assumed_clear(self) -> None:
        # Arrange
        memory = Memory(fill=0)

        # Act
        cpu = built(memory)

        # Assert
        self.assertNotEqual((cpu.a, cpu.x, cpu.y), (0, 0, 0))

    def test_a_reset_repeats_for_one_seed(self) -> None:
        # Arrange
        one = built(Memory(fill=0), seed=11)

        # Act
        other = built(Memory(fill=0), seed=11)

        # Assert
        self.assertEqual((one.a, one.x, one.y, one.sp), (other.a, other.x, other.y, other.sp))

    def test_a_different_seed_gives_a_different_machine(self) -> None:
        # Arrange
        one = built(Memory(fill=0), seed=1)

        # Act
        other = built(Memory(fill=0), seed=2)

        # Assert
        self.assertNotEqual((one.a, one.x, one.y), (other.a, other.x, other.y))


class StatusTest(unittest.TestCase):
    def test_every_flag_survives_a_round_trip(self) -> None:
        cpu, _ = machine([0x00])

        cpu.psw = 0xFF

        self.assertEqual(cpu.psw, 0xFF)

    def test_no_flag_set_reads_back_as_zero(self) -> None:
        cpu, _ = machine([0x00])

        cpu.psw = 0x00

        self.assertEqual(cpu.psw, 0x00)

    def test_the_page_flag_moves_the_direct_page(self) -> None:
        # Arrange
        cpu, _ = machine([0x00])

        # Act
        cpu.psw = FLAG_P

        # Assert
        self.assertEqual(cpu.direct_page, 0x0100)

    def test_the_direct_page_is_the_bottom_page_without_it(self) -> None:
        cpu, _ = machine([0x00])

        cpu.psw = 0x00

        self.assertEqual(cpu.direct_page, 0x0000)


class HaltTest(unittest.TestCase):
    def test_a_sleep_stops_the_processor(self) -> None:
        cpu, _ = run([0xEF])

        self.assertTrue(cpu.stopped)

    def test_a_stop_stops_the_processor(self) -> None:
        cpu, _ = run([0xFF])

        self.assertTrue(cpu.stopped)

    def test_a_stopped_processor_stays_where_it_is(self) -> None:
        cpu, _ = run([0xFF, 0x00], steps=2)

        self.assertEqual(cpu.pc, 0x0201)

    def test_running_until_a_condition_returns_the_machine(self) -> None:
        cpu, _ = machine([0x00])

        self.assertIs(cpu.run_until(lambda found: found.steps > 0), cpu)

    def test_a_call_of_its_own_can_be_bounded_shorter_than_the_part_s(self) -> None:
        cpu, _ = machine([0x00])

        with self.assertRaises(RunLimit):
            cpu.run_until(lambda found: False, limit=4)

    def test_and_that_bound_is_the_one_the_message_names(self) -> None:
        cpu, _ = machine([0x00])

        with self.assertRaises(RunLimit) as raised:
            cpu.run_until(lambda found: False, limit=4)

        self.assertIn("gave up after 4", str(raised.exception))

    def test_a_run_that_never_settles_is_stopped(self) -> None:
        cpu, _ = machine([0x2F, 0xFE])
        cpu.step_limit = 100

        with self.assertRaises(RunLimit):
            cpu.run_until(lambda found: False)


class EveryOpcodeTest(unittest.TestCase):
    def test_every_opcode_executes(self) -> None:
        # Arrange
        parts = [ready(opcode) for opcode in range(256)]

        # Act
        costs = [cpu.step() for cpu in parts]

        # Assert
        self.assertEqual([cpu.steps for cpu in parts], [1] * 256)
        self.assertEqual([opcode for opcode, cost in enumerate(costs) if cost < 2], [])

    def test_every_opcode_has_an_implementation_behind_it(self) -> None:
        # Arrange
        cpu = built(Memory(fill=0))

        # Act
        missing = [
            f"${opcode:02X} {mnemonic}"
            for opcode, (mnemonic, _, _) in enumerate(OPCODES)
            if not hasattr(cpu, f"op_{mnemonic}")
        ]

        # Assert
        self.assertEqual(missing, [])


class ResetDirectPageTest(unittest.TestCase):
    def test_reset_leaves_the_direct_page_flag_clear(self) -> None:
        cpu, _memory = machine([0x00])

        cpu.reset(seed=1)

        self.assertFalse(cpu.p)

    def test_it_stays_clear_whatever_the_scramble_produced(self) -> None:
        cpu, _memory = machine([0x00])

        clear = []
        for seed in range(64):
            cpu.reset(seed=seed)
            clear.append(cpu.p)

        self.assertEqual(set(clear), {False})

    def test_the_rest_of_the_flag_word_is_still_scrambled(self) -> None:
        cpu, _memory = machine([0x00])

        seen = set()
        for seed in range(64):
            cpu.reset(seed=seed)
            seen.add(cpu.psw)

        self.assertGreater(len(seen), 1)

    def test_a_direct_page_write_after_reset_reaches_the_zero_page(self) -> None:
        cpu, memory = machine([0x8F, 0xAA, 0xF4])
        cpu.reset(seed=7)
        cpu.pc = 0x0200

        cpu.step()

        self.assertEqual(memory.read8(0x00F4), 0xAA)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import threading
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import spc700  # noqa: E402

NOP = 0x00

ORIGIN = 0x0200

INSTRUCTIONS = 4

BUDGET = 8

PATIENCE_SECONDS = 10.0


def a_run_of_nops() -> Any:
    cpu = spc700.Cpu("spc700", spc700.Memory(fill=NOP))
    cpu.psw = 0x00
    cpu.pc = ORIGIN
    return cpu


def stepped(instructions: int) -> tuple[int, int, int]:
    cpu = a_run_of_nops()
    for _ in range(instructions):
        cpu.step()
    return cpu.steps, cpu.cycles, cpu.pc


def within(call: Callable[[], Any]) -> tuple[str, Any]:
    outcome: list[tuple[str, Any]] = []

    def attempt() -> None:
        try:
            outcome.append(("returned", call()))
        except Exception as raised:  # noqa: BLE001
            outcome.append(("raised", raised))

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(PATIENCE_SECONDS)
    return outcome[0] if outcome else ("still running", None)


def clocked_then_closed(budget: int) -> tuple[int, int, int]:
    cpu = a_run_of_nops()
    with spc700.Clock(cpu) as clock:
        clock.run_for(budget)
    return cpu.steps, cpu.cycles, cpu.pc


class ClockTest(unittest.TestCase):
    def part(self) -> Any:
        self.memory = spc700.Memory(fill=0x00)
        for at, byte in enumerate((0xE4, 0x10, 0x00, 0x00)):
            self.memory.write8(at, byte)
        self.memory.write8(0x0010, 0x11)
        cpu = spc700.Cpu("spc700", self.memory)
        cpu.psw = 0x00
        cpu.pc = 0x0000
        return cpu

    def test_a_tick_spends_exactly_one_cycle(self) -> None:
        cpu = self.part()
        before = cpu.cycles

        with spc700.Clock(cpu) as clock:
            clock.tick()

        self.assertEqual((clock.cycles, cpu.cycles - before), (1, 1))

    def test_a_budget_stops_between_cycles_rather_than_overshooting(self) -> None:
        cpu = self.part()

        with spc700.Clock(cpu) as clock:
            spent = clock.run_for(7)

        self.assertEqual(spent, 7)

    def test_the_part_is_suspended_part_way_through_an_instruction(self) -> None:
        cpu = self.part()
        cpu.bus.recording = True

        with spc700.Clock(cpu) as clock:
            clock.tick()
            self.memory.write8(0x0010, 0x99)
            clock.run_for(2)

            held = [value for _, value, _ in cpu.bus.log]

        self.assertIn(0x99, held)

    def test_a_budget_on_a_running_part_overshoots_rather_than_cutting_one_short(
        self,
    ) -> None:
        cpu = self.part()

        spent = cpu.run_for(2)

        self.assertGreaterEqual(spent, 2)
        self.assertEqual(spent, cpu.cycles)

    def test_a_stopped_part_still_costs_its_host_the_whole_budget(self) -> None:
        space = spc700.Memory(fill=0x00)
        space.write8(0x0000, 0xFF)
        cpu = spc700.Cpu("spc700", space)
        cpu.psw = 0x00
        cpu.pc = 0x0000
        cpu.run_for(16)
        before = cpu.cycles

        spent = cpu.run_for(32)

        self.assertEqual((spent, cpu.cycles - before, cpu.held()), (32, 32, True))

    def test_a_jammed_part_keeps_costing_cycles_under_a_clock(self) -> None:
        space = spc700.Memory(fill=0x00)
        space.write8(0x0000, 0xFF)
        cpu = spc700.Cpu("spc700", space)
        cpu.psw = 0x00
        cpu.pc = 0x0000

        with spc700.Clock(cpu) as clock:
            clock.run_for(20)

        self.assertEqual((clock.cycles, cpu.held()), (20, True))

    def test_a_clock_can_be_iterated(self) -> None:
        cpu = self.part()

        with spc700.Clock(cpu) as clock:
            spent = [total for total, _ in zip(clock, range(4), strict=False)]

        self.assertEqual(spent, [1, 2, 3, 4])

    def test_iteration_ends_when_the_clock_is_closed(self) -> None:
        # Arrange
        clock = spc700.Clock(self.part())
        clock.close()

        # Act
        found = within(lambda: list(clock))

        # Assert
        self.assertEqual(found, ("returned", []))

    def test_a_closed_clock_refuses_to_tick(self) -> None:
        # Arrange
        clock = spc700.Clock(self.part())
        clock.close()

        # Act
        kind, raised = within(clock.tick)

        # Assert
        self.assertEqual(
            (kind, type(raised).__name__, str(raised)),
            ("raised", "ClockClosed", "this clock has been closed"),
        )

    def test_closing_twice_is_not_an_error(self) -> None:
        clock = spc700.Clock(self.part())
        clock.close()

        clock.close()

        self.assertTrue(clock.closed)

    def test_closing_gives_the_part_its_hook_back(self) -> None:
        cpu = self.part()
        watched: list[int] = []
        cpu.on_cycle = lambda: watched.append(1)

        with spc700.Clock(cpu) as clock:
            clock.tick()
        cpu.step()

        self.assertEqual((clock.cycles, bool(watched)), (1, True))

    def test_a_failure_inside_the_part_reaches_the_driver(self) -> None:
        cpu = self.part()
        clock = spc700.Clock(cpu)
        self.addCleanup(clock.close)

        def explode() -> None:
            raise RuntimeError("a device said no")

        clock.tick()
        cpu.on_cycle = explode

        with self.assertRaises(RuntimeError):
            clock.run_for(8)

    def test_and_the_clock_refuses_to_go_on_afterwards(self) -> None:
        cpu = self.part()
        clock = spc700.Clock(cpu)
        self.addCleanup(clock.close)

        def explode() -> None:
            raise RuntimeError("a device said no")

        clock.tick()
        cpu.on_cycle = explode
        with self.assertRaises(RuntimeError):
            clock.run_for(8)

        with self.assertRaises(spc700.ClockClosed):
            clock.tick()


class CountedLikeAStepTest(unittest.TestCase):
    def test_a_clock_counts_the_same_instructions_and_cycles_as_stepping(self) -> None:
        # Arrange
        cpu = a_run_of_nops()
        clock = spc700.Clock(cpu)
        self.addCleanup(clock.close)

        # Act
        clock.run_for(BUDGET)

        # Assert
        self.assertEqual(
            ((cpu.steps, cpu.cycles, cpu.pc), stepped(INSTRUCTIONS)),
            ((4, 8, 0x0204),) * 2,
        )

    def test_and_still_does_once_the_clock_is_closed(self) -> None:
        # Arrange
        expected = stepped(INSTRUCTIONS)

        # Act
        found = within(lambda: clocked_then_closed(BUDGET))

        # Assert
        self.assertEqual((found, expected), (("returned", (4, 8, 0x0204)), (4, 8, 0x0204)))


if __name__ == "__main__":
    unittest.main()

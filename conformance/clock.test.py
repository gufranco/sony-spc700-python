"""That a part can be driven one cycle at a time, and stopped between any two.

The claim worth testing is not that the count comes out right. It is that the
part is genuinely suspended part way through an instruction, which is shown by
changing what memory answers between two cycles and watching the instruction
pick the new value up. A model that ran the instruction and replayed its cycles
afterwards would pass a count test and fail that one.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import spc700  # noqa: E402


class ClockTest(unittest.TestCase):
    def part(self) -> Any:
        """A part in a state this file chose, rather than the one a rail leaves.

        The flags are cleared, which matters most for `P`: a scrambled
        direct-page bit sends the read below into page one, where nothing was
        written, and the test then measures where it landed rather than when.
        """
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
        """A write landing between two cycles of one instruction is seen by it.

        That is the whole point of a clock: the part is stopped inside an
        instruction, not between two of them, so a board can change what the next
        read answers.

        The log is read inside the block and while the instruction is the one in
        flight, because the bus forgets the previous instruction when the next
        one starts. Reading it afterwards finds an empty list and proves nothing.
        """
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
        """An instruction is not divisible, so the budget is a floor.

        A host carries the difference into the next slice rather than discarding
        it, and a long run does not drift.
        """
        cpu = self.part()

        spent = cpu.run_for(2)

        self.assertGreaterEqual(spent, 2)
        self.assertEqual(spent, cpu.cycles)

    def test_a_stopped_part_still_costs_its_host_the_whole_budget(self) -> None:
        """The board's clock has not stopped just because the processor has.

        A host pacing against a wall has to be told the time passed, so a budget
        handed to a stopped part comes back spent rather than short.
        """
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
        clock = spc700.Clock(self.part())
        clock.close()

        self.assertEqual(list(clock), [])

    def test_a_closed_clock_refuses_to_tick(self) -> None:
        clock = spc700.Clock(self.part())
        clock.close()

        with self.assertRaises(spc700.ClockClosed):
            clock.tick()

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


if __name__ == "__main__":
    unittest.main()

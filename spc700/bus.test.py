import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import Bus, Cpu, Memory

READ = "read"
WRITE = "write"
WAIT = "wait"


def a_part(program: bytes, at: int = 0x0000, recording: bool = True) -> Any:
    memory = Memory(fill=0)
    for offset, byte in enumerate(program):
        memory.write8((at + offset) & 0xFFFF, byte)
    cpu = Cpu("spc700", memory).reset()
    cpu.pc = at
    cpu.bus.recording = recording
    return cpu


class RecordingTest(unittest.TestCase):
    def test_a_bus_that_is_not_recording_keeps_nothing(self) -> None:
        # Arrange
        cpu = a_part(bytes([0xE8, 0x42]), recording=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.log, [])

    def test_a_recording_bus_keeps_a_read_with_the_value_it_returned(self) -> None:
        # Arrange
        cpu = a_part(bytes([0xE8, 0x42]))

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.log, [(0x0000, 0xE8, READ), (0x0001, 0x42, READ)])

    def test_a_write_records_the_value_that_went_out(self) -> None:
        # Arrange
        cpu = a_part(bytes([0xC4, 0x10]))
        cpu.a = 0xAB
        cpu.p = False

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.log[-1], (0x0010, 0xAB, WRITE))

    def test_an_internal_cycle_names_no_address(self) -> None:
        # Arrange
        cpu = a_part(bytes([0x9E]))

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.log[2], (None, None, WAIT))

    def test_several_internal_cycles_are_recorded_one_by_one(self) -> None:
        # Arrange
        cpu = a_part(bytes([0x9E]))

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.log[2:], [(None, None, WAIT)] * 10)


class CountingTest(unittest.TestCase):
    def test_a_bus_that_is_not_recording_still_counts(self) -> None:
        # Arrange
        cpu = a_part(bytes([0x9E]), recording=False)

        # Act
        cost = cpu.step()

        # Assert
        self.assertEqual((cost, cpu.bus.cycles), (12, 12))

    def test_the_count_and_the_log_cover_only_the_instruction_in_progress(self) -> None:
        # Arrange
        cpu = a_part(bytes([0x9E, 0xE8, 0x42]))
        cpu.step()

        # Act
        cost = cpu.step()

        # Assert
        self.assertEqual(
            (cost, cpu.bus.cycles, cpu.bus.log),
            (2, 2, [(0x0001, 0xE8, READ), (0x0002, 0x42, READ)]),
        )


class MaskingTest(unittest.TestCase):
    def test_an_address_past_the_space_wraps(self) -> None:
        # Arrange
        cpu = a_part(bytes([0x1F, 0xFF, 0xFF]), at=0x0200)
        cpu.x = 0x00

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.log[-2:], [(0xFFFF, 0x00, READ), (0x0000, 0x00, READ)])

    def test_a_value_past_a_byte_is_kept_to_one(self) -> None:
        # Arrange
        cpu = a_part(bytes([0x3F, 0x34, 0x12]), at=0x0200)
        cpu.sp = 0xEF

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            [entry for entry in cpu.bus.log if entry[2] == WRITE],
            [(0x01EF, 0x02, WRITE), (0x01EE, 0x03, WRITE)],
        )


class StandaloneTest(unittest.TestCase):
    def test_a_bus_with_no_part_behind_it_still_counts(self) -> None:
        # Arrange
        line = Bus()
        line.read(0x1234, 0x56)
        line.write(0x1234, 0x78)

        # Act
        line.idle(2)

        # Assert
        self.assertEqual((line.cycles, line.log), (4, []))

    def test_and_records_what_it_is_handed_kept_to_the_space_and_a_byte(self) -> None:
        # Arrange
        line = Bus(recording=True)

        # Act
        line.read(0x1_0001, 0x1FF)

        # Assert
        self.assertEqual(line.log, [(0x0001, 0xFF, READ)])

    def test_a_bus_handed_to_a_part_is_the_one_it_spends_through(self) -> None:
        # Arrange
        line = Bus(recording=True)
        cpu = Cpu("spc700", Memory(image=bytes([0xE8, 0x42]), fill=0), bus=line).reset()

        # Act
        cost = cpu.step()

        # Assert
        self.assertIs(cpu.bus, line)
        self.assertEqual(
            (cost, line.cycles, line.log),
            (2, 2, [(0x0000, 0xE8, READ), (0x0001, 0x42, READ)]),
        )


if __name__ == "__main__":
    unittest.main(verbosity=1)

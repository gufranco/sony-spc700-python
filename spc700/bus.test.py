"""What the bus records, and what it deliberately does not."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import bus as module
from spc700.bus import Bus


class RecordingTest(unittest.TestCase):
    def test_a_bus_that_is_not_recording_keeps_nothing(self) -> None:
        line = Bus()

        line.read(0x1234, 0x56)

        self.assertEqual(line.log, [])

    def test_a_recording_bus_keeps_a_read_with_the_value_it_returned(self) -> None:
        line = Bus(recording=True)

        line.read(0x1234, 0x56)

        self.assertEqual(line.log, [(0x1234, 0x56, module.READ)])

    def test_a_write_records_the_value_that_went_out(self) -> None:
        line = Bus(recording=True)

        line.write(0x00F0, 0xAB)

        self.assertEqual(line.log, [(0x00F0, 0xAB, module.WRITE)])

    def test_an_internal_cycle_names_no_address(self) -> None:
        line = Bus(recording=True)

        line.idle()

        self.assertEqual(line.log, [(None, None, module.WAIT)])

    def test_several_internal_cycles_are_recorded_one_by_one(self) -> None:
        line = Bus(recording=True)

        line.idle(3)

        self.assertEqual(line.log, [(None, None, module.WAIT)] * 3)


class CountingTest(unittest.TestCase):
    def test_a_bus_that_is_not_recording_still_counts(self) -> None:
        line = Bus()

        line.read(0x1234, 0x56)
        line.write(0x1234, 0x78)
        line.idle(2)

        self.assertEqual(line.cycles, 4)

    def test_counting_survives_a_cleared_log(self) -> None:
        line = Bus(recording=True)
        line.read(0x1234, 0x56)

        line.restart()

        self.assertEqual((line.log, line.cycles), ([], 0))


class MaskingTest(unittest.TestCase):
    def test_an_address_past_the_space_wraps(self) -> None:
        line = Bus(recording=True)

        line.read(0x1_0001, 0x00)

        self.assertEqual(line.log[0][0], 0x0001)

    def test_a_value_past_a_byte_is_kept_to_one(self) -> None:
        line = Bus(recording=True)

        line.write(0x0000, 0x1FF)

        self.assertEqual(line.log[0][1], 0xFF)


if __name__ == "__main__":
    unittest.main(verbosity=1)

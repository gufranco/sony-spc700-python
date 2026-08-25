import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spc700
from spc700 import models
from spc700.errors import UnknownModelError
from spc700.memory import Memory


class CatalogueTest(unittest.TestCase):
    def test_the_family_names_every_model_it_covers(self) -> None:
        self.assertIn("spc700", models.MODELS)

    def test_a_model_says_what_it_is_and_what_it_reaches(self) -> None:
        found = models.describe("spc700")

        self.assertTrue(found.summary)
        self.assertEqual(found.address_bits, 16)
        self.assertEqual(found.data_bits, 8)

    def test_a_model_name_is_matched_however_it_is_written(self) -> None:
        for written in ("SPC700", "spc-700", "s_smp", "SPC_700"):
            self.assertEqual(models.describe(written).name, "spc700")

    def test_a_model_the_family_does_not_have_is_refused_by_name(self) -> None:
        with self.assertRaises(UnknownModelError):
            models.describe("z80")

    def test_the_refusal_lists_what_is_available(self) -> None:
        with self.assertRaises(UnknownModelError) as raised:
            models.describe("nonsense")

        self.assertIn("spc700", str(raised.exception))

    def test_the_address_mask_follows_the_address_bits(self) -> None:
        self.assertEqual(models.describe("spc700").address_mask, 0xFFFF)

    def test_a_model_prints_as_its_name_and_reach(self) -> None:
        printed = repr(models.describe("spc700"))

        self.assertIn("spc700", printed)
        self.assertIn("16", printed)


class BuildTest(unittest.TestCase):
    def test_a_processor_is_built_from_its_model_name(self) -> None:
        cpu = spc700.Cpu("spc700", Memory(fill=0))

        self.assertEqual(cpu.model, "spc700")

    def test_the_default_model_is_the_one_the_console_carries(self) -> None:
        cpu = spc700.Cpu(memory=Memory(fill=0))

        self.assertEqual(cpu.model, "spc700")

    def test_options_reach_the_processor_that_gets_built(self) -> None:
        cpu = spc700.Cpu("spc700", Memory(fill=0), step_limit=17)

        self.assertEqual(cpu.step_limit, 17)

    def test_a_model_the_family_does_not_have_is_refused_at_construction(self) -> None:
        with self.assertRaises(UnknownModelError):
            spc700.Cpu("6502", Memory(fill=0))


class QuietStoreTest(unittest.TestCase):
    """`fill`, which is the one spelling across this family for a store of one byte.

    Not what a board hands over and not the default: a caller asking for zeroes
    is asking for something no machine does, so they have to say so. What it is
    for is a run that has to get through a few dozen instructions without meeting
    an opcode that stops the part, which is what every check of a cycle budget
    needs and what scrambled memory cannot give.
    """

    def test_a_fill_puts_that_byte_everywhere(self) -> None:
        part = spc700.Cpu(spc700.DEFAULT_MODEL, fill=0)

        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0})

    def test_and_any_byte_works_rather_than_only_zero(self) -> None:
        part = spc700.Cpu(spc700.DEFAULT_MODEL, fill=0xAA)

        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0xAA})

    def test_without_one_the_store_is_scrambled_rather_than_cleared(self) -> None:
        """The default has to stay the thing a machine actually hands over.

        Read address by address rather than off the store's own bytes, because
        the default store allocates nothing until it is asked and has no bytes
        to read.
        """
        part = spc700.Cpu(spc700.DEFAULT_MODEL)

        held = {part.memory.read8(address) for address in range(0x40)}

        self.assertNotEqual(held, {0})

    def test_and_a_store_handed_in_is_left_alone(self) -> None:
        """So `fill` cannot quietly replace memory a caller already built."""
        own = spc700.Memory(fill=0xAA)

        part = spc700.Cpu(spc700.DEFAULT_MODEL, own, fill=0)

        self.assertIs(part.memory, own)
        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0xAA})


if __name__ == "__main__":
    unittest.main()

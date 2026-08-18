import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spc700
from spc700 import models
from spc700.memory import Memory


class CatalogueTest(unittest.TestCase):
    def test_the_family_names_every_model_it_covers(self):
        self.assertIn("spc700", models.MODELS)

    def test_a_model_says_what_it_is_and_what_it_reaches(self):
        found = models.describe("spc700")

        self.assertTrue(found.summary)
        self.assertEqual(found.address_bits, 16)
        self.assertEqual(found.data_bits, 8)

    def test_a_model_name_is_matched_however_it_is_written(self):
        for written in ("SPC700", "spc-700", "s_smp", "SPC_700"):
            self.assertEqual(models.describe(written).name, "spc700")

    def test_a_model_the_family_does_not_have_is_refused_by_name(self):
        with self.assertRaises(models.UnknownModelError):
            models.describe("z80")

    def test_the_refusal_lists_what_is_available(self):
        with self.assertRaises(models.UnknownModelError) as raised:
            models.describe("nonsense")

        self.assertIn("spc700", str(raised.exception))

    def test_the_address_mask_follows_the_address_bits(self):
        self.assertEqual(models.describe("spc700").address_mask, 0xFFFF)

    def test_a_model_prints_as_its_name_and_reach(self):
        printed = repr(models.describe("spc700"))

        self.assertIn("spc700", printed)
        self.assertIn("16", printed)


class BuildTest(unittest.TestCase):
    def test_a_processor_is_built_from_its_model_name(self):
        cpu = spc700.Cpu(Memory(fill=0), model="spc700")

        self.assertEqual(cpu.model, "spc700")

    def test_the_default_model_is_the_one_the_console_carries(self):
        cpu = spc700.Cpu(Memory(fill=0))

        self.assertEqual(cpu.model, "spc700")

    def test_options_reach_the_processor_that_gets_built(self):
        cpu = spc700.Cpu(Memory(fill=0), model="spc700", step_limit=17)

        self.assertEqual(cpu.step_limit, 17)

    def test_a_model_the_family_does_not_have_is_refused_at_construction(self):
        with self.assertRaises(models.UnknownModelError):
            spc700.Cpu(Memory(fill=0), model="6502")


if __name__ == "__main__":
    unittest.main()

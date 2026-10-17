import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spc700


class CatalogueTest(unittest.TestCase):
    def test_the_family_names_every_model_it_covers(self) -> None:
        # Arrange
        catalogue = spc700.MODELS

        # Act
        names = sorted(catalogue)

        # Assert
        self.assertEqual(names, ["spc700"])

    def test_a_model_says_what_it_is_and_what_it_reaches(self) -> None:
        # Arrange
        catalogue = spc700.MODELS

        # Act
        found = catalogue["spc700"]

        # Assert
        self.assertTrue(found.summary)
        self.assertEqual(found.address_bits, 16)
        self.assertEqual(found.data_bits, 8)

    def test_a_model_name_is_matched_however_it_is_written(self) -> None:
        # Arrange
        written = ("SPC700", "spc-700", "s_smp", "SPC_700")

        # Act
        built = {spc700.Cpu(name).model for name in written}

        # Assert
        self.assertEqual(built, {"spc700"})

    def test_every_alias_the_catalogue_lists_builds_the_part(self) -> None:
        # Arrange
        aliases = spc700.MODELS["spc700"].aliases

        # Act
        built = {spc700.Cpu(alias).model for alias in aliases}

        # Assert
        self.assertEqual((aliases, built), (("spc", "ssmp", "smp", "sonyspc700"), {"spc700"}))

    def test_a_model_the_family_does_not_have_is_refused_by_name(self) -> None:
        # Arrange
        def attempt() -> Any:
            return spc700.Cpu("z80")

        # Act
        with self.assertRaises(spc700.UnknownModelError) as raised:
            attempt()

        # Assert
        self.assertIn("z80", str(raised.exception))

    def test_the_refusal_lists_what_is_available(self) -> None:
        # Arrange
        def attempt() -> Any:
            return spc700.Cpu("nonsense")

        # Act
        with self.assertRaises(spc700.UnknownModelError) as raised:
            attempt()

        # Assert
        self.assertIn("spc700", str(raised.exception))

    def test_the_address_mask_follows_the_address_bits(self) -> None:
        # Arrange
        model = spc700.MODELS["spc700"]

        # Act
        mask = model.address_mask

        # Assert
        self.assertEqual(mask, 0xFFFF)

    def test_a_model_prints_as_its_name_and_reach(self) -> None:
        # Arrange
        model = spc700.MODELS["spc700"]

        # Act
        printed = repr(model)

        # Assert
        self.assertEqual(printed, "<Model spc700, 16 address bits>")


class BuildTest(unittest.TestCase):
    def test_a_processor_is_built_from_its_model_name(self) -> None:
        # Arrange
        memory = spc700.Memory(fill=0)

        # Act
        cpu = spc700.Cpu("spc700", memory)

        # Assert
        self.assertEqual(cpu.model, "spc700")

    def test_building_without_naming_a_model_is_refused(self) -> None:
        # Arrange
        def attempt() -> Any:
            return spc700.Cpu()

        # Act
        with self.assertRaises(spc700.UnknownModelError) as raised:
            attempt()

        # Assert
        self.assertIn("no model was named", str(raised.exception))

    def test_and_the_refusal_names_every_model_there_is(self) -> None:
        # Arrange
        def attempt() -> Any:
            return spc700.Cpu()

        # Act
        with self.assertRaises(spc700.UnknownModelError) as caught:
            attempt()

        # Assert
        missing = [name for name in spc700.MODELS if name not in str(caught.exception)]
        self.assertEqual(missing, [])

    def test_nothing_named_describe_is_published(self) -> None:
        # Arrange
        name = "describe"

        # Act
        published = hasattr(spc700, name)

        # Assert
        self.assertFalse(published)

    def test_and_no_default_model_is_published_either(self) -> None:
        # Arrange
        name = "DEFAULT_MODEL"

        # Act
        published = hasattr(spc700, name)

        # Assert
        self.assertFalse(published)

    def test_options_reach_the_processor_that_gets_built(self) -> None:
        # Arrange
        memory = spc700.Memory(fill=0)

        # Act
        cpu = spc700.Cpu("spc700", memory, step_limit=17)

        # Assert
        self.assertEqual(cpu.step_limit, 17)

    def test_a_model_the_family_does_not_have_is_refused_at_construction(self) -> None:
        # Arrange
        def attempt() -> Any:
            return spc700.Cpu("6502", spc700.Memory(fill=0))

        # Act
        with self.assertRaises(spc700.UnknownModelError) as raised:
            attempt()

        # Assert
        self.assertIn("6502", str(raised.exception))


class QuietStoreTest(unittest.TestCase):
    def test_a_fill_puts_that_byte_everywhere(self) -> None:
        # Arrange
        fill = 0

        # Act
        part = spc700.Cpu("spc700", fill=fill)

        # Assert
        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0})

    def test_and_any_byte_works_rather_than_only_zero(self) -> None:
        # Arrange
        fill = 0xAA

        # Act
        part = spc700.Cpu("spc700", fill=fill)

        # Assert
        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0xAA})

    def test_without_one_the_store_is_scrambled_rather_than_cleared(self) -> None:
        # Arrange
        part = spc700.Cpu("spc700")

        # Act
        held = {part.memory.read8(address) for address in range(0x40)}

        # Assert
        self.assertNotEqual(held, {0})

    def test_and_a_store_handed_in_is_left_alone(self) -> None:
        # Arrange
        own = spc700.Memory(fill=0xAA)

        # Act
        part = spc700.Cpu("spc700", own, fill=0)

        # Assert
        self.assertIs(part.memory, own)
        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0xAA})


if __name__ == "__main__":
    unittest.main()

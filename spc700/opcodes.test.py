import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import opcodes
from spc700.errors import Truncated


class TableTest(unittest.TestCase):
    def test_the_table_covers_the_whole_byte(self) -> None:
        self.assertEqual(len(opcodes.OPCODES), 256)

    def test_every_entry_names_an_instruction_a_mode_and_a_size(self) -> None:
        for mnemonic, mode, size in opcodes.OPCODES:
            self.assertTrue(mnemonic)
            self.assertTrue(mode)
            self.assertIn(size, (1, 2, 3))

    def test_the_disassembly_templates_cover_the_whole_byte(self) -> None:
        self.assertEqual(len(opcodes.TEXT), 256)

    def test_a_size_matches_its_template_operands(self) -> None:
        self.assertEqual(opcodes.OPCODES[0x00], ("nop", "implied", 1))
        self.assertEqual(opcodes.OPCODES[0xE8], ("mov", "a_imm", 2))
        self.assertEqual(opcodes.OPCODES[0xE5], ("mov", "a_abs", 3))

    def test_bit_indexed_instructions_share_one_mnemonic(self) -> None:
        self.assertEqual(opcodes.OPCODES[0x02][0], "set1")
        self.assertEqual(opcodes.OPCODES[0x22][0], "set1")
        self.assertEqual(opcodes.OPCODES[0x12][0], "clr1")
        self.assertEqual(opcodes.OPCODES[0x03][0], "bbs")
        self.assertEqual(opcodes.OPCODES[0x13][0], "bbc")

    def test_the_table_call_targets_are_all_one_mnemonic(self) -> None:
        for opcode in range(0x01, 0x100, 0x10):
            self.assertEqual(opcodes.OPCODES[opcode][0], "tcall")


class BitIndexTest(unittest.TestCase):
    def test_a_bit_instruction_takes_its_index_from_the_opcode(self) -> None:
        self.assertEqual(opcodes.bit_index(0x02), 0)
        self.assertEqual(opcodes.bit_index(0x22), 1)
        self.assertEqual(opcodes.bit_index(0xE2), 7)

    def test_a_clear_takes_the_same_index_as_its_set(self) -> None:
        self.assertEqual(opcodes.bit_index(0x12), 0)
        self.assertEqual(opcodes.bit_index(0xF2), 7)

    def test_a_table_call_takes_its_index_from_the_opcode(self) -> None:
        self.assertEqual(opcodes.call_index(0x01), 0)
        self.assertEqual(opcodes.call_index(0x71), 7)
        self.assertEqual(opcodes.call_index(0xF1), 15)


class DecodeTest(unittest.TestCase):
    def test_an_implied_instruction_is_one_byte(self) -> None:
        found = opcodes.decode(bytes([0x00]), 0, 0x0200)

        self.assertEqual(found.size, 1)
        self.assertEqual(found.text, "nop")

    def test_an_immediate_load_shows_its_operand(self) -> None:
        found = opcodes.decode(bytes([0xE8, 0x42]), 0, 0x0200)

        self.assertEqual(found.text, "mov a,#$42")

    def test_a_direct_page_address_follows_the_page_flag(self) -> None:
        low = opcodes.decode(bytes([0xE4, 0x10]), 0, 0x0200, p=0)
        high = opcodes.decode(bytes([0xE4, 0x10]), 0, 0x0200, p=1)

        self.assertEqual(low.text, "mov a,$010")
        self.assertEqual(high.text, "mov a,$110")

    def test_a_branch_target_is_resolved(self) -> None:
        found = opcodes.decode(bytes([0x2F, 0x02]), 0, 0x0200)

        self.assertEqual(found.text, "bra $0204")

    def test_a_backward_branch_target_is_resolved(self) -> None:
        found = opcodes.decode(bytes([0x2F, 0xFE]), 0, 0x0200)

        self.assertEqual(found.text, "bra $0200")

    def test_a_bit_address_splits_into_address_and_bit(self) -> None:
        found = opcodes.decode(bytes([0x0A, 0x34, 0xE2]), 0, 0x0200)

        self.assertEqual(found.text, "or1 c,$0234:7")

    def test_reading_past_the_end_is_refused(self) -> None:
        with self.assertRaises(Truncated):
            opcodes.decode(bytes([0xE8]), 0, 0x0200)

    def test_an_offset_past_the_end_is_refused(self) -> None:
        with self.assertRaises(Truncated):
            opcodes.decode(bytes([0x00]), 5, 0x0200)

    def test_the_opcode_is_carried_on_the_result(self) -> None:
        self.assertEqual(opcodes.decode(bytes([0x00]), 0, 0x0200).opcode, 0x00)

    def test_the_address_is_carried_on_the_result(self) -> None:
        self.assertEqual(opcodes.decode(bytes([0x00]), 0, 0x1234).address, 0x1234)


class DisassembleTest(unittest.TestCase):
    def test_a_listing_walks_every_instruction(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0x00, 0x00]), 0, 0x0200)

        self.assertEqual(len(listing), 3)

    def test_a_listing_advances_the_address(self) -> None:
        listing = opcodes.disassemble(bytes([0xE8, 0x01, 0x00]), 0, 0x0200)

        self.assertEqual([step.address for step in listing], [0x0200, 0x0202])

    def test_a_listing_stops_once_it_holds_the_count_asked_for(self) -> None:
        listing = opcodes.disassemble(bytes([0x00] * 10), 0, 0x0200, count=3)

        self.assertEqual(len(listing), 3)

    def test_asking_for_no_steps_gives_none(self) -> None:
        self.assertEqual(opcodes.disassemble(bytes([0x00] * 4), 0, 0x0200, count=0), [])

    def test_a_listing_stops_where_the_bytes_run_out(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0xE8]), 0, 0x0200)

        self.assertEqual(len(listing), 1)

    def test_a_listing_stops_at_a_return_when_asked(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0x6F, 0x00]), 0, 0x0200, stop_at_return=True)

        self.assertEqual([step.text for step in listing], ["nop", "ret"])

    def test_a_listing_runs_past_a_return_when_not_asked(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0x6F, 0x00]), 0, 0x0200)

        self.assertEqual(len(listing), 3)

    def test_the_address_wraps_at_the_top_of_the_space(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0x00]), 0, 0xFFFF)

        self.assertEqual([step.address for step in listing], [0xFFFF, 0x0000])


if __name__ == "__main__":
    unittest.main()

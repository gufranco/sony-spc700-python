import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import OPCODES, Cpu, Memory, Truncated, decode, disassemble

TESTED_BYTE = 0x10


def ran(program: bytes, held: int = 0x00, **vectors: int) -> tuple[Any, Memory]:
    memory = Memory(image=program, fill=0)
    memory.write8(TESTED_BYTE, held)
    for name, target in vectors.items():
        address = int(name.removeprefix("at_"), 16)
        memory.write8(address, target & 0xFF)
        memory.write8(address + 1, target >> 8)
    cpu = Cpu("spc700", memory).reset()
    cpu.sp = 0xEF
    cpu.step()
    return cpu, memory


class TableTest(unittest.TestCase):
    def test_the_table_covers_the_whole_byte(self) -> None:
        # Arrange
        table = OPCODES

        # Act
        counted = len(table)

        # Assert
        self.assertEqual(counted, 256)

    def test_every_entry_names_an_instruction_a_mode_and_a_size(self) -> None:
        # Arrange
        table = OPCODES

        # Act
        odd = [
            opcode
            for opcode, (mnemonic, mode, size) in enumerate(table)
            if not mnemonic or not mode or size not in (1, 2, 3)
        ]

        # Assert
        self.assertEqual(odd, [])

    def test_every_opcode_disassembles_to_text_of_its_own(self) -> None:
        # Arrange
        programs = [bytes([opcode, 0x34, 0x12]) for opcode in range(256)]

        # Act
        texts = [disassemble(program, 0, 0x0200, count=1)[0].text for program in programs]

        # Assert
        self.assertEqual([opcode for opcode, text in enumerate(texts) if not text], [])
        self.assertEqual(texts[0x00], "nop")
        self.assertEqual(texts[0xE5], "mov a,$1234")

    def test_a_size_matches_its_template_operands(self) -> None:
        # Arrange
        table = OPCODES

        # Act
        rows = (table[0x00], table[0xE8], table[0xE5])

        # Assert
        self.assertEqual(rows, (("nop", "implied", 1), ("mov", "a_imm", 2), ("mov", "a_abs", 3)))

    def test_bit_indexed_instructions_share_one_mnemonic(self) -> None:
        # Arrange
        table = OPCODES

        # Act
        names = [table[opcode][0] for opcode in (0x02, 0x22, 0x12, 0x03, 0x13)]

        # Assert
        self.assertEqual(names, ["set1", "set1", "clr1", "bbs", "bbc"])

    def test_the_table_call_targets_are_all_one_mnemonic(self) -> None:
        # Arrange
        table = OPCODES

        # Act
        names = {table[opcode][0] for opcode in range(0x01, 0x100, 0x10)}

        # Assert
        self.assertEqual(names, {"tcall"})


class BitIndexTest(unittest.TestCase):
    def test_a_bit_instruction_takes_its_index_from_the_opcode(self) -> None:
        # Arrange
        programs = {opcode: bytes([opcode, TESTED_BYTE]) for opcode in (0x02, 0x22, 0xE2)}

        # Act
        held = {opcode: ran(program)[1].read8(TESTED_BYTE) for opcode, program in programs.items()}

        # Assert
        self.assertEqual(held, {0x02: 0x01, 0x22: 0x02, 0xE2: 0x80})

    def test_a_clear_takes_the_same_index_as_its_set(self) -> None:
        # Arrange
        programs = {opcode: bytes([opcode, TESTED_BYTE]) for opcode in (0x12, 0xF2)}

        # Act
        held = {
            opcode: ran(program, held=0xFF)[1].read8(TESTED_BYTE)
            for opcode, program in programs.items()
        }

        # Assert
        self.assertEqual(held, {0x12: 0xFE, 0xF2: 0x7F})

    def test_a_table_call_takes_its_index_from_the_opcode(self) -> None:
        # Arrange
        vectors = {"at_ffde": 0x1000, "at_ffd0": 0x2000, "at_ffc0": 0x3000}

        # Act
        landed = {opcode: ran(bytes([opcode]), **vectors)[0].pc for opcode in (0x01, 0x71, 0xF1)}

        # Assert
        self.assertEqual(landed, {0x01: 0x1000, 0x71: 0x2000, 0xF1: 0x3000})


class DecodeTest(unittest.TestCase):
    def test_an_implied_instruction_is_one_byte(self) -> None:
        # Arrange
        program = bytes([0x00])

        # Act
        found = decode(program, 0, 0x0200)

        # Assert
        self.assertEqual((found.size, found.text), (1, "nop"))

    def test_an_immediate_load_shows_its_operand(self) -> None:
        # Arrange
        program = bytes([0xE8, 0x42])

        # Act
        found = decode(program, 0, 0x0200)

        # Assert
        self.assertEqual(found.text, "mov a,#$42")

    def test_a_direct_page_address_follows_the_page_flag(self) -> None:
        # Arrange
        program = bytes([0xE4, 0x10])

        # Act
        found = [decode(program, 0, 0x0200, p=page).text for page in (0, 1)]

        # Assert
        self.assertEqual(found, ["mov a,$010", "mov a,$110"])

    def test_a_branch_target_is_resolved(self) -> None:
        # Arrange
        program = bytes([0x2F, 0x02])

        # Act
        found = decode(program, 0, 0x0200)

        # Assert
        self.assertEqual(found.text, "bra $0204")

    def test_a_backward_branch_target_is_resolved(self) -> None:
        # Arrange
        program = bytes([0x2F, 0xFE])

        # Act
        found = decode(program, 0, 0x0200)

        # Assert
        self.assertEqual(found.text, "bra $0200")

    def test_a_bit_address_splits_into_address_and_bit(self) -> None:
        # Arrange
        program = bytes([0x0A, 0x34, 0xE2])

        # Act
        found = decode(program, 0, 0x0200)

        # Assert
        self.assertEqual(found.text, "or1 c,$0234:7")

    def test_reading_past_the_end_is_refused(self) -> None:
        # Arrange
        program = bytes([0xE8])

        # Act
        with self.assertRaises(Truncated) as raised:
            decode(program, 0, 0x0200)

        # Assert
        self.assertEqual(str(raised.exception), "opcode E8 at 0 needs 2 bytes, 1 remain")

    def test_an_offset_past_the_end_is_refused(self) -> None:
        # Arrange
        program = bytes([0x00])

        # Act
        with self.assertRaises(Truncated) as raised:
            decode(program, 5, 0x0200)

        # Assert
        self.assertEqual(str(raised.exception), "offset 5 is past the end of 1 bytes")

    def test_the_opcode_is_carried_on_the_result(self) -> None:
        # Arrange
        program = bytes([0x00])

        # Act
        found = decode(program, 0, 0x0200)

        # Assert
        self.assertEqual((found.opcode, found.mnemonic, found.mode), (0x00, "nop", "implied"))

    def test_the_address_is_carried_on_the_result(self) -> None:
        # Arrange
        program = bytes([0x00])

        # Act
        found = decode(program, 0, 0x1234)

        # Assert
        self.assertEqual(found.address, 0x1234)


class DisassembleTest(unittest.TestCase):
    def test_a_listing_walks_every_instruction(self) -> None:
        # Arrange
        program = bytes([0x00, 0x00, 0x00])

        # Act
        listing = disassemble(program, 0, 0x0200)

        # Assert
        self.assertEqual(len(listing), 3)

    def test_a_listing_advances_the_address(self) -> None:
        # Arrange
        program = bytes([0xE8, 0x01, 0x00])

        # Act
        listing = disassemble(program, 0, 0x0200)

        # Assert
        self.assertEqual([step.address for step in listing], [0x0200, 0x0202])

    def test_a_listing_stops_once_it_holds_the_count_asked_for(self) -> None:
        # Arrange
        program = bytes([0x00] * 10)

        # Act
        listing = disassemble(program, 0, 0x0200, count=3)

        # Assert
        self.assertEqual(len(listing), 3)

    def test_asking_for_no_steps_gives_none(self) -> None:
        # Arrange
        program = bytes([0x00] * 4)

        # Act
        listing = disassemble(program, 0, 0x0200, count=0)

        # Assert
        self.assertEqual(listing, [])

    def test_a_listing_stops_where_the_bytes_run_out(self) -> None:
        # Arrange
        program = bytes([0x00, 0xE8])

        # Act
        listing = disassemble(program, 0, 0x0200)

        # Assert
        self.assertEqual(len(listing), 1)

    def test_a_listing_stops_at_a_return_when_asked(self) -> None:
        # Arrange
        program = bytes([0x00, 0x6F, 0x00])

        # Act
        listing = disassemble(program, 0, 0x0200, stop_at_return=True)

        # Assert
        self.assertEqual([step.text for step in listing], ["nop", "ret"])

    def test_a_listing_runs_past_a_return_when_not_asked(self) -> None:
        # Arrange
        program = bytes([0x00, 0x6F, 0x00])

        # Act
        listing = disassemble(program, 0, 0x0200)

        # Assert
        self.assertEqual(len(listing), 3)

    def test_the_address_wraps_at_the_top_of_the_space(self) -> None:
        # Arrange
        program = bytes([0x00, 0x00])

        # Act
        listing = disassemble(program, 0, 0xFFFF)

        # Assert
        self.assertEqual([step.address for step in listing], [0xFFFF, 0x0000])


if __name__ == "__main__":
    unittest.main()

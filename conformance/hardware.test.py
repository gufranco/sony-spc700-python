"""Hold this core to the figures Nintendo printed, rather than to prose about them.

Every number in `hardware.json` was read off a rendered page of the manual. This
assembles each documented instruction, steps it, and compares the cycles it took
against the figure the table gives, so a citation is a check that can fail rather
than a claim nobody runs.

The three rows where the manual and the recording disagree are named here as
exceptions and cross-checked against `divergences.json`, so removing one from the
divergence record breaks a test rather than quietly widening what this core is
allowed to do.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import Cpu, SparseMemory
from spc700.bus import Bus
from spc700.opcodes import OPCODES

HERE = Path(__file__).resolve().parent
FACTS: dict[str, Any] = json.loads((HERE / "hardware.json").read_text())
DIVERGENCES: dict[str, Any] = json.loads((HERE / "divergences.json").read_text())

ROWS: dict[str, dict[str, Any]] = {
    row["code"]: {**row, "table": table["table"], "manualPage": table["manualPage"]}
    for table in FACTS["tables"]
    for row in table["rows"]
}

FOLLOWS_THE_RECORDING_INSTEAD = {
    "DA": "movw-dp-ya-costs-five",
    "EF": "sleep-and-stop-have-no-cycle-count",
    "FF": "sleep-and-stop-have-no-cycle-count",
}

PROGRAM_AT = 0x0400
"""Somewhere with a direct page below it and a stack above, so nothing overlaps."""

TESTED_BYTE = 0x10
"""The direct page offset every assembled instruction is given as its operand."""

FLAG_C = 0x01
FLAG_Z = 0x02
FLAG_V = 0x40
FLAG_N = 0x80

BY_FLAG = {
    "10": (FLAG_N, False),
    "30": (FLAG_N, True),
    "50": (FLAG_V, False),
    "70": (FLAG_V, True),
    "90": (FLAG_C, False),
    "B0": (FLAG_C, True),
    "D0": (FLAG_Z, False),
    "F0": (FLAG_Z, True),
}
"""Which flag each conditional branch reads, and the value it branches on."""


def _run(
    code: int,
    *operands: int,
    psw: int = 0x00,
    a: int = 0x00,
    y: int = 0x00,
    held: int | None = None,
) -> int:
    """Assemble one instruction, step it once, and report the cycles it took.

    `held` is the byte at the direct page offset the operand names, which is what
    the bit branches and the compare branches read their condition out of.
    """
    memory = SparseMemory(seed=code)
    memory.write8(PROGRAM_AT, code)
    for offset, value in enumerate(operands, start=1):
        memory.write8(PROGRAM_AT + offset, value)
    if held is not None:
        memory.write8(TESTED_BYTE, held)

    line = Bus()
    cpu = Cpu(memory=memory, bus=line)
    cpu.a = a
    cpu.x = 0x00
    cpu.y = y
    cpu.sp = 0xF0
    cpu.psw = psw
    cpu.pc = PROGRAM_AT
    cpu.step()
    return line.cycles


def _branch(code: str, taken: bool) -> int:
    """One conditional branch, in a state where it does or does not branch."""
    number = int(code, 16)
    if code in BY_FLAG:
        flag, branches_when_set = BY_FLAG[code]
        return _run(number, 0x10, psw=flag if taken == branches_when_set else 0x00)
    if code.endswith("3"):
        bit = 1 << (number >> 5)
        set_branches = number & 0x10 == 0
        return _run(number, TESTED_BYTE, 0x10, held=bit if taken == set_branches else bit ^ 0xFF)
    if code in ("2E", "DE"):
        return _run(number, TESTED_BYTE, 0x10, a=0x00, held=0x55 if taken else 0x00)
    if code == "6E":
        return _run(number, TESTED_BYTE, 0x10, held=0x00 if taken else 0x01)
    return _run(number, 0x10, y=0x00 if taken else 0x01)


class DocumentTest(unittest.TestCase):
    def test_the_document_is_pinned_by_digest(self) -> None:
        document = FACTS["documents"]["developmentManual"]

        self.assertEqual(len(document["sha256"]), 64)

    def test_every_opcode_the_part_has_appears_in_the_tables(self) -> None:
        missing = [f"{number:02X}" for number in range(256) if f"{number:02X}" not in ROWS]

        self.assertEqual(missing, [])

    def test_no_opcode_appears_in_two_tables(self) -> None:
        counted = sum(len(table["rows"]) for table in FACTS["tables"])

        self.assertEqual(counted, len(ROWS))

    def test_every_row_names_the_page_it_was_read_from(self) -> None:
        missing = [code for code, row in ROWS.items() if not row["manualPage"]]

        self.assertEqual(missing, [])

    def test_what_the_manual_does_not_state_is_recorded_rather_than_filled_in(self) -> None:
        stated = FACTS["notStated"]

        self.assertGreaterEqual(len(stated), 4)


class LengthTest(unittest.TestCase):
    def test_every_documented_length_matches_this_package(self) -> None:
        wrong = [
            (code, row["bytes"], OPCODES[int(code, 16)][2])
            for code, row in ROWS.items()
            if row["bytes"] != OPCODES[int(code, 16)][2]
        ]

        self.assertEqual(wrong, [])

    def test_every_documented_mnemonic_matches_this_package(self) -> None:
        wrong = [
            (code, row["mnemonic"])
            for code, row in ROWS.items()
            if row["mnemonic"].lower().rstrip("1") not in OPCODES[int(code, 16)][0]
            and OPCODES[int(code, 16)][0] not in row["mnemonic"].lower()
        ]

        self.assertEqual(wrong, [])


class CycleTest(unittest.TestCase):
    """Every instruction the manual gives one figure for, run and counted.

    A branch is excluded because its figure depends on whether it is taken, and a
    taken branch needs a state the condition holds in. Those have their own test
    below rather than being folded in here.
    """

    def _fixed(self) -> list[tuple[str, dict[str, Any]]]:
        return [
            (code, row)
            for code, row in sorted(ROWS.items())
            if "/" not in row["cycles"] and code not in FOLLOWS_THE_RECORDING_INSTEAD
        ]

    def test_every_fixed_figure_in_the_manual_is_what_this_core_takes(self) -> None:
        wrong = [
            (code, row["mnemonic"], row["cycles"], _run(int(code, 16), TESTED_BYTE, 0x04))
            for code, row in self._fixed()
            if int(row["cycles"]) != _run(int(code, 16), TESTED_BYTE, 0x04)
        ]

        self.assertEqual(wrong, [])

    def test_that_check_covered_most_of_the_instruction_set(self) -> None:
        covered = len(self._fixed())

        self.assertEqual(covered, 256 - 28 - len(FOLLOWS_THE_RECORDING_INSTEAD))

    def test_an_untaken_branch_takes_the_left_figure(self) -> None:
        wrong = [
            (code, row["mnemonic"], row["cycles"], _branch(code, taken=False))
            for code, row in sorted(ROWS.items())
            if "/" in row["cycles"]
            and int(row["cycles"].split("/")[0]) != _branch(code, taken=False)
        ]

        self.assertEqual(wrong, [])

    def test_a_taken_branch_takes_the_right_figure(self) -> None:
        wrong = [
            (code, row["mnemonic"], row["cycles"], _branch(code, taken=True))
            for code, row in sorted(ROWS.items())
            if "/" in row["cycles"]
            and int(row["cycles"].split("/")[1]) != _branch(code, taken=True)
        ]

        self.assertEqual(wrong, [])

    def test_a_taken_branch_costs_two_more_than_an_untaken_one(self) -> None:
        pairs = [
            (row["cycles"], int(row["cycles"].split("/")[1]) - int(row["cycles"].split("/")[0]))
            for row in ROWS.values()
            if "/" in row["cycles"]
        ]

        self.assertEqual({difference for _, difference in pairs}, {2})

    def test_every_branch_row_was_checked(self) -> None:
        branches = [code for code, row in ROWS.items() if "/" in row["cycles"]]

        self.assertEqual(len(branches), 28)


class WorkedExampleTest(unittest.TestCase):
    """A few instructions whose figure is worth naming on its own."""

    def test_a_multiply_takes_the_nine_cycles_the_manual_gives_it(self) -> None:
        row = ROWS["CF"]

        self.assertEqual(_run(0xCF), int(row["cycles"]))

    def test_a_divide_takes_twelve(self) -> None:
        row = ROWS["9E"]

        self.assertEqual(_run(0x9E), int(row["cycles"]))

    def test_the_shortest_instruction_takes_two(self) -> None:
        shortest = min(int(row["cycles"].split("/")[0]) for row in ROWS.values())

        self.assertEqual((shortest, _run(0x00)), (2, 2))

    def test_a_store_costs_a_cycle_more_than_the_load_it_mirrors(self) -> None:
        load, store = int(ROWS["E4"]["cycles"]), int(ROWS["C4"]["cycles"])

        self.assertEqual((store - load, _run(0xC4, TESTED_BYTE) - _run(0xE4, TESTED_BYTE)), (1, 1))


class DivergenceTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries: list[dict[str, Any]] = DIVERGENCES["divergences"]

    def test_every_row_this_core_departs_from_is_recorded(self) -> None:
        named = {entry["id"] for entry in self.entries}

        self.assertEqual(set(FOLLOWS_THE_RECORDING_INSTEAD.values()) - named, set())

    def test_each_entry_says_which_source_the_package_follows(self) -> None:
        allowed = {"document", "recording", "neither"}

        self.assertEqual({entry["packageFollows"] for entry in self.entries} - allowed, set())

    def test_each_entry_says_what_would_settle_it(self) -> None:
        missing = [entry["id"] for entry in self.entries if not entry.get("wouldSettleIt")]

        self.assertEqual(missing, [])

    def test_the_word_store_divergence_names_both_figures(self) -> None:
        found = next(entry for entry in self.entries if entry["id"] == "movw-dp-ya-costs-five")

        self.assertIn("4 cycles", found["documentSays"])

    def test_the_core_takes_the_recorded_count_for_that_store(self) -> None:
        self.assertEqual((int(ROWS["DA"]["cycles"]), _run(0xDA, TESTED_BYTE)), (4, 5))

    def test_the_shape_of_a_cycle_is_recorded_as_resting_on_the_recording(self) -> None:
        found = next(
            entry
            for entry in self.entries
            if entry["id"] == "the-cycle-shape-rests-on-the-recording-alone"
        )

        self.assertEqual(found["documentSays"].split(".")[0], "Nothing")

    def test_a_halted_part_is_not_claimed_to_have_a_cycle_count(self) -> None:
        found = next(
            entry for entry in self.entries if entry["id"] == "sleep-and-stop-have-no-cycle-count"
        )

        self.assertEqual(found["status"], "notADisagreement")


if __name__ == "__main__":
    unittest.main(verbosity=1)

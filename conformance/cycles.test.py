"""What the cycle comparison compares, and what it refuses to compare."""

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "conformance"))

cycles: Any = importlib.import_module("cycles")


def _case(name: str, cycle_list: list[list[Any]], **initial: Any) -> dict[str, Any]:
    state = {"pc": 0x1000, "a": 0x00, "x": 0x00, "y": 0x00, "sp": 0xFF, "psw": 0x00, "ram": []}
    state.update(initial)
    return {
        "name": name,
        "initial": state,
        "final": {key: state[key] for key in ("a", "x", "y", "sp", "psw", "pc")},
        "cycles": cycle_list,
    }


class ComparisonTest(unittest.TestCase):
    def test_a_core_that_reproduces_the_recording_reports_nothing(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x1001, None, "read"]], ram=[[0x1000, 0x00]])

        wrong = cycles.check(case)

        self.assertEqual(wrong, [])

    def test_a_cycle_at_the_wrong_address_is_reported(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x2222, None, "read"]], ram=[[0x1000, 0x00]])

        wrong = cycles.check(case)

        self.assertEqual([entry[0] for entry in wrong], [1])

    def test_a_cycle_of_the_wrong_kind_is_reported(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x1001, None, "write"]], ram=[[0x1000, 0x00]])

        wrong = cycles.check(case)

        self.assertEqual([entry[0] for entry in wrong], [1])

    def test_a_value_the_case_does_not_assert_is_not_compared(self) -> None:
        case = _case(
            "mov a,#imm",
            [[0x1000, 0xE8, "read"], [0x1001, None, "read"]],
            ram=[[0x1000, 0xE8]],
        )

        wrong = cycles.check(case)

        self.assertEqual(wrong, [])

    def test_a_value_the_case_does_assert_is_compared(self) -> None:
        case = _case(
            "mov a,#imm",
            [[0x1000, 0xE8, "read"], [0x1001, 0x99, "read"]],
            ram=[[0x1000, 0xE8], [0x1001, 0x42]],
        )

        wrong = cycles.check(case)

        self.assertEqual([entry[0] for entry in wrong], [1])

    def test_too_few_cycles_is_reported_at_the_first_missing_one(self) -> None:
        case = _case(
            "nop",
            [[0x1000, 0x00, "read"], [0x1001, None, "read"], [None, None, "wait"]],
            ram=[[0x1000, 0x00]],
        )

        wrong = cycles.check(case)

        self.assertEqual([entry[0] for entry in wrong], [2])

    def test_too_many_cycles_is_reported_at_the_first_extra_one(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"]], ram=[[0x1000, 0x00]])

        wrong = cycles.check(case)

        self.assertEqual([entry[0] for entry in wrong], [1])

    def test_an_instruction_that_raises_is_reported_rather_than_escaping(self) -> None:
        case = _case("broken", [[0x1000, 0x00, "read"]], ram=[[0x1000, 0x00]])
        case["initial"]["pc"] = "not an address"

        wrong = cycles.run_tests([case])[1]

        self.assertEqual(wrong, 1)


class TallyTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.good = _case(
            "nop", [[0x1000, 0x00, "read"], [0x1001, None, "read"]], ram=[[0x1000, 0x00]]
        )
        self.bad = _case(
            "nop", [[0x1000, 0x00, "read"], [0x2222, None, "read"]], ram=[[0x1000, 0x00]]
        )

    def test_agreements_and_disagreements_are_counted_apart(self) -> None:
        passed, failed, examples = cycles.run_tests([self.good, self.bad, self.good])

        self.assertEqual((passed, failed, len(examples)), (2, 1, 1))

    def test_the_cycles_compared_are_counted_rather_than_the_cases(self) -> None:
        counted = cycles.count_cycles([self.good, self.bad])

        self.assertEqual(counted, 4)

    def test_only_a_few_examples_are_kept(self) -> None:
        _, _, examples = cycles.run_tests([self.bad] * (cycles.EXAMPLE_LIMIT + 5))

        self.assertEqual(len(examples), cycles.EXAMPLE_LIMIT)


class FileTest(unittest.TestCase):
    def _suite(self, folder: str, cases: list[dict[str, Any]]) -> Path:
        path = Path(folder) / "00.json"
        path.write_text(json.dumps(cases))
        return path

    def test_a_file_is_read_and_compared(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x1001, None, "read"]], ram=[[0x1000, 0x00]])

        with tempfile.TemporaryDirectory() as folder:
            passed, failed, _, compared = cycles.run_file(self._suite(folder, [case, case]))

            self.assertEqual((passed, failed, compared), (2, 0, 4))

    def test_a_limit_reads_only_the_first_cases(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x1001, None, "read"]], ram=[[0x1000, 0x00]])

        with tempfile.TemporaryDirectory() as folder:
            passed, _, _, compared = cycles.run_file(self._suite(folder, [case] * 5), limit=2)

            self.assertEqual((passed, compared), (2, 4))


class MainTest(unittest.TestCase):
    def test_no_arguments_explains_itself(self) -> None:
        code = cycles.main([])

        self.assertEqual(code, 2)

    def test_an_absent_suite_is_said_rather_than_treated_as_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code = cycles.main([str(Path(folder) / "nothing")])

            self.assertEqual(code, 0)

    def test_a_suite_that_agrees_ends_clean(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x1001, None, "read"]], ram=[[0x1000, 0x00]])

        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "00.json").write_text(json.dumps([case]))

            self.assertEqual(cycles.main([folder]), 0)

    def test_a_suite_that_disagrees_ends_dirty(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x2222, None, "read"]], ram=[[0x1000, 0x00]])

        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "00.json").write_text(json.dumps([case]))

            self.assertEqual(cycles.main([folder]), 1)

    def test_more_failing_files_than_it_prints_are_counted_rather_than_dropped(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x2222, None, "read"]], ram=[[0x1000, 0x00]])

        with tempfile.TemporaryDirectory() as folder:
            for number in range(cycles.EXAMPLE_LIMIT + 2):
                (Path(folder) / f"{number:02X}.json").write_text(json.dumps([case]))

            self.assertEqual(cycles.main([folder, "1"]), 1)

    def test_a_name_filter_selects_files(self) -> None:
        case = _case("nop", [[0x1000, 0x00, "read"], [0x2222, None, "read"]], ram=[[0x1000, 0x00]])

        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "00.json").write_text(json.dumps([case]))

            self.assertEqual(cycles.main([folder, "1000", "FF"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)

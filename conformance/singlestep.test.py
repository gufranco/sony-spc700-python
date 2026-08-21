import contextlib
import importlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "conformance"))

singlestep = importlib.import_module("singlestep")


def a_test(**changes: Any) -> dict[str, Any]:
    initial = {
        "pc": 0x0200,
        "a": 0x12,
        "x": 0x34,
        "y": 0x56,
        "sp": 0xEF,
        "psw": 0x00,
        "ram": [[0x0200, 0x00]],
    }
    final = dict(initial, pc=0x0201)
    found = {"name": "00 0000", "initial": initial, "final": final, "cycles": []}
    found.update(changes)
    return found


class LoadTest(unittest.TestCase):
    def test_a_missing_suite_reports_itself_rather_than_raising(self) -> None:
        self.assertEqual(singlestep.suite_files(Path("/nowhere/at/all")), [])

    def test_files_come_back_sorted_so_a_run_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            for name in ("ff.json", "00.json", "7a.json"):
                (Path(where) / name).write_text("[]")

            found = [path.name for path in singlestep.suite_files(where)]

        self.assertEqual(found, ["00.json", "7a.json", "ff.json"])

    def test_anything_that_is_not_a_test_file_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            (Path(where) / "00.json").write_text("[]")
            (Path(where) / "README.md").write_text("not a suite")

            found = [path.name for path in singlestep.suite_files(where)]

        self.assertEqual(found, ["00.json"])


class StateTest(unittest.TestCase):
    def test_the_initial_state_reaches_every_register(self) -> None:
        cpu, _ = singlestep.machine_for(a_test()["initial"])

        self.assertEqual((cpu.a, cpu.x, cpu.y), (0x12, 0x34, 0x56))

    def test_the_stack_pointer_is_taken_from_the_test(self) -> None:
        cpu, _ = singlestep.machine_for(a_test()["initial"])

        self.assertEqual(cpu.sp, 0xEF)

    def test_the_status_register_is_taken_from_the_test(self) -> None:
        case = a_test()
        case["initial"]["psw"] = 0xC3

        cpu, _ = singlestep.machine_for(case["initial"])

        self.assertEqual(cpu.psw, 0xC3)

    def test_the_bytes_the_test_names_are_placed(self) -> None:
        _, memory = singlestep.machine_for(a_test()["initial"])

        self.assertEqual(memory.read8(0x0200), 0x00)

    def test_memory_outside_the_test_is_not_assumed_clear(self) -> None:
        _, memory = singlestep.machine_for(a_test()["initial"])

        unwritten = {memory.read8(address) for address in range(0x8000, 0x8400)}

        self.assertGreater(len(unwritten), 1)

    def test_the_machine_does_not_reset_itself_over_the_state(self) -> None:
        cpu, _ = singlestep.machine_for(a_test()["initial"])

        self.assertEqual(cpu.pc, 0x0200)


class CompareTest(unittest.TestCase):
    def test_a_matching_run_reports_nothing(self) -> None:
        self.assertEqual(singlestep.check(a_test()), [])

    def test_a_wrong_register_is_reported(self) -> None:
        wrong = a_test()
        wrong["final"] = dict(wrong["final"], a=0x99)

        self.assertIn(("a", 0x99, 0x12), singlestep.check(wrong))

    def test_a_wrong_status_register_is_reported(self) -> None:
        wrong = a_test()
        wrong["final"] = dict(wrong["final"], psw=0xFF)

        self.assertIn(("psw", 0xFF, 0x00), singlestep.check(wrong))

    def test_a_wrong_byte_of_memory_is_reported(self) -> None:
        wrong = a_test()
        wrong["final"] = dict(wrong["final"], ram=[[0x0200, 0x99]])

        self.assertEqual(singlestep.check(wrong)[0][0], "$0200")

    def test_a_register_the_test_leaves_out_is_not_compared(self) -> None:
        quiet = a_test()
        quiet["final"] = {"pc": 0x0201}

        self.assertEqual(singlestep.check(quiet), [])


class RunTest(unittest.TestCase):
    def test_a_run_counts_what_passed_and_what_did_not(self) -> None:
        passed, failed, examples = singlestep.run_tests([a_test(), a_test()])

        self.assertEqual((passed, failed), (2, 0))
        self.assertEqual(examples, [])

    def test_a_failing_case_is_kept_as_an_example(self) -> None:
        broken = a_test()
        broken["final"] = dict(broken["final"], a=0x99)

        passed, failed, examples = singlestep.run_tests([broken])

        self.assertEqual((passed, failed), (0, 1))
        self.assertEqual(examples[0][0], "00 0000")

    def test_only_a_few_examples_are_kept(self) -> None:
        broken = a_test()
        broken["final"] = dict(broken["final"], a=0x99)

        _, _, examples = singlestep.run_tests([broken] * 50)

        self.assertLessEqual(len(examples), singlestep.EXAMPLE_LIMIT)

    def test_a_case_that_raises_is_counted_rather_than_ending_the_run(self) -> None:
        broken = a_test()
        broken["initial"] = dict(broken["initial"], ram="not a list of pairs")

        passed, failed, examples = singlestep.run_tests([broken, a_test()])

        self.assertEqual((passed, failed), (1, 1))
        self.assertEqual(examples[0][1][0][0], "raised")


class FileTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="singlestep-file-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, name: str, tests: list[dict[str, Any]]) -> Path:
        path = Path(self.root) / name
        path.write_text(json.dumps(tests))
        return path

    def test_a_file_runs_every_case_it_holds(self) -> None:
        path = self.write("00.json", [a_test(), a_test()])

        passed, failed, _ = singlestep.run_file(path)

        self.assertEqual((passed, failed), (2, 0))

    def test_a_limit_takes_only_the_first_few_cases(self) -> None:
        path = self.write("00.json", [a_test()] * 10)

        passed, failed, _ = singlestep.run_file(path, limit=3)

        self.assertEqual((passed, failed), (3, 0))


class MainTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="singlestep-main-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, name: str, tests: list[dict[str, Any]]) -> None:
        (Path(self.root) / name).write_text(json.dumps(tests))

    def broken_test(self) -> dict[str, Any]:
        broken = a_test()
        broken["final"] = dict(broken["final"], a=0x99)
        return broken

    def run_main(self, argv: list[str]) -> tuple[int, str]:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = singlestep.main(argv)
        return code, captured.getvalue()

    def test_no_arguments_explains_how_to_call_it(self) -> None:
        code, output = self.run_main([])

        self.assertEqual(code, 2)
        self.assertIn("usage", output)

    def test_a_suite_that_is_not_there_says_so_without_failing_the_build(self) -> None:
        code, output = self.run_main([str(Path(self.root) / "absent")])

        self.assertEqual(code, 0)
        self.assertIn("no suite at", output)

    def test_a_passing_suite_reports_success(self) -> None:
        self.write("00.json", [a_test(), a_test()])

        code, output = self.run_main([str(self.root)])

        self.assertEqual(code, 0)
        self.assertIn("2 agreed, 0 did not", output)

    def test_a_failing_suite_names_the_file_and_the_first_disagreement(self) -> None:
        self.write("00.json", [self.broken_test()])

        code, output = self.run_main([str(self.root)])

        self.assertEqual(code, 1)
        self.assertIn("00.json: 1 wrong", output)
        self.assertIn("a want 153", output)

    def test_a_filter_takes_only_the_files_whose_name_matches(self) -> None:
        self.write("00.json", [a_test()])
        self.write("ff.json", [self.broken_test()])

        code, output = self.run_main([str(self.root), "0", "00"])

        self.assertEqual(code, 0)
        self.assertIn("1 files", output)

    def test_a_limit_is_taken_from_the_second_argument(self) -> None:
        self.write("00.json", [a_test()] * 10)

        _, output = self.run_main([str(self.root), "4"])

        self.assertIn("4 agreed", output)

    def test_only_a_few_broken_files_are_listed_and_the_rest_are_counted(self) -> None:
        for index in range(singlestep.EXAMPLE_LIMIT + 2):
            self.write(f"{index:02x}.json", [self.broken_test()])

        code, output = self.run_main([str(self.root)])

        self.assertEqual(code, 1)
        self.assertIn("more files with failures", output)


if __name__ == "__main__":
    unittest.main()

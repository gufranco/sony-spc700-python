import json
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

RECORD = HERE / "cartridge.json"

TEST_ROMS = HERE / "testroms.json"


def recorded(name: str) -> dict[str, Any]:
    held: list[dict[str, Any]] = json.loads(RECORD.read_text())["cartridges"]
    return next(one for one in held if one["id"] == name)


def listed(name: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = json.loads(TEST_ROMS.read_text())["cartridges"]
    return next(one for one in entries if one["id"] == name)


def agreed_throughout(name: str) -> tuple[int, int, list[str], bool]:
    entry = recorded(name)
    astray = [one["check"] for one in entry["checks"] if one["console"] != one["thisModel"]]
    same = entry["sha256"] == listed(name)["sha256"]
    return entry["agreed"], len(entry["checks"]), astray, same


def self_test(name: str) -> tuple[bool, int, str, list[str]]:
    images: list[dict[str, Any]] = json.loads(RECORD.read_text())["selfTests"]["images"]
    run = next(one for one in images if one["id"] == name)["measured"]
    failing = [one for one, passed in run["subTests"].items() if not passed]
    return run["handshake"], run["result"] & ~0x04, run["ports"], failing


def handshake(name: str) -> dict[str, Any]:
    images: list[dict[str, Any]] = json.loads(RECORD.read_text())["handshakes"]["images"]
    measured: dict[str, Any] = next(one for one in images if one["id"] == name)["measured"]
    return measured


class TheRecordedVerdictsTest(unittest.TestCase):
    def test_every_check_spc_smp_reaches_agrees_with_a_console(self) -> None:
        # Arrange
        name = "blargg-spc-smp"

        # Act
        held = agreed_throughout(name)

        # Assert
        self.assertEqual(held, (18, 18, [], True))

    def test_every_check_spc_mem_access_times_reaches_agrees_with_a_console(self) -> None:
        # Arrange
        name = "blargg-spc-mem-access-times"

        # Act
        held = agreed_throughout(name)

        # Assert
        self.assertEqual(held, (2, 2, [], True))

    def test_gilyon_spctest_reports_success_on_its_own_screen(self) -> None:
        # Arrange
        entry = recorded("gilyon-spctest")

        # Act
        screen = entry["screen"]

        # Assert
        self.assertEqual(screen, " Running tests... Success\n Test number: 0527")

    def test_peter_lemons_cartridges_pass_with_only_the_interrupt_flag_excused(self) -> None:
        # Arrange
        names = [
            "peterlemon-spc700-adc",
            "peterlemon-spc700-and",
            "peterlemon-spc700-dec",
            "peterlemon-spc700-eor",
            "peterlemon-spc700-inc",
            "peterlemon-spc700-ora",
            "peterlemon-spc700-sbc",
        ]

        # Act
        endings = [recorded(name)["screen"].split()[-1] for name in names]
        apart = {
            int(one["expected"], 16) ^ int(one["thisModel"], 16)
            for name in names
            for one in recorded(name)["excused"]
        }

        # Assert
        self.assertEqual((endings, apart), (["PASS"] * 7, {0x04}))

    def test_the_burn_in_self_test_passes_every_sub_test_but_the_envelope(self) -> None:
        # Arrange
        name = "burn-in-rev-d-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))

    def test_the_snsp_aging_self_test_passes_every_sub_test(self) -> None:
        # Arrange
        name = "snsp-aging-1-02-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))

    def test_the_control_deck_tester_self_test_passes_every_sub_test(self) -> None:
        # Arrange
        name = "control-deck-tester-rev-1-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))

    def test_the_aging_1_00_self_test_passes_all_six_of_its_sub_tests(self) -> None:
        # Arrange
        name = "aging-1-00-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))

    def test_the_ntsc_240p_suite_upload_is_echoed_byte_for_byte_and_runs(self) -> None:
        # Arrange
        name = "240p-test-suite-1-061-ntsc"

        # Act
        run = handshake(name)

        # Assert
        self.assertEqual(run, {"echoes": 5562, "of": 5562, "landed": True})

    def test_the_pal_240p_suite_upload_is_echoed_byte_for_byte_and_runs(self) -> None:
        # Arrange
        name = "240p-test-suite-1-061-pal"

        # Act
        run = handshake(name)

        # Assert
        self.assertEqual(run, {"echoes": 5562, "of": 5562, "landed": True})


if __name__ == "__main__":
    unittest.main()

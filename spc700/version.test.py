import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import spc700  # noqa: E402

VERSION_FILE = ROOT / "spc700" / "version.py"


def stamped() -> str:
    line = next(
        one for one in VERSION_FILE.read_text().splitlines() if one.startswith("VERSION = ")
    )
    return line.split('"')[1]


class VersionTest(unittest.TestCase):
    def test_the_version_is_three_numbers(self) -> None:
        # Arrange
        held = spc700.__version__

        # Act
        parts = held.split(".")

        # Assert
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))

    def test_the_package_reports_the_version_the_release_job_stamped(self) -> None:
        # Arrange
        held = stamped()

        # Act
        reported = spc700.__version__

        # Assert
        self.assertEqual(reported, held)


if __name__ == "__main__":
    unittest.main()

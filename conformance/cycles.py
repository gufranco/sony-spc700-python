"""Compare the core against the suite cycle by cycle, not instruction by instruction.

The state comparison beside this one asks what the registers and memory hold
after one instruction. That question cannot see the order the bytes were touched
in, cannot see a read the core performs and discards, and cannot see a cycle the
core spends on itself. Two cores that disagree about all three still pass it.

This asks the other question. Every cycle of every case is compared: what kind of
cycle it was, and which address it drove. A value is compared only where the case
asserts one, because the suite leaves the value null at every address the case
does not name, and at those addresses the byte is whatever the machine held.

Nintendo's command tables give a count per instruction and no breakdown, so the
count is the only part of this a document can settle. The shape comes from the
recording alone, and where the two disagree the disagreement is written down
rather than averaged away.
"""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import Cpu, SparseMemory
from spc700.bus import Bus

EXAMPLE_LIMIT = 5

WAIT = "wait"


def machine_for(initial: dict[str, Any]) -> tuple[Any, Bus]:
    """A processor and memory in exactly the state the case declares."""
    memory = SparseMemory(seed=initial["pc"])
    for address, value in initial["ram"]:
        memory.write8(address, value)

    line = Bus(recording=True)
    cpu = Cpu("spc700", memory=memory, bus=line)
    cpu.a = initial["a"]
    cpu.x = initial["x"]
    cpu.y = initial["y"]
    cpu.sp = initial["sp"]
    cpu.psw = initial["psw"]
    cpu.pc = initial["pc"]
    return cpu, line


def _disagreement(
    index: int, wanted: list[Any], got: tuple[int | None, int | None, str] | None
) -> tuple[int, str, str] | None:
    """Where one cycle of the recording and one cycle of the core part company."""
    address, value, kind = wanted
    if got is None:
        return (index, f"{kind} {address if address is None else f'${address:04X}'}", "nothing")
    mine_address, mine_value, mine_kind = got
    if kind != mine_kind or address != mine_address:
        return (
            index,
            f"{kind} {'-' if address is None else f'${address:04X}'}",
            f"{mine_kind} {'-' if mine_address is None else f'${mine_address:04X}'}",
        )
    if value is not None and value != mine_value:
        return (index, f"{kind} ${address:04X}={value:02X}", f"={mine_value:02X}")
    return None


def check(test: dict[str, Any]) -> list[tuple[int, str, str]]:
    """Every cycle where the core and the recording disagree."""
    cpu, line = machine_for(test["initial"])
    cpu.step()

    wrong: list[tuple[int, str, str]] = []
    recorded = test["cycles"]
    for index, wanted in enumerate(recorded):
        found = _disagreement(index, wanted, line.log[index] if index < len(line.log) else None)
        if found is not None:
            wrong.append(found)
            break

    if not wrong and len(line.log) > len(recorded):
        extra = line.log[len(recorded)]
        wrong.append(
            (
                len(recorded),
                "nothing",
                f"{extra[2]} {'-' if extra[0] is None else f'${extra[0]:04X}'}",
            )
        )
    return wrong


def count_cycles(tests: list[dict[str, Any]]) -> int:
    """How many cycles the comparison covered, which is not how many cases."""
    return sum(len(test["cycles"]) for test in tests)


def run_tests(
    tests: list[dict[str, Any]],
) -> tuple[int, int, list[tuple[str, list[tuple[int, str, str]]]]]:
    """How many agreed, how many did not, and a few that did not."""
    passed = failed = 0
    examples: list[tuple[str, list[tuple[int, str, str]]]] = []
    for test in tests:
        try:
            wrong = check(test)
        except Exception as error:  # noqa: BLE001
            wrong = [(0, "no exception", f"{type(error).__name__}: {str(error)[:40]}")]
        if wrong:
            failed += 1
            if len(examples) < EXAMPLE_LIMIT:
                examples.append((test["name"], wrong))
        else:
            passed += 1
    return passed, failed, examples


def run_file(
    path: Path | str, limit: int | None = None
) -> tuple[int, int, list[tuple[str, list[tuple[int, str, str]]]], int]:
    """One test file, optionally only its first few cases.

    The cycle count travels with the result rather than being recomputed by the
    caller, because recomputing it means reading and limiting the file a second
    time and the two can then disagree about what was measured.
    """
    with Path(path).open() as handle:
        tests = json.load(handle)
    if limit:
        tests = tests[:limit]
    passed, failed, examples = run_tests(tests)
    return passed, failed, examples, count_cycles(tests)


def suite_files(directory: Path | str) -> list[Path]:
    """Every test file in the suite, in a fixed order, or none if it is absent."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"))


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: cycles.py <suite directory> [cases per file] [name filter]")
        return 2

    directory = Path(argv[0])
    limit = int(argv[1]) if len(argv) > 1 else None
    wanted = argv[2] if len(argv) > 2 else ""

    files = [path for path in suite_files(directory) if wanted in path.name]
    if not files:
        print(f"  no suite at {directory}; clone SingleStepTests/ProcessorTests to get one")
        return 0

    print(f"  {len(files)} files from {directory}")
    passed = failed = compared = 0
    broken = []
    for path in files:
        file_passed, file_failed, examples, file_cycles = run_file(path, limit)
        compared += file_cycles
        passed += file_passed
        failed += file_failed
        if file_failed:
            broken.append((path.name, file_failed, examples))

    print(f"  {passed} agreed, {failed} did not, over {compared} cycles")
    for name, count, examples in broken[:EXAMPLE_LIMIT]:
        index, want, got = examples[0][1][0]
        print(
            f"    {name}: {count} wrong, first {examples[0][0]}: cycle {index} want {want} got {got}"
        )
    if len(broken) > EXAMPLE_LIMIT:
        print(f"    and {len(broken) - EXAMPLE_LIMIT} more files with failures")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

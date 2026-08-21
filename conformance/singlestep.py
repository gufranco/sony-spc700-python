"""Check the interpreter against the SingleStepTests suite for the SPC700.

Each case gives a full initial state, the bytes of memory that matter, and the
state one instruction later. This builds exactly that machine, steps once, and
compares every register and every named byte.

Memory outside the bytes a case names is scrambled rather than cleared. The suite
says nothing about those addresses, so an instruction that reads one is reading
something undefined, and filling them with zeroes would make such a read look
deliberate.
"""

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import Cpu, SparseMemory

EXAMPLE_LIMIT = 5

REGISTERS = (
    ("a", "a"),
    ("x", "x"),
    ("y", "y"),
    ("sp", "sp"),
    ("pc", "pc"),
)


def suite_files(directory: Path | str) -> list[Path]:
    """Every test file in the suite, in a fixed order, or none if it is absent."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"))


def machine_for(initial: Mapping[str, Any]) -> tuple[Any, Any]:
    """A processor and memory in exactly the state the case declares."""
    memory = SparseMemory(seed=initial["pc"])
    for address, value in initial["ram"]:
        memory.write8(address, value)

    cpu = Cpu(memory, reset=False)
    cpu.a = initial["a"]
    cpu.x = initial["x"]
    cpu.y = initial["y"]
    cpu.sp = initial["sp"]
    cpu.psw = initial["psw"]
    cpu.pc = initial["pc"]
    return cpu, memory


def check(test: Mapping[str, Any]) -> list[tuple[str, object, object]]:
    """Where the interpreter and the suite disagree after one instruction."""
    cpu, memory = machine_for(test["initial"])
    cpu.step()

    final = test["final"]
    wrong = []
    for name, attribute in REGISTERS:
        if name not in final:
            continue
        got = getattr(cpu, attribute)
        if final[name] != got:
            wrong.append((name, final[name], got))

    if "psw" in final and final["psw"] != cpu.psw:
        wrong.append(("psw", final["psw"], cpu.psw))

    for address, value in final.get("ram", ()):
        got = memory.read8(address)
        if got != value:
            wrong.append((f"${address:04X}", value, got))

    return wrong


def run_tests(
    tests: list[dict[str, Any]],
) -> tuple[int, int, list[tuple[str, list[tuple[str, object, object]]]]]:
    """How many agreed, how many did not, and a few that did not."""
    passed = failed = 0
    examples: list[tuple[str, list[tuple[str, object, object]]]] = []
    for test in tests:
        try:
            wrong = check(test)
        except Exception as error:  # noqa: BLE001
            wrong = [("raised", type(error).__name__, str(error)[:60])]
        if wrong:
            failed += 1
            if len(examples) < EXAMPLE_LIMIT:
                examples.append((test["name"], wrong))
        else:
            passed += 1
    return passed, failed, examples


def run_file(
    path: Path | str, limit: int | None = None
) -> tuple[int, int, list[tuple[str, list[tuple[str, object, object]]]]]:
    """One test file, optionally only its first few cases."""
    with Path(path).open() as handle:
        tests = json.load(handle)
    if limit:
        tests = tests[:limit]
    return run_tests(tests)


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: singlestep.py <suite directory> [tests per file] [name filter]")
        return 2

    directory = Path(argv[0])
    limit = int(argv[1]) if len(argv) > 1 else None
    wanted = argv[2] if len(argv) > 2 else ""

    files = [path for path in suite_files(directory) if wanted in path.name]
    if not files:
        print(f"  no suite at {directory}; clone SingleStepTests/ProcessorTests to get one")
        return 0

    print(f"  {len(files)} files from {directory}")
    passed = failed = 0
    broken = []
    for path in files:
        file_passed, file_failed, examples = run_file(path, limit)
        passed += file_passed
        failed += file_failed
        if file_failed:
            broken.append((path.name, file_failed, examples))

    print(f"  {passed} agreed, {failed} did not")
    for name, count, examples in broken[:EXAMPLE_LIMIT]:
        detail = ", ".join(f"{field} want {want} got {got}" for field, want, got in examples[0][1])
        print(f"    {name}: {count} wrong, first {examples[0][0]}: {detail}")
    if len(broken) > EXAMPLE_LIMIT:
        print(f"    and {len(broken) - EXAMPLE_LIMIT} more files with failures")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

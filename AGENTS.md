# Working in this repository

Read [FAMILY.md](FAMILY.md) first. It is the standard every member of this
family carries, byte for byte, and it decides most questions before they are
asked. What follows is only what is true of this member. [README.md](README.md)
is the document written for a person.

## What this project is, in one paragraph

The SPC700: the processor Sony put inside the SNES audio unit. An interpreter for
all 256 opcodes, held to a published per-opcode corpus that states every register
and every byte of memory before and after, and then held to it again cycle by
cycle, with the address each access drove and the cycle it fell on. Sony
published no data sheet, so the top rung of the authority ladder is occupied by
Nintendo's development manual, which tabulates the instruction set for somebody
writing sound drivers and says almost nothing about what happens inside a cycle.
This models the processor alone: the RAM and the boot ROM beside it are the
audio unit's, not the processor's.

## The interface a caller drives

`Cpu(model, memory)`, the shape every clocked part in the family takes.

| Call                          | What it does                                                            |
| :---------------------------- | :---------------------------------------------------------------------- |
| `step()`                      | One instruction, returning what it cost in cycles                       |
| `run_for(cycles)`             | Instructions until the budget is spent, returning what was really spent |
| `run_until(predicate, limit)` | Instructions until the predicate holds, refusing to run forever         |
| `reset()`                     | The reset line, which is a different event from power on                |
| `held()`                      | Whether the part has stopped advancing the program on its own           |
| `cycles`, `steps`             | What has been spent, and how many instructions spent it                 |

There is no `irq` and no `nmi`, and that is a fact about the part rather than an
omission: the audio unit brings no interrupt line out. `INTERRUPT_LINES` in
[`conformance/family_member.py`](conformance/family_member.py) is empty here, and the
record accounts for why.

`Clock(cpu)` drives it one cycle at a time. Every cycle passes through one place,
so the clock can stop between two cycles of one instruction rather than only
after it.

## The authority ladder

1. **Nintendo's SNES Development Manual, Appendix C**, for the instruction tables
   it prints. All 256 rows are pinned with the page each was read from.
2. **The single step corpus**, for everything the manual does not print, which is
   most of the behaviour and all of the cycle shape.
3. **Nothing else.**

The rung a Sony data sheet would occupy is empty and the record says so rather
than promoting the rung below it.

## What is settled and what is not

**Not settled: 3 things**, each in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with the measurement that would close it.
The sharp one is that most of the cycle shape rests on a recording alone: no
document describes what happens inside a cycle, and the one console measurement,
Shay Green's `spc_mem_access_times.sfc`, holds the memory access timing of 172
opcodes and nothing finer.

Settled: every instruction's effect, every instruction's cycle count and access
order, and every figure the manual prints. One row of the manual disagrees with
the corpus, a console measurement sides with the corpus, and the disagreement is
recorded rather than averaged away.

## Power on scrambles, reset defines

Two events, not one. The constructor does not reset: it hands back a part holding
a scrambled pattern derived from a seed, which is reproducible and is not zero.
`reset()` is the reset line, and it is a separate call.

There is no option to arrive cleared, because no machine hands one over. A model
that answers zero to a read of a byte nothing wrote turns a defect into a passing
test.

## Every cycle passes through one place

`Bus.spend` charges every read, write and idle, and each charge opens a cycle on
the part. `Cpu.settle` is the only thing that closes one: it advances the cycle
count and calls `on_cycle`. It runs just before the next access and at the end of
an instruction, so a clock that stops on a cycle sees the access that cycle
performed and the work done before the next one, and no access moves to another
cycle. A clock stopped on an instruction's last cycle leaves the part as
`step()` does.

## Test cartridges

[`conformance/testroms.json`](conformance/testroms.json) lists every test
cartridge that exercises this processor, each pinned by SHA-256 and none
carried.

**Ten run, in the member that composes this one.** A cartridge needs the audio
unit around this processor and a console to upload into it, so it runs in
[sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python), whose
`conformance/cartridges.py` drives it from a cut-down console with this member
pinned as a submodule:

```bash
cd ../sony-s-smp-python
SSMP_CARTRIDGE_DIR=external/cartridges python3 -m conformance.cartridges
```

What those runs showed is recorded here in
[`conformance/cartridge.json`](conformance/cartridge.json) and replayed by
[`conformance/cartridge.test.py`](conformance/cartridge.test.py) with no image
present:

- Shay Green's `spc_smp.sfc`: 18 of 18 verdicts agree with a console.
- Shay Green's `spc_mem_access_times.sfc`: 2 of 2 agree.
- gilyon's `spctest.sfc`, every opcode but `SLEEP` and `STOP`: `Success`.
- Peter Lemon's seven SPC700 cartridges: every PASS their source prints, with
  the interrupt flag excused. The status word they store differs from what they
  expect in that flag alone, which a reset leaves set here, and his expected
  values carry no stated hardware provenance, so the reset stays an open
  question under what the part holds when it comes up in
  [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) and `conformance/divergences.json`
  records why.

A change to this processor reaches those runs only once sony-s-smp-python moves
its pin, so run them there before calling a change finished.

**Six more run there and are recorded here.** Burn-in revision D, SNSP Aging
1.02, the Control Deck Tester and Aging Program 1.00 upload an SPC700 self-test
that this processor runs: memory patterns, timer counts and the rest, decided
by the program itself. All four pass every sub-test in sony-s-smp-python's
`conformance/selftest.py`. Both builds of the 240p Test Suite upload a driver
through the boot program this processor runs, and every echo and the jump
arrive in its `conformance/handshake.py`. The measurements are in
`conformance/cartridge.json` under `selfTests` and `handshakes`.

The NTF 2.5 test, the Test Program that overdumps it and the controller test
cassette upload a sound driver and check nothing on the unit, so they are not
listed.

## Files kept in `external/`

Everything this member reads and may not ship sits in `external/`, which git
ignores and Dropbox is told to leave alone, per FAMILY.md's "Where the files a
member reads are kept". [`artifacts.manifest.json`](artifacts.manifest.json)
names it by size, CRC32, MD5, SHA-1 and SHA-256:

- `external/conformance-suites/spc700`, the SingleStepTests checkout at the
  commit [`conformance/suites.json`](conformance/suites.json) pins, fetched by
  `python3 -m conformance.fetch`. A test holds its commit to that record.

The test cartridges are not read here. They sit in `sony-s-smp-python`'s
`external/cartridges/`, where the member that runs them keeps them.

```bash
python3 -m conformance.external
python3 -m conformance.external --describe external/<file>
```

The first says which are here, verified, missing or wrong. The second prints
the manifest entry for a file being added, which gets its entry in the same
change.

## Every gate, in the order to run them

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 --with types-setuptools==84.0.0.20260812 mypy==1.14.1
pnpm run format:check
uvx yamllint==1.38.0 --strict .
cov=(uvx --python 3.12 --from coverage==7.6.10 --with setuptools==84.0.0 coverage)
"${cov[@]}" erase
for f in $(find spc700 conformance -name '*.test.py' | sort); do
  "${cov[@]}" run -a "$f" || echo "FAILED $f"
done
"${cov[@]}" report
```

Then the throughput floor, which runs outside the coverage step because a tracer
costs about ten times what the model does:

```bash
python3 -m conformance.speed
```

The conformance walk needs the corpus, which is fetched rather than vendored:

```bash
python3 -m conformance.fetch external/conformance-suites
python3 -m conformance.singlestep external/conformance-suites/spc700/spc700/v1
python3 -m conformance.cycles external/conformance-suites/spc700/spc700/v1
```

And the runs that report what they could not check rather than passing quietly:

```bash
python3 spc700/doctor.py
python3 -m conformance.quotes
```

Everything under `conformance/` runs as a module. Run as a script, its own
directory goes on the import path and a file there shadows any standard library
module of the same name. `doctor.py` is the exception and runs as a file on
purpose, so that it still runs when the package itself will not import, which is
the case it exists for.

## Conventions that are not negotiable

- Python only, standard library only, no dependencies.
- No comments in source, and a docstring counts as one. A step that would need
  a comment is a step that should be a named function.
- Tests sit beside the module they cover as `<module>.test.py`. Arrange, act
  and assert, each block opened by its bare marker.
- 100% statement and branch coverage, enforced. `mypy` at strict, with every
  optional error class on.
- Everything a caller can catch is defined once, in `spc700/errors.py`, and
  imported from there.
- A check nobody has seen fail is not known to work. Drive every new check
  against input that should fail it before keeping it.
- [`spc700/core.py`](spc700/core.py) passes 500 lines under the exemption for
  a single calculation engine sharing intermediate state: one `Cpu` whose 256
  opcode handlers read and write the same registers, flags and bus.

The linter's ignores in [`pyproject.toml`](pyproject.toml) carry no comments, so
their reasons live here:

- `N818`: some exceptions are control flow signals rather than failures. The
  standard library names those without the suffix too, and the ones that report
  a failure do end in `Error`.
- `N999` in tests: a test file sits beside its module and is named after it with
  a dot, so a module and its tests are read together.
- `T201` in `conformance/`: these are command line tools, and printing is their
  output.
- `BLE001` and `T201` in `environment.py`: a check that throws has to become a
  line in the report rather than end the run, and the report is the product.
- `BLE001` and `T201` in the doctor: it has to survive whatever a check throws
  and report it. A narrower catch would let a traceback take the rest of the
  report with it.

The coverage exclusions carry none either:

- `if __name__ == "__main__":`: the guard hands argv to a function that is
  itself tested, and importing the module to cover it would run the tool.
- `if TYPE_CHECKING:`: the block never runs. Python 3.14 drops it before
  coverage sees it and earlier versions do not, so counting it would make the
  gate mean something different on each runtime.
- `^\s*\.\.\.$` and `: \.\.\.$`: a protocol method's ellipsis is a contract the
  type checker reads and the runtime never runs.
- `@unittest\.skipUnless\(A_PART,`,
  `@unittest\.skipUnless\(A_PART and BUILDABLE,` and
  `^def accounts_for_a_reset\(` in the coverage exclusions: this member is not a
  part, so the family tests that build a `Chip` and account for its reset are
  skipped here and their bodies never run.
- `@unittest\.skipUnless\(SOLD_AS_A_COMPONENT,`, `^def machine_mentions\(` and
  `^def listing\(` in the coverage exclusions: this part only existed inside one
  machine, so the family sweep for machine names is skipped here.

The formatter's ignores in [`.prettierignore`](.prettierignore) carry no
comments either, so their reasons live here:

- `pnpm-lock.yaml` and `package-lock.json`: the package manager writes them, in
  its own layout, on every install.
- `node_modules/`, `.venv/`, `venv/`, `build/`, `dist/` and `*.egg-info/`:
  installed or built, never written by hand.
- `.coverage`, `coverage.json`, `htmlcov/` and the tool caches: the output of a
  run, never committed.
- `docs/`, `specs/`, `.work/` and `.claude/`: local working material, never
  committed.

## Layout

```text
spc700/
  __init__.py    the package, and the part chosen at construction
  core.py        the processor
  bus.py         cycles, and the one place they are spent
  clock.py       driving it one cycle at a time
  opcodes.py     the opcode table and a disassembler
  syntax.py      the text each opcode disassembles to
  memory.py      memory that holds what it held
  models.py      the catalogue, and the names the part answers to
  errors.py      everything this package raises, in one place
  doctor.py      what is actually on this machine, printed for a bug report
  version.py     rewritten by the release job and by nothing else
conformance/
  family_*.test.py the family standard, held to this repository, one topic a file
  family_member.py what this member answers to them
  family_shared.py what more than one of them reads
  external.py       which files in external/ are here, verified, missing or wrong
  suites.json    which corpus, at which commit
  fetch.py       fetching it into a cache
  singlestep.py  running it, state by state
  cycles.py      running it, cycle by cycle
  hardware.json  what Nintendo printed, fact by fact, with the page
  divergences.json where the document and the recording part
  cartridge.json what test cartridges showed when sony-s-smp-python ran them
  testroms.json  every test cartridge that exercises this processor
  quotes.py      looks for every quoted sentence in the document it cites
  speed.py       the throughput floor
external/           the SingleStepTests checkout, never committed
artifacts.manifest.json  every file in external/, by size and every digest
```

## Things that will bite you

- **The constructor does not reset.** A test that expects a cleared status word
  gets a scrambled one, and a scrambled P flag sends a direct-page read to page
  one rather than page zero. Set what the test depends on explicitly.
- **`Memory` takes `image` and `fill` separately.** `image` is bytes loaded at
  the bottom with the rest left as it was. `fill` is one byte across the whole
  space. One parameter carrying both was how this was written, and it made an
  image silently zero everything it did not reach.
- **`disassemble(data, offset, address)` takes three.** The offset into the
  buffer and the address it maps to are separate, which the sibling members do
  not need and this one does.
- **The corpus is not here.** A run without it compares nothing and says so.
  `python3 spc700/doctor.py` is the way to find out which state this machine is
  in.

## Before calling anything finished

Every gate above, green, with output shown. A claim without a run behind it is
not evidence. If a check was skipped because a file is not on this machine, say
which check and why rather than reporting a pass.

## What a change is expected to leave behind

A test that fails without the change and passes with it. An entry in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) if it turned a settled thing into an open
one, or removed one. A record entry with the sentence and the page if it added a
fact from the manual. Nothing fetched into the repository, ever.

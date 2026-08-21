<div align="center">

<h1>SPC700</h1>

<strong>An interpreter for the Sony SPC700, the processor inside the SNES audio unit.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml)
[![Conformance](https://img.shields.io/badge/SingleStepTests-256%2C000%20%2F%20256%2C000-brightgreen)](#conformance)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#conformance">Conformance</a> &nbsp;|&nbsp;
  <a href="#the-instructions-worth-knowing-about">Hardware quirks</a> &nbsp;|&nbsp;
  <a href="#what-nothing-starts-clean-means">Undefined state</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/sony-spc700-python/issues">Issues</a>
</p>

**256** opcodes · **256,000** conformance cases and **1,182,940** cycles compared, **0** failures · every cycle count checked against **Nintendo's own tables** · **271** tests · **100%** statement and branch coverage

```python
from spc700 import Cpu, SparseMemory

memory = SparseMemory()
memory.write8(0x0200, 0xE8)
memory.write8(0x0201, 0x42)

cpu = Cpu(memory, model="spc700", reset=False)
cpu.pc = 0x0200
cpu.step()

cpu.a
# 0x42
```

---

## The problem

The SPC700 looks like a 6502 with a couple of extra registers, and that resemblance is the trap. Several of its instructions behave in ways the family would not lead you to expect, and each one is a place where a reasonable implementation quietly diverges from the hardware.

The division does not compute a quotient once the answer stops fitting. The decimal adjust reads an accumulator it has already modified halfway through. The half carry means the opposite thing after a subtraction than it does after an addition. None of those is exotic; all of them are reachable from ordinary audio driver code, and all of them are easy to get subtly wrong in a way no smoke test catches.

## The solution

Every one of the 256 opcodes is implemented, and correctness is measured rather than asserted. Two different questions are asked and both are gates. What do the registers and memory hold one instruction later, against [SingleStepTests](https://github.com/SingleStepTests/ProcessorTests) and its 1,000 cases per opcode. And what happened on the bus while that instruction ran, cycle by cycle, against the same recording. All 256,000 cases and all 1,182,940 cycles agree.

And nothing starts clean. Memory is filled with a reproducible scrambled pattern unless a caller asks for something else in writing, and a reset sets only what the hardware itself defines.

<table>
<tr>
<td width="50%" valign="top">

### Every opcode, no gaps

The SPC700 leaves none of its 256 opcodes undefined, so there is no illegal instruction to decide about and no excuse for a gap.

</td>
<td width="50%" valign="top">

### The awkward ones, verbatim

The division past its useful range, both decimal adjusts, and the inverted half carry are written the way the silicon does them.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Undefined state stays undefined

`SparseMemory` derives an unwritten byte from its address, so such a read is arbitrary, reproducible, and not zero, at no allocation cost.

</td>
<td width="50%" valign="top">

### A disassembler in the same table

One table drives both execution and listing, so a new opcode cannot be added to one and forgotten in the other.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### The oracle is pinned, and watched

The suite commit is pinned so a build is reproducible. A weekly job runs against whatever upstream holds now and opens a pull request or an issue.

</td>
<td width="50%" valign="top">

### No dependencies

Pure Python, standard library only. The release tooling is the sole `node_modules`, and it never ships.

</td>
</tr>
</table>

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | >= 3.12 | [python.org](https://www.python.org/downloads/) |

### Setup

```bash
git clone https://github.com/gufranco/sony-spc700-python.git
cd sony-spc700-python
```

### Verify

```bash
python3 spc700/core.test.py
# Ran 105 tests in 0.03s
# OK
```

## The instructions worth knowing about

These are the four places an implementation written from a summary of the instruction set will disagree with a console.

### The division keeps going past the answer

```python
cpu.y, cpu.a, cpu.x = 0x00, 0x0A, 0x03
cpu.step()
# a = 3, y = 1, an ordinary quotient and remainder
```

Once the quotient no longer fits, the hardware does not fail and does not saturate. It runs the same shift and subtract network past the end of its useful range and leaves behind whatever falls out. The overflow flag reports that the result is not a quotient, and the half carry reports a nibble comparison that has nothing to do with the division at all. Dividing by zero is not a special case either: it takes the same path and produces a defined value.

### The decimal adjust reads what it just wrote

```python
cpu.a, cpu.c = 0x9A, False
cpu.step()
# a = 0x00, c = True
```

`DAA` tests the accumulator twice. The second test looks at the value the first branch may already have changed, so a carry produced by adding sixty feeds the nibble test below it. Testing the original value instead is the obvious reading, and the wrong one.

### The half carry inverts after a subtraction

After `ADC` the half carry is set when a carry crossed out of the low nibble. After `SBC` it is set when one did **not** cross. Carrying the addition rule into the subtraction gives an answer that is right about half the time, which is the worst possible failure mode.

### The direct page moves

The `P` flag decides whether the direct page sits at `$0000` or `$0100`, so the same instruction byte reaches two different addresses depending on a flag set somewhere else entirely. A word read inside that page wraps within the page rather than carrying into the next one.

## What "nothing starts clean" means

```python
from spc700 import Cpu, Memory, SparseMemory

SparseMemory().read8(0x1234)
# some byte derived from the address; the same byte every time; not zero

Memory(size=0x1000).data == bytearray(0x1000)
# False

Memory(size=0x1000, fill=0).data == bytearray(0x1000)
# True, because a caller asked for it in writing

cpu = Cpu(Memory(fill=0))
cpu.a, cpu.x, cpu.y, cpu.sp
# whatever a reset leaves behind, reproducible from the seed, not zero
```

Audio RAM is not cleared at power on. It holds whatever pattern the parts settle into, and a driver that reads a byte before writing it is reading that pattern. Memory that begins at zero makes such a read look deliberate and stable, which is exactly how that class of bug survives a test suite and fails on hardware.

## Where the facts come from

Two sources, in order, and they answer different questions.

**Nintendo's SNES Development Manual, Appendix C** gives every opcode with its length and the cycles it takes. [`conformance/hardware.json`](conformance/hardware.json) pins all 256 rows with the page each was read from, and [`conformance/hardware.test.py`](conformance/hardware.test.py) assembles each instruction, steps it, and checks it against that figure. A citation here is a check that can fail, not a claim in prose.

**The recording** decides everything the manual does not, which is most of what matters. A count per instruction says nothing about which address a cycle drives, where the internal cycles fall, or which reads the part performs and throws away. Two cores agreeing with the manual on all 256 totals can still disagree with each other on most cycles.

Nothing else is evidence. No emulator, no wiki, no other implementation of this part.

> [!WARNING]
> The manual's OCR text layer interleaves the table columns and will hand you a plausible wrong number without complaint. Every row was read off a rendered page image, and the three that disagree with the recording were read again at 450 dots per inch before being called a disagreement.

[`conformance/divergences.json`](conformance/divergences.json) records every place the two part company, including the one instruction Nintendo gives the wrong figure.

### The manual is wrong about one instruction

`MOVW dp, YA` is printed as four cycles. The part takes five.

The fifth is a read of the destination that every store on this part performs and discards. The manual is also uneven here: it gives the reading form `MOVW YA, dp` five cycles for two reads, and the writing form four for two writes plus the same addressing work.

That read is invisible in a comparison of the final state, because the byte goes nowhere. It went unnoticed here through 256,000 passing cases until the bus was compared.

## Conformance

```bash
python3 conformance/fetch.py ~/.cache/conformance-suites

python3 conformance/singlestep.py ~/.cache/conformance-suites/spc700/spc700/v1
#   256 files from ~/.cache/conformance-suites/spc700/spc700/v1
#   256000 agreed, 0 did not

python3 conformance/cycles.py ~/.cache/conformance-suites/spc700/spc700/v1
#   256 files from ~/.cache/conformance-suites/spc700/spc700/v1
#   256000 agreed, 0 did not, over 1182940 cycles
```

The suite is several gigabytes, so [`conformance/fetch.py`](conformance/fetch.py) takes a partial clone that skips blob history and a sparse checkout of only the directories [`conformance/suites.json`](conformance/suites.json) names.

Each case gives a full initial state, the bytes in memory, and the state one instruction later. [`conformance/singlestep.py`](conformance/singlestep.py) builds exactly that machine, steps once, and compares every register, the status register and every named byte. Memory outside the named bytes is scrambled rather than cleared, because the suite says nothing about those addresses.

[`conformance/cycles.py`](conformance/cycles.py) asks the other question. Every cycle carries an address and a kind, and both are compared. A value is compared only where the case asserts one: the suite writes the value as null at every address the case does not name, and there the byte is whatever the machine held. That rule was checked across the suite rather than assumed.

The suite comes from JSMoo by way of SingleStepTests, and its generator is published alongside it, so more cases can be produced than the 1,000 per opcode that ship.

### How the pin is kept honest

| When | What runs | On disagreement |
|:-----|:----------|:----------------|
| Pull request | 100 cases per opcode, both runners, against the pinned commit | Fails the check |
| Push to `main` | Every case, both runners, against the pinned commit | Fails the check |
| Weekly | Every case against whatever upstream holds now | Opens a pull request if it passes, an issue naming the opcodes if it does not |

A pinned oracle keeps a build reproducible and stops an upstream edit from turning this repository red with no commit of its own to explain it. It is also how a repository stops noticing that the thing judging it has moved. [`.github/workflows/suite-watch.yml`](.github/workflows/suite-watch.yml) closes that gap without ever moving the pin on its own.

## Models

The model is chosen at construction, the same way it is across the sibling repositories.

```python
from spc700 import Cpu, SparseMemory, describe

describe("s-smp").name
# 'spc700'

cpu = Cpu(SparseMemory(), model="spc700")
```

| Model | Address bits | Notes |
|:------|:------------:|:------|
| `spc700` | 16 | Sony SPC700, the core inside the S-SMP. Aliases: `spc`, `ssmp`, `smp`, `sonyspc700` |

> [!NOTE]
> Unlike the 65xx parts, the SPC700 has essentially one form. Sony built it into the S-SMP and never sold it separately, so there is no family of pin variants or licensee revisions to model. The catalogue exists anyway, because a hardware difference discovered later should mean adding an entry rather than restructuring the package.

## Project structure

```
spc700/
  __init__.py     the package, and the model chosen at construction
  core.py         the interpreter
  bus.py          the cycle: what happened, and where
  opcodes.py      one table driving both execution and disassembly
  memory.py       memory that holds what it held
  models.py       what each part is
  version.py      rewritten by the release job and by nothing else
conformance/
  fetch.py          partial, sparse, pinned checkout of the suites
  singlestep.py     what the registers and memory hold afterwards
  cycles.py         what happened on the bus, cycle by cycle
  hardware.json     Nintendo's tables, pinned row by row
  hardware.test.py  this core's timing against those rows
  divergences.json  every place the manual and the part part company
  suites.json       which suite, which commit
```

Each module has its tests beside it as `<module>.test.py`, so a module and the cases that pin its behaviour are read together.

## Tests

```bash
for f in spc700/*.test.py conformance/*.test.py; do python3 "$f"; done
```

| Suite | File | Covers |
|:------|:-----|:-------|
| Core | [`spc700/core.test.py`](spc700/core.test.py) | Every opcode, addressing, arithmetic, both decimal adjusts, the division, bit instructions, branches, stack, reset |
| Opcode table | [`spc700/opcodes.test.py`](spc700/opcodes.test.py) | Decoding, bit and call index extraction, disassembly |
| Memory | [`spc700/memory.test.py`](spc700/memory.test.py) | Scrambled fills, sparse derivation, address wrapping, seeding |
| Models | [`spc700/models.test.py`](spc700/models.test.py) | The catalogue, alias matching, construction |
| Bus | [`spc700/bus.test.py`](spc700/bus.test.py) | Recording, counting, masking, and what an internal cycle looks like |
| State harness | [`conformance/singlestep.test.py`](conformance/singlestep.test.py) | State construction, comparison, reporting, the command line |
| Cycle harness | [`conformance/cycles.test.py`](conformance/cycles.test.py) | Which cycles are compared, which values are not, and how a disagreement is named |
| Timing | [`conformance/hardware.test.py`](conformance/hardware.test.py) | Every documented length and cycle count, and both figures of every branch |
| Suite fetch | [`conformance/fetch.test.py`](conformance/fetch.test.py) | Checkout shape, timeouts, failure reporting, against a real git repository |

Nothing is stubbed. The fetch tests run git against a repository built in a temporary directory, because a stand-in for git would only prove the stand-in works.

Coverage is enforced at 100% of statements and branches by [`pyproject.toml`](pyproject.toml), so a new branch without a test fails the build rather than quietly lowering the number.

## Development

| Command | Description |
|:--------|:------------|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `python3 -m coverage run -a <file>` | Run one test file under coverage |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 conformance/fetch.py <dir>` | Fetch the pinned suite |
| `python3 conformance/singlestep.py <dir> [limit] [filter]` | Run the suite |

## Project conventions

| Convention | Source |
|:-----------|:-------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Releases | [semantic-release](https://semantic-release.gitbook.io/), driven by [`.releaserc.json`](.releaserc.json) |
| Lint and format | [Ruff](https://docs.astral.sh/ruff/), configured in [`pyproject.toml`](pyproject.toml) |
| Test layout | `<module>.test.py` beside the module it covers |

## Versioning

This project follows [Semantic Versioning](https://semver.org/), and every release is tagged from `main` by semantic-release. See [releases](https://github.com/gufranco/sony-spc700-python/releases).

> [!IMPORTANT]
> While the version is below `1.0.0`, the public interface may change on a minor release. Pin an exact version if that matters to you.

## FAQ

<details>
<summary><strong>Does this emulate the audio DSP as well?</strong></summary>
<br>

No. This is the SPC700 processor core: instruction execution and its memory interface. The S-DSP that turns the driver's register writes into sound is separate hardware with a separate job, and mixing the two into one package would make neither testable on its own.

</details>

<details>
<summary><strong>Why scramble memory instead of zeroing it?</strong></summary>
<br>

Because audio RAM is not zeroed at power on. Code that reads a byte it never wrote is reading whatever the hardware settled on, and that read is a bug. Zero-filled memory makes it invisible: the value is stable, plausible, and usually harmless, so the test passes and the console does not. Pass `fill=0` when you genuinely want zeroes, and the decision is then recorded in the code.

</details>

<details>
<summary><strong>Is it cycle accurate?</strong></summary>
<br>

Yes, against the recording, and the claim is worth stating precisely. Every cycle of all 256,000 cases is compared: 1,182,940 of them, each by kind and by the address it drives, plus the value wherever the case asserts one. Separately, and with no suite on the machine, every documented cycle count is checked against the figure Nintendo printed for it.

What that does not cover is written down in [`conformance/divergences.json`](conformance/divergences.json). The shape of a cycle rests on the recording alone, because no document describes it. Interrupts are not modelled, because there is no pin to raise one on and the suite never raises one. The reset state of the registers is scrambled rather than claimed, because no source states it. `SLEEP` and `STOP` reproduce a recorded slice of a halt that does not end, which is not a cycle count at all.

</details>

<details>
<summary><strong>Why is there only one model when the sibling repository has several?</strong></summary>
<br>

Because the hardware only has one. The 65xx family was sold to many customers in many packages, so its differences are real and worth modelling. The SPC700 shipped inside one chip in one console.

</details>

## License

[MIT](LICENSE)

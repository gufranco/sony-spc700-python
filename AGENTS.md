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

| Call | What it does |
|:--|:--|
| `step()` | One instruction, returning what it cost in cycles |
| `run_for(cycles)` | Instructions until the budget is spent, returning what was really spent |
| `run_until(predicate, limit)` | Instructions until the predicate holds, refusing to run forever |
| `reset()` | The reset line, which is a different event from power on |
| `held()` | Whether the part has stopped advancing the program on its own |
| `cycles`, `steps` | What has been spent, and how many instructions spent it |

There is no `irq` and no `nmi`, and that is a fact about the part rather than an
omission: the audio unit brings no interrupt line out. `INTERRUPT_LINES` in
[`conformance/family.test.py`](conformance/family.test.py) is empty here, and the
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

**Not settled: 5 things**, each in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with the measurement that would close it.
The sharp one is that the cycle shape rests on a recording alone: no document
describes what happens inside a cycle, so 1,182,940 cycles of agreement are
agreement between two implementations rather than a measurement of silicon.

Settled: every instruction's effect, every instruction's cycle count and access
order, and every figure the manual prints. One row of the manual disagrees with
the corpus and the disagreement is recorded rather than averaged away.

## Power on scrambles, reset defines

Two events, not one. The constructor does not reset: it hands back a part holding
a scrambled pattern derived from a seed, which is reproducible and is not zero.
`reset()` is the reset line, and it is a separate call.

There is no option to arrive cleared, because no machine hands one over. A model
that answers zero to a read of a byte nothing wrote turns a defect into a passing
test.

## Every cycle passes through one place

`Bus.spend` is the only thing that advances the cycle count, and every read,
write and idle goes through it. That is what lets a clock stop mid-instruction,
and it is why the order matters: the access is recorded first and charged second,
so a clock that stops on a cycle sees the access that cycle performed rather than
the one before it.

## Every gate, in the order to run them

```bash
ruff format --check .
ruff check .
mypy
pnpm run format:check
python3 -m coverage erase
for file in $(find spc700 conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
```

Then the throughput floor, which runs outside the coverage step because a tracer
costs about ten times what the model does:

```bash
python3 -m conformance.speed
```

The conformance walk needs the corpus, which is fetched rather than vendored:

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/spc700/spc700/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/spc700/spc700/v1
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
- No comments in source. Reasoning goes in docstrings, and a step that would need
  a comment is a step that should be a named function.
- Tests sit beside the module they cover as `<module>.test.py`. Arrange, blank
  line, one act, blank line, assert, with no section labels.
- 100% statement and branch coverage, enforced. `mypy` at strict, with every
  optional error class on.
- Everything a caller can catch is defined once, in `spc700/errors.py`, and
  imported from there.
- A check nobody has seen fail is not known to work. Drive every new check
  against input that should fail it before keeping it.

## Layout

```text
spc700/
  __init__.py    the package, and the part chosen at construction
  core.py        the processor
  bus.py         cycles, and the one place they are spent
  clock.py       driving it one cycle at a time
  opcodes.py     the opcode table and a disassembler
  memory.py      memory that holds what it held
  models.py      the catalogue, and the names the part answers to
  errors.py      everything this package raises, in one place
  doctor.py      what is actually on this machine, printed for a bug report
  version.py     rewritten by the release job and by nothing else
conformance/
  family.test.py the family standard, held to this repository
  suites.json    which corpus, at which commit
  fetch.py       fetching it into a cache
  singlestep.py  running it, state by state
  cycles.py      running it, cycle by cycle
  hardware.json  what Nintendo printed, fact by fact, with the page
  divergences.json where the document and the recording part
  quotes.py      looks for every quoted sentence in the document it cites
  speed.py       the throughput floor
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

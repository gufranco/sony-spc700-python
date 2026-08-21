# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

An interpreter for the Sony SPC700, the eight bit processor inside the SNES audio
unit. All 256 opcodes are implemented, and the core does not merely execute them:
it emits the bus activity of every cycle, which is the only form in which a claim
of cycle accuracy can be checked. Nintendo's development manual settles how many
cycles each instruction takes. A recording of the part settles what happens
inside them, because no document describes that.

## The authority ladder

1. **`conformance/hardware.json`**, which is Appendix C of Nintendo's SNES
   Development Manual pinned row by row: every opcode with its length, its cycle
   count, and the page it was read from. It decides totals.
2. **`~/.cache/conformance-suites/spc700`**, the SingleStepTests recording pinned
   by commit in `conformance/suites.json`. It decides everything the document
   does not: which address each cycle drives, where the internal cycles fall, and
   which reads the part performs and discards.
3. **Nothing else.** No emulator, no wiki, no other implementation of this part.

`conformance/divergences.json` records every place the two part company.

## Read the page, never the text layer

The manual is a scan with an OCR layer, and that layer interleaves the table
columns. It reads `MOV A, #imm E8 2 2` as four numbers in the wrong order and it
will hand you a plausible wrong figure without complaint.

Every row in `hardware.json` was read off a rendered page:

```bash
pdftoppm -r 200 -png -f 229 -l 236 book1.pdf pages/p
```

Appendix C is PDF pages 227 to 236. The three rows that disagree with the
recording were rendered again at 450 dots per inch before being called a
disagreement.

## Every gate, in the order to run them

```bash
ruff format --check .                     # formatting
ruff check .                              # lint, zero warnings
mypy                                      # types, strict
pnpm run format:check                     # every JSON file
for f in spc700/*.test.py conformance/*.test.py; do python3 "$f"; done
python3 -m coverage report                # fails below 100%

python3 conformance/fetch.py              # brings the suite down, once
python3 conformance/singlestep.py ~/.cache/conformance-suites/spc700/spc700/v1
python3 conformance/cycles.py    ~/.cache/conformance-suites/spc700/spc700/v1
```

The last two are different questions and both must pass. The state comparison
asks what the registers and memory hold afterwards. The cycle comparison asks
what happened on the bus, cycle by cycle, and it is the one that can see a
discarded read or a swapped write order.

Coverage is collected by running each test file under `coverage run -a`, not by a
test runner, and it is 100% of statements and branches.

## What the cycle comparison compares

Every cycle carries an address and a kind. A value is compared only where the
case asserts one: the suite writes the value as null at every address the case
does not name, and there the byte is whatever the machine happened to hold. That
rule was checked rather than assumed, and it holds on every case.

## Things that will bite you

**The second cycle of every instruction is a read of the byte after the opcode.**
Always, on all 256 opcodes and all 256,000 cases. For a one byte instruction that
read is discarded, and `step` issues it. For a longer one it is the operand
fetch. Getting this wrong shifts every subsequent cycle.

**Every store reads its destination first and throws the byte away.** `MOV dp, A`
is read, then write. The exception is `MOV (X)+, A`, which idles instead. Neither
is visible in a state comparison.

**Adding an index costs a cycle.** `dp+X`, `!abs+X`, `!abs+Y`, `[dp+X]` and
`[dp]+Y` each pay one, and the pointer forms pay it before either half of the
pointer is read rather than after. `MOV [dp]+Y, A` pays it after, unlike its
reading twin. That asymmetry is in the recording and is not a mistake here.

**A taken branch costs two cycles more than an untaken one**, which is what the
two figures in the manual's cycle column mean.

**`INCW` and `DECW` write the low half before reading the high half.** Treating
the word as a unit leaves the same two bytes behind and touches them in an order
the part never uses.

**`SLEEP` and `STOP` have no cycle count.** The part halts and repeats a read and
an idle forever. The seven cycles here are where the recording stops.

## What is deliberately not here

- **No firmware, no ROM, no fragment of either.** The IPL boot ROM is Nintendo's
  and is not in this repository in any form.
- **The rest of the S-SMP.** The timers, the four communication ports at 00F0 to
  00FF, and the boot ROM belong to the audio unit around this processor. The
  suite treats those addresses as ordinary memory and so does this.
- **Interrupts.** There is no pin to raise one on and the suite never raises one.

## Conventions

| Thing | Rule |
|:------|:-----|
| Language | Python only |
| Comments | None in source. Docstrings carry the reasoning, and say why rather than what |
| Test layout | `<module>.test.py` beside the module it covers |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Conformance imports | Through `importlib.import_module`, matching the sibling runners, so the module has one name |
| Package manager for tooling | pnpm, never npm |
| Commits | Conventional Commits |

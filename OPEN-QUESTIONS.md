# Open questions

What this project does not know for certain, and what it would take to find out.

Sony published no data sheet for this processor. What exists is Nintendo's
appendix, written for somebody writing sound drivers rather than describing a
part, so it tabulates operands, lengths and cycle counts and says almost nothing
about what happens inside a cycle, what a flag does at an edge, or what the part
holds when it comes up.

That leaves an unusually sharp split. Everything the corpus reaches is settled to
a degree few members reach: 256,000 cases across every opcode, each comparing
every register and every byte of memory before and after, and 1,182,940 cycles
compared access by access with the cycle each access fell on. Everything the
corpus does not reach is open, and the list below is that.

Every entry is also in
[`conformance/divergences.json`](conformance/divergences.json) with its status
and severity, so a program can read what a person reads here.

## Why the corpus cannot close the rest

It is a recording of an implementation rather than a measurement of silicon, and
the family's ladder puts it below a document for that reason. What it settles is
enormous and it settles none of it about the part: two careful implementations
agreeing tells you they agree.

What would move any of these up a rung is a Sony document, and none is known to
exist.

## What would settle almost all of them

A logic analyser on the audio unit's bus while a real cartridge plays, which is
outside what this project can do, or a data sheet nobody has published.

## Where the document and the recording disagree

### `MOVW dp, YA` costs four cycles or five.

**The document says.** Table C-11 gives the instruction as two bytes and four
cycles, read off the rendered page at 450 dots per inch rather than from the scan
text layer, which interleaves the columns.

**What this project follows.** Five, which is what the corpus records.

**Why.** The manual contradicts itself here: the same instruction's read-modify
counterpart is given a count that only makes sense if this one is five, and every
implementation that has been compared records five. The manual keeps the higher
rung and this is the one place the corpus is followed over it, which is why it is
written down rather than quietly resolved.

**What would settle or reopen it.** A second printing of the table, or a
measurement of the real part.

## Where no document exists at all

### What the part holds when it comes up.

**The document says.** Nothing. Appendix C describes the instruction set. Neither
the register contents nor the eight bits of the status word are given power-on
values.

**What this project follows.** A scrambled pattern derived from a seed, which is
reproducible and is not zero.

**Why.** Zero is the one answer that is certainly wrong: a machine does not hand
over cleared registers, and a model that answers zero turns a read of something
nothing wrote into a passing test. The scramble is honest about being arbitrary
in a way zero is not.

**One bit of it is settled, and the part settled it.** The direct-page flag is
cleared rather than scrambled, because the boot program Sony put in the audio
unit depends on it. Those sixty four bytes answer the console's handshake with
`mov $f4,#$aa` and `mov $f5,#$bb`, and a direct-page write reaches the four ports
only while the direct page is the zero page. With the flag set the same two
instructions would write ordinary memory at `$01f4`, the handshake would never
appear at the console, and no cartridge would ever get its audio program
uploaded. Every SNES that has ever made a sound is the measurement.

That is the artifact answering a question the manual leaves open, which is rung
two of this family's ladder rather than a value copied from an implementation.
Nothing else in the flag word moves: the rest is still scrambled because the rest
is still genuinely undefined.

**What would settle or reopen it.** A measurement of a real audio unit at power
on, or a Sony document. Neither is needed for the direct-page bit.

### What an interrupt does.

**The document says.** `BRK` and `RETI` exist as instructions. No figure is given
for an interrupt the part accepts from outside.

**What this project does.** Models neither an interrupt line nor its timing, and
publishes no `irq` or `nmi`, because the audio unit as Sony shipped it brings
none out.

**Why.** A method that pretends a pin exists is an invented interface. The family
requires a clocked part to publish one method per interrupt line it has, and this
part is the reason that list is declared per member rather than assumed.

**What would settle or reopen it.** A schematic of the audio unit showing an
interrupt reaching the processor, or a document naming the pin.

### What happens inside a cycle.

**The document says.** A count per instruction and no breakdown.

**What this project follows.** The corpus, which records an address and a kind
for every cycle, and the model is held to all 1,182,940 of them.

**Why.** It is the only source that says anything at all. That makes the cycle
shape rest on a recording alone, which is a rung lower than anything else here
and is recorded as such rather than presented as settled.

**What would settle or reopen it.** A bus capture, or a Sony document.

### Whether a second independent source agrees.

**The document says.** Not applicable.

**What this project follows.** One corpus.

**Why.** Every other clocked member in this family is compared against a corpus
and a second thing: a die simulation, a second implementation, or a manufacturer
figure. This one has the corpus and Nintendo's tables, and the tables do not
reach the cycle level.

**What is now known.** A second source exists and it disagrees. Shay Green's
`spc_mem_access_times.sfc` walks the instruction set on a console, records which
cycle of each instruction touches memory and how, and checks the whole table
against a value he took on hardware. Run against this model through the audio
unit in [sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python), it
reports `Failed 02` and a table checksum of `CFE3BDF7`. The same check inside his
`spc_smp.sfc` reports the same value.

The obvious way for that to be an artefact is the clock: the console and the
audio unit run from separate crystals, so the harness driving this had to pick a
rate, and picking one is the sort of arbitrary choice that produces a false
result. It does not. Driven at one, two, three and five of the unit's cycles per
console instruction, the checksum is `CFE3BDF7` every time, which is what a
figure that comes out of the part rather than out of the harness looks like.

**What is not known.** Which opcodes disagree, and whose fault it is. The check
publishes one checksum over the whole table rather than a per-opcode expectation,
so a disagreement says the table is wrong somewhere and nothing more. The corpus
this model is held to could be wrong, the model could be reading it wrongly, or
the harness could be. Nothing here separates those.

**What would settle or reopen it.** His reference table, rather than the checksum
over it, which would name the opcodes. Failing that, running the check on real
hardware to confirm it passes there, or a die-level simulation of the part.

## What is not in question

So the boundary is visible rather than implied:

- **Every instruction's effect.** 256,000 cases, every register and every byte of
  memory compared before and after, no failures.
- **Every instruction's cycle count and access order.** 1,182,940 cycles
  compared, each with the address it drove and the cycle it fell on. A case that
  disagrees about when an access happened fails as loudly as one that disagrees
  about what was read.
- **That a clock can stop mid-instruction.** The part spends its cycles through
  one place, so a caller driving the clock gets control back between two cycles
  of one instruction rather than after it.
- **Every cycle count Nintendo printed.** All 256 rows are pinned with the page
  each was read from, and the one disagreement is above.

## What is deliberately not modelled

Absent rather than unknown, and absent on purpose:

- **The rest of the audio unit.** The processor is one of three things Sony put
  in it: the other two are 64 KB of RAM and a 64 byte boot ROM, and neither
  belongs in a processor. The sound generator beside them is
  [sony-s-dsp-python](https://github.com/gufranco/sony-s-dsp-python).
- **The boot ROM.** It is Sony's program and is not carried, not linked to and
  not reconstructible from anything here.
- **Interrupts.** Not because they are unknown, but because the part as shipped
  brings no line out. See above.

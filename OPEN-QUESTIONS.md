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
compared access by access with the cycle each access fell on. One console
measurement now stands behind part of it: Shay Green's check of which cycle of
each of 172 opcodes touches memory reproduces the value he took on hardware.
Everything neither reaches is open, and the list below is that.

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

**Peter Lemon's seven SPC700 cartridges lean on two more bits.** Each one checks
the whole status word after its first instruction and expects the interrupt
flag clear, though neither his program nor the boot program clears it. This
part comes out of reset with the flag set, so every status word his checks
compare is one bit apart from what they expect, the interrupt flag: `ADC #const`
stores `$0f` where it expects `$0b`, `AND #const` and `DEC A` store `$06` where
they expect `$02`. His mirror and his source make no claim that the expected
values were taken on a console, and the screenshots beside them are not a
console's, so they settle nothing and the reset is left as it is.
sony-s-smp-python runs them with that flag alone excused and every other field
compared, and all seven print every PASS (as of 2026-10-19).
`conformance/divergences.json` records it.

**What would settle or reopen it.** A measurement of a real audio unit at power
on, or a Sony document. Neither is needed for the direct-page bit. His cartridges
passing on a console would settle the interrupt flag, and the break flag beside
it, at reset.

### What an interrupt does.

**The document says.** `BRK` and `RETI` exist as instructions. No figure is given
for an interrupt the part accepts from outside.

**What this project does.** Models neither an interrupt line nor its timing, and
publishes no `irq` or `nmi`, because the audio unit as Sony shipped it brings
none out.

**Why.** A method that pretends a pin exists is an invented interface. The family
requires a clocked part to publish one method per interrupt line it has, and this
part is the reason that list is declared per member rather than assumed.

**What was looked at.** The SNESdev wiki's APU pinout page, edited on
2026-10-04, lists all 64 pins of the S-SMP and all 24 of the sound module's
connector. It names no interrupt input on either: the console reaches the module
through the data bus, two address lines, two chip selects, the read and write
strobes and the reset line. That page is a community reading of a board rather
than a document pinned by digest, so it narrows the question and does not close
it. Two pins it names, `T0` and `T1`, are not explained there.

**What would settle or reopen it.** A schematic of the audio unit pinned by
digest, showing what `T0`, `T1` and the two general ports connect to, or a
document naming the pins.

### What happens inside a cycle.

**The document says.** A count per instruction and no breakdown.

**What this project follows.** The corpus, which records an address and a kind
for every cycle, and the model is held to all 1,182,940 of them.

**Why.** It is the only source that names every cycle. A console measurement now
holds part of it: `spc_mem_access_times.sfc` checks which cycle of each of 172
opcodes reads or writes memory against a value taken on hardware, and this model
reproduces that value. What the measurement does not reach is the other 84
opcodes, the addresses an idle cycle drives, and anything a checksum of access
timing cannot tell apart. Those still rest on the recording alone.

**What would settle or reopen it.** A bus capture, or a Sony document. Shay
Green's reference table would name the 172 opcodes one by one rather than as a
checksum.

## What was open and is now closed

**`MOVW dp, YA` costs five cycles, and a console says so.** Table C-11 prints
four. The corpus records five, in the shape read opcode, read operand, read the
low destination byte and discard it, write the low half, write the high half.
Shay Green's `spc_mem_access_times.sfc` settles it against hardware: it walks 172
opcodes, records which cycle of each touches memory and how, and checks the whole
table against `8f 77 58 15`, a value he took on a console. Driven through the
audio unit in [sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python)
with its timers corrected (as of 2026-10-19), this processor produces
`8f 77 58 15`. The same run with `MOVW dp, YA` cut to four cycles, the discarded
read removed, produces `2e a2 c2 0f`. The check reaches this instruction, and
only five matches the console. The manual's four is a misprint, and the record
keeps it as a disagreement with the manual rather than deleting it.

**A second independent source now agrees.** The same console value holds the
access timing of all 172 opcodes in that table, which is a measurement rather
than a second recording. Two earlier versions of this entry located the
disagreement first in this processor and then in the cut-down console the
cartridge was driven from. It was neither. The audio unit's timers restarted
their prescaler whenever a timer was switched on and wrapped a lowered divider
at once, where Nintendo's Book I draws one free-running prescaler for all three
timers and says switching a timer on clears only that timer's two counters,
with its divider matched by equality. With those two corrected in the unit,
the same cut-down console and the same processor give the console's value. The
cartridge is `spc_mem_access_times.sfc`, SHA-256
`53dc8005959d54ccfc95b8d4222e1d51d21e3d9f3491058320f105edc1a4454a`, from
`https://gitlab.com/higan/snes-test-roms` at commit
`26e8aa91e0d3b90b901e7e693bc4a8244b391d7b`, and it is not carried here.

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
  each was read from. The one that disagrees, `MOVW dp, YA`, is settled above by
  a console.

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

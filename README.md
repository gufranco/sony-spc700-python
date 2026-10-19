# Sony SPC700

The Sony SPC700, the processor inside the S-SMP of the SNES audio unit, in Python, stepped one instruction or one cycle at a time and held to Appendix C of Nintendo's SNES Development Manual and to the SingleStepTests corpus.

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-spc700-python)](https://github.com/gufranco/sony-spc700-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**256** opcodes, **256,000** conformance cases and **1,182,940** cycles compared, **0** failures, **256** lengths and **253** cycle counts held to Nintendo's tables, **918** tests, **100%** statement and branch coverage, no dependencies

```python
from spc700 import Cpu, Memory

program = bytes([0xE8, 0x42, 0xC4, 0x10, 0x8F, 0x07, 0x11, 0x2F, 0xFE])
memory = Memory(image=program, fill=0)
cpu = Cpu("spc700", memory).reset()

print([cpu.step() for _ in range(3)])
print(hex(cpu.a), hex(memory.read8(0x10)), hex(memory.read8(0x11)))
print(cpu.run_for(10), cpu.cycles, cpu.steps, cpu.held())
```

```
[2, 4, 5]
0x42 0x42 0x7
12 25 6 False
```

The program loads `$42` into A, stores it at `$10`, writes `$07` to `$11`, then branches to itself forever. `fill=0` zeroes the 64 KB space, so the reset vector at `$FFFE` reads `$0000` and the reset spends 2 cycles reading it. The three instructions cost 2, 4 and 5 cycles. `run_for(10)` runs three 4-cycle branches and reports the 12 cycles it really spent, 2 more than it was asked for.

## Install

| Requirement | Version       |
| :---------- | :------------ |
| Python      | 3.12 or newer |
| git         | Any           |

```bash
git clone https://github.com/gufranco/sony-spc700-python.git
cd sony-spc700-python
python3 spc700/doctor.py
```

The package imports nothing outside the standard library. `pip install git+https://github.com/gufranco/sony-spc700-python.git` installs it into another project.

The doctor checks the machine, builds and resets the part, and looks for the conformance suite in `~/.cache/conformance-suites`. It ends with one line. Paste its whole output into any bug report.

```
  6 checks, nothing to report
```

Releases follow [Semantic Versioning](https://semver.org/) and are cut from the commit history by semantic-release. Every release is tagged and listed on the [releases page](https://github.com/gufranco/sony-spc700-python/releases).

## The interface

`spc700.Cpu(model, memory=None, fill=None, step_limit=STEP_LIMIT, seed=UNSET_SEED, bus=None)` builds one part. `model` is required. `memory` is any object with `read8(address)` and `write8(address, value)`; without one the part gets a `SparseMemory`, or a `Memory` holding `fill` in every byte when `fill` is given. `seed` sets the power-on pattern of the registers. `bus` is a `spc700.Bus`, and the part builds one when it is left out. The constructor does not reset the part.

| Model    | Aliases                            | Address bits | Data bits |
| :------- | :--------------------------------- | :----------- | :-------- |
| `spc700` | `spc`, `ssmp`, `smp`, `sonyspc700` | 16           | 8         |

A name is matched after lowercasing it and dropping `-` and `_`, so `Cpu("S-SMP")` builds the `spc700`.

### Calls

| Call                               | Effect                                                                                                                                                             |
| :--------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `step()`                           | Runs one instruction and returns the cycles it cost. Returns 0 once the part is held                                                                               |
| `run_for(cycles)`                  | Steps until at least `cycles` cycles are spent and returns what was spent. A held part spends the rest one cycle at a time                                         |
| `run_until(predicate, limit=None)` | Steps while `predicate(cpu)` is false and returns the part. Raises `RunLimit` after `limit` instructions, or once `steps` reaches `step_limit`                     |
| `reset(seed=UNSET_SEED)`           | The reset line. Reloads A, X, Y, SP and PSW from the seeded pattern, clears P, reads PC from `$FFFE`, sets `steps` to 0 and releases a held part. Returns the part |
| `held()`                           | True after `SLEEP` or `STOP`                                                                                                                                       |
| `held_cycle()`                     | Spends one cycle of a held part. `Clock` and `run_for` call it                                                                                                     |

The other methods on `Cpu`, `fetch8`, `push16`, `op_adc` and the rest, are the instruction implementation that `step()` dispatches to.

```python
from spc700 import Cpu, Memory, RunLimit

cpu = Cpu("spc700", Memory(image=bytes([0x3D, 0x2F, 0xFD]), fill=0)).reset()
cpu.x = 0
cpu.run_until(lambda part: part.x == 5)
print(cpu.x, cpu.steps, cpu.cycles)

try:
    cpu.run_until(lambda part: part.x == 0, limit=8)
except RunLimit as error:
    print(error)
```

```
5 9 28
gave up after 8 instructions at $0001
```

`INC X` and a branch back to it run until X is 5: five increments at 2 cycles, four branches at 4, and the 2 cycles of the reset.

### State

| Attribute                              | Meaning                                                                                                                                                                                               |
| :------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `a`, `x`, `y`, `sp`, `pc`              | The registers. `sp` addresses page `$01`                                                                                                                                                              |
| `ya`                                   | Y and A read or written as one 16-bit value, Y high                                                                                                                                                   |
| `psw`                                  | The status word as one byte. Writing it sets the eight flags                                                                                                                                          |
| `n`, `v`, `p`, `b`, `h`, `i`, `z`, `c` | The eight flags as booleans                                                                                                                                                                           |
| `direct_page`                          | `$0000` or `$0100`, chosen by `p`                                                                                                                                                                     |
| `cycles`                               | Cycles since the part was built, across resets                                                                                                                                                        |
| `steps`                                | Instructions since the last reset                                                                                                                                                                     |
| `stopped`                              | The flag `held()` reads                                                                                                                                                                               |
| `step_limit`                           | The instruction count at which `run_until` gives up                                                                                                                                                   |
| `model`                                | The canonical model name                                                                                                                                                                              |
| `memory`                               | The store the part reads and writes                                                                                                                                                                   |
| `bus`                                  | The cycle recorder. `bus.cycles` is the cost of the instruction in progress, and with `bus.recording` set, `bus.log` lists each cycle as `(address, value, kind)` with kind `read`, `write` or `wait` |
| `on_cycle`                             | A callable run once per cycle, at its end, after that cycle's work, or `None`. `Clock` installs its own                                                                                               |

### Module contents

| Name                                                                                  | Content                                                                                                              |
| :------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------- |
| `spc700.MODELS`                                                                       | The `Model` records keyed by name: `name`, `summary`, `address_bits`, `data_bits`, `aliases`, `address_mask`         |
| `spc700.Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)`                 | A flat store in `data`. Scrambled from `seed` unless `fill` is given, then `image` copied in at address 0            |
| `spc700.SparseMemory(seed=UNSET_SEED)`                                                | Holds only written bytes in `cells`. An unwritten byte is derived from its address and `seed`                        |
| `spc700.scramble(size, seed=UNSET_SEED)`                                              | The seeded byte pattern behind both stores and the registers                                                         |
| `spc700.UNSET_SEED`                                                                   | The default seed, `0x5A5A5A5A`                                                                                       |
| `spc700.STEP_LIMIT`                                                                   | The default `step_limit`, 2,000,000                                                                                  |
| `spc700.FLAG_N`, `FLAG_V`, `FLAG_P`, `FLAG_B`, `FLAG_H`, `FLAG_I`, `FLAG_Z`, `FLAG_C` | The bits of `psw`: `0x80`, `0x40`, `0x20`, `0x10`, `0x08`, `0x04`, `0x02`, `0x01`                                    |
| `spc700.OPCODES`                                                                      | 256 `(mnemonic, mode, size)` rows indexed by opcode byte. Execution and disassembly both read it                     |
| `spc700.disassemble(data, offset, address, count=None, p=0, stop_at_return=False)`    | A list of instructions, each with `address`, `size`, `text`, `opcode`, `mnemonic` and `mode`                         |
| `spc700.decode(data, offset, address, p=0)`                                           | One instruction at `offset`, with the same fields. Raises `Truncated` when the bytes run out partway through it      |
| `spc700.Bus(recording=False)`                                                         | The cycle recorder a part spends every cycle through, with the `cycles`, `recording` and `log` described under `bus` |
| `spc700.Clock(cpu)`                                                                   | Drives the part one cycle at a time                                                                                  |
| `spc700.__version__`                                                                  | The installed version                                                                                                |

### Errors

| Error               | Raised when                                                                                         |
| :------------------ | :-------------------------------------------------------------------------------------------------- |
| `UnknownModelError` | `Cpu` gets no model name, or one no model goes by. The message lists the names accepted             |
| `RunLimit`          | `run_until` passes its `limit`, or `steps` reaches `step_limit`                                     |
| `ClockClosed`       | `tick()` is called on a closed `Clock`                                                              |
| `Truncated`         | `spc700.decode` runs out of bytes partway through an instruction. `disassemble` stops there instead |

```python
import spc700

for name, model in spc700.MODELS.items():
    print(name, model.aliases, model.address_bits, model.data_bits)

print(spc700.Cpu("S-SMP").model, spc700.OPCODES[0x9E], len(spc700.OPCODES))

for name in (None, "spc800"):
    try:
        spc700.Cpu(name)
    except spc700.UnknownModelError as error:
        print(error)
```

```
spc700 ('spc', 'ssmp', 'smp', 'sonyspc700') 16 8
spc700 ('div', 'ya_x', 1) 256
no model was named, and this package will not choose one for you. Name one of: spc700
spc800 is not a model this package covers; it has spc700
```

### Command-line tools

| Command                             | Arguments                                                                                                                                 | Exit codes                                                                              |
| :---------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------- |
| `python3 spc700/doctor.py`          | None                                                                                                                                      | 0 when every check passes, 1 otherwise                                                  |
| `python3 -m conformance.fetch`      | `[directory] [--latest]`. The directory defaults to `~/.cache/conformance-suites`. `--latest` takes upstream's newest commit over the pin | 0, or 1 when upstream cannot be reached                                                 |
| `python3 -m conformance.singlestep` | `<suite directory> [cases per file] [name filter]`                                                                                        | 0 when every case agrees or no suite is there, 1 on a disagreement, 2 with no arguments |
| `python3 -m conformance.cycles`     | Same as `singlestep`                                                                                                                      | Same as `singlestep`                                                                    |
| `python3 -m conformance.documents`  | `[--check] [--only SUBSTRING]`. `--check` verifies what is on disk without downloading                                                    | 0 when every document verifies, 1 otherwise                                             |
| `python3 -m conformance.quotes`     | None                                                                                                                                      | 0 when every quote is found, or when no document is on the machine; 1 otherwise         |
| `python3 -m conformance.speed`      | None                                                                                                                                      | 0 at or above the throughput floor, 1 below it                                          |
| `python3 -m conformance.links`      | None                                                                                                                                      | 0, or 1 when an address in this file answers 404 or 410                                 |
| `python3 -m conformance.package`    | `<wheel>`                                                                                                                                 | 0 when every module ships and no test does, 1 otherwise, 2 with no arguments            |

## Running it at a real speed

The model runs as fast as the host allows. A host that wants the part's pace gives it a budget of cycles per slice and carries the overshoot into the next slice, because an instruction is not divisible.

```python
from spc700 import Cpu, Memory

cpu = Cpu("spc700", Memory(image=bytes([0x2F, 0xFE]), fill=0)).reset()
owed = 0
for _ in range(3):
    budget = 10 - owed
    spent = cpu.run_for(budget)
    owed = spent - budget
    print(spent, owed, cpu.cycles)
```

```
12 2 14
8 0 22
12 2 34
```

The program is one 4-cycle branch to itself. The first slice of 10 spends 12, so the second asks for 8, and after three slices the part has spent 32 cycles for a requested 30 with the 2 still owed. A host sleeps after each slice for the time those cycles take at the part's clock.

`python3 -m conformance.speed` times 20,000 `step()` calls five times and fails below a floor of 150,000 instructions per second. CI runs it outside the coverage step, so a tracer does not slow the measurement.

## Driving it one cycle at a time

`Clock(cpu)` stops the part between any two cycles, including two cycles of one instruction. A host can change what the next read answers partway through an instruction.

```python
from spc700 import Clock, ClockClosed, Cpu, Memory

cpu = Cpu("spc700", Memory(image=bytes([0xE8, 0x2A, 0xC4, 0x20]), fill=0)).reset()
with Clock(cpu) as clock:
    seen = []
    for _ in range(6):
        clock.tick()
        seen.append((clock.cycles, cpu.steps, hex(cpu.a)))
print(seen)

try:
    clock.tick()
except ClockClosed as error:
    print(error)
```

```
[(1, 1, '0xeb'), (2, 1, '0x2a'), (3, 2, '0x2a'), (4, 2, '0x2a'), (5, 2, '0x2a'), (6, 2, '0x2a')]
this clock has been closed
```

`MOV A, #$2A` takes 2 cycles. After the first tick only the opcode has been fetched, and A still holds its power-on value, `$EB`. The second tick ends the instruction, so A holds `$2A` as one `step()` leaves it, whether the clock is then closed or not. The third tick stops on the first cycle of the store.

| Clock call        | Effect                                                                  |
| :---------------- | :---------------------------------------------------------------------- |
| `tick()`          | Advances one cycle and returns `cycles`                                 |
| `run_for(cycles)` | Calls `tick()` that many times and returns `cycles`                     |
| `cycles`          | Ticks since this clock was built                                        |
| `close()`         | Stops the worker thread and gives the part back its previous `on_cycle` |

A `Clock` is an iterator that yields `tick()` until closed, and a context manager that closes on exit. It runs the part on a thread that blocks wherever a cycle is spent, so it is slower than `step()`. A held part keeps spending cycles under a clock.

## Models

The model is named at construction, and there is no default. The catalogue has one entry because Sony built the SPC700 into the S-SMP and sold no separate part or variant.

```python
from spc700 import Cpu, SparseMemory

for name in ("spc700", "s-smp", "SPC"):
    print(Cpu(name, SparseMemory()).model)
```

```
spc700
spc700
spc700
```

An alias builds the part it names, and the part reports the canonical name.

## Reading without running

`disassemble(data, offset, address)` takes the offset into the buffer and the address that offset maps to as separate arguments. `p` sets the direct page used to print direct-page operands.

```python
from spc700 import Truncated, decode, disassemble

program = bytes([0xE8, 0x42, 0xC4, 0x10, 0x3F, 0x00, 0x04, 0x6F, 0x8F])
for found in disassemble(program, 0, 0x0200):
    print(f"{found.address:04X}  {found.size}  {found.text}")

for found in disassemble(program, 0, 0x0200, p=1, count=2):
    print(f"{found.address:04X}  {found.text}")

try:
    decode(program, 8, 0x0208)
except Truncated as error:
    print(error)
```

```
0200  2  mov a,#$42
0202  2  mov $010,a
0204  3  call $0400
0207  1  ret
0200  mov a,#$42
0202  mov $110,a
opcode 8F at 8 needs 3 bytes, 1 remain
```

The last byte, `$8F`, opens a 3-byte `MOV dp, #imm`. `disassemble` stops before it, and `decode` raises `Truncated` on it. `stop_at_return=True` ends a listing after the first `RET` or `RETI`.

## Nothing starts clean

```python
from spc700 import Cpu, Memory, SparseMemory, scramble

print(hex(SparseMemory().read8(0x1234)), hex(SparseMemory(seed=1).read8(0x1234)))
print(Memory(size=0x1000).data == bytearray(0x1000))
print(Memory(size=0x1000, fill=0).data == bytearray(0x1000))
print(scramble(6).hex())

cpu = Cpu("spc700", Memory(fill=0))
print(hex(cpu.a), hex(cpu.x), hex(cpu.y), hex(cpu.sp), hex(cpu.pc), hex(cpu.psw))
cpu.reset()
print(hex(cpu.a), hex(cpu.x), hex(cpu.y), hex(cpu.sp), hex(cpu.pc), hex(cpu.psw))
```

```
0x5e 0xc8
False
True
eb6cefd86c31
0xeb 0x6c 0xef 0xd8 0x316c 0x6c
0xeb 0x6c 0xef 0xd8 0x0 0x4c
```

Audio RAM holds no defined value at power on, so neither store starts at zero unless `fill` asks for it. `SparseMemory` answers an unwritten address with the same byte on every read, derived from the address and the seed, and allocates nothing for it. A newly built part takes A, X, Y and SP from the first four bytes of `scramble(6)`, PSW from the fifth, and PC from the last two, low byte first. `reset()` reloads them from the same pattern, clears P and loads PC from the reset vector, which reads `$0000` here.

## The instructions worth knowing about

Four behaviours where the SPC700 departs from the 6502 it resembles. Each one is checked by the suite.

### The division keeps going past the answer

```python
from spc700 import Cpu, Memory


def divide(ya, x):
    cpu = Cpu("spc700", Memory(image=bytes([0x9E]), fill=0)).reset()
    cpu.ya, cpu.x = ya, x
    cost = cpu.step()
    return hex(cpu.a), hex(cpu.y), cpu.v, cpu.h, cost


print(divide(0x000A, 0x03))
print(divide(0x0400, 0x02))
print(divide(0x1234, 0x00))
```

```
('0x3', '0x1', False, False, 12)
('0xff', '0x2', True, True, 12)
('0xed', '0x34', True, True, 12)
```

`DIV YA, X` costs 12 cycles in every case. 10 divided by 3 gives quotient 3 and remainder 1. 1,024 divided by 2 does not fit in A, and the part returns `$FF` and `$02` with V set. Dividing by zero raises nothing and returns `$ED` and `$34`. H compares the low nibbles of X and Y and says nothing about the quotient.

### The decimal adjust reads what it just wrote

```python
from spc700 import Cpu, Memory

cpu = Cpu("spc700", Memory(image=bytes([0xDF]), fill=0)).reset()
cpu.a, cpu.c, cpu.h = 0x9A, False, False
cpu.step()
print(hex(cpu.a), cpu.c)
```

```
0x0 True
```

`DAA` tests A twice. `$9A` is above `$99`, so it adds `$60` and sets C, giving `$FA`. The second test reads that new value, whose low nibble `$A` is above 9, and adds `$06`, giving `$00`. `DAS` does the same in reverse.

### The half carry inverts after a subtraction

```python
from spc700 import Cpu, Memory


def half_carry(opcode, a, operand, carry):
    cpu = Cpu("spc700", Memory(image=bytes([opcode, operand]), fill=0)).reset()
    cpu.a, cpu.c = a, carry
    cpu.step()
    return hex(cpu.a), cpu.h


print(half_carry(0x88, 0x0F, 0x01, False))
print(half_carry(0xA8, 0x10, 0x01, True))
print(half_carry(0xA8, 0x1F, 0x01, True))
```

```
('0x10', True)
('0xf', False)
('0x1e', True)
```

After `ADC` H is set when a carry left the low nibble. After `SBC` H is set when no borrow crossed it: `$10 - 1` borrows and clears H, `$1F - 1` does not and sets it.

### The direct page moves

```python
from spc700 import Cpu, Memory

memory = Memory(image=bytes([0xE4, 0x10]), fill=0)
memory.write8(0x0010, 0xAA)
memory.write8(0x0110, 0xBB)
for page in (False, True):
    cpu = Cpu("spc700", memory).reset()
    cpu.p = page
    cpu.step()
    print(cpu.direct_page, hex(cpu.a))
```

```
0 0xaa
256 0xbb
```

The same `MOV A, $10` reads `$0010` with P clear and `$0110` with P set. A 16-bit read at the last byte of the direct page takes its high byte from the first byte of the same page.

## Is it right

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/spc700/spc700/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/spc700/spc700/v1
```

`singlestep` ends with `256000 agreed, 0 did not`, and `cycles` with `256000 agreed, 0 did not, over 1182940 cycles`. Each exits 1 on any disagreement.

The corpus is SingleStepTests/ProcessorTests, 1,000 cases per opcode, pinned by commit in [`conformance/suites.json`](conformance/suites.json). [`conformance/fetch.py`](conformance/fetch.py) takes a partial clone with a sparse checkout of the `spc700` directory only. Each case gives a full state, the bytes in memory, and the state one instruction later.

[`conformance/singlestep.py`](conformance/singlestep.py) builds that machine, steps once, and compares every register, the status word and every named byte. Memory the case does not name is scrambled. [`conformance/cycles.py`](conformance/cycles.py) compares each cycle's address and kind, and its value wherever the case states one.

| When           | What runs                                                | On disagreement                                                                        |
| :------------- | :------------------------------------------------------- | :------------------------------------------------------------------------------------- |
| Pull request   | 100 cases per opcode, both runners, at the pinned commit | The check fails                                                                        |
| Push to `main` | Every case, both runners, at the pinned commit           | The check fails                                                                        |
| Every Monday   | Every case at upstream's newest commit                   | A pull request moving the pin if it passes, an issue naming the opcodes if it does not |

[`.github/workflows/suite-watch.yml`](.github/workflows/suite-watch.yml) runs the weekly job and never moves the pin on its own.

### Where the facts come from

1. Nintendo's SNES Development Manual, Book 1, Appendix C, tables C-4 to C-20. [`conformance/hardware.json`](conformance/hardware.json) pins all 256 rows with their byte length, cycle count and page. Each row was read off the rendered page at 200 dots per inch, because the scan's text layer interleaves the table columns. [`conformance/hardware.test.py`](conformance/hardware.test.py) checks every row's length, assembles and steps each instruction, and checks 253 cycle counts, including both counts of all 28 conditional branches. The other 3 rows follow the corpus: `MOVW dp, YA` below, and `SLEEP` and `STOP`, which halt and never finish. The manual prints 3 cycles for them, the recording stops at 7, and the model reproduces the 7.
2. The corpus, for everything the manual does not print: which address each cycle drives, where the internal cycles fall, and which reads the part performs and discards.
3. Nothing else.

Sony published no data sheet for the SPC700, and the record names that rung as empty.

### The manual is wrong about one instruction

Table C-11 on manual page C-8 prints `MOVW dp, YA` as 4 cycles, and `MOVW YA, dp` as 5. The part takes 5 for both. The store reads its destination first and discards the byte, like every store on this part:

```python
from spc700 import Cpu, Memory

cpu = Cpu("spc700", Memory(image=bytes([0xDA, 0x40]), fill=0)).reset()
cpu.ya = 0x1234
cpu.bus.recording = True
print(cpu.step())
for address, value, kind in cpu.bus.log:
    print(kind, f"${address:04X}", f"${value:02X}")
```

```
5
read $0000 $DA
read $0001 $40
read $0040 $00
write $0040 $34
write $0041 $12
```

The read of `$0040` leaves no trace in the final state, so only the cycle comparison sees it. This row was read again at 450 dots per inch before being recorded as a disagreement. A console settles it: Shay Green's `spc_mem_access_times.sfc` checks which cycle of each of 172 opcodes touches memory against a value taken on hardware, and the composed audio unit reproduces that value with this instruction at 5 cycles and misses it at 4.

[`conformance/divergences.json`](conformance/divergences.json) holds this and the 6 other places where a source is silent or the model departs from one, each with its status and severity. [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) gives each open one the measurement that would settle it. Interrupts are not modelled because the audio unit brings out no interrupt line. The timers, ports and DSP around the processor are outside this package.

Test cartridges run in [sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python), which composes this processor into the audio unit and drives it from a cut-down console. [`conformance/cartridge.json`](conformance/cartridge.json) records what they showed: Shay Green's `spc_smp` agrees with a console on 18 of 18 verdicts and his `spc_mem_access_times` on 2 of 2, and gilyon's `spctest`, which tests every opcode but `SLEEP` and `STOP`, reports `Success`. Peter Lemon's seven SPC700 cartridges print every PASS with one field excused, the interrupt flag a reset leaves set here: his expected values carry no stated hardware provenance, so [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) keeps the reset open. [`conformance/testroms.json`](conformance/testroms.json) lists every test cartridge for this processor. Four factory and service cartridges, Burn-in revision D, SNSP Aging 1.02, the Control Deck Tester and Aging Program 1.00, upload a self-test this processor runs, and all four pass every sub-test; both builds of the 240p Test Suite upload a driver through the boot program it runs, and every echo arrives.

## Working on it

| Need                                                            | Where                                                                  |
| :-------------------------------------------------------------- | :--------------------------------------------------------------------- |
| Every gate and the order to run them                            | [CONTRIBUTING.md](CONTRIBUTING.md)                                     |
| The same material for a coding agent                            | [AGENTS.md](AGENTS.md)                                                 |
| The standard this repository shares with the rest of the family | [FAMILY.md](FAMILY.md)                                                 |
| Bug reports                                                     | [GitHub Issues](https://github.com/gufranco/sony-spc700-python/issues) |
| Security reports                                                | [SECURITY.md](SECURITY.md)                                             |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 spc700/core.test.py
```

Each module has a test file beside it named `<module>.test.py`, and each runs on its own as above. Coverage is a hard gate at 100% statement and branch, set in [pyproject.toml](pyproject.toml).

## References

- _SNES Development Manual, Book 1_, Nintendo of America Inc., undated. Appendix C, SPC700 Commands. 240 pages, 21,022,582 bytes, SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`. It is not redistributable and is not in this repository. `python3 -m conformance.documents` downloads it into `docs/`, which git ignores, and refuses any file whose digest differs. [`conformance/documents.json`](conformance/documents.json) holds its address. `python3 -m conformance.quotes` finds every sentence [`conformance/hardware.json`](conformance/hardware.json) quotes from it.
- SingleStepTests/ProcessorTests, `spc700/v1`, at commit `bb11756436da8fd16cce86aef63dc6725f48836f`, https://github.com/SingleStepTests/ProcessorTests. 1,000 cases for each of the 256 opcodes.

## Citing this

[CITATION.cff](CITATION.cff) is updated with each release by the script that stamps the package version.

## License

MIT. See [LICENSE](LICENSE).

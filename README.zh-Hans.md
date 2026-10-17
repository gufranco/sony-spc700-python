# Sony SPC700

Sony SPC700 是 SNES 音频单元中 S-SMP 内部的处理器。本项目用 Python 实现它，可以每次执行一条指令或一个周期，并以 Nintendo 的 SNES Development Manual 附录 C 和 SingleStepTests 语料库为准。

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-spc700-python)](https://github.com/gufranco/sony-spc700-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**256** 个操作码，比对了 **256,000** 个一致性用例和 **1,182,940** 个周期，**0** 个失败，**256** 个长度和 **253** 个周期数与 Nintendo 的表格一致，**868** 个测试，**100%** 语句和分支覆盖率，无依赖

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

该程序把 `$42` 载入 A，存到 `$10`，把 `$07` 写入 `$11`，然后永远跳转到自身。`fill=0` 将 64 KB 空间清零，因此位于 `$FFFE` 的复位向量读出 `$0000`，复位花 2 个周期读取它。这三条指令分别耗费 2、4 和 5 个周期。`run_for(10)` 执行了三次 4 周期的跳转，并报告实际花费的 12 个周期，比要求的多 2 个。

## 安装

| 要求 | 版本 |
|:--|:--|
| Python | 3.12 或更新 |
| git | 任意 |

```bash
git clone https://github.com/gufranco/sony-spc700-python.git
cd sony-spc700-python
python3 spc700/doctor.py
```

该包只导入标准库中的内容。`pip install git+https://github.com/gufranco/sony-spc700-python.git` 可以把它安装到其他项目中。

诊断脚本检查本机环境，构建并复位该器件，并在 `~/.cache/conformance-suites` 中查找一致性测试套件。它最后输出一行。提交缺陷报告时，请粘贴它的完整输出。

```
  6 checks, nothing to report
```

版本发布遵循 [Semantic Versioning](https://semver.org/)，由 semantic-release 根据提交历史生成。每个版本都打上标签，并列在[版本发布页面](https://github.com/gufranco/sony-spc700-python/releases)上。

## 接口

`spc700.Cpu(model, memory=None, fill=None, step_limit=STEP_LIMIT, seed=UNSET_SEED, bus=None)` 构建一个器件。`model` 是必需的。`memory` 可以是任何具有 `read8(address)` 和 `write8(address, value)` 的对象；不提供时，器件得到一个 `SparseMemory`，若给出了 `fill`，则得到一个每个字节都为 `fill` 的 `Memory`。`seed` 设定寄存器的上电模式。`bus` 是一个 `spc700.Bus`，省略时器件会自行构建一个。构造函数不会复位器件。

| 型号 | 别名 | 地址位数 | 数据位数 |
|:--|:--|:--|:--|
| `spc700` | `spc`、`ssmp`、`smp`、`sonyspc700` | 16 | 8 |

名称先转为小写并去掉 `-` 和 `_` 再匹配，因此 `Cpu("S-SMP")` 构建的是 `spc700`。

### 调用

| 调用 | 作用 |
|:--|:--|
| `step()` | 执行一条指令并返回其耗费的周期数。器件进入挂起状态后返回 0 |
| `run_for(cycles)` | 持续单步执行，直到至少花费 `cycles` 个周期，并返回实际花费的周期数。挂起的器件以每次一个周期的方式花掉剩余部分 |
| `run_until(predicate, limit=None)` | 在 `predicate(cpu)` 为假时持续单步执行，并返回该器件。执行 `limit` 条指令后，或 `steps` 达到 `step_limit` 时，抛出 `RunLimit` |
| `reset(seed=UNSET_SEED)` | 复位线。从带种子的模式重新载入 A、X、Y、SP 和 PSW，清除 P，从 `$FFFE` 读取 PC，将 `steps` 置为 0，并释放挂起的器件。返回该器件 |
| `held()` | 执行 `SLEEP` 或 `STOP` 后为 True |
| `held_cycle()` | 让挂起的器件花费一个周期。`Clock` 和 `run_for` 会调用它 |

`Cpu` 上的其他方法，如 `fetch8`、`push16`、`op_adc` 等，是 `step()` 分派到的指令实现。

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

`INC X` 和跳回它的分支一直运行到 X 为 5：五次自增各 2 个周期，四次跳转各 4 个周期，再加上复位的 2 个周期。

### 状态

| 属性 | 含义 |
|:--|:--|
| `a`、`x`、`y`、`sp`、`pc` | 寄存器。`sp` 寻址 `$01` 页 |
| `ya` | 作为一个 16 位值读写的 Y 和 A，Y 为高位 |
| `psw` | 作为一个字节的状态字。写入它会设置八个标志 |
| `n`、`v`、`p`、`b`、`h`、`i`、`z`、`c` | 以布尔值表示的八个标志 |
| `direct_page` | `$0000` 或 `$0100`，由 `p` 选择 |
| `cycles` | 自器件构建以来的周期数，跨越复位累计 |
| `steps` | 自上次复位以来的指令数 |
| `stopped` | `held()` 读取的标志 |
| `step_limit` | `run_until` 放弃时的指令数 |
| `model` | 规范的型号名称 |
| `memory` | 器件读写的存储 |
| `bus` | 周期记录器。`bus.cycles` 是正在执行的指令的耗费，设置 `bus.recording` 后，`bus.log` 将每个周期列为 `(address, value, kind)`，其中 kind 为 `read`、`write` 或 `wait` |
| `on_cycle` | 每个周期运行一次的可调用对象，或 `None`。`Clock` 会安装自己的 |

### 模块内容

| 名称 | 内容 |
|:--|:--|
| `spc700.MODELS` | 以名称为键的 `Model` 记录：`name`、`summary`、`address_bits`、`data_bits`、`aliases`、`address_mask` |
| `spc700.Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)` | 位于 `data` 中的平坦存储。除非给出 `fill`，否则按 `seed` 打乱，然后把 `image` 复制到地址 0 处 |
| `spc700.SparseMemory(seed=UNSET_SEED)` | 只在 `cells` 中保存写入过的字节。未写入的字节由其地址和 `seed` 推导得出 |
| `spc700.scramble(size, seed=UNSET_SEED)` | 两种存储和寄存器背后的带种子字节模式 |
| `spc700.UNSET_SEED` | 默认种子，`0x5A5A5A5A` |
| `spc700.STEP_LIMIT` | 默认的 `step_limit`，2,000,000 |
| `spc700.FLAG_N`、`FLAG_V`、`FLAG_P`、`FLAG_B`、`FLAG_H`、`FLAG_I`、`FLAG_Z`、`FLAG_C` | `psw` 的各位：`0x80`、`0x40`、`0x20`、`0x10`、`0x08`、`0x04`、`0x02`、`0x01` |
| `spc700.OPCODES` | 按操作码字节索引的 256 行 `(mnemonic, mode, size)`。执行和反汇编都读取它 |
| `spc700.disassemble(data, offset, address, count=None, p=0, stop_at_return=False)` | 指令列表，每条带有 `address`、`size`、`text`、`opcode`、`mnemonic` 和 `mode` |
| `spc700.decode(data, offset, address, p=0)` | `offset` 处的一条指令，带有相同的属性。字节在指令中途用完时抛出 `Truncated` |
| `spc700.Bus(recording=False)` | 器件每个周期都经过的周期记录器，带有 `bus` 一项所述的 `cycles`、`recording` 和 `log` |
| `spc700.Clock(cpu)` | 以每次一个周期的方式驱动器件 |
| `spc700.__version__` | 已安装的版本 |

### 错误

| 错误 | 抛出时机 |
|:--|:--|
| `UnknownModelError` | `Cpu` 没有得到型号名称，或得到的名称不对应任何型号。消息中列出可接受的名称 |
| `RunLimit` | `run_until` 超过其 `limit`，或 `steps` 达到 `step_limit` |
| `ClockClosed` | 在已关闭的 `Clock` 上调用 `tick()` |
| `Truncated` | `spc700.decode` 在一条指令中途用完了字节。`disassemble` 则在该处停止 |

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

### 命令行工具

| 命令 | 参数 | 退出码 |
|:--|:--|:--|
| `python3 spc700/doctor.py` | 无 | 所有检查通过时为 0，否则为 1 |
| `python3 -m conformance.fetch` | `[directory] [--latest]`。目录默认为 `~/.cache/conformance-suites`。`--latest` 采用上游最新的提交，而非固定的提交 | 0，无法连接上游时为 1 |
| `python3 -m conformance.singlestep` | `<suite directory> [cases per file] [name filter]` | 所有用例一致或没有测试套件时为 0，出现不一致时为 1，无参数时为 2 |
| `python3 -m conformance.cycles` | 与 `singlestep` 相同 | 与 `singlestep` 相同 |
| `python3 -m conformance.documents` | `[--check] [--only SUBSTRING]`。`--check` 只校验磁盘上已有的内容，不下载 | 所有文档校验通过时为 0，否则为 1 |
| `python3 -m conformance.quotes` | 无 | 找到所有引文，或本机上没有文档时为 0；否则为 1 |
| `python3 -m conformance.speed` | 无 | 达到或超过吞吐量下限时为 0，低于下限时为 1 |
| `python3 -m conformance.links` | 无 | 0，本文件中的某个地址返回 404 或 410 时为 1 |
| `python3 -m conformance.package` | `<wheel>` | 每个模块都已打包且没有测试被打包时为 0，否则为 1，无参数时为 2 |

## 以真实速度运行

该模型以宿主允许的最快速度运行。需要器件真实节奏的宿主为每个时间片分配一个周期预算，并把超出的部分计入下一个时间片，因为一条指令不可分割。

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

该程序是一条跳转到自身的 4 周期分支指令。第一个 10 周期的时间片花费了 12 个周期，所以第二个时间片请求 8 个；三个时间片之后，器件为请求的 30 个周期花费了 32 个，仍欠 2 个。宿主在每个时间片之后休眠，时长为这些周期在器件时钟下所需的时间。

`python3 -m conformance.speed` 对 20,000 次 `step()` 调用计时五次，低于每秒 150,000 条指令的下限即失败。CI 在覆盖率步骤之外运行它，避免追踪器拖慢测量。

## 每次驱动一个周期

`Clock(cpu)` 可以在任意两个周期之间暂停器件，包括同一条指令的两个周期之间。宿主可以在指令执行中途改变下一次读取的应答。

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
[(1, 0, '0xeb'), (2, 0, '0xeb'), (3, 1, '0x2a'), (4, 1, '0x2a'), (5, 1, '0x2a'), (6, 1, '0x2a')]
this clock has been closed
```

`MOV A, #$2A` 需要 2 个周期。第二个节拍之后，操作数已被取出，A 仍保持其上电值 `$EB`。A 在第三个节拍之前改变，第三个节拍停在存储指令的第一个周期上。

| Clock 调用 | 作用 |
|:--|:--|
| `tick()` | 前进一个周期并返回 `cycles` |
| `run_for(cycles)` | 调用 `tick()` 相应次数并返回 `cycles` |
| `cycles` | 自该时钟构建以来的节拍数 |
| `close()` | 停止工作线程，并把之前的 `on_cycle` 还给器件 |

`Clock` 是一个迭代器，在关闭之前不断产出 `tick()`；它也是一个上下文管理器，退出时关闭。它在一个线程上运行器件，该线程在每个花费周期的地方阻塞，因此比 `step()` 慢。挂起的器件在时钟驱动下仍会持续花费周期。

## 型号

型号在构造时指定，没有默认值。目录中只有一项，因为 Sony 把 SPC700 内置于 S-SMP 中，没有单独销售该器件或其变体。

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

别名构建它所指的器件，器件报告规范名称。

## 不运行而读取

`disassemble(data, offset, address)` 将缓冲区中的偏移量和该偏移量对应的地址作为两个独立参数。`p` 设定打印直接页操作数时所用的直接页。

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

最后一个字节 `$8F` 开始一条 3 字节的 `MOV dp, #imm`。`disassemble` 在它之前停止，`decode` 则对它抛出 `Truncated`。`stop_at_return=True` 使列表在第一条 `RET` 或 `RETI` 之后结束。

## 一切都不是从干净状态开始

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

音频 RAM 在上电时没有确定的值，因此除非 `fill` 要求，两种存储都不会从零开始。`SparseMemory` 对未写入的地址每次读取都返回同一个字节，该字节由地址和种子推导得出，且不为其分配任何空间。新构建的器件从 `scramble(6)` 的前四个字节取得 A、X、Y 和 SP，从第五个字节取得 PSW，从最后两个字节取得 PC，低字节在前。`reset()` 从同一模式重新载入它们，清除 P，并从复位向量载入 PC，此处复位向量读出 `$0000`。

## 值得了解的指令

SPC700 与它所类似的 6502 有四处不同的行为。每一处都由测试套件检查。

### 除法在得出答案后仍继续

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

`DIV YA, X` 在任何情况下都耗费 12 个周期。10 除以 3 得到商 3、余数 1。1,024 除以 2 的结果放不进 A，器件返回 `$FF` 和 `$02`，并设置 V。除以零不会抛出任何异常，返回 `$ED` 和 `$34`。H 比较 X 和 Y 的低半字节，与商无关。

### 十进制调整会读取它刚写入的值

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

`DAA` 对 A 进行两次测试。`$9A` 大于 `$99`，因此加上 `$60` 并设置 C，得到 `$FA`。第二次测试读取这个新值，其低半字节 `$A` 大于 9，于是加上 `$06`，得到 `$00`。`DAS` 以相反方向做同样的事。

### 减法之后半进位取反

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

`ADC` 之后，若有进位离开低半字节，则设置 H。`SBC` 之后，若没有借位越过低半字节，则设置 H：`$10 - 1` 发生借位并清除 H，`$1F - 1` 不借位并设置 H。

### 直接页会移动

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

同一条 `MOV A, $10` 在 P 清除时读取 `$0010`，在 P 设置时读取 `$0110`。在直接页最后一个字节处进行的 16 位读取，从同一页的第一个字节取得高字节。

## 它是否正确

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/spc700/spc700/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/spc700/spc700/v1
```

`singlestep` 以 `256000 agreed, 0 did not` 结束，`cycles` 以 `256000 agreed, 0 did not, over 1182940 cycles` 结束。任何一处不一致，两者都以 1 退出。

语料库是 SingleStepTests/ProcessorTests，每个操作码 1,000 个用例，按提交固定在 [`conformance/suites.json`](conformance/suites.json) 中。[`conformance/fetch.py`](conformance/fetch.py) 进行部分克隆，并以稀疏检出只取 `spc700` 目录。每个用例给出完整状态、内存中的字节，以及执行一条指令之后的状态。

[`conformance/singlestep.py`](conformance/singlestep.py) 构建该机器，单步执行一次，然后比较每个寄存器、状态字和每个指定的字节。用例未指定的内存会被打乱。[`conformance/cycles.py`](conformance/cycles.py) 比较每个周期的地址和类型，并在用例给出值的地方比较其值。

| 时机 | 运行内容 | 出现不一致时 |
|:--|:--|:--|
| 拉取请求 | 每个操作码 100 个用例，两个运行器，使用固定的提交 | 检查失败 |
| 推送到 `main` | 所有用例，两个运行器，使用固定的提交 | 检查失败 |
| 每周一 | 所有用例，使用上游最新的提交 | 通过则提交一个移动固定提交的拉取请求，不通过则提交一个列出相关操作码的 issue |

[`.github/workflows/suite-watch.yml`](.github/workflows/suite-watch.yml) 运行每周任务，从不自行移动固定的提交。

### 事实的来源

1. Nintendo 的 SNES Development Manual 第 1 册附录 C，表 C-4 至 C-20。[`conformance/hardware.json`](conformance/hardware.json) 固定了全部 256 行及其字节长度、周期数和页码。每一行都是在 200 dpi 下从渲染后的页面上读取的，因为扫描件的文本层把表格各列交错在一起。[`conformance/hardware.test.py`](conformance/hardware.test.py) 检查每一行的长度，汇编并单步执行每条指令，并检查 253 个周期数，包括全部 28 条条件分支的两种周期数。其余 3 行以语料库为准：下文的 `MOVW dp, YA`，以及会挂起且永不结束的 `SLEEP` 和 `STOP`。手册为后两者印的是 3 个周期，记录在 7 处停止，模型重现了这个 7。
2. 对于手册没有印出的所有内容，以语料库为准：每个周期驱动哪个地址，内部周期落在何处，以及器件执行并丢弃了哪些读取。
3. 没有其他来源。

Sony 没有发布 SPC700 的数据手册，记录中将这一级来源标为空缺。

### 手册对一条指令的描述有误

手册第 C-8 页的表 C-11 把 `MOVW dp, YA` 印为 4 个周期，把 `MOVW YA, dp` 印为 5 个周期。器件执行两者都用 5 个周期。该存储指令先读取目标地址并丢弃读到的字节，与本器件上的每条存储指令一样：

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

对 `$0040` 的读取在最终状态中不留痕迹，因此只有周期比较能发现它。这一行在被记录为不一致之前，又在 450 dpi 下重新读取了一次。

[`conformance/divergences.json`](conformance/divergences.json) 记录了这一处以及另外 6 处来源未作说明或模型与来源不同的地方，每处都附有状态和严重程度。[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 为每个未决问题给出能解决它的测量方法。中断没有建模，因为音频单元没有引出中断线。处理器周围的定时器、端口和 DSP 不在本包范围内。

## 参与开发

| 需求 | 位置 |
|:--|:--|
| 所有门禁检查及其运行顺序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 面向编程代理的相同内容 | [AGENTS.md](AGENTS.md) |
| 本仓库与同系列其他仓库共享的标准 | [FAMILY.md](FAMILY.md) |
| 缺陷报告 | [GitHub Issues](https://github.com/gufranco/sony-spc700-python/issues) |
| 安全报告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 spc700/core.test.py
```

每个模块旁边都有一个名为 `<module>.test.py` 的测试文件，每个测试文件都可以像上面那样单独运行。覆盖率是一项硬性门禁检查，要求语句和分支均为 100%，在 [pyproject.toml](pyproject.toml) 中设置。

## 参考资料

- *SNES Development Manual, Book 1*，Nintendo of America Inc.，未注明日期。附录 C，SPC700 Commands。240 页，21,022,582 字节，SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`。它不可再分发，也不在本仓库中。`python3 -m conformance.documents` 将它下载到 git 忽略的 `docs/` 中，并拒绝任何摘要不同的文件。[`conformance/documents.json`](conformance/documents.json) 保存它的地址。`python3 -m conformance.quotes` 查找 [`conformance/hardware.json`](conformance/hardware.json) 从中引用的每一句话。
- SingleStepTests/ProcessorTests，`spc700/v1`，提交 `bb11756436da8fd16cce86aef63dc6725f48836f`，https://github.com/SingleStepTests/ProcessorTests 。256 个操作码各 1,000 个用例。

## 引用本项目

每次发布时，为包打上版本号的脚本会同时更新 [CITATION.cff](CITATION.cff)。

## 许可证

MIT。参见 [LICENSE](LICENSE)。

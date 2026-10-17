# Sony SPC700

Sony SPC700 是 SNES 音效單元中 S-SMP 內的處理器。本專案以 Python 實作，可逐條指令或逐個週期執行，並以 Nintendo《SNES Development Manual》附錄 C 及 SingleStepTests 語料庫為準。

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文（香港）

[![CI](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-spc700-python)](https://github.com/gufranco/sony-spc700-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

比對了 **256** 個操作碼、**256,000** 個一致性案例及 **1,182,940** 個週期，**0** 個失敗；**256** 個長度及 **253** 個週期數與 Nintendo 的表格相符；**830** 個測試；**100%** 語句及分支覆蓋率；無任何依賴

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

程式把 `$42` 載入 A，存到 `$10`，將 `$07` 寫入 `$11`，然後永遠跳轉到自身。`fill=0` 把 64 KB 空間清零，因此位於 `$FFFE` 的重設向量讀出 `$0000`，重設花 2 個週期讀取它。三條指令分別花 2、4 及 5 個週期。`run_for(10)` 執行三次各 4 個週期的跳轉，並回報實際花費的 12 個週期，比要求的多 2 個。

## 安裝

| 需求 | 版本 |
|:--|:--|
| Python | 3.12 或更新 |
| git | 任何版本 |

```bash
git clone https://github.com/gufranco/sony-spc700-python.git
cd sony-spc700-python
python3 spc700/doctor.py
```

本套件只匯入標準程式庫。`pip install git+https://github.com/gufranco/sony-spc700-python.git` 可把它安裝到另一個專案。

診斷腳本會檢查機器、建立並重設這個部件，並在 `~/.cache/conformance-suites` 尋找一致性測試套件。它以一行結束。提交錯誤報告時請貼上其全部輸出。

```
  6 checks, nothing to report
```

版本遵循 [Semantic Versioning](https://semver.org/)，由 semantic-release 根據提交記錄發佈。每個版本都有標籤，並列於[版本發佈頁面](https://github.com/gufranco/sony-spc700-python/releases)。

## 介面

`spc700.Cpu(model, memory=None, fill=None, step_limit=STEP_LIMIT, seed=UNSET_SEED, bus=None)` 建立一個部件。`model` 為必填。`memory` 可以是任何具備 `read8(address)` 及 `write8(address, value)` 的物件；若未提供，部件會取得一個 `SparseMemory`，或在提供 `fill` 時取得一個每個位元組都是 `fill` 的 `Memory`。`seed` 設定暫存器的開機模式。`bus` 是一個 `spc700.bus.Bus`，若省略，部件會自行建立。建構函式不會重設部件。

| 型號 | 別名 | 位址位元數 | 數據位元數 |
|:--|:--|:--|:--|
| `spc700` | `spc`, `ssmp`, `smp`, `sonyspc700` | 16 | 8 |

名稱會先轉為小寫並去掉 `-` 及 `_` 再比對，因此 `Cpu("S-SMP")` 會建立 `spc700`。

### 呼叫

| 呼叫 | 作用 |
|:--|:--|
| `step()` | 執行一條指令並回傳其花費的週期數。部件被停住後回傳 0 |
| `run_for(cycles)` | 逐步執行直至至少花費 `cycles` 個週期，並回傳實際花費。被停住的部件會逐個週期花掉餘數 |
| `run_until(predicate, limit=None)` | 在 `predicate(cpu)` 為假時逐步執行，並回傳部件。執行 `limit` 條指令後，或 `steps` 達到 `step_limit` 時，拋出 `RunLimit` |
| `reset(seed=UNSET_SEED)` | 重設線。從種子模式重新載入 A、X、Y、SP 及 PSW，清除 P，從 `$FFFE` 讀取 PC，把 `steps` 設為 0，並釋放被停住的部件。回傳部件 |
| `held()` | 在 `SLEEP` 或 `STOP` 之後為真 |
| `held_cycle()` | 讓被停住的部件花費一個週期。由 `Clock` 及 `run_for` 呼叫 |

`Cpu` 上的其他方法，例如 `fetch8`、`push16`、`op_adc` 等，是 `step()` 分派到的指令實作。

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

`INC X` 及跳回它的分支會一直執行，直至 X 為 5：五次遞增各 2 個週期，四次跳轉各 4 個週期，加上重設的 2 個週期。

### 狀態

| 屬性 | 意義 |
|:--|:--|
| `a`, `x`, `y`, `sp`, `pc` | 暫存器。`sp` 定址第 `$01` 頁 |
| `ya` | 把 Y 及 A 當作一個 16 位元值讀寫，Y 為高位 |
| `psw` | 以一個位元組表示的狀態字。寫入它會設定八個旗標 |
| `n`, `v`, `p`, `b`, `h`, `i`, `z`, `c` | 以布林值表示的八個旗標 |
| `direct_page` | `$0000` 或 `$0100`，由 `p` 選擇 |
| `cycles` | 部件建立以來的週期數，跨越重設累計 |
| `steps` | 上次重設以來的指令數 |
| `stopped` | `held()` 讀取的旗標 |
| `step_limit` | `run_until` 放棄時的指令數 |
| `model` | 標準型號名稱 |
| `memory` | 部件讀寫的儲存區 |
| `bus` | 週期記錄器。`bus.cycles` 是進行中指令的花費；設定 `bus.recording` 後，`bus.log` 以 `(address, value, kind)` 列出每個週期，kind 為 `read`、`write` 或 `wait` |
| `on_cycle` | 每個週期執行一次的可呼叫物件，或 `None`。`Clock` 會安裝自己的版本 |

### 模組內容

| 名稱 | 內容 |
|:--|:--|
| `spc700.MODELS` | 以名稱為鍵的 `Model` 記錄：`name`、`summary`、`address_bits`、`data_bits`、`aliases`、`address_mask` |
| `spc700.Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)` | 存放於 `data` 的平面儲存區。除非提供 `fill`，否則按 `seed` 打亂，然後把 `image` 複製到位址 0 |
| `spc700.SparseMemory(seed=UNSET_SEED)` | 只在 `cells` 中保存寫入過的位元組。未寫入的位元組由其位址及 `seed` 推算 |
| `spc700.scramble(size, seed=UNSET_SEED)` | 兩種儲存區及暫存器背後的種子位元組模式 |
| `spc700.UNSET_SEED` | 預設種子，`0x5A5A5A5A` |
| `spc700.STEP_LIMIT` | 預設 `step_limit`，2,000,000 |
| `spc700.FLAG_N`, `FLAG_V`, `FLAG_P`, `FLAG_B`, `FLAG_H`, `FLAG_I`, `FLAG_Z`, `FLAG_C` | `psw` 的各位元：`0x80`、`0x40`、`0x20`、`0x10`、`0x08`、`0x04`、`0x02`、`0x01` |
| `spc700.OPCODES` | 以操作碼位元組為索引的 256 行 `(mnemonic, mode, size)`。執行及反組譯都讀取它 |
| `spc700.disassemble(data, offset, address, count=None, p=0, stop_at_return=False)` | 指令清單，每條帶有 `address`、`size`、`text`、`opcode`、`mnemonic` 及 `mode` |
| `spc700.Clock(cpu)` | 逐個週期驅動部件 |
| `spc700.__version__` | 已安裝的版本 |

### 錯誤

| 錯誤 | 拋出時機 |
|:--|:--|
| `UnknownModelError` | `Cpu` 沒有取得型號名稱，或取得的名稱不屬於任何型號。訊息會列出可接受的名稱 |
| `RunLimit` | `run_until` 超過其 `limit`，或 `steps` 達到 `step_limit` |
| `ClockClosed` | 在已關閉的 `Clock` 上呼叫 `tick()` |
| `Truncated` | `spc700.opcodes.decode` 在指令中途用完位元組。`disassemble` 則會在該處停止 |

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

### 命令列工具

| 命令 | 參數 | 結束碼 |
|:--|:--|:--|
| `python3 spc700/doctor.py` | 無 | 所有檢查通過時為 0，否則為 1 |
| `python3 -m conformance.fetch` | `[directory] [--latest]`。目錄預設為 `~/.cache/conformance-suites`。`--latest` 採用上游最新的提交，而非固定版本 | 0；無法連上上游時為 1 |
| `python3 -m conformance.singlestep` | `<suite directory> [cases per file] [name filter]` | 每個案例都一致或沒有測試套件時為 0，出現不一致時為 1，沒有參數時為 2 |
| `python3 -m conformance.cycles` | 與 `singlestep` 相同 | 與 `singlestep` 相同 |
| `python3 -m conformance.documents` | `[--check] [--only SUBSTRING]`。`--check` 只驗證磁碟上已有的檔案，不會下載 | 每份文件都通過驗證時為 0，否則為 1 |
| `python3 -m conformance.quotes` | 無 | 每段引文都找到，或機器上沒有文件時為 0；否則為 1 |
| `python3 -m conformance.speed` | 無 | 達到或高於吞吐量下限時為 0，低於下限時為 1 |
| `python3 -m conformance.links` | 無 | 0；本檔案中有位址回應 404 或 410 時為 1 |
| `python3 -m conformance.package` | `<wheel>` | 每個模組都包含在內且沒有包含任何測試時為 0，否則為 1，沒有參數時為 2 |

## 以真實速度執行

模型會以主機容許的最快速度執行。若主機需要部件本身的節奏，可為每個時間片設定週期預算，並把超出的部分帶到下一個時間片，因為一條指令不能分割。

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

程式是一條跳轉到自身的 4 週期分支。第一個 10 週期的時間片花了 12 個週期，所以第二個只要求 8 個；三個時間片之後，部件為要求的 30 個週期花了 32 個，仍欠 2 個。主機在每個時間片後休眠，時間長度等於這些週期在部件時鐘下所需的時間。

`python3 -m conformance.speed` 對 20,000 次 `step()` 呼叫計時五次，低於每秒 150,000 條指令的下限即失敗。CI 在覆蓋率步驟以外執行它，因此追蹤器不會拖慢量度。

## 逐個週期驅動

`Clock(cpu)` 可以在任何兩個週期之間停住部件，包括同一條指令的兩個週期之間。主機可以在指令中途改變下一次讀取的回應。

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

`MOV A, #$2A` 需時 2 個週期。第二個節拍之後，運算元已被取出，而 A 仍保留其開機值 `$EB`。A 在第三個節拍之前改變，該節拍停在存儲指令的第一個週期。

| Clock 呼叫 | 作用 |
|:--|:--|
| `tick()` | 前進一個週期並回傳 `cycles` |
| `run_for(cycles)` | 呼叫 `tick()` 指定次數並回傳 `cycles` |
| `cycles` | 這個時鐘建立以來的節拍數 |
| `close()` | 停止工作執行緒，並把部件原先的 `on_cycle` 交還給它 |

`Clock` 是一個迭代器，在關閉前不斷產生 `tick()`；它也是一個上下文管理器，離開時自動關閉。它在一條執行緒上執行部件，該執行緒在每個花費週期的地方阻塞，因此比 `step()` 慢。被停住的部件在時鐘下會繼續花費週期。

## 型號

型號在建構時指定，沒有預設值。目錄只有一個項目，因為 Sony 把 SPC700 內置於 S-SMP，沒有另行出售獨立部件或變體。

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

別名會建立它所指的部件，而部件會回報標準名稱。

## 不執行而讀取

`disassemble(data, offset, address)` 以獨立參數接收緩衝區內的偏移量，以及該偏移量對應的位址。`p` 設定列印直接頁運算元時所用的直接頁。

```python
from spc700 import Truncated, disassemble
from spc700.opcodes import decode

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

最後一個位元組 `$8F` 是一條 3 位元組 `MOV dp, #imm` 的開頭。`disassemble` 在它之前停止，`decode` 則對它拋出 `Truncated`。`stop_at_return=True` 會在第一個 `RET` 或 `RETI` 之後結束清單。

## 沒有甚麼是乾淨地開始

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

音效 RAM 在開機時沒有確定的值，因此除非 `fill` 要求，否則兩種儲存區都不會從零開始。`SparseMemory` 對未寫入的位址每次讀取都回應同一個位元組，該位元組由位址及種子推算，且不會為它配置任何空間。新建立的部件從 `scramble(6)` 的前四個位元組取得 A、X、Y 及 SP，從第五個取得 PSW，從最後兩個取得 PC，低位元組在前。`reset()` 從同一模式重新載入它們，清除 P，並從重設向量載入 PC，此處讀出 `$0000`。

## 值得了解的指令

以下是 SPC700 與其相似的 6502 不同的四種行為。每一種都經測試套件檢查。

### 除法在得出答案後仍繼續

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

`DIV YA, X` 在任何情況下都花 12 個週期。10 除以 3 得商 3 餘 1。1,024 除以 2 的結果放不進 A，部件回傳 `$FF` 及 `$02`，並設定 V。除以零不會拋出任何錯誤，並回傳 `$ED` 及 `$34`。H 比較 X 及 Y 的低半位元組，與商無關。

### 十進位調整會讀取它剛寫入的值

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

`DAA` 對 A 測試兩次。`$9A` 大於 `$99`，因此加上 `$60` 並設定 C，得出 `$FA`。第二次測試讀取這個新值，其低半位元組 `$A` 大於 9，因此加上 `$06`，得出 `$00`。`DAS` 以相反方向做同樣的事。

### 減法之後半進位會反轉

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

`ADC` 之後，若有進位離開低半位元組，H 會被設定。`SBC` 之後，若沒有借位越過低半位元組，H 會被設定：`$10 - 1` 會借位並清除 H，`$1F - 1` 不會借位並設定 H。

### 直接頁會移動

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

同一條 `MOV A, $10` 在 P 清除時讀取 `$0010`，在 P 設定時讀取 `$0110`。在直接頁最後一個位元組進行的 16 位元讀取，會從同一頁的第一個位元組取得高位元組。

## 它是否正確

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/spc700/spc700/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/spc700/spc700/v1
```

`singlestep` 以 `256000 agreed, 0 did not` 結束，`cycles` 則以 `256000 agreed, 0 did not, over 1182940 cycles` 結束。任何一項出現不一致都會以 1 結束。

語料庫是 SingleStepTests/ProcessorTests，每個操作碼 1,000 個案例，以提交固定於 [`conformance/suites.json`](conformance/suites.json)。[`conformance/fetch.py`](conformance/fetch.py) 以部分複製加稀疏簽出的方式，只取得 `spc700` 目錄。每個案例提供完整狀態、記憶體中的位元組，以及執行一條指令後的狀態。

[`conformance/singlestep.py`](conformance/singlestep.py) 建立該機器，執行一步，然後比較每個暫存器、狀態字及每個列明的位元組。案例沒有列明的記憶體會被打亂。[`conformance/cycles.py`](conformance/cycles.py) 比較每個週期的位址及類型，並在案例列出值時比較其值。

| 時機 | 執行內容 | 出現不一致時 |
|:--|:--|:--|
| Pull request | 每個操作碼 100 個案例，兩個執行器，於固定的提交 | 檢查失敗 |
| 推送到 `main` | 所有案例，兩個執行器，於固定的提交 | 檢查失敗 |
| 每個星期一 | 所有案例，於上游最新的提交 | 通過時開一個移動固定版本的 pull request，不通過時開一個列出相關操作碼的 issue |

[`.github/workflows/suite-watch.yml`](.github/workflows/suite-watch.yml) 執行每週工作，並且永不自行移動固定版本。

### 事實的來源

1. Nintendo《SNES Development Manual》第 1 冊附錄 C，表 C-4 至 C-20。[`conformance/hardware.json`](conformance/hardware.json) 固定了全部 256 行，連同其位元組長度、週期數及頁碼。每一行都是從以每吋 200 點渲染的頁面讀出，因為掃描檔的文字層把表格各欄交錯在一起。[`conformance/hardware.test.py`](conformance/hardware.test.py) 檢查每一行的長度，組譯並逐步執行每條指令，並檢查 253 個週期數，包括全部 28 條條件分支的兩個週期數。其餘 3 行以語料庫為準：下文的 `MOVW dp, YA`，以及會停機且永不完成的 `SLEEP` 和 `STOP`。手冊為後兩者印出 3 個週期，記錄停在 7，而模型重現了 7。
2. 語料庫，用於手冊沒有印出的一切：每個週期驅動哪個位址、內部週期落在何處，以及部件執行並丟棄了哪些讀取。
3. 沒有其他來源。

Sony 沒有為 SPC700 發佈數據表，記錄把這一級標明為空缺。

### 手冊在一條指令上有誤

手冊第 C-8 頁的表 C-11 把 `MOVW dp, YA` 印為 4 個週期，把 `MOVW YA, dp` 印為 5 個。部件兩者都花 5 個。存儲指令會先讀取目的地並丟棄該位元組，與這個部件上的每條存儲指令一樣：

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

對 `$0040` 的讀取不會在最終狀態留下痕跡，因此只有週期比對能看到它。這一行在記錄為不一致之前，曾以每吋 450 點重新讀取。

[`conformance/divergences.json`](conformance/divergences.json) 載有這一項，以及另外 6 處來源未有說明或模型偏離來源的地方，每項都附有狀態及嚴重程度。[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 為每個未解決的問題列出能解決它的量度。中斷沒有建模，因為音效單元沒有引出中斷線。處理器周邊的計時器、連接埠及 DSP 不在本套件範圍內。

## 參與開發

| 需要 | 位置 |
|:--|:--|
| 所有關卡檢查及其執行次序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 給編程代理的相同材料 | [AGENTS.md](AGENTS.md) |
| 本儲存庫與家族其他成員共用的標準 | [FAMILY.md](FAMILY.md) |
| 錯誤報告 | [GitHub Issues](https://github.com/gufranco/sony-spc700-python/issues) |
| 安全報告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 spc700/core.test.py
```

每個模組旁邊都有一個名為 `<module>.test.py` 的測試檔案，每個都可如上所示單獨執行。覆蓋率是一道硬性關卡，要求 100% 語句及分支覆蓋，設定於 [pyproject.toml](pyproject.toml)。

## 參考資料

- *SNES Development Manual, Book 1*，Nintendo of America Inc.，未註明日期。附錄 C，SPC700 Commands。240 頁，21,022,582 位元組，SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`。它不可再分發，也不在本儲存庫中。`python3 -m conformance.documents` 會把它下載到 git 忽略的 `docs/`，並拒絕任何摘要不符的檔案。[`conformance/documents.json`](conformance/documents.json) 載有其位址。`python3 -m conformance.quotes` 會找出 [`conformance/hardware.json`](conformance/hardware.json) 從中引用的每一句。
- SingleStepTests/ProcessorTests，`spc700/v1`，提交 `bb11756436da8fd16cce86aef63dc6725f48836f`，https://github.com/SingleStepTests/ProcessorTests 。256 個操作碼各有 1,000 個案例。

## 引用本專案

[CITATION.cff](CITATION.cff) 會在每次發佈時，由標記套件版本的腳本更新。

## 授權

MIT。見 [LICENSE](LICENSE)。

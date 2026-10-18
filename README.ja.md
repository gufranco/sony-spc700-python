# Sony SPC700

SNESオーディオユニットのS-SMPに内蔵されたプロセッサであるSony SPC700をPythonで実装したものです。1命令ずつ、または1サイクルずつ実行でき、NintendoのSNES Development ManualのAppendix CとSingleStepTestsコーパスに準拠しています。

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-spc700-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-spc700-python)](https://github.com/gufranco/sony-spc700-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**256**個のオペコード、**256,000**件の適合性ケースと**1,182,940**サイクルを比較して失敗**0**件、**256**個の命令長と**253**個のサイクル数がNintendoの表に一致、テスト**870**件、ステートメントとブランチのカバレッジ**100%**、依存関係なし

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

このプログラムは`$42`をAにロードし、それを`$10`にストアし、`$07`を`$11`に書き込み、その後は自分自身へ永久に分岐します。`fill=0`で64 KBの空間をゼロにするため、`$FFFE`のリセットベクタは`$0000`を読み出し、リセットはその読み出しに2サイクルを費やします。3つの命令のコストは2、4、5サイクルです。`run_for(10)`は4サイクルの分岐を3回実行し、実際に費やした12サイクルを返します。これは要求より2多い値です。

## インストール

| 要件 | バージョン |
|:--|:--|
| Python | 3.12以降 |
| git | 任意 |

```bash
git clone https://github.com/gufranco/sony-spc700-python.git
cd sony-spc700-python
python3 spc700/doctor.py
```

このパッケージは標準ライブラリ以外を何もインポートしません。`pip install git+https://github.com/gufranco/sony-spc700-python.git`で別のプロジェクトにインストールできます。

ドクターはマシンを確認し、パーツを構築してリセットし、`~/.cache/conformance-suites`にある適合性スイートを探します。出力は1行で終わります。バグ報告にはその出力全体を貼り付けてください。

```
  6 checks, nothing to report
```

リリースは[Semantic Versioning](https://semver.org/)に従い、semantic-releaseによってコミット履歴から作成されます。すべてのリリースにはタグが付けられ、[リリースページ](https://github.com/gufranco/sony-spc700-python/releases)に掲載されます。

## インターフェース

`spc700.Cpu(model, memory=None, fill=None, step_limit=STEP_LIMIT, seed=UNSET_SEED, bus=None)`はパーツを1つ構築します。`model`は必須です。`memory`は`read8(address)`と`write8(address, value)`を持つ任意のオブジェクトです。指定しない場合、パーツは`SparseMemory`を受け取り、`fill`を指定した場合はすべてのバイトに`fill`を保持する`Memory`を受け取ります。`seed`はレジスタの電源投入時のパターンを設定します。`bus`は`spc700.Bus`で、省略するとパーツが自分で構築します。コンストラクタはパーツをリセットしません。

| モデル | 別名 | アドレスビット数 | データビット数 |
|:--|:--|:--|:--|
| `spc700` | `spc`, `ssmp`, `smp`, `sonyspc700` | 16 | 8 |

名前は小文字に変換し、`-`と`_`を取り除いてから照合されます。そのため`Cpu("S-SMP")`は`spc700`を構築します。

### 呼び出し

| 呼び出し | 効果 |
|:--|:--|
| `step()` | 1命令を実行し、費やしたサイクル数を返します。パーツが停止状態になると0を返します |
| `run_for(cycles)` | 少なくとも`cycles`サイクルを費やすまでステップを進め、費やした量を返します。停止状態のパーツは残りを1サイクルずつ費やします |
| `run_until(predicate, limit=None)` | `predicate(cpu)`が偽の間ステップを進め、パーツを返します。`limit`命令を超えた場合、または`steps`が`step_limit`に達した場合は`RunLimit`を送出します |
| `reset(seed=UNSET_SEED)` | リセットラインです。シードから得たパターンでA、X、Y、SP、PSWを再ロードし、Pをクリアし、`$FFFE`からPCを読み出し、`steps`を0にし、停止状態のパーツを解放します。パーツを返します |
| `held()` | `SLEEP`または`STOP`の後はTrueです |
| `held_cycle()` | 停止状態のパーツの1サイクルを費やします。`Clock`と`run_for`がこれを呼び出します |

`Cpu`のその他のメソッド、`fetch8`、`push16`、`op_adc`などは、`step()`がディスパッチする命令の実装です。

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

`INC X`とそこへ戻る分岐は、Xが5になるまで実行されます。2サイクルのインクリメントが5回、4サイクルの分岐が4回、そしてリセットの2サイクルです。

### 状態

| 属性 | 意味 |
|:--|:--|
| `a`, `x`, `y`, `sp`, `pc` | レジスタです。`sp`はページ`$01`を指します |
| `ya` | YとAを1つの16ビット値として読み書きします。Yが上位です |
| `psw` | ステータスワードを1バイトとして表したものです。書き込むと8つのフラグが設定されます |
| `n`, `v`, `p`, `b`, `h`, `i`, `z`, `c` | 8つのフラグをブール値で表したものです |
| `direct_page` | `$0000`または`$0100`で、`p`によって選ばれます |
| `cycles` | パーツの構築以降のサイクル数で、リセットをまたいで数えます |
| `steps` | 最後のリセット以降の命令数です |
| `stopped` | `held()`が読むフラグです |
| `step_limit` | `run_until`があきらめる命令数です |
| `model` | 正規のモデル名です |
| `memory` | パーツが読み書きするストアです |
| `bus` | サイクルレコーダーです。`bus.cycles`は実行中の命令のコストで、`bus.recording`を設定すると、`bus.log`が各サイクルを`(address, value, kind)`として列挙します。kindは`read`、`write`、`wait`のいずれかです |
| `on_cycle` | 1サイクルごとに1回実行される呼び出し可能オブジェクト、または`None`です。`Clock`は独自のものを設定します |

### モジュールの内容

| 名前 | 内容 |
|:--|:--|
| `spc700.MODELS` | 名前をキーとする`Model`レコードです。`name`、`summary`、`address_bits`、`data_bits`、`aliases`、`address_mask`を持ちます |
| `spc700.Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)` | `data`に格納されるフラットなストアです。`fill`を指定しない限り`seed`からスクランブルされ、その後`image`がアドレス0からコピーされます |
| `spc700.SparseMemory(seed=UNSET_SEED)` | 書き込まれたバイトだけを`cells`に保持します。書き込まれていないバイトはアドレスと`seed`から導出されます |
| `spc700.scramble(size, seed=UNSET_SEED)` | 両方のストアとレジスタの元になるシード付きバイトパターンです |
| `spc700.UNSET_SEED` | デフォルトのシード`0x5A5A5A5A`です |
| `spc700.STEP_LIMIT` | `step_limit`のデフォルト値2,000,000です |
| `spc700.FLAG_N`, `FLAG_V`, `FLAG_P`, `FLAG_B`, `FLAG_H`, `FLAG_I`, `FLAG_Z`, `FLAG_C` | `psw`のビットで、`0x80`、`0x40`、`0x20`、`0x10`、`0x08`、`0x04`、`0x02`、`0x01`です |
| `spc700.OPCODES` | オペコードバイトでインデックスされた256行の`(mnemonic, mode, size)`です。実行と逆アセンブルの両方がこれを読みます |
| `spc700.disassemble(data, offset, address, count=None, p=0, stop_at_return=False)` | 命令のリストで、各命令は`address`、`size`、`text`、`opcode`、`mnemonic`、`mode`を持ちます |
| `spc700.decode(data, offset, address, p=0)` | `offset`にある1命令で、同じ属性を持ちます。命令の途中でバイトが尽きると`Truncated`を送出します |
| `spc700.Bus(recording=False)` | パーツがすべてのサイクルを通すサイクル記録器で、`bus`の項で説明した`cycles`、`recording`、`log`を持ちます |
| `spc700.Clock(cpu)` | パーツを1サイクルずつ駆動します |
| `spc700.__version__` | インストールされているバージョンです |

### エラー

| エラー | 送出される条件 |
|:--|:--|
| `UnknownModelError` | `Cpu`にモデル名が渡されない場合、またはどのモデルにも該当しない名前が渡された場合です。メッセージには受け付ける名前が列挙されます |
| `RunLimit` | `run_until`が`limit`を超えた場合、または`steps`が`step_limit`に達した場合です |
| `ClockClosed` | 閉じた`Clock`で`tick()`が呼ばれた場合です |
| `Truncated` | `spc700.decode`が命令の途中でバイトを使い切った場合です。`disassemble`は代わりにそこで停止します |

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

### コマンドラインツール

| コマンド | 引数 | 終了コード |
|:--|:--|:--|
| `python3 spc700/doctor.py` | なし | すべてのチェックに合格すると0、それ以外は1 |
| `python3 -m conformance.fetch` | `[directory] [--latest]`。ディレクトリのデフォルトは`~/.cache/conformance-suites`です。`--latest`はピンの代わりにアップストリームの最新コミットを使います | 0、またはアップストリームに到達できない場合は1 |
| `python3 -m conformance.singlestep` | `<suite directory> [cases per file] [name filter]` | すべてのケースが一致するかスイートが存在しない場合は0、不一致があると1、引数なしでは2 |
| `python3 -m conformance.cycles` | `singlestep`と同じ | `singlestep`と同じ |
| `python3 -m conformance.documents` | `[--check] [--only SUBSTRING]`。`--check`はダウンロードせずにディスク上のものを検証します | すべての文書が検証されると0、それ以外は1 |
| `python3 -m conformance.quotes` | なし | すべての引用が見つかった場合、またはマシン上に文書がない場合は0、それ以外は1 |
| `python3 -m conformance.speed` | なし | スループットの下限以上なら0、下回ると1 |
| `python3 -m conformance.links` | なし | 0、またはこのファイル内のアドレスが404か410を返すと1 |
| `python3 -m conformance.package` | `<wheel>` | すべてのモジュールが同梱されテストが1つも同梱されていなければ0、それ以外は1、引数なしでは2 |

## 実機の速度で動かす

モデルはホストが許す限り高速に動作します。パーツの速度に合わせたいホストは、スライスごとにサイクルの予算を与え、超過分を次のスライスに繰り越します。命令は分割できないためです。

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

このプログラムは自分自身への4サイクルの分岐1つです。最初の10サイクルのスライスは12を費やすので、2番目は8を要求し、3つのスライスの後、パーツは要求された30に対して32サイクルを費やし、2がまだ繰り越されています。ホストは各スライスの後、それらのサイクルがパーツのクロックでかかる時間だけスリープします。

`python3 -m conformance.speed`は20,000回の`step()`呼び出しを5回計測し、毎秒150,000命令の下限を下回ると失敗します。CIはこれをカバレッジのステップとは別に実行するため、トレーサーが計測を遅くすることはありません。

## 1サイクルずつ駆動する

`Clock(cpu)`は、1つの命令内の2つのサイクルの間も含め、任意の2サイクルの間でパーツを停止させます。ホストは命令の途中で、次の読み出しが返す値を変更できます。

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
[(1, 1, '0xeb'), (2, 1, '0xeb'), (3, 2, '0x2a'), (4, 2, '0x2a'), (5, 2, '0x2a'), (6, 2, '0x2a')]
this clock has been closed
```

`MOV A, #$2A`は2サイクルかかります。2回目のティックの後、オペランドはフェッチ済みですが、Aはまだ電源投入時の値`$EB`を保持しています。Aは3回目のティックの前に変わり、3回目のティックはストアの最初のサイクルで停止します。

| Clockの呼び出し | 効果 |
|:--|:--|
| `tick()` | 1サイクル進め、`cycles`を返します |
| `run_for(cycles)` | `tick()`をその回数呼び出し、`cycles`を返します |
| `cycles` | このクロックの構築以降のティック数です |
| `close()` | ワーカースレッドを停止し、パーツに以前の`on_cycle`を戻します |

`Clock`は閉じられるまで`tick()`をyieldするイテレータであり、終了時に閉じるコンテキストマネージャでもあります。サイクルが費やされるたびにブロックするスレッド上でパーツを実行するため、`step()`より低速です。停止状態のパーツは、クロックの下でもサイクルを費やし続けます。

## モデル

モデルは構築時に指定し、デフォルトはありません。SonyはSPC700をS-SMPに組み込み、単体のパーツやバリアントを販売しなかったため、カタログの項目は1つです。

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

別名はそれが指すパーツを構築し、パーツは正規の名前を報告します。

## 実行せずに読む

`disassemble(data, offset, address)`は、バッファ内のオフセットと、そのオフセットが対応するアドレスを別々の引数として受け取ります。`p`は、ダイレクトページのオペランドを表示する際に使うダイレクトページを設定します。

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

最後のバイト`$8F`は3バイトの`MOV dp, #imm`の始まりです。`disassemble`はその手前で停止し、`decode`はそこで`Truncated`を送出します。`stop_at_return=True`は最初の`RET`または`RETI`の後で一覧を終えます。

## 最初からきれいなものはない

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

オーディオRAMは電源投入時に定まった値を持たないため、`fill`で指定しない限り、どちらのストアもゼロから始まりません。`SparseMemory`は書き込まれていないアドレスに対して、アドレスとシードから導出した同じバイトを毎回の読み出しで返し、そのための領域は確保しません。新しく構築したパーツは、A、X、Y、SPを`scramble(6)`の最初の4バイトから、PSWを5番目のバイトから、PCを最後の2バイトから下位バイトを先にして取得します。`reset()`は同じパターンからそれらを再ロードし、Pをクリアし、リセットベクタからPCをロードします。ここではリセットベクタは`$0000`を読み出します。

## 知っておくべき命令

SPC700が、よく似た6502と異なる4つの動作です。いずれもスイートで確認されています。

### 除算は答えを過ぎても続く

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

`DIV YA, X`はどの場合も12サイクルかかります。10を3で割ると商3、余り1になります。1,024を2で割った結果はAに収まらず、パーツはVをセットして`$FF`と`$02`を返します。ゼロ除算は何も送出せず、`$ED`と`$34`を返します。HはXとYの下位ニブルを比較したもので、商については何も示しません。

### 十進補正は書いたばかりの値を読む

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

`DAA`はAを2回テストします。`$9A`は`$99`より大きいので、`$60`を加算してCをセットし、`$FA`になります。2回目のテストはその新しい値を読み、下位ニブル`$A`が9より大きいので`$06`を加算し、`$00`になります。`DAS`は同じことを逆向きに行います。

### ハーフキャリーは減算の後で反転する

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

`ADC`の後、Hは下位ニブルからキャリーが出たときにセットされます。`SBC`の後、Hは下位ニブルをボローがまたがなかったときにセットされます。`$10 - 1`はボローが発生してHをクリアし、`$1F - 1`はボローが発生せずHをセットします。

### ダイレクトページは移動する

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

同じ`MOV A, $10`が、Pがクリアのときは`$0010`を、Pがセットのときは`$0110`を読みます。ダイレクトページの最後のバイトでの16ビット読み出しは、上位バイトを同じページの最初のバイトから取得します。

## 正しいか

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/spc700/spc700/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/spc700/spc700/v1
```

`singlestep`は`256000 agreed, 0 did not`で、`cycles`は`256000 agreed, 0 did not, over 1182940 cycles`で終わります。どちらも不一致が1つでもあれば1で終了します。

コーパスはSingleStepTests/ProcessorTestsで、オペコードごとに1,000ケースあり、[`conformance/suites.json`](conformance/suites.json)でコミットにより固定されています。[`conformance/fetch.py`](conformance/fetch.py)は、`spc700`ディレクトリだけをスパースチェックアウトする部分クローンを取得します。各ケースは完全な状態、メモリ上のバイト、1命令後の状態を与えます。

[`conformance/singlestep.py`](conformance/singlestep.py)はそのマシンを構築し、1回ステップを進め、すべてのレジスタ、ステータスワード、指定されたすべてのバイトを比較します。ケースが指定しないメモリはスクランブルされます。[`conformance/cycles.py`](conformance/cycles.py)は各サイクルのアドレスと種類を比較し、ケースが値を示している場合はその値も比較します。

| タイミング | 実行内容 | 不一致の場合 |
|:--|:--|:--|
| プルリクエスト | オペコードごとに100ケース、両方のランナー、固定されたコミット | チェックが失敗します |
| `main`へのプッシュ | すべてのケース、両方のランナー、固定されたコミット | チェックが失敗します |
| 毎週月曜日 | アップストリームの最新コミットですべてのケース | 合格すればピンを移動するプルリクエスト、合格しなければオペコードを列挙したissue |

[`.github/workflows/suite-watch.yml`](.github/workflows/suite-watch.yml)が週次ジョブを実行し、ピンを自動で移動することはありません。

### 事実の出典

1. NintendoのSNES Development Manual、Book 1、Appendix C、表C-4からC-20。[`conformance/hardware.json`](conformance/hardware.json)は256行すべてを、バイト長、サイクル数、ページとともに固定しています。スキャンのテキストレイヤーは表の列を交互に混ぜてしまうため、各行は200 dpiでレンダリングしたページから読み取りました。[`conformance/hardware.test.py`](conformance/hardware.test.py)はすべての行の命令長を確認し、各命令をアセンブルしてステップ実行し、28個すべての条件分岐の両方のサイクル数を含む253個のサイクル数を確認します。残りの3行はコーパスに従います。後述の`MOVW dp, YA`と、停止して終わることのない`SLEEP`と`STOP`です。マニュアルはこれらを3サイクルと記載していますが、記録は7で止まっており、モデルは7を再現します。
2. マニュアルに記載がないすべてのことについてはコーパス。各サイクルがどのアドレスを駆動するか、内部サイクルがどこに入るか、パーツがどの読み出しを行って破棄するかです。
3. それ以外にはありません。

SonyはSPC700のデータシートを公開しておらず、記録ではその段を空として明記しています。

### マニュアルは1つの命令について誤っている

マニュアルのページC-8にある表C-11は、`MOVW dp, YA`を4サイクル、`MOVW YA, dp`を5サイクルと記載しています。パーツはどちらも5サイクルかかります。このストアは、このパーツ上のすべてのストアと同様に、まず書き込み先を読み出してそのバイトを破棄します。

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

`$0040`の読み出しは最終状態に痕跡を残さないため、サイクルの比較だけがそれを捉えます。この行は不一致として記録する前に、450 dpiで再度読み取りました。

[`conformance/divergences.json`](conformance/divergences.json)は、これと、出典が何も述べていないかモデルが出典から外れている他の6か所を、それぞれの状態と重大度とともに保持しています。[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)は、未解決の各項目について、それを決着させる測定を示しています。オーディオユニットは割り込みラインを外部に出していないため、割り込みはモデル化していません。プロセッサ周辺のタイマー、ポート、DSPはこのパッケージの対象外です。

## 開発に参加する

| 必要なもの | 場所 |
|:--|:--|
| すべてのゲートとその実行順序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| コーディングエージェント向けの同じ内容 | [AGENTS.md](AGENTS.md) |
| このリポジトリがファミリーの他のリポジトリと共有する基準 | [FAMILY.md](FAMILY.md) |
| バグ報告 | [GitHub Issues](https://github.com/gufranco/sony-spc700-python/issues) |
| セキュリティ報告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 spc700/core.test.py
```

各モジュールの隣には`<module>.test.py`という名前のテストファイルがあり、上のようにそれぞれ単独で実行できます。カバレッジはステートメントとブランチで100%を求める必須のゲートで、[pyproject.toml](pyproject.toml)で設定されています。

## 参考文献

- *SNES Development Manual, Book 1*、Nintendo of America Inc.、日付なし。Appendix C、SPC700 Commands。240ページ、21,022,582バイト、SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`。再配布はできず、このリポジトリには含まれていません。`python3 -m conformance.documents`がgitで無視される`docs/`にダウンロードし、ダイジェストが異なるファイルは拒否します。[`conformance/documents.json`](conformance/documents.json)にそのアドレスがあります。`python3 -m conformance.quotes`は、[`conformance/hardware.json`](conformance/hardware.json)が引用しているすべての文をこの文書の中から見つけます。
- SingleStepTests/ProcessorTests、`spc700/v1`、コミット`bb11756436da8fd16cce86aef63dc6725f48836f`、https://github.com/SingleStepTests/ProcessorTests 。256個のオペコードそれぞれに1,000ケースです。

## 引用

[CITATION.cff](CITATION.cff)は、パッケージのバージョンを刻印するスクリプトによってリリースごとに更新されます。

## ライセンス

MITです。[LICENSE](LICENSE)を参照してください。

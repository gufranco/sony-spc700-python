from collections.abc import Callable
from typing import Protocol

from . import opcodes as table
from .bus import Bus
from .errors import RunLimit
from .memory import UNSET_SEED, scramble


class MemoryLike(Protocol):
    def read8(self, address: int) -> int: ...

    def write8(self, address: int, value: int) -> None: ...


OPCODES = table.OPCODES

STEP_LIMIT = 2_000_000

HALT_CYCLES = 2

FLAG_C = 0x01
FLAG_Z = 0x02
FLAG_I = 0x04
FLAG_H = 0x08
FLAG_B = 0x10
FLAG_P = 0x20
FLAG_V = 0x40
FLAG_N = 0x80

RESET_VECTOR = 0xFFFE
BREAK_VECTOR = 0xFFDE
CALL_TABLE_TOP = 0xFFDE

STACK_PAGE = 0x0100
UPPER_PAGE = 0xFF00

BRANCHES = {
    "bra": None,
    "beq": ("z", True),
    "bne": ("z", False),
    "bcs": ("c", True),
    "bcc": ("c", False),
    "bvs": ("v", True),
    "bvc": ("v", False),
    "bmi": ("n", True),
    "bpl": ("n", False),
}


class Cpu:
    __slots__ = (
        "a",
        "b",
        "bus",
        "c",
        "cycles",
        "h",
        "i",
        "memory",
        "model",
        "n",
        "on_cycle",
        "p",
        "pc",
        "sp",
        "step_limit",
        "steps",
        "stopped",
        "v",
        "x",
        "y",
        "z",
    )

    on_cycle: Callable[[], None] | None

    def __init__(
        self,
        memory: MemoryLike,
        step_limit: int = STEP_LIMIT,
        seed: int = UNSET_SEED,
        bus: Bus | None = None,
    ) -> None:
        self.memory = memory
        self.bus = Bus() if bus is None else bus
        self.bus.on_spend = self._spent
        self.step_limit = step_limit
        self.model = "spc700"
        self.steps = 0
        self.cycles = 0
        self.on_cycle = None
        self.stopped = False
        self.a = self.x = self.y = 0x00
        self.sp = 0xFF
        self.pc = 0x0000
        undefined = scramble(6, seed)
        self.a = undefined[0]
        self.x = undefined[1]
        self.y = undefined[2]
        self.sp = undefined[3]
        self.pc = undefined[4] | (undefined[5] << 8)
        self.psw = undefined[4]

    def reset(self, seed: int = UNSET_SEED) -> "Cpu":
        undefined = scramble(6, seed)
        self.a = undefined[0]
        self.x = undefined[1]
        self.y = undefined[2]
        self.sp = undefined[3]
        self.psw = undefined[4] & ~FLAG_P

        self.pc = self.read16(RESET_VECTOR)
        self.steps = 0
        self.stopped = False
        return self

    @property
    def psw(self) -> int:
        value = 0
        value |= FLAG_N if self.n else 0
        value |= FLAG_V if self.v else 0
        value |= FLAG_P if self.p else 0
        value |= FLAG_B if self.b else 0
        value |= FLAG_H if self.h else 0
        value |= FLAG_I if self.i else 0
        value |= FLAG_Z if self.z else 0
        value |= FLAG_C if self.c else 0
        return value

    @psw.setter
    def psw(self, value: int) -> None:
        self.n = bool(value & FLAG_N)
        self.v = bool(value & FLAG_V)
        self.p = bool(value & FLAG_P)
        self.b = bool(value & FLAG_B)
        self.h = bool(value & FLAG_H)
        self.i = bool(value & FLAG_I)
        self.z = bool(value & FLAG_Z)
        self.c = bool(value & FLAG_C)

    @property
    def direct_page(self) -> int:
        return 0x0100 if self.p else 0x0000

    @property
    def ya(self) -> int:
        return (self.y << 8) | self.a

    @ya.setter
    def ya(self, value: int) -> None:
        self.a = value & 0xFF
        self.y = (value >> 8) & 0xFF

    def read8(self, address: int) -> int:
        value = self.memory.read8(address & 0xFFFF) & 0xFF
        self.bus.read(address, value)
        return value

    def peek8(self, address: int) -> None:
        self.bus.read(address, self.memory.read8(address & 0xFFFF) & 0xFF)

    def idle(self, count: int = 1) -> None:
        self.bus.idle(count)

    def write8(self, address: int, value: int) -> None:
        self.memory.write8(address & 0xFFFF, value & 0xFF)
        self.bus.write(address, value)

    def store8(self, address: int, value: int) -> None:
        self.peek8(address)
        self.write8(address, value)

    def read16(self, address: int) -> int:
        return self.read8(address) | (self.read8(address + 1) << 8)

    def read_direct16(self, address: int) -> int:
        page = address & 0xFF00
        return self.read8(address) | (self.read8(page | ((address + 1) & 0xFF)) << 8)

    def write_direct16(self, address: int, value: int) -> None:
        page = address & 0xFF00
        self.write8(address, value)
        self.write8(page | ((address + 1) & 0xFF), value >> 8)

    def fetch8(self) -> int:
        value = self.read8(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return value

    def fetch16(self) -> int:
        return self.fetch8() | (self.fetch8() << 8)

    def push8(self, value: int) -> None:
        self.write8(STACK_PAGE | self.sp, value)
        self.sp = (self.sp - 1) & 0xFF

    def pull8(self) -> int:
        self.sp = (self.sp + 1) & 0xFF
        return self.read8(STACK_PAGE | self.sp)

    def pull_after_idle8(self) -> int:
        self.idle()
        return self.pull8()

    def push16(self, value: int) -> None:
        self.push8(value >> 8)
        self.push8(value)

    def pull16(self) -> int:
        return self.pull8() | (self.pull8() << 8)

    def set_nz(self, value: int) -> int:
        self.n = bool(value & 0x80)
        self.z = (value & 0xFF) == 0
        return value & 0xFF

    def set_nz16(self, value: int) -> int:
        self.n = bool(value & 0x8000)
        self.z = (value & 0xFFFF) == 0
        return value & 0xFFFF

    def direct(self, offset: int) -> int:
        return self.direct_page | (offset & 0xFF)

    def step(self) -> int:
        if self.stopped:
            return 0
        self.bus.restart()
        opcode = self.fetch8()
        mnemonic, mode, size = OPCODES[opcode]
        if size == 1:
            self.peek8(self.pc)
        getattr(self, f"op_{mnemonic}")(mode, opcode)
        self.steps += 1
        return self.bus.cycles

    def run_for(self, cycles: int) -> int:
        spent = 0
        while spent < cycles:
            if self.stopped:
                while spent < cycles:
                    self.held_cycle()
                    spent += 1
                return spent
            spent += self.step()
        return spent

    def _spent(self, count: int = 1) -> None:
        self.cycles += count
        if self.on_cycle is not None:
            for _ in range(count):
                self.on_cycle()

    def held(self) -> bool:
        return self.stopped

    def held_cycle(self) -> None:
        self._spent(1)

    def run_until(self, predicate: Callable[["Cpu"], bool], limit: int | None = None) -> "Cpu":
        taken = 0
        while not predicate(self):
            if self.steps >= self.step_limit:
                raise RunLimit(f"still running after {self.steps} instructions")
            self.step()
            taken += 1
            if limit is not None and taken >= limit:
                raise RunLimit(f"gave up after {taken} instructions at ${self.pc:04X}")
        return self

    def operand_address(self, mode: str, opcode: int) -> int:
        if mode in ("dp", "dp_bit", "dp_a", "dp_x", "dp_y", "dp_ya", "a_dp", "x_dp", "y_dp"):
            return self.direct(self.fetch8())
        if mode in ("dpx", "dpx_a", "dpx_y", "a_dpx", "y_dpx"):
            offset = self.fetch8()
            self.idle()
            return self.direct(offset + self.x)
        if mode in ("dpy_x", "x_dpy"):
            offset = self.fetch8()
            self.idle()
            return self.direct(offset + self.y)
        if mode in ("abs", "abs_a", "abs_x", "abs_y", "a_abs", "x_abs", "y_abs"):
            return self.fetch16()
        if mode in ("absx_a", "a_absx"):
            address = self.fetch16()
            self.idle()
            return (address + self.x) & 0xFFFF
        if mode in ("absy_a", "a_absy"):
            address = self.fetch16()
            self.idle()
            return (address + self.y) & 0xFFFF
        if mode in ("idx_a", "a_idx"):
            offset = self.fetch8()
            self.idle()
            return self.read_direct16(self.direct(offset + self.x))
        if mode == "a_idy":
            offset = self.fetch8()
            self.idle()
            return (self.read_direct16(self.direct(offset)) + self.y) & 0xFFFF
        if mode == "idy_a":
            pointer = self.read_direct16(self.direct(self.fetch8()))
            self.idle()
            return (pointer + self.y) & 0xFFFF
        if mode in ("ix_a", "a_ix", "ixinc_a", "a_ixinc"):
            return self.direct(self.x)
        raise KeyError(f"{mode} does not name an address")

    def source_value(self, mode: str, opcode: int) -> int:
        if mode in ("a_imm", "x_imm", "y_imm"):
            return self.fetch8()
        if mode == "ix_iy":
            return self.read8(self.direct(self.y))
        if mode == "dp_imm":
            return self.fetch8()
        if mode == "dp_dp":
            return self.read8(self.direct(self.fetch8()))
        return self.read8(self.operand_address(mode, opcode))

    def target_address(self, mode: str, opcode: int) -> int:
        if mode == "ix_iy":
            return self.direct(self.x)
        return self.direct(self.fetch8())

    def _accumulate(
        self, mode: str, opcode: int, operation: Callable[[int, int], int | None]
    ) -> None:
        if mode in ("dp_imm", "dp_dp", "ix_iy"):
            value = self.source_value(mode, opcode)
            address = self.target_address(mode, opcode)
            result = operation(self.read8(address), value)
            if result is None:
                self.idle()
            else:
                self.write8(address, result)
            return
        result = operation(self.a, self.source_value(mode, opcode))
        if result is not None:
            self.a = result

    def add_with_carry(self, first: int, second: int) -> int:
        result = first + second + int(self.c)
        self.c = result > 0xFF
        self.h = bool((first ^ second ^ result) & 0x10)
        self.v = bool(~(first ^ second) & (first ^ result) & 0x80)
        return self.set_nz(result)

    def subtract_with_carry(self, first: int, second: int) -> int:
        result = first - second - int(not self.c)
        self.c = result >= 0
        self.h = not ((first ^ second ^ result) & 0x10)
        self.v = bool((first ^ second) & (first ^ result) & 0x80)
        return self.set_nz(result)

    def compare(self, first: int, second: int) -> None:
        result = first - second
        self.c = result >= 0
        self.set_nz(result)

    def op_adc(self, mode: str, opcode: int) -> None:
        self._accumulate(mode, opcode, self.add_with_carry)

    def op_sbc(self, mode: str, opcode: int) -> None:
        self._accumulate(mode, opcode, self.subtract_with_carry)

    def op_cmp(self, mode: str, opcode: int) -> None:
        if mode.startswith("x"):
            self.compare(self.x, self.source_value(mode, opcode))
            return
        if mode.startswith("y"):
            self.compare(self.y, self.source_value(mode, opcode))
            return
        self._accumulate(mode, opcode, self.compare)

    def op_and(self, mode: str, opcode: int) -> None:
        self._accumulate(mode, opcode, lambda first, second: self.set_nz(first & second))

    def op_or(self, mode: str, opcode: int) -> None:
        self._accumulate(mode, opcode, lambda first, second: self.set_nz(first | second))

    def op_eor(self, mode: str, opcode: int) -> None:
        self._accumulate(mode, opcode, lambda first, second: self.set_nz(first ^ second))

    def _read_modify_write(self, mode: str, opcode: int, operation: Callable[[int], int]) -> None:
        if mode == "a":
            self.a = operation(self.a)
            return
        if mode == "x":
            self.x = operation(self.x)
            return
        if mode == "y":
            self.y = operation(self.y)
            return
        address = self.operand_address(mode, opcode)
        self.write8(address, operation(self.read8(address)))

    def op_inc(self, mode: str, opcode: int) -> None:
        self._read_modify_write(mode, opcode, lambda value: self.set_nz(value + 1))

    def op_dec(self, mode: str, opcode: int) -> None:
        self._read_modify_write(mode, opcode, lambda value: self.set_nz(value - 1))

    def shift_left(self, value: int) -> int:
        self.c = bool(value & 0x80)
        return self.set_nz(value << 1)

    def shift_right(self, value: int) -> int:
        self.c = bool(value & 0x01)
        return self.set_nz(value >> 1)

    def rotate_left(self, value: int) -> int:
        carried = int(self.c)
        self.c = bool(value & 0x80)
        return self.set_nz((value << 1) | carried)

    def rotate_right(self, value: int) -> int:
        carried = int(self.c) << 7
        self.c = bool(value & 0x01)
        return self.set_nz((value >> 1) | carried)

    def op_asl(self, mode: str, opcode: int) -> None:
        self._read_modify_write(mode, opcode, self.shift_left)

    def op_lsr(self, mode: str, opcode: int) -> None:
        self._read_modify_write(mode, opcode, self.shift_right)

    def op_rol(self, mode: str, opcode: int) -> None:
        self._read_modify_write(mode, opcode, self.rotate_left)

    def op_ror(self, mode: str, opcode: int) -> None:
        self._read_modify_write(mode, opcode, self.rotate_right)

    def op_xcn(self, mode: str, opcode: int) -> None:
        self.idle(3)
        self.a = self.set_nz((self.a >> 4) | (self.a << 4))

    def op_mov(self, mode: str, opcode: int) -> None:
        if mode == "a_imm":
            self.a = self.set_nz(self.fetch8())
        elif mode == "x_imm":
            self.x = self.set_nz(self.fetch8())
        elif mode == "y_imm":
            self.y = self.set_nz(self.fetch8())
        elif mode in ("a_dp", "a_dpx", "a_abs", "a_absx", "a_absy", "a_idx", "a_idy", "a_ix"):
            self.a = self.set_nz(self.read8(self.operand_address(mode, opcode)))
        elif mode == "a_ixinc":
            self.a = self.set_nz(self.read8(self.direct(self.x)))
            self.idle()
            self.x = (self.x + 1) & 0xFF
        elif mode in ("x_dp", "x_dpy", "x_abs"):
            self.x = self.set_nz(self.read8(self.operand_address(mode, opcode)))
        elif mode in ("y_dp", "y_dpx", "y_abs"):
            self.y = self.set_nz(self.read8(self.operand_address(mode, opcode)))
        elif mode == "a_x":
            self.a = self.set_nz(self.x)
        elif mode == "a_y":
            self.a = self.set_nz(self.y)
        elif mode == "x_a":
            self.x = self.set_nz(self.a)
        elif mode == "y_a":
            self.y = self.set_nz(self.a)
        elif mode == "x_sp":
            self.x = self.set_nz(self.sp)
        elif mode == "sp_x":
            self.sp = self.x
        elif mode == "ixinc_a":
            self.idle()
            self.write8(self.direct(self.x), self.a)
            self.x = (self.x + 1) & 0xFF
        elif mode == "dp_dp":
            value = self.read8(self.direct(self.fetch8()))
            self.write8(self.direct(self.fetch8()), value)
        elif mode == "dp_imm":
            value = self.fetch8()
            self.store8(self.direct(self.fetch8()), value)
        elif mode in ("dp_x", "dpy_x", "abs_x"):
            self.store8(self.operand_address(mode, opcode), self.x)
        elif mode in ("dp_y", "dpx_y", "abs_y"):
            self.store8(self.operand_address(mode, opcode), self.y)
        else:
            self.store8(self.operand_address(mode, opcode), self.a)

    def op_movw(self, mode: str, opcode: int) -> None:
        if mode == "ya_dp":
            self.ya = self.set_nz16(self._word_at_direct())
            return
        address = self.direct(self.fetch8())
        self.read8(address)
        self.write_direct16(address, self.ya)

    def _word_at_direct(self, pause: bool = True) -> int:
        address = self.direct(self.fetch8())
        page = address & 0xFF00
        low = self.read8(address)
        if pause:
            self.idle()
        return low | (self.read8(page | ((address + 1) & 0xFF)) << 8)

    def op_addw(self, mode: str, opcode: int) -> None:
        value = self._word_at_direct()
        self.c = False
        low = self.add_with_carry(self.a, value & 0xFF)
        high = self.add_with_carry(self.y, value >> 8)
        result = (high << 8) | low
        self.z = result == 0
        self.ya = result

    def op_subw(self, mode: str, opcode: int) -> None:
        value = self._word_at_direct()
        self.c = True
        low = self.subtract_with_carry(self.a, value & 0xFF)
        high = self.subtract_with_carry(self.y, value >> 8)
        result = (high << 8) | low
        self.z = result == 0
        self.ya = result

    def op_cmpw(self, mode: str, opcode: int) -> None:
        value = self._word_at_direct(pause=False)
        result = self.ya - value
        self.c = result >= 0
        self.set_nz16(result)

    def _word_read_modify_write(self, step: int) -> None:
        address = self.direct(self.fetch8())
        page = address & 0xFF00
        high_address = page | ((address + 1) & 0xFF)

        low = self.read8(address) + step
        self.write8(address, low)
        carry = -1 if low < 0 else (1 if low > 0xFF else 0)
        high = (self.read8(high_address) + carry) & 0xFF
        self.write8(high_address, high)

        self.set_nz16((high << 8) | (low & 0xFF))

    def op_incw(self, mode: str, opcode: int) -> None:
        self._word_read_modify_write(1)

    def op_decw(self, mode: str, opcode: int) -> None:
        self._word_read_modify_write(-1)

    def op_mul(self, mode: str, opcode: int) -> None:
        self.idle(7)
        result = self.y * self.a
        self.ya = result
        self.set_nz(self.y)

    def op_div(self, mode: str, opcode: int) -> None:
        self.idle(10)
        dividend = self.ya
        divisor = self.x
        self.h = (divisor & 0x0F) <= (self.y & 0x0F)
        self.v = self.y >= divisor
        if self.y < (divisor << 1):
            self.a = dividend // divisor
            self.y = dividend % divisor
        else:
            self.a = 255 - (dividend - (divisor << 9)) // (256 - divisor)
            self.y = divisor + (dividend - (divisor << 9)) % (256 - divisor)
        self.a &= 0xFF
        self.y &= 0xFF
        self.set_nz(self.a)

    def op_daa(self, mode: str, opcode: int) -> None:
        self.idle()
        if self.c or self.a > 0x99:
            self.a = (self.a + 0x60) & 0xFF
            self.c = True
        if self.h or (self.a & 0x0F) > 0x09:
            self.a = (self.a + 0x06) & 0xFF
        self.set_nz(self.a)

    def op_das(self, mode: str, opcode: int) -> None:
        self.idle()
        if not self.c or self.a > 0x99:
            self.a = (self.a - 0x60) & 0xFF
            self.c = False
        if not self.h or (self.a & 0x0F) > 0x09:
            self.a = (self.a - 0x06) & 0xFF
        self.set_nz(self.a)

    def _branch(self, taken: bool) -> None:
        offset = self.fetch8()
        if taken:
            self.idle(2)
            self.pc = (self.pc + (offset - 0x100 if offset >= 0x80 else offset)) & 0xFFFF

    def _conditional_branch(self, mnemonic: str) -> None:
        condition = BRANCHES[mnemonic]
        self._branch(True if condition is None else getattr(self, condition[0]) == condition[1])

    def op_bra(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bra")

    def op_beq(self, mode: str, opcode: int) -> None:
        self._conditional_branch("beq")

    def op_bne(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bne")

    def op_bcs(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bcs")

    def op_bcc(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bcc")

    def op_bvs(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bvs")

    def op_bvc(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bvc")

    def op_bmi(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bmi")

    def op_bpl(self, mode: str, opcode: int) -> None:
        self._conditional_branch("bpl")

    def op_bbs(self, mode: str, opcode: int) -> None:
        value = self.read8(self.direct(self.fetch8()))
        self.idle()
        self._branch(bool(value & (1 << table.bit_index(opcode))))

    def op_bbc(self, mode: str, opcode: int) -> None:
        value = self.read8(self.direct(self.fetch8()))
        self.idle()
        self._branch(not value & (1 << table.bit_index(opcode)))

    def op_cbne(self, mode: str, opcode: int) -> None:
        address = self.operand_address("dpx" if mode == "dpx_rel" else "dp", opcode)
        value = self.read8(address)
        self.idle()
        self._branch(value != self.a)

    def op_dbnz(self, mode: str, opcode: int) -> None:
        if mode == "y_rel":
            self.peek8(self.pc)
            self.idle()
            self.y = (self.y - 1) & 0xFF
            self._branch(self.y != 0)
            return
        address = self.direct(self.fetch8())
        result = (self.read8(address) - 1) & 0xFF
        self.write8(address, result)
        self._branch(result != 0)

    def op_jmp(self, mode: str, opcode: int) -> None:
        if mode == "abs_indirect_x":
            table_address = self.fetch16()
            self.idle()
            self.pc = self.read16((table_address + self.x) & 0xFFFF)
            return
        self.pc = self.fetch16()

    def op_call(self, mode: str, opcode: int) -> None:
        target = self.fetch16()
        self.idle()
        self.push16(self.pc)
        self.idle(2)
        self.pc = target

    def op_pcall(self, mode: str, opcode: int) -> None:
        target = self.fetch8()
        self.idle()
        self.push16(self.pc)
        self.idle()
        self.pc = UPPER_PAGE | target

    def op_tcall(self, mode: str, opcode: int) -> None:
        vector = CALL_TABLE_TOP - (table.call_index(opcode) << 1)
        self.idle()
        self.push16(self.pc)
        self.idle()
        self.pc = self.read16(vector)

    def op_brk(self, mode: str, opcode: int) -> None:
        self.push16(self.pc)
        self.push8(self.psw)
        self.idle()
        self.b = True
        self.i = False
        self.pc = self.read16(BREAK_VECTOR)

    def op_ret(self, mode: str, opcode: int) -> None:
        self.idle()
        self.pc = self.pull16()

    def op_reti(self, mode: str, opcode: int) -> None:
        self.psw = self.pull_after_idle8()
        self.pc = self.pull16()

    def op_push(self, mode: str, opcode: int) -> None:
        self.push8({"a": self.a, "x": self.x, "y": self.y, "p": self.psw}[mode])
        self.idle()

    def op_pop(self, mode: str, opcode: int) -> None:
        value = self.pull_after_idle8()
        if mode == "a":
            self.a = value
        elif mode == "x":
            self.x = value
        elif mode == "y":
            self.y = value
        else:
            self.psw = value

    def op_set1(self, mode: str, opcode: int) -> None:
        address = self.direct(self.fetch8())
        self.write8(address, self.read8(address) | (1 << table.bit_index(opcode)))

    def op_clr1(self, mode: str, opcode: int) -> None:
        address = self.direct(self.fetch8())
        self.write8(address, self.read8(address) & ~(1 << table.bit_index(opcode)))

    def op_tset(self, mode: str, opcode: int) -> None:
        address = self.fetch16()
        held = self.read8(address)
        self.peek8(address)
        self.write8(address, held | self.a)
        self.set_nz(self.a - held)

    def op_tclr(self, mode: str, opcode: int) -> None:
        address = self.fetch16()
        held = self.read8(address)
        self.peek8(address)
        self.write8(address, held & ~self.a)
        self.set_nz(self.a - held)

    def _addressed_bit(self) -> tuple[int, int]:
        packed = self.fetch16()
        return packed & 0x1FFF, packed >> 13

    def op_and1(self, mode: str, opcode: int) -> None:
        address, bit = self._addressed_bit()
        held = bool(self.read8(address) & (1 << bit))
        self.c = self.c and (not held if mode == "c_notmembit" else held)

    def op_or1(self, mode: str, opcode: int) -> None:
        address, bit = self._addressed_bit()
        held = bool(self.read8(address) & (1 << bit))
        self.idle()
        self.c = self.c or (not held if mode == "c_notmembit" else held)

    def op_eor1(self, mode: str, opcode: int) -> None:
        address, bit = self._addressed_bit()
        held = bool(self.read8(address) & (1 << bit))
        self.idle()
        self.c = self.c != held

    def op_not1(self, mode: str, opcode: int) -> None:
        address, bit = self._addressed_bit()
        self.write8(address, self.read8(address) ^ (1 << bit))

    def op_mov1(self, mode: str, opcode: int) -> None:
        address, bit = self._addressed_bit()
        if mode == "membit_c":
            held = self.read8(address)
            self.idle()
            self.write8(address, (held | (1 << bit)) if self.c else (held & ~(1 << bit)))
            return
        self.c = bool(self.read8(address) & (1 << bit))

    def op_clrc(self, mode: str, opcode: int) -> None:
        self.c = False

    def op_setc(self, mode: str, opcode: int) -> None:
        self.c = True

    def op_notc(self, mode: str, opcode: int) -> None:
        self.idle()
        self.c = not self.c

    def op_clrv(self, mode: str, opcode: int) -> None:
        self.v = False
        self.h = False

    def op_clrp(self, mode: str, opcode: int) -> None:
        self.p = False

    def op_setp(self, mode: str, opcode: int) -> None:
        self.p = True

    def op_ei(self, mode: str, opcode: int) -> None:
        self.idle()
        self.i = True

    def op_di(self, mode: str, opcode: int) -> None:
        self.idle()
        self.i = False

    def op_nop(self, mode: str, opcode: int) -> None:
        return

    def op_sleep(self, mode: str, opcode: int) -> None:
        self._halt()

    def op_stop(self, mode: str, opcode: int) -> None:
        self._halt()

    def _halt(self) -> None:
        for _ in range(HALT_CYCLES):
            self.idle()
            self.peek8(self.pc)
        self.idle()
        self.stopped = True

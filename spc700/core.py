"""An SPC700 interpreter that follows the processor rather than a convenient model.

All 256 opcodes are implemented. The SPC700 leaves none undefined, so there is no
illegal instruction to decide about, but several of the defined ones behave in
ways no summary of the instruction set would lead you to expect. The division
does not compute a quotient once the result stops fitting, the decimal adjust
reads the accumulator it has already modified, and the half carry means the
opposite thing after a subtraction than it does after an addition. Each of those
is written the way the hardware does it, not the way it reads better.

Nothing here starts from a clean state. A processor coming out of reset holds
whatever its registers held, memory holds whatever it held, and an interpreter
that quietly begins at zero models a machine that has never existed.
"""

from . import opcodes as table
from .memory import UNSET_SEED, scramble

OPCODES = table.OPCODES

STEP_LIMIT = 2_000_000

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


class StepLimit(Exception):
    pass


class Cpu:
    """An SPC700 in the state a reset leaves it, not one chosen for tidiness.

    A reset defines less than a model usually assumes. It loads the program
    counter from the vector at the top of the space and says nothing about the
    accumulator, the index registers, the stack pointer, or most of the status
    register. Hardware leaves those holding whatever they held, so they are
    scrambled from a seed here rather than zeroed: reproducible, so a differential
    run stays comparable, and not zero, which is what stops code that reads them
    before writing them from looking correct here and failing on a console.
    """

    def __init__(self, memory, step_limit=STEP_LIMIT, seed=UNSET_SEED, reset=True):
        self.memory = memory
        self.step_limit = step_limit
        self.model = "spc700"
        self.steps = 0
        self.stopped = False
        self.a = self.x = self.y = 0x00
        self.sp = 0xFF
        self.pc = 0x0000
        self.n = self.v = self.p = self.b = False
        self.h = self.i = self.z = self.c = False
        if reset:
            self.reset(seed)

    def reset(self, seed=UNSET_SEED):
        """Put the processor where a reset puts it, undefined parts included."""
        undefined = scramble(6, seed)
        self.a = undefined[0]
        self.x = undefined[1]
        self.y = undefined[2]
        self.sp = undefined[3]
        self.psw = undefined[4]

        self.pc = self.read16(RESET_VECTOR)
        self.steps = 0
        self.stopped = False

    @property
    def psw(self):
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
    def psw(self, value):
        self.n = bool(value & FLAG_N)
        self.v = bool(value & FLAG_V)
        self.p = bool(value & FLAG_P)
        self.b = bool(value & FLAG_B)
        self.h = bool(value & FLAG_H)
        self.i = bool(value & FLAG_I)
        self.z = bool(value & FLAG_Z)
        self.c = bool(value & FLAG_C)

    @property
    def direct_page(self):
        """Where the direct page currently sits, which the P flag decides."""
        return 0x0100 if self.p else 0x0000

    @property
    def ya(self):
        return (self.y << 8) | self.a

    @ya.setter
    def ya(self, value):
        self.a = value & 0xFF
        self.y = (value >> 8) & 0xFF

    def read8(self, address):
        return self.memory.read8(address & 0xFFFF) & 0xFF

    def write8(self, address, value):
        self.memory.write8(address & 0xFFFF, value & 0xFF)

    def read16(self, address):
        return self.read8(address) | (self.read8(address + 1) << 8)

    def read_direct16(self, address):
        """A word in the direct page, whose high byte wraps inside that page."""
        page = address & 0xFF00
        return self.read8(address) | (self.read8(page | ((address + 1) & 0xFF)) << 8)

    def write_direct16(self, address, value):
        page = address & 0xFF00
        self.write8(address, value)
        self.write8(page | ((address + 1) & 0xFF), value >> 8)

    def fetch8(self):
        value = self.read8(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return value

    def fetch16(self):
        return self.fetch8() | (self.fetch8() << 8)

    def push8(self, value):
        self.write8(STACK_PAGE | self.sp, value)
        self.sp = (self.sp - 1) & 0xFF

    def pull8(self):
        self.sp = (self.sp + 1) & 0xFF
        return self.read8(STACK_PAGE | self.sp)

    def push16(self, value):
        self.push8(value >> 8)
        self.push8(value)

    def pull16(self):
        return self.pull8() | (self.pull8() << 8)

    def set_nz(self, value):
        self.n = bool(value & 0x80)
        self.z = (value & 0xFF) == 0
        return value & 0xFF

    def set_nz16(self, value):
        self.n = bool(value & 0x8000)
        self.z = (value & 0xFFFF) == 0
        return value & 0xFFFF

    def direct(self, offset):
        return self.direct_page | (offset & 0xFF)

    def step(self):
        """Execute one instruction, or nothing at all once the processor stops."""
        if self.stopped:
            return self
        opcode = self.fetch8()
        mnemonic, mode, _ = OPCODES[opcode]
        getattr(self, f"op_{mnemonic}")(mode, opcode)
        self.steps += 1
        return self

    def run_until(self, done):
        """Step until the caller says stop, or refuse to run forever."""
        while not done(self):
            if self.steps >= self.step_limit:
                raise StepLimit(f"still running after {self.steps} instructions")
            self.step()
        return self

    def operand_address(self, mode, opcode):
        """Where an addressing mode points, for the modes that name a location."""
        if mode in ("dp", "dp_bit", "dp_a", "dp_x", "dp_y", "dp_ya", "a_dp", "x_dp", "y_dp"):
            return self.direct(self.fetch8())
        if mode in ("dpx", "dpx_a", "dpx_y", "a_dpx", "y_dpx"):
            return self.direct(self.fetch8() + self.x)
        if mode in ("dpy_x", "x_dpy"):
            return self.direct(self.fetch8() + self.y)
        if mode in ("abs", "abs_a", "abs_x", "abs_y", "a_abs", "x_abs", "y_abs"):
            return self.fetch16()
        if mode in ("absx_a", "a_absx"):
            return (self.fetch16() + self.x) & 0xFFFF
        if mode in ("absy_a", "a_absy"):
            return (self.fetch16() + self.y) & 0xFFFF
        if mode in ("idx_a", "a_idx"):
            return self.read_direct16(self.direct(self.fetch8() + self.x))
        if mode in ("idy_a", "a_idy"):
            return (self.read_direct16(self.direct(self.fetch8())) + self.y) & 0xFFFF
        if mode in ("ix_a", "a_ix", "ixinc_a", "a_ixinc"):
            return self.direct(self.x)
        raise KeyError(f"{mode} does not name an address")

    def source_value(self, mode, opcode):
        """The value an arithmetic or logic instruction reads."""
        if mode in ("a_imm", "x_imm", "y_imm"):
            return self.fetch8()
        if mode == "ix_iy":
            return self.read8(self.direct(self.y))
        if mode == "dp_imm":
            return self.fetch8()
        if mode == "dp_dp":
            return self.read8(self.direct(self.fetch8()))
        return self.read8(self.operand_address(mode, opcode))

    def target_address(self, mode, opcode):
        """Where a two operand instruction writes, once its source is read."""
        if mode == "ix_iy":
            return self.direct(self.x)
        return self.direct(self.fetch8())

    def _accumulate(self, mode, opcode, operation):
        """Run one of the forms every accumulator arithmetic instruction comes in.

        Only the accumulator is handled here. The index registers appear in these
        instructions once each, as the left side of a comparison, and a comparison
        writes nothing back, so routing them through a path that assigns a result
        would add a store that no opcode can reach.
        """
        if mode in ("dp_imm", "dp_dp", "ix_iy"):
            value = self.source_value(mode, opcode)
            address = self.target_address(mode, opcode)
            result = operation(self.read8(address), value)
            if result is not None:
                self.write8(address, result)
            return
        result = operation(self.a, self.source_value(mode, opcode))
        if result is not None:
            self.a = result

    def add_with_carry(self, first, second):
        result = first + second + int(self.c)
        self.c = result > 0xFF
        self.h = bool((first ^ second ^ result) & 0x10)
        self.v = bool(~(first ^ second) & (first ^ result) & 0x80)
        return self.set_nz(result)

    def subtract_with_carry(self, first, second):
        result = first - second - int(not self.c)
        self.c = result >= 0
        self.h = not ((first ^ second ^ result) & 0x10)
        self.v = bool((first ^ second) & (first ^ result) & 0x80)
        return self.set_nz(result)

    def compare(self, first, second):
        result = first - second
        self.c = result >= 0
        self.set_nz(result)

    def op_adc(self, mode, opcode):
        self._accumulate(mode, opcode, self.add_with_carry)

    def op_sbc(self, mode, opcode):
        self._accumulate(mode, opcode, self.subtract_with_carry)

    def op_cmp(self, mode, opcode):
        if mode.startswith("x"):
            self.compare(self.x, self.source_value(mode, opcode))
            return
        if mode.startswith("y"):
            self.compare(self.y, self.source_value(mode, opcode))
            return
        self._accumulate(mode, opcode, self.compare)

    def op_and(self, mode, opcode):
        self._accumulate(mode, opcode, lambda first, second: self.set_nz(first & second))

    def op_or(self, mode, opcode):
        self._accumulate(mode, opcode, lambda first, second: self.set_nz(first | second))

    def op_eor(self, mode, opcode):
        self._accumulate(mode, opcode, lambda first, second: self.set_nz(first ^ second))

    def _read_modify_write(self, mode, opcode, operation):
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

    def op_inc(self, mode, opcode):
        self._read_modify_write(mode, opcode, lambda value: self.set_nz(value + 1))

    def op_dec(self, mode, opcode):
        self._read_modify_write(mode, opcode, lambda value: self.set_nz(value - 1))

    def shift_left(self, value):
        self.c = bool(value & 0x80)
        return self.set_nz(value << 1)

    def shift_right(self, value):
        self.c = bool(value & 0x01)
        return self.set_nz(value >> 1)

    def rotate_left(self, value):
        carried = int(self.c)
        self.c = bool(value & 0x80)
        return self.set_nz((value << 1) | carried)

    def rotate_right(self, value):
        carried = int(self.c) << 7
        self.c = bool(value & 0x01)
        return self.set_nz((value >> 1) | carried)

    def op_asl(self, mode, opcode):
        self._read_modify_write(mode, opcode, self.shift_left)

    def op_lsr(self, mode, opcode):
        self._read_modify_write(mode, opcode, self.shift_right)

    def op_rol(self, mode, opcode):
        self._read_modify_write(mode, opcode, self.rotate_left)

    def op_ror(self, mode, opcode):
        self._read_modify_write(mode, opcode, self.rotate_right)

    def op_xcn(self, mode, opcode):
        self.a = self.set_nz((self.a >> 4) | (self.a << 4))

    def op_mov(self, mode, opcode):
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
            self.write8(self.direct(self.x), self.a)
            self.x = (self.x + 1) & 0xFF
        elif mode == "dp_dp":
            value = self.read8(self.direct(self.fetch8()))
            self.write8(self.direct(self.fetch8()), value)
        elif mode == "dp_imm":
            value = self.fetch8()
            self.write8(self.direct(self.fetch8()), value)
        elif mode in ("dp_x", "dpy_x", "abs_x"):
            self.write8(self.operand_address(mode, opcode), self.x)
        elif mode in ("dp_y", "dpx_y", "abs_y"):
            self.write8(self.operand_address(mode, opcode), self.y)
        else:
            self.write8(self.operand_address(mode, opcode), self.a)

    def op_movw(self, mode, opcode):
        if mode == "ya_dp":
            self.ya = self.set_nz16(self.read_direct16(self.direct(self.fetch8())))
            return
        address = self.direct(self.fetch8())
        self.read8(address)
        self.write_direct16(address, self.ya)

    def _word_at_direct(self):
        return self.read_direct16(self.direct(self.fetch8()))

    def op_addw(self, mode, opcode):
        value = self._word_at_direct()
        self.c = False
        low = self.add_with_carry(self.a, value & 0xFF)
        high = self.add_with_carry(self.y, value >> 8)
        result = (high << 8) | low
        self.z = result == 0
        self.ya = result

    def op_subw(self, mode, opcode):
        value = self._word_at_direct()
        self.c = True
        low = self.subtract_with_carry(self.a, value & 0xFF)
        high = self.subtract_with_carry(self.y, value >> 8)
        result = (high << 8) | low
        self.z = result == 0
        self.ya = result

    def op_cmpw(self, mode, opcode):
        value = self._word_at_direct()
        result = self.ya - value
        self.c = result >= 0
        self.set_nz16(result)

    def _word_read_modify_write(self, step):
        address = self.direct(self.fetch8())
        result = self.set_nz16(self.read_direct16(address) + step)
        self.write_direct16(address, result)

    def op_incw(self, mode, opcode):
        self._word_read_modify_write(1)

    def op_decw(self, mode, opcode):
        self._word_read_modify_write(-1)

    def op_mul(self, mode, opcode):
        result = self.y * self.a
        self.ya = result
        self.set_nz(self.y)

    def op_div(self, mode, opcode):
        """The divide, including what it does once the quotient stops fitting.

        Below the point where the result fits, this is an ordinary division. Above
        it the hardware does not fail or saturate; it keeps running the same shift
        and subtract network past the end of its useful range and leaves behind
        the value that falls out. The overflow flag reports that the answer is not
        a quotient, and the half carry reports a nibble comparison that has nothing
        to do with the division at all.
        """
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

    def op_daa(self, mode, opcode):
        """Decimal adjust after an addition, reading the accumulator it just wrote.

        The second test looks at the value the first branch may already have
        changed, so a carry produced by adding sixty can feed the nibble test
        below it. Testing the original value instead is the obvious reading and
        the wrong one.
        """
        if self.c or self.a > 0x99:
            self.a = (self.a + 0x60) & 0xFF
            self.c = True
        if self.h or (self.a & 0x0F) > 0x09:
            self.a = (self.a + 0x06) & 0xFF
        self.set_nz(self.a)

    def op_das(self, mode, opcode):
        if not self.c or self.a > 0x99:
            self.a = (self.a - 0x60) & 0xFF
            self.c = False
        if not self.h or (self.a & 0x0F) > 0x09:
            self.a = (self.a - 0x06) & 0xFF
        self.set_nz(self.a)

    def _branch(self, taken):
        offset = self.fetch8()
        if taken:
            self.pc = (self.pc + (offset - 0x100 if offset >= 0x80 else offset)) & 0xFFFF

    def _conditional_branch(self, mnemonic):
        condition = BRANCHES[mnemonic]
        self._branch(True if condition is None else getattr(self, condition[0]) == condition[1])

    def op_bra(self, mode, opcode):
        self._conditional_branch("bra")

    def op_beq(self, mode, opcode):
        self._conditional_branch("beq")

    def op_bne(self, mode, opcode):
        self._conditional_branch("bne")

    def op_bcs(self, mode, opcode):
        self._conditional_branch("bcs")

    def op_bcc(self, mode, opcode):
        self._conditional_branch("bcc")

    def op_bvs(self, mode, opcode):
        self._conditional_branch("bvs")

    def op_bvc(self, mode, opcode):
        self._conditional_branch("bvc")

    def op_bmi(self, mode, opcode):
        self._conditional_branch("bmi")

    def op_bpl(self, mode, opcode):
        self._conditional_branch("bpl")

    def op_bbs(self, mode, opcode):
        value = self.read8(self.direct(self.fetch8()))
        self._branch(bool(value & (1 << table.bit_index(opcode))))

    def op_bbc(self, mode, opcode):
        value = self.read8(self.direct(self.fetch8()))
        self._branch(not value & (1 << table.bit_index(opcode)))

    def op_cbne(self, mode, opcode):
        address = self.operand_address("dpx" if mode == "dpx_rel" else "dp", opcode)
        self._branch(self.read8(address) != self.a)

    def op_dbnz(self, mode, opcode):
        if mode == "y_rel":
            self.y = (self.y - 1) & 0xFF
            self._branch(self.y != 0)
            return
        address = self.direct(self.fetch8())
        result = (self.read8(address) - 1) & 0xFF
        self.write8(address, result)
        self._branch(result != 0)

    def op_jmp(self, mode, opcode):
        if mode == "abs_indirect_x":
            self.pc = self.read16((self.fetch16() + self.x) & 0xFFFF)
            return
        self.pc = self.fetch16()

    def op_call(self, mode, opcode):
        target = self.fetch16()
        self.push16(self.pc)
        self.pc = target

    def op_pcall(self, mode, opcode):
        target = self.fetch8()
        self.push16(self.pc)
        self.pc = UPPER_PAGE | target

    def op_tcall(self, mode, opcode):
        vector = CALL_TABLE_TOP - (table.call_index(opcode) << 1)
        self.push16(self.pc)
        self.pc = self.read16(vector)

    def op_brk(self, mode, opcode):
        self.push16(self.pc)
        self.push8(self.psw)
        self.b = True
        self.i = False
        self.pc = self.read16(BREAK_VECTOR)

    def op_ret(self, mode, opcode):
        self.pc = self.pull16()

    def op_reti(self, mode, opcode):
        self.psw = self.pull8()
        self.pc = self.pull16()

    def op_push(self, mode, opcode):
        self.push8({"a": self.a, "x": self.x, "y": self.y, "p": self.psw}[mode])

    def op_pop(self, mode, opcode):
        value = self.pull8()
        if mode == "a":
            self.a = value
        elif mode == "x":
            self.x = value
        elif mode == "y":
            self.y = value
        else:
            self.psw = value

    def op_set1(self, mode, opcode):
        address = self.direct(self.fetch8())
        self.write8(address, self.read8(address) | (1 << table.bit_index(opcode)))

    def op_clr1(self, mode, opcode):
        address = self.direct(self.fetch8())
        self.write8(address, self.read8(address) & ~(1 << table.bit_index(opcode)))

    def op_tset(self, mode, opcode):
        address = self.fetch16()
        held = self.read8(address)
        self.write8(address, held | self.a)
        self.set_nz(self.a - held)

    def op_tclr(self, mode, opcode):
        address = self.fetch16()
        held = self.read8(address)
        self.write8(address, held & ~self.a)
        self.set_nz(self.a - held)

    def _addressed_bit(self):
        """The address and bit a memory bit instruction names, packed in one word."""
        packed = self.fetch16()
        return packed & 0x1FFF, packed >> 13

    def op_and1(self, mode, opcode):
        address, bit = self._addressed_bit()
        held = bool(self.read8(address) & (1 << bit))
        self.c = self.c and (not held if mode == "c_notmembit" else held)

    def op_or1(self, mode, opcode):
        address, bit = self._addressed_bit()
        held = bool(self.read8(address) & (1 << bit))
        self.c = self.c or (not held if mode == "c_notmembit" else held)

    def op_eor1(self, mode, opcode):
        address, bit = self._addressed_bit()
        self.c = self.c != bool(self.read8(address) & (1 << bit))

    def op_not1(self, mode, opcode):
        address, bit = self._addressed_bit()
        self.write8(address, self.read8(address) ^ (1 << bit))

    def op_mov1(self, mode, opcode):
        address, bit = self._addressed_bit()
        if mode == "membit_c":
            held = self.read8(address)
            self.write8(address, (held | (1 << bit)) if self.c else (held & ~(1 << bit)))
            return
        self.c = bool(self.read8(address) & (1 << bit))

    def op_clrc(self, mode, opcode):
        self.c = False

    def op_setc(self, mode, opcode):
        self.c = True

    def op_notc(self, mode, opcode):
        self.c = not self.c

    def op_clrv(self, mode, opcode):
        self.v = False
        self.h = False

    def op_clrp(self, mode, opcode):
        self.p = False

    def op_setp(self, mode, opcode):
        self.p = True

    def op_ei(self, mode, opcode):
        self.i = True

    def op_di(self, mode, opcode):
        self.i = False

    def op_nop(self, mode, opcode):
        return

    def op_sleep(self, mode, opcode):
        self.stopped = True

    def op_stop(self, mode, opcode):
        self.stopped = True

import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spc700 import core
from spc700.errors import RunLimit
from spc700.memory import Memory


def machine(
    code: Sequence[int], base: int = 0x0200, fill: int = 0, **registers: int
) -> tuple[Any, Memory]:
    """A part in a state this file chose, rather than the one a rail leaves.

    Construction scrambles every register, because that is what powering on
    does. These are tests of what an instruction does, so they start from a
    defined state and say so here: the flags are cleared, which matters most for
    `P`, since a scrambled direct-page bit sends every direct access to the wrong
    page and turns an instruction test into a test of where it landed.

    A test that wants a flag set passes it, and the power-on state itself is
    tested where it belongs rather than relied on here.
    """
    memory = Memory(fill=fill)
    for offset, byte in enumerate(code):
        memory.write8(base + offset, byte)
    cpu = core.Cpu(memory)
    cpu.psw = 0x00
    cpu.a = cpu.x = cpu.y = 0x00
    cpu.pc = base
    cpu.sp = 0xEF
    for name, value in registers.items():
        setattr(cpu, name, value)
    return cpu, memory


def run(code: Sequence[int], steps: int = 1, **registers: int) -> tuple[Any, Memory]:
    cpu, memory = machine(code, **registers)
    for _ in range(steps):
        cpu.step()
    return cpu, memory


class ResetTest(unittest.TestCase):
    def test_the_program_counter_comes_from_the_reset_vector(self) -> None:
        memory = Memory(fill=0)
        memory.write8(core.RESET_VECTOR, 0x00)
        memory.write8(core.RESET_VECTOR + 1, 0xFF)
        cpu = core.Cpu(memory)

        cpu.reset()

        self.assertEqual(cpu.pc, 0xFF00)

    def test_but_only_once_a_caller_drives_the_pin(self) -> None:
        """Power on and reset are two events, and construction is the first.

        A part that arrived reset would hide one that costs cycles and drives
        pins, and no board offers one.
        """
        memory = Memory(fill=0)
        memory.write8(core.RESET_VECTOR, 0x00)
        memory.write8(core.RESET_VECTOR + 1, 0xFF)

        cpu = core.Cpu(memory)

        self.assertNotEqual(cpu.pc, 0xFF00)

    def test_and_the_program_counter_comes_up_holding_something(self) -> None:
        """Rubbish from a rubbish address, which is what the silicon does."""
        held = {core.Cpu(Memory(fill=0), seed=one).pc for one in range(8)}

        self.assertGreater(len(held), 1)

    def test_the_registers_are_not_assumed_clear(self) -> None:
        cpu = core.Cpu(Memory(fill=0))

        self.assertNotEqual((cpu.a, cpu.x, cpu.y), (0, 0, 0))

    def test_a_reset_repeats_for_one_seed(self) -> None:
        one = core.Cpu(Memory(fill=0), seed=11)
        other = core.Cpu(Memory(fill=0), seed=11)

        self.assertEqual((one.a, one.x, one.y, one.sp), (other.a, other.x, other.y, other.sp))

    def test_a_different_seed_gives_a_different_machine(self) -> None:
        one = core.Cpu(Memory(fill=0), seed=1)
        other = core.Cpu(Memory(fill=0), seed=2)

        self.assertNotEqual((one.a, one.x, one.y), (other.a, other.x, other.y))


class StatusTest(unittest.TestCase):
    def test_every_flag_survives_a_round_trip(self) -> None:
        cpu, _ = machine([0x00])

        cpu.psw = 0xFF

        self.assertEqual(cpu.psw, 0xFF)

    def test_no_flag_set_reads_back_as_zero(self) -> None:
        cpu, _ = machine([0x00])

        cpu.psw = 0x00

        self.assertEqual(cpu.psw, 0x00)

    def test_the_page_flag_moves_the_direct_page(self) -> None:
        cpu, _ = machine([0x00])

        cpu.psw = core.FLAG_P

        self.assertEqual(cpu.direct_page, 0x0100)

    def test_the_direct_page_is_the_bottom_page_without_it(self) -> None:
        cpu, _ = machine([0x00])

        cpu.psw = 0x00

        self.assertEqual(cpu.direct_page, 0x0000)


class MoveTest(unittest.TestCase):
    def test_an_immediate_load_sets_the_accumulator(self) -> None:
        cpu, _ = run([0xE8, 0x42])

        self.assertEqual(cpu.a, 0x42)

    def test_a_load_sets_the_negative_flag(self) -> None:
        cpu, _ = run([0xE8, 0x80])

        self.assertTrue(cpu.n)

    def test_a_load_sets_the_zero_flag(self) -> None:
        cpu, _ = run([0xE8, 0x00])

        self.assertTrue(cpu.z)

    def test_a_store_leaves_the_flags_alone(self) -> None:
        cpu, memory = run([0xC4, 0x10], a=0x00)

        self.assertEqual(memory.read8(0x0010), 0x00)
        self.assertFalse(cpu.z)

    def test_a_direct_page_store_follows_the_page_flag(self) -> None:
        _, memory = run([0xC4, 0x10], a=0x5A, psw=core.FLAG_P)

        self.assertEqual(memory.read8(0x0110), 0x5A)

    def test_an_indirect_store_uses_the_index_register(self) -> None:
        _, memory = run([0xC6], a=0x77, x=0x30)

        self.assertEqual(memory.read8(0x0030), 0x77)

    def test_a_post_increment_store_advances_the_index(self) -> None:
        cpu, memory = run([0xAF], a=0x99, x=0x40)

        self.assertEqual(memory.read8(0x0040), 0x99)
        self.assertEqual(cpu.x, 0x41)

    def test_a_post_increment_load_advances_the_index(self) -> None:
        cpu, memory = machine([0xBF], x=0x40)
        memory.write8(0x0040, 0x3C)

        cpu.step()

        self.assertEqual(cpu.a, 0x3C)
        self.assertEqual(cpu.x, 0x41)

    def test_a_direct_to_direct_move_leaves_the_flags_alone(self) -> None:
        cpu, memory = machine([0xFA, 0x10, 0x20])
        memory.write8(0x0010, 0x00)

        cpu.step()

        self.assertEqual(memory.read8(0x0020), 0x00)
        self.assertFalse(cpu.z)

    def test_transferring_the_stack_pointer_into_the_index_sets_flags(self) -> None:
        cpu, _ = run([0x9D], sp=0x00)

        self.assertTrue(cpu.z)

    def test_transferring_the_index_into_the_stack_pointer_leaves_flags(self) -> None:
        cpu, _ = run([0xBD], x=0x00)

        self.assertEqual(cpu.sp, 0x00)
        self.assertFalse(cpu.z)


class ArithmeticTest(unittest.TestCase):
    def test_addition_carries_out_of_eight_bits(self) -> None:
        cpu, _ = run([0x60, 0x88, 0x01], steps=2, a=0xFF)

        self.assertEqual(cpu.a, 0x00)
        self.assertTrue(cpu.c)

    def test_addition_brings_the_carry_in(self) -> None:
        cpu, _ = run([0x80, 0x88, 0x01], steps=2, a=0x00)

        self.assertEqual(cpu.a, 0x02)

    def test_addition_sets_overflow_when_the_sign_is_wrong(self) -> None:
        cpu, _ = run([0x60, 0x88, 0x01], steps=2, a=0x7F)

        self.assertTrue(cpu.v)

    def test_addition_sets_the_half_carry_at_the_nibble(self) -> None:
        cpu, _ = run([0x60, 0x88, 0x01], steps=2, a=0x0F)

        self.assertTrue(cpu.h)

    def test_subtraction_borrows_when_the_carry_is_clear(self) -> None:
        cpu, _ = run([0x60, 0xA8, 0x01], steps=2, a=0x10)

        self.assertEqual(cpu.a, 0x0E)

    def test_subtraction_below_zero_clears_the_carry(self) -> None:
        cpu, _ = run([0x80, 0xA8, 0x02], steps=2, a=0x01)

        self.assertFalse(cpu.c)

    def test_a_comparison_leaves_the_accumulator_alone(self) -> None:
        cpu, _ = run([0x68, 0x10], a=0x20)

        self.assertEqual(cpu.a, 0x20)
        self.assertTrue(cpu.c)

    def test_a_comparison_of_equals_sets_zero(self) -> None:
        cpu, _ = run([0x68, 0x20], a=0x20)

        self.assertTrue(cpu.z)

    def test_a_bitwise_and_keeps_the_common_bits(self) -> None:
        cpu, _ = run([0x28, 0x0F], a=0x3C)

        self.assertEqual(cpu.a, 0x0C)

    def test_a_bitwise_or_keeps_every_bit(self) -> None:
        cpu, _ = run([0x08, 0x0F], a=0x30)

        self.assertEqual(cpu.a, 0x3F)

    def test_an_exclusive_or_drops_the_common_bits(self) -> None:
        cpu, _ = run([0x48, 0x0F], a=0x3C)

        self.assertEqual(cpu.a, 0x33)

    def test_incrementing_wraps_at_the_top(self) -> None:
        cpu, _ = run([0xBC], a=0xFF)

        self.assertEqual(cpu.a, 0x00)
        self.assertTrue(cpu.z)

    def test_decrementing_wraps_at_the_bottom(self) -> None:
        cpu, _ = run([0x9C], a=0x00)

        self.assertEqual(cpu.a, 0xFF)
        self.assertTrue(cpu.n)

    def test_a_nibble_exchange_swaps_the_halves(self) -> None:
        cpu, _ = run([0x9F], a=0x3C)

        self.assertEqual(cpu.a, 0xC3)


class ShiftTest(unittest.TestCase):
    def test_a_shift_left_moves_the_top_bit_into_the_carry(self) -> None:
        cpu, _ = run([0x1C], a=0x81)

        self.assertEqual(cpu.a, 0x02)
        self.assertTrue(cpu.c)

    def test_a_shift_right_moves_the_bottom_bit_into_the_carry(self) -> None:
        cpu, _ = run([0x5C], a=0x03)

        self.assertEqual(cpu.a, 0x01)
        self.assertTrue(cpu.c)

    def test_a_rotate_left_brings_the_carry_in(self) -> None:
        cpu, _ = run([0x80, 0x3C], steps=2, a=0x00)

        self.assertEqual(cpu.a, 0x01)

    def test_a_rotate_right_brings_the_carry_into_the_top(self) -> None:
        cpu, _ = run([0x80, 0x7C], steps=2, a=0x00)

        self.assertEqual(cpu.a, 0x80)

    def test_a_shift_in_memory_writes_the_result_back(self) -> None:
        cpu, memory = machine([0x0B, 0x10])
        memory.write8(0x0010, 0x40)

        cpu.step()

        self.assertEqual(memory.read8(0x0010), 0x80)


class WordTest(unittest.TestCase):
    def test_a_word_load_takes_two_bytes(self) -> None:
        cpu, memory = machine([0xBA, 0x10])
        memory.write8(0x0010, 0x34)
        memory.write8(0x0011, 0x12)

        cpu.step()

        self.assertEqual((cpu.y << 8) | cpu.a, 0x1234)

    def test_a_word_store_writes_two_bytes(self) -> None:
        _, memory = run([0xDA, 0x10], a=0x34, y=0x12)

        self.assertEqual(memory.read8(0x0010), 0x34)
        self.assertEqual(memory.read8(0x0011), 0x12)

    def test_a_word_addition_carries_between_the_bytes(self) -> None:
        cpu, memory = machine([0x7A, 0x10], a=0xFF, y=0x00)
        memory.write8(0x0010, 0x01)
        memory.write8(0x0011, 0x00)

        cpu.step()

        self.assertEqual((cpu.y << 8) | cpu.a, 0x0100)

    def test_a_word_subtraction_borrows_between_the_bytes(self) -> None:
        cpu, memory = machine([0x9A, 0x10], a=0x00, y=0x01)
        memory.write8(0x0010, 0x01)
        memory.write8(0x0011, 0x00)

        cpu.step()

        self.assertEqual((cpu.y << 8) | cpu.a, 0x00FF)

    def test_a_word_comparison_leaves_the_pair_alone(self) -> None:
        cpu, memory = machine([0x5A, 0x10], a=0x34, y=0x12)
        memory.write8(0x0010, 0x34)
        memory.write8(0x0011, 0x12)

        cpu.step()

        self.assertEqual((cpu.y << 8) | cpu.a, 0x1234)
        self.assertTrue(cpu.z)

    def test_a_word_increment_carries_into_the_high_byte(self) -> None:
        cpu, memory = machine([0x3A, 0x10])
        memory.write8(0x0010, 0xFF)
        memory.write8(0x0011, 0x00)

        cpu.step()

        self.assertEqual(memory.read8(0x0010), 0x00)
        self.assertEqual(memory.read8(0x0011), 0x01)

    def test_a_word_decrement_borrows_from_the_high_byte(self) -> None:
        cpu, memory = machine([0x1A, 0x10])
        memory.write8(0x0010, 0x00)
        memory.write8(0x0011, 0x01)

        cpu.step()

        self.assertEqual(memory.read8(0x0010), 0xFF)
        self.assertEqual(memory.read8(0x0011), 0x00)


class MultiplyDivideTest(unittest.TestCase):
    def test_a_multiply_fills_the_register_pair(self) -> None:
        cpu, _ = run([0xCF], y=0x10, a=0x10)

        self.assertEqual((cpu.y << 8) | cpu.a, 0x0100)

    def test_a_multiply_sets_flags_from_the_high_byte(self) -> None:
        cpu, _ = run([0xCF], y=0x00, a=0x00)

        self.assertTrue(cpu.z)

    def test_a_divide_gives_a_quotient_and_a_remainder(self) -> None:
        cpu, _ = run([0x9E], y=0x00, a=0x0A, x=0x03)

        self.assertEqual(cpu.a, 0x03)
        self.assertEqual(cpu.y, 0x01)

    def test_a_divide_by_zero_does_not_raise(self) -> None:
        cpu, _ = run([0x9E], y=0x01, a=0x00, x=0x00)

        self.assertIsInstance(cpu.a, int)


class DecimalTest(unittest.TestCase):
    def test_a_decimal_adjust_after_add_carries_at_nine(self) -> None:
        cpu, _ = run([0x60, 0x88, 0x01, 0xDF], steps=3, a=0x09)

        self.assertEqual(cpu.a, 0x10)

    def test_a_decimal_adjust_after_subtract_borrows_at_zero(self) -> None:
        cpu, _ = run([0x80, 0xA8, 0x01, 0xBE], steps=3, a=0x10)

        self.assertEqual(cpu.a, 0x09)

    def test_a_decimal_adjust_above_ninety_nine_adds_sixty_and_carries(self) -> None:
        cpu, _ = run([0xDF], a=0xAA, psw=0x00)

        self.assertEqual(cpu.a, 0x10)
        self.assertTrue(cpu.c)

    def test_a_decimal_adjust_with_the_carry_already_set_adds_sixty(self) -> None:
        cpu, _ = run([0xDF], a=0x11, psw=core.FLAG_C)

        self.assertEqual(cpu.a, 0x71)

    def test_a_decimal_adjust_reads_the_accumulator_it_just_changed(self) -> None:
        cpu, _ = run([0xDF], a=0x9A, psw=0x00)

        self.assertEqual(cpu.a, 0x00)
        self.assertTrue(cpu.c)

    def test_a_decimal_adjust_leaves_a_valid_pair_alone(self) -> None:
        cpu, _ = run([0xDF], a=0x42, psw=0x00)

        self.assertEqual(cpu.a, 0x42)

    def test_a_decimal_subtract_above_ninety_nine_takes_sixty_off(self) -> None:
        cpu, _ = run([0xBE], a=0xAA, psw=core.FLAG_C | core.FLAG_H)

        self.assertEqual(cpu.a, 0x44)
        self.assertFalse(cpu.c)

    def test_a_decimal_subtract_with_the_half_carry_set_leaves_the_nibble(self) -> None:
        cpu, _ = run([0xBE], a=0x42, psw=core.FLAG_C | core.FLAG_H)

        self.assertEqual(cpu.a, 0x42)

    def test_a_decimal_subtract_without_the_half_carry_takes_six_off(self) -> None:
        cpu, _ = run([0xBE], a=0x42, psw=core.FLAG_C)

        self.assertEqual(cpu.a, 0x3C)


class IndexComparisonTest(unittest.TestCase):
    def test_an_index_comparison_leaves_the_index_alone(self) -> None:
        cpu, _ = run([0xC8, 0x10], x=0x20)

        self.assertEqual(cpu.x, 0x20)
        self.assertTrue(cpu.c)

    def test_an_index_comparison_of_equals_sets_zero(self) -> None:
        cpu, _ = run([0xC8, 0x20], x=0x20)

        self.assertTrue(cpu.z)

    def test_the_other_index_compares_the_same_way(self) -> None:
        cpu, _ = run([0xAD, 0x20], y=0x20)

        self.assertTrue(cpu.z)
        self.assertEqual(cpu.y, 0x20)

    def test_an_index_comparison_below_clears_the_carry(self) -> None:
        cpu, _ = run([0xAD, 0x30], y=0x20)

        self.assertFalse(cpu.c)


class AddressingGuardTest(unittest.TestCase):
    def test_a_mode_that_names_no_address_is_refused(self) -> None:
        cpu, _ = machine([0x00])

        with self.assertRaises(KeyError):
            cpu.operand_address("implied", 0x00)


class BranchTest(unittest.TestCase):
    def test_an_unconditional_branch_moves_the_program_counter(self) -> None:
        cpu, _ = run([0x2F, 0x02])

        self.assertEqual(cpu.pc, 0x0204)

    def test_a_branch_taken_on_zero_moves(self) -> None:
        cpu, _ = run([0xE8, 0x00, 0xF0, 0x02], steps=2)

        self.assertEqual(cpu.pc, 0x0206)

    def test_a_branch_not_taken_falls_through(self) -> None:
        cpu, _ = run([0xE8, 0x01, 0xF0, 0x02], steps=2)

        self.assertEqual(cpu.pc, 0x0204)

    def test_a_branch_on_bit_set_is_taken(self) -> None:
        cpu, memory = machine([0x03, 0x10, 0x02])
        memory.write8(0x0010, 0x01)

        cpu.step()

        self.assertEqual(cpu.pc, 0x0205)

    def test_a_branch_on_bit_clear_is_taken(self) -> None:
        cpu, memory = machine([0x13, 0x10, 0x02])
        memory.write8(0x0010, 0x00)

        cpu.step()

        self.assertEqual(cpu.pc, 0x0205)

    def test_a_compare_and_branch_is_taken_when_they_differ(self) -> None:
        cpu, memory = machine([0x2E, 0x10, 0x02], a=0x01)
        memory.write8(0x0010, 0x02)

        cpu.step()

        self.assertEqual(cpu.pc, 0x0205)

    def test_a_decrement_and_branch_is_taken_until_zero(self) -> None:
        cpu, memory = machine([0x6E, 0x10, 0x02])
        memory.write8(0x0010, 0x02)

        cpu.step()

        self.assertEqual(memory.read8(0x0010), 0x01)
        self.assertEqual(cpu.pc, 0x0205)

    def test_a_decrement_and_branch_on_the_index_stops_at_zero(self) -> None:
        cpu, _ = run([0xFE, 0x02], y=0x01)

        self.assertEqual(cpu.y, 0x00)
        self.assertEqual(cpu.pc, 0x0202)


class ControlTest(unittest.TestCase):
    def test_a_jump_moves_the_program_counter(self) -> None:
        cpu, _ = run([0x5F, 0x00, 0x03])

        self.assertEqual(cpu.pc, 0x0300)

    def test_an_indexed_indirect_jump_reads_its_target(self) -> None:
        cpu, memory = machine([0x1F, 0x00, 0x03], x=0x02)
        memory.write8(0x0302, 0x00)
        memory.write8(0x0303, 0x04)

        cpu.step()

        self.assertEqual(cpu.pc, 0x0400)

    def test_a_call_pushes_the_return_address(self) -> None:
        cpu, memory = run([0x3F, 0x00, 0x03])

        self.assertEqual(cpu.pc, 0x0300)
        self.assertEqual(memory.read8(0x01EF), 0x02)
        self.assertEqual(memory.read8(0x01EE), 0x03)

    def test_a_return_takes_the_address_back_off(self) -> None:
        cpu, _ = run([0x3F, 0x05, 0x02, 0x00, 0x00, 0x6F], steps=2)

        self.assertEqual(cpu.pc, 0x0203)

    def test_a_page_call_jumps_into_the_top_page(self) -> None:
        cpu, _ = run([0x4F, 0x40])

        self.assertEqual(cpu.pc, 0xFF40)

    def test_a_table_call_reads_its_vector(self) -> None:
        cpu, memory = machine([0x01])
        memory.write8(0xFFDE, 0x00)
        memory.write8(0xFFDF, 0x05)

        cpu.step()

        self.assertEqual(cpu.pc, 0x0500)

    def test_a_break_takes_its_vector_and_sets_the_break_flag(self) -> None:
        cpu, memory = machine([0x0F])
        memory.write8(core.BREAK_VECTOR, 0x00)
        memory.write8(core.BREAK_VECTOR + 1, 0x06)

        cpu.step()

        self.assertEqual(cpu.pc, 0x0600)
        self.assertTrue(cpu.b)
        self.assertFalse(cpu.i)

    def test_a_return_from_interrupt_restores_the_status(self) -> None:
        cpu, memory = machine([0x7F])
        memory.write8(0x01F0, 0xAA)
        memory.write8(0x01F1, 0x34)
        memory.write8(0x01F2, 0x12)
        cpu.sp = 0xEF

        cpu.step()

        self.assertEqual(cpu.psw, 0xAA)
        self.assertEqual(cpu.pc, 0x1234)


class StackTest(unittest.TestCase):
    def test_a_push_lowers_the_stack_pointer(self) -> None:
        cpu, memory = run([0x2D], a=0x5A)

        self.assertEqual(cpu.sp, 0xEE)
        self.assertEqual(memory.read8(0x01EF), 0x5A)

    def test_a_pull_raises_the_stack_pointer(self) -> None:
        cpu, memory = machine([0xAE])
        memory.write8(0x01F0, 0x3C)

        cpu.step()

        self.assertEqual(cpu.a, 0x3C)
        self.assertEqual(cpu.sp, 0xF0)

    def test_a_pushed_value_comes_back(self) -> None:
        cpu, _ = run([0x2D, 0xE8, 0x00, 0xAE], steps=3, a=0x77)

        self.assertEqual(cpu.a, 0x77)

    def test_the_stack_pointer_wraps_inside_its_page(self) -> None:
        cpu, memory = run([0x2D], sp=0x00, a=0x11)

        self.assertEqual(cpu.sp, 0xFF)
        self.assertEqual(memory.read8(0x0100), 0x11)

    def test_the_status_register_survives_a_push_and_pull(self) -> None:
        cpu, _ = run([0x0D, 0x8E], steps=2, psw=0xC5)

        self.assertEqual(cpu.psw, 0xC5)


class BitTest(unittest.TestCase):
    def test_setting_a_bit_leaves_the_others_alone(self) -> None:
        cpu, memory = machine([0x02, 0x10])
        memory.write8(0x0010, 0x00)

        cpu.step()

        self.assertEqual(memory.read8(0x0010), 0x01)

    def test_setting_the_top_bit_uses_the_opcode_index(self) -> None:
        cpu, memory = machine([0xE2, 0x10])
        memory.write8(0x0010, 0x00)

        cpu.step()

        self.assertEqual(memory.read8(0x0010), 0x80)

    def test_clearing_a_bit_leaves_the_others_alone(self) -> None:
        cpu, memory = machine([0x12, 0x10])
        memory.write8(0x0010, 0xFF)

        cpu.step()

        self.assertEqual(memory.read8(0x0010), 0xFE)

    def test_a_test_and_set_leaves_the_bits_of_the_accumulator(self) -> None:
        cpu, memory = machine([0x0E, 0x00, 0x03], a=0x0F)
        memory.write8(0x0300, 0xF0)

        cpu.step()

        self.assertEqual(memory.read8(0x0300), 0xFF)

    def test_a_test_and_clear_removes_the_bits_of_the_accumulator(self) -> None:
        cpu, memory = machine([0x4E, 0x00, 0x03], a=0x0F)
        memory.write8(0x0300, 0xFF)

        cpu.step()

        self.assertEqual(memory.read8(0x0300), 0xF0)

    def test_a_carry_load_takes_the_addressed_bit(self) -> None:
        cpu, memory = machine([0xAA, 0x00, 0xE0])
        memory.write8(0x0000, 0x80)

        cpu.step()

        self.assertTrue(cpu.c)

    def test_a_carry_store_writes_the_addressed_bit(self) -> None:
        cpu, memory = machine([0xCA, 0x00, 0xE0], psw=core.FLAG_C)
        memory.write8(0x0000, 0x00)

        cpu.step()

        self.assertEqual(memory.read8(0x0000), 0x80)

    def test_an_inverted_carry_load_takes_the_complement(self) -> None:
        cpu, memory = machine([0x6A, 0x00, 0xE0], psw=core.FLAG_C)
        memory.write8(0x0000, 0x80)

        cpu.step()

        self.assertFalse(cpu.c)

    def test_a_bit_complement_flips_the_addressed_bit(self) -> None:
        cpu, memory = machine([0xEA, 0x00, 0xE0])
        memory.write8(0x0000, 0x80)

        cpu.step()

        self.assertEqual(memory.read8(0x0000), 0x00)


class FlagTest(unittest.TestCase):
    def test_the_carry_can_be_set_and_cleared(self) -> None:
        cpu, _ = run([0x80, 0x60], steps=2)

        self.assertFalse(cpu.c)

    def test_the_carry_can_be_complemented(self) -> None:
        cpu, _ = run([0xED], psw=0x00)

        self.assertTrue(cpu.c)

    def test_the_overflow_flag_clears_the_half_carry_with_it(self) -> None:
        cpu, _ = run([0xE0], psw=core.FLAG_V | core.FLAG_H)

        self.assertFalse(cpu.v)
        self.assertFalse(cpu.h)

    def test_the_page_flag_can_be_set_and_cleared(self) -> None:
        cpu, _ = run([0x40, 0x20], steps=2)

        self.assertEqual(cpu.direct_page, 0x0000)

    def test_the_interrupt_flag_can_be_set_and_cleared(self) -> None:
        cpu, _ = run([0xA0, 0xC0], steps=2)

        self.assertFalse(cpu.i)


class HaltTest(unittest.TestCase):
    def test_a_sleep_stops_the_processor(self) -> None:
        cpu, _ = run([0xEF])

        self.assertTrue(cpu.stopped)

    def test_a_stop_stops_the_processor(self) -> None:
        cpu, _ = run([0xFF])

        self.assertTrue(cpu.stopped)

    def test_a_stopped_processor_stays_where_it_is(self) -> None:
        cpu, _ = run([0xFF, 0x00], steps=2)

        self.assertEqual(cpu.pc, 0x0201)

    def test_running_until_a_condition_returns_the_machine(self) -> None:
        cpu, _ = machine([0x00])

        self.assertIs(cpu.run_until(lambda found: found.steps > 0), cpu)

    def test_a_run_that_never_settles_is_stopped(self) -> None:
        cpu, _ = machine([0x2F, 0xFE])
        cpu.step_limit = 100

        with self.assertRaises(RunLimit):
            cpu.run_until(lambda found: False)


class EveryOpcodeTest(unittest.TestCase):
    def test_every_opcode_executes(self) -> None:
        for opcode in range(256):
            memory = Memory(seed=opcode)
            cpu = core.Cpu(memory)
            cpu.pc = 0x0200
            memory.write8(0x0200, opcode)
            with self.subTest(opcode=f"${opcode:02X}"):
                cpu.step()
                self.assertEqual(cpu.steps, 1)

    def test_every_opcode_has_an_implementation_behind_it(self) -> None:
        missing = [
            f"${opcode:02X} {mnemonic}"
            for opcode, (mnemonic, _, _) in enumerate(core.OPCODES)
            if not hasattr(core.Cpu, f"op_{mnemonic}")
        ]

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()

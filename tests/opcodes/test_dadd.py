"""Tests for DADD: 64-bit addition of two double-words held as (lo, hi) cell pairs.

Operand layout after the four PUSHes (top-down): Bhi, Blo, Ahi, Alo.
After DADD the stack holds the 64-bit result as nos = Rlo, tos = Rhi.
"""

from app.isa.flag import Flag
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.simulation.control_unit import CUSnapshot

from tests.shared import run_simulation

MASK64 = 0xFFFFFFFFFFFFFFFF


def run_dadd(a: int, b: int) -> CUSnapshot:
    alo, ahi = a & 0xFFFFFFFF, (a >> 32) & 0xFFFFFFFF
    blo, bhi = b & 0xFFFFFFFF, (b >> 32) & 0xFFFFFFFF
    instructions = [
        Instruction(Opcode.PUSH, alo),
        Instruction(Opcode.PUSH, ahi),
        Instruction(Opcode.PUSH, blo),
        Instruction(Opcode.PUSH, bhi),
        Instruction(Opcode.DADD),
        Instruction(Opcode.HALT),
    ]
    return run_simulation(instructions, {})


def result64(snapshot: CUSnapshot) -> int:
    return (snapshot.tos << 32) | snapshot.nos


def test_dadd_basic():
    # 1 + 2 = 3, fits in the low word
    snapshot = run_dadd(1, 2)
    assert result64(snapshot) == 3
    assert snapshot.tos == 0x00000000
    assert snapshot.nos == 0x00000003
    assert snapshot.flags == Flag(0)


def test_dadd_carry_between_words():
    # 0x1_FFFFFFFF + 1 = 0x2_00000000: carry propagates from low to high word
    snapshot = run_dadd(0x00000001_FFFFFFFF, 1)
    assert result64(snapshot) == 0x00000002_00000000
    assert snapshot.tos == 0x00000002
    assert snapshot.nos == 0x00000000
    assert snapshot.flags == Flag(0)


def test_dadd_low_word_carry_only():
    # 0xFFFFFFFF + 1 = 0x1_00000000: only the low word overflows
    snapshot = run_dadd(0x00000000_FFFFFFFF, 1)
    assert result64(snapshot) == 0x00000001_00000000
    assert snapshot.flags == Flag(0)


def test_dadd_high_words_add():
    # high words add without touching the low word
    snapshot = run_dadd(0x00000001_00000000, 0x00000002_00000000)
    assert result64(snapshot) == 0x00000003_00000000
    assert snapshot.flags == Flag(0)


def test_dadd_flag_z_combined_high_zero():
    # Regression: high word is zero but the 64-bit result is non-zero → Z must NOT be set
    snapshot = run_dadd(2, 3)
    assert result64(snapshot) == 5
    assert snapshot.tos == 0x00000000
    assert snapshot.nos == 0x00000005
    assert snapshot.flags == Flag(0)


def test_dadd_flag_z_c_full_wrap():
    # 0xFFFFFFFFFFFFFFFF + 1 = 0 (mod 2^64) → Z and carry out of bit 63
    snapshot = run_dadd(MASK64, 1)
    assert result64(snapshot) == 0
    assert snapshot.flags == Flag.Z | Flag.C


def test_dadd_flag_c_without_zero():
    # 0xFFFFFFFFFFFFFFFF + 2 = 1 (mod 2^64) → carry out, result non-zero
    snapshot = run_dadd(MASK64, 2)
    assert result64(snapshot) == 1
    assert snapshot.flags == Flag.C


def test_dadd_flag_n():
    # negative + small positive stays negative, no overflow → N only
    snapshot = run_dadd(0x80000000_00000000, 1)
    assert result64(snapshot) == 0x80000000_00000001
    assert snapshot.tos == 0x80000000
    assert snapshot.nos == 0x00000001
    assert snapshot.flags == Flag.N


def test_dadd_flag_n_v_signed_overflow():
    # 0x7FFFFFFFFFFFFFFF + 1 = 0x8000000000000000: positive+positive → negative → N V
    snapshot = run_dadd(0x7FFFFFFF_FFFFFFFF, 1)
    assert result64(snapshot) == 0x80000000_00000000
    assert snapshot.tos == 0x80000000
    assert snapshot.nos == 0x00000000
    assert snapshot.flags == Flag.N | Flag.V


def test_dadd_high_word_carry_in_overflow():
    # Carry into a high word that is 0xFFFFFFFF must still produce a carry out of bit 63.
    # 0xFFFFFFFF_FFFFFFFF + 0x00000000_00000001 exercises Ahi=0xFFFFFFFF + carry.
    snapshot = run_dadd(0xFFFFFFFF_FFFFFFFF, 0x00000000_00000001)
    assert result64(snapshot) == 0
    assert snapshot.flags == Flag.Z | Flag.C


def test_dadd_two_negatives():
    # 0xFFFFFFFF00000000 + 0xFFFFFFFF00000000 = 0xFFFFFFFE00000000 (mod 2^64) → N C
    snapshot = run_dadd(0xFFFFFFFF_00000000, 0xFFFFFFFF_00000000)
    assert result64(snapshot) == 0xFFFFFFFE_00000000
    assert snapshot.flags == Flag.N | Flag.C

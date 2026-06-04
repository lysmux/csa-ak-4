"""Tests for the 64-bit double-word ops DSUB, DMUL, DDIV (operands are (lo, hi) cell pairs).

Operand layout after the four PUSHes (top-down): Bhi, Blo, Ahi, Alo. The op computes
A <op> B and leaves the 64-bit result as nos = Rlo, tos = Rhi.
"""

from app.isa.flag import Flag
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.simulation.control_unit import CUSnapshot

from tests.shared import run_simulation

MASK64 = 0xFFFFFFFFFFFFFFFF
SIGN64 = 1 << 63


def signed64(v: int) -> int:
    v &= MASK64
    return v - (1 << 64) if v & SIGN64 else v


def run_dword(op: Opcode, a: int, b: int) -> CUSnapshot:
    alo, ahi = a & 0xFFFFFFFF, (a >> 32) & 0xFFFFFFFF
    blo, bhi = b & 0xFFFFFFFF, (b >> 32) & 0xFFFFFFFF
    instructions = [
        Instruction(Opcode.PUSH, alo),
        Instruction(Opcode.PUSH, ahi),
        Instruction(Opcode.PUSH, blo),
        Instruction(Opcode.PUSH, bhi),
        Instruction(op),
        Instruction(Opcode.HALT),
    ]
    return run_simulation(instructions, {})


def result64(snapshot: CUSnapshot) -> int:
    return (snapshot.tos << 32) | snapshot.nos


def flagstr(flags: Flag) -> str:
    names = [("N", Flag.N), ("Z", Flag.Z), ("V", Flag.V), ("C", Flag.C)]
    return "".join(n for n, f in names if flags.has(f)) or "-"


def make_flags(*, n: bool = False, z: bool = False, v: bool = False, c: bool = False) -> str:
    return "".join(name for name, on in [("N", n), ("Z", z), ("V", v), ("C", c)] if on) or "-"


# --- DSUB -------------------------------------------------------------------


def test_dsub_basic():
    snapshot = run_dword(Opcode.DSUB, 5, 3)
    assert result64(snapshot) == 2
    assert flagstr(snapshot.flags) == make_flags()


def test_dsub_borrow_between_words():
    # 0x0000000100000000 - 1 = 0x00000000FFFFFFFF: borrow propagates into the high word
    snapshot = run_dword(Opcode.DSUB, 0x00000001_00000000, 1)
    assert result64(snapshot) == 0x00000000_FFFFFFFF
    assert flagstr(snapshot.flags) == make_flags()


def test_dsub_zero():
    snapshot = run_dword(Opcode.DSUB, 0x1234_5678_9ABC, 0x1234_5678_9ABC)
    assert result64(snapshot) == 0
    assert flagstr(snapshot.flags) == make_flags(z=True)


def test_dsub_borrow_out():
    # 0 - 1 = 0xFFFFFFFFFFFFFFFF: unsigned borrow out (C), result negative (N)
    snapshot = run_dword(Opcode.DSUB, 0, 1)
    assert result64(snapshot) == MASK64
    assert flagstr(snapshot.flags) == make_flags(n=True, c=True)


def test_dsub_signed_overflow():
    # MIN64 - 1 -> overflow: 0x8000000000000000 - 1 = 0x7FFFFFFFFFFFFFFF (positive) -> V
    snapshot = run_dword(Opcode.DSUB, 0x80000000_00000000, 1)
    assert result64(snapshot) == 0x7FFFFFFF_FFFFFFFF
    assert flagstr(snapshot.flags) == make_flags(v=True)


# --- DMUL -------------------------------------------------------------------


def test_dmul_basic():
    snapshot = run_dword(Opcode.DMUL, 6, 7)
    assert result64(snapshot) == 42
    assert flagstr(snapshot.flags) == make_flags()


def test_dmul_crosses_word_boundary():
    # 0x100000000 * 2 = 0x200000000 (uses both words, no overflow)
    snapshot = run_dword(Opcode.DMUL, 0x1_00000000, 2)
    assert result64(snapshot) == 0x2_00000000
    assert flagstr(snapshot.flags) == make_flags()


def test_dmul_zero():
    snapshot = run_dword(Opcode.DMUL, 0xDEAD_BEEF, 0)
    assert result64(snapshot) == 0
    assert flagstr(snapshot.flags) == make_flags(z=True)


def test_dmul_negative():
    # (-1) * 3 = -3 = 0xFFFFFFFFFFFFFFFD
    snapshot = run_dword(Opcode.DMUL, MASK64, 3)
    assert result64(snapshot) == 0xFFFFFFFF_FFFFFFFD
    assert flagstr(snapshot.flags) == make_flags(n=True)


def test_dmul_signed_overflow():
    # Large * large overflows the 64-bit signed range -> V and C
    a = 0x0000_0001_0000_0000  # 2**32
    snapshot = run_dword(Opcode.DMUL, a, a)  # 2**64 -> low 64 bits = 0
    assert result64(snapshot) == 0
    assert snapshot.flags.has(Flag.V)
    assert snapshot.flags.has(Flag.C)
    assert snapshot.flags.has(Flag.Z)


# --- DDIV -------------------------------------------------------------------


def test_ddiv_basic():
    snapshot = run_dword(Opcode.DDIV, 42, 6)
    assert result64(snapshot) == 7
    assert flagstr(snapshot.flags) == make_flags()


def test_ddiv_large():
    # 0x2_00000000 / 2 = 0x1_00000000 (result spans both words)
    snapshot = run_dword(Opcode.DDIV, 0x2_00000000, 2)
    assert result64(snapshot) == 0x1_00000000
    assert flagstr(snapshot.flags) == make_flags()


def test_ddiv_negative_truncates_toward_zero():
    # -7 / 2 = -3 (truncate toward zero), not -4
    snapshot = run_dword(Opcode.DDIV, MASK64 - 6, 2)  # -7
    assert signed64(result64(snapshot)) == -3
    assert flagstr(snapshot.flags) == make_flags(n=True)


def test_ddiv_zero_result():
    snapshot = run_dword(Opcode.DDIV, 3, 10)
    assert result64(snapshot) == 0
    assert flagstr(snapshot.flags) == make_flags(z=True)


def test_ddiv_overflow():
    # MIN64 / -1 overflows the signed range -> V
    snapshot = run_dword(Opcode.DDIV, 0x80000000_00000000, MASK64)  # MIN64 / -1
    assert snapshot.flags.has(Flag.V)

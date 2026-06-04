from app.isa.flag import Flag
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode

from tests.shared import run_simulation


def test_add():
    instructions = [
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.PUSH, 0x2),
        Instruction(Opcode.ADD),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x3
    assert snapshot.flags == Flag(0)


def test_add_flag_n():
    # 0xFFFFFFFE + 1 = 0xFFFFFFFF  →  N
    instructions = [
        Instruction(Opcode.PUSH, 0xFFFFFFFE),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.ADD),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0xFFFFFFFF
    assert snapshot.flags == Flag.N


def test_add_flag_z_c():
    # 0xFFFFFFFF + 1 = 0  →  Z C
    instructions = [
        Instruction(Opcode.PUSH, 0xFFFFFFFF),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.ADD),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z | Flag.C


def test_add_flag_v():
    # 0x7FFFFFFF + 1 = 0x80000000  →  N V
    instructions = [
        Instruction(Opcode.PUSH, 0x7FFFFFFF),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.ADD),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    assert snapshot.flags == Flag.N | Flag.V


def test_sub():
    # NOS(2) - TOS(1) = 1
    instructions = [
        Instruction(Opcode.PUSH, 0x2),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.SUB),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x1
    assert snapshot.flags == Flag(0)


def test_sub_flag_z():
    instructions = [
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.SUB),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z


def test_sub_flag_n_c():
    # NOS(2) - TOS(5) = 2-5 = 0xFFFFFFFD  →  N C
    instructions = [
        Instruction(Opcode.PUSH, 0x2),
        Instruction(Opcode.PUSH, 0x5),
        Instruction(Opcode.SUB),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0xFFFFFFFD
    assert snapshot.flags == Flag.N | Flag.C


def test_sub_flag_v():
    # NOS(0x80000000) - TOS(0x7FFFFFFF) = 1  →  V
    instructions = [
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.PUSH, 0x7FFFFFFF),
        Instruction(Opcode.SUB),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x1
    assert snapshot.flags == Flag.V


def test_mul():
    instructions = [
        Instruction(Opcode.PUSH, 0x2),
        Instruction(Opcode.PUSH, 0x2),
        Instruction(Opcode.MUL),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x4
    assert snapshot.flags == Flag(0)


def test_div():
    instructions = [
        Instruction(Opcode.PUSH, 0x2),
        Instruction(Opcode.PUSH, 0x2),
        Instruction(Opcode.DIV),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x1
    assert snapshot.flags == Flag(0)


def test_inc():
    instructions = [
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.INC),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x2
    assert snapshot.flags == Flag(0)


def test_inc_flag_z_c():
    # INC(0xFFFFFFFF) = 0  →  Z C
    instructions = [
        Instruction(Opcode.PUSH, 0xFFFFFFFF),
        Instruction(Opcode.INC),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z | Flag.C


def test_inc_flag_n_v():
    # INC(0x7FFFFFFF) = 0x80000000  →  N V
    instructions = [
        Instruction(Opcode.PUSH, 0x7FFFFFFF),
        Instruction(Opcode.INC),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    assert snapshot.flags == Flag.N | Flag.V


def test_dec():
    instructions = [
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.DEC),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z


def test_dec_flag_n_c():
    # DEC(0) = 0xFFFFFFFF  →  N C
    instructions = [
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.DEC),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0xFFFFFFFF
    assert snapshot.flags == Flag.N | Flag.C


def test_dec_flag_v():
    # DEC(0x80000000) = 0x7FFFFFFF  →  V
    instructions = [
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.DEC),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x7FFFFFFF
    assert snapshot.flags == Flag.V


def test_neg():
    instructions = [
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.NEG),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0xFFFFFFFF
    assert snapshot.flags == Flag.N | Flag.C


def test_neg_flag_z():
    # NEG(0) = 0  →  Z
    instructions = [
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.NEG),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z


def test_neg_flag_v():
    # NEG(0x80000000) = 0x80000000 (overflow)  →  N C V
    instructions = [
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.NEG),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    assert snapshot.flags == Flag.N | Flag.C | Flag.V


def test_and():
    instructions = [
        Instruction(Opcode.PUSH, 0b101),
        Instruction(Opcode.PUSH, 0b001),
        Instruction(Opcode.AND),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0b001
    assert snapshot.flags == Flag(0)


def test_and_flag_n():
    # 0x80000000 & 0xFFFFFFFF = 0x80000000  →  N
    instructions = [
        Instruction(Opcode.PUSH, 0xFFFFFFFF),
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.AND),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    assert snapshot.flags == Flag.N


def test_and_flag_z():
    # 0 & 0xFFFFFFFF = 0  →  Z
    instructions = [
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.PUSH, 0xFFFFFFFF),
        Instruction(Opcode.AND),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z


def test_or():
    instructions = [
        Instruction(Opcode.PUSH, 0b101),
        Instruction(Opcode.PUSH, 0b001),
        Instruction(Opcode.OR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0b101
    assert snapshot.flags == Flag(0)


def test_or_flag_n():
    # 0x80000000 | 1 = 0x80000001  →  N
    instructions = [
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.OR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000001
    assert snapshot.flags == Flag.N


def test_or_flag_z():
    instructions = [
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.OR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z


def test_xor():
    instructions = [
        Instruction(Opcode.PUSH, 0b101),
        Instruction(Opcode.PUSH, 0b001),
        Instruction(Opcode.XOR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0b100
    assert snapshot.flags == Flag(0)


def test_xor_flag_n():
    # 0x7FFFFFFF ^ 0xFFFFFFFF = 0x80000000  →  N
    instructions = [
        Instruction(Opcode.PUSH, 0xFFFFFFFF),
        Instruction(Opcode.PUSH, 0x7FFFFFFF),
        Instruction(Opcode.XOR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    assert snapshot.flags == Flag.N


def test_xor_flag_z():
    instructions = [
        Instruction(Opcode.PUSH, 0xABCD),
        Instruction(Opcode.PUSH, 0xABCD),
        Instruction(Opcode.XOR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z


def test_not():
    # 32-bit bitwise inversion: ~0x00000005 = 0xFFFFFFFA
    instructions = [
        Instruction(Opcode.PUSH, 0b101),
        Instruction(Opcode.NOT),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0xFFFFFFFA
    assert snapshot.flags == Flag.N


def test_not_flag_z():
    # ~0xFFFFFFFF = 0 → Z
    instructions = [
        Instruction(Opcode.PUSH, 0xFFFFFFFF),
        Instruction(Opcode.NOT),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z


def test_not_flag_n():
    # ~0 = 0xFFFFFFFF → N
    instructions = [
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.NOT),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0xFFFFFFFF
    assert snapshot.flags == Flag.N


def test_shl():
    instructions = [
        Instruction(Opcode.PUSH, 0b101),
        Instruction(Opcode.SHL),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0b1010
    assert snapshot.flags == Flag(0)


def test_shl_flag_n():
    # SHL(0x40000000) = 0x80000000  →  N
    instructions = [
        Instruction(Opcode.PUSH, 0x40000000),
        Instruction(Opcode.SHL),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    assert snapshot.flags == Flag.N


def test_shl_flag_z_c():
    # SHL(0x80000000) = 0  →  Z C
    instructions = [
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.SHL),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z | Flag.C


def test_shr():
    instructions = [
        Instruction(Opcode.PUSH, 0b101),
        Instruction(Opcode.SHR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0b10
    assert snapshot.flags == Flag.C


def test_shr_flag_z_c():
    # SHR(1) = 0  →  Z C
    instructions = [
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.SHR),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flag.Z | Flag.C

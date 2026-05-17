from app.isa.flag import Flag
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode

from tests.shared import run_simulation


def test_push():
    memory = {}
    instructions = [
        Instruction(Opcode.PUSH, 0x123),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)

    assert snapshot.data_stack[0] == 0x123

def test_dup():
    memory = {}
    instructions = [
        Instruction(Opcode.PUSH, 0x123),
        Instruction(Opcode.DUP),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)

    assert snapshot.data_stack[0] == 0x123
    assert snapshot.data_stack[1] == 0x123

def test_drop():
    memory = {}
    instructions = [
        Instruction(Opcode.PUSH, 0x123),
        Instruction(Opcode.PUSH, 0x456),
        Instruction(Opcode.DROP),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)
    assert snapshot.data_stack[0] == 0x123
    assert snapshot.data_stack[1] == 0

def test_swap():
    memory = {}
    instructions = [
        Instruction(Opcode.PUSH, 0x123),
        Instruction(Opcode.PUSH, 0x456),
        Instruction(Opcode.SWAP),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)
    assert snapshot.data_stack[1] == 0x123
    assert snapshot.data_stack[0] == 0x456

def test_over():
    memory = {}
    instructions = [
        Instruction(Opcode.PUSH, 0x123),
        Instruction(Opcode.PUSH, 0x456),
        Instruction(Opcode.OVER),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)
    assert snapshot.data_stack[0] == 0x123
    assert snapshot.data_stack[1] == 0x456
    assert snapshot.data_stack[2] == 0x123


def test_drop_preserves_flags():
    # DROP does not modify FLAGS; flags reflect the last PUSH (0x1 → no flags)
    instructions = [
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.DROP),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    # FLAGS were last set by PUSH 0x1 (not zero, not negative) → no flags
    assert snapshot.flags == Flag(0)


def test_drop_does_not_set_n():
    # DROP does not set N even though new TOS has bit 31
    instructions = [
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.DROP),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    # FLAGS were set by PUSH 0x1 → no flags
    assert snapshot.flags == Flag(0)

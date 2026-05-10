from app.isa.flags import Flags
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


def test_drop_flag_z():
    instructions = [
        Instruction(Opcode.PUSH, 0x0),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.DROP),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x0
    assert snapshot.flags == Flags.Z


def test_drop_flag_n():
    instructions = [
        Instruction(Opcode.PUSH, 0x80000000),
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.DROP),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x80000000
    assert snapshot.flags == Flags.N

from app.isa.instruction import Instruction
from app.isa.opcode import Opcode

from tests.shared import run_simulation


def test_load():
    memory = {0x0: 0x1}
    instructions = [
        Instruction(Opcode.LOAD, 0x0),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)

    assert snapshot.tos == 0x1


def test_store():
    memory = {}
    instructions = [
        Instruction(Opcode.PUSH, 0x1),
        Instruction(Opcode.STORE, 0x0),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)

    assert snapshot.data_memory[0] == 0x1

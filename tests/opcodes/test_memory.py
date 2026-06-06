from app.isa.consts import WORD_BYTES
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode

from tests.shared import read_word, run_simulation


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

    assert read_word(snapshot.data_memory, 0) == 0x1


# ---------------------------------------------------------------------------
# Indexed memory access — address taken from the stack
# ---------------------------------------------------------------------------


def test_loadi():
    # LOADI: pop the byte address from TOS, push M[addr].
    addr = 2 * WORD_BYTES  # word index 2
    memory = {addr: 0x99}
    instructions = [
        Instruction(Opcode.PUSH, addr),
        Instruction(Opcode.LOADI),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, memory)

    assert snapshot.tos == 0x99


def test_storei():
    # STOREI: stack is [value, addr]; writes value to M[addr].
    addr = 2 * WORD_BYTES
    instructions = [
        Instruction(Opcode.PUSH, 0x42),  # value
        Instruction(Opcode.PUSH, addr),  # address
        Instruction(Opcode.STOREI),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, {})

    assert read_word(snapshot.data_memory, 2) == 0x42


def test_storei_then_loadi_round_trip():
    addr = 3 * WORD_BYTES
    instructions = [
        Instruction(Opcode.PUSH, 0x1234),  # value
        Instruction(Opcode.PUSH, addr),  # address
        Instruction(Opcode.STOREI),
        Instruction(Opcode.PUSH, addr),
        Instruction(Opcode.LOADI),
        Instruction(Opcode.HALT),
    ]

    snapshot = run_simulation(instructions, {})

    assert snapshot.tos == 0x1234
    assert read_word(snapshot.data_memory, 3) == 0x1234

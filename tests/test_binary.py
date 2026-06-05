import io

import pytest
from app import binary
from app.binary import BinaryFormatError
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.translator.codegen import CompiledProgram


def _program() -> CompiledProgram:
    return CompiledProgram(
        instructions=[
            Instruction(Opcode.PUSH, 0x1234).to_binary(),
            Instruction(Opcode.STORE, 0x8).to_binary(),
            Instruction(Opcode.HALT).to_binary(),
        ],
        data=[1, 2, 3, 0x41],
        interrupt_handlers={1: 0x18, 5: 0x40},
    )


def test_round_trip_preserves_program():
    program = _program()
    buf = io.BytesIO()
    binary.write(buf, program)
    buf.seek(0)
    restored = binary.read(buf)

    assert restored.instructions == program.instructions
    assert restored.data == program.data
    assert restored.interrupt_handlers == program.interrupt_handlers


def test_round_trip_empty_program():
    program = CompiledProgram(instructions=[], data=[], interrupt_handlers={})
    buf = io.BytesIO()
    binary.write(buf, program)
    buf.seek(0)
    restored = binary.read(buf)

    assert restored.instructions == []
    assert restored.data == []
    assert restored.interrupt_handlers == {}


def test_bad_magic_raises():
    buf = io.BytesIO(b"NOPE" + b"\x00" * 64)
    with pytest.raises(BinaryFormatError, match="magic"):
        binary.read(buf)


def test_unsupported_version_raises():
    program = _program()
    buf = io.BytesIO()
    binary.write(buf, program)
    raw = bytearray(buf.getvalue())
    raw[4] = 0xFF  # corrupt the version byte (right after the 4-byte magic)
    with pytest.raises(BinaryFormatError, match="version"):
        binary.read(io.BytesIO(bytes(raw)))

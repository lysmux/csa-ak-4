from __future__ import annotations

import struct
from typing import BinaryIO

from app.translator.codegen import CompiledProgram

MAGIC = b"CUBE"
FORMAT_VERSION = 1

_HEADER = struct.Struct("<4sBxxxIII12x")
_INSTR = struct.Struct("<BI")
_WORD = struct.Struct("<i")
_IVT_ENTRY = struct.Struct("<II")


def write(
    file: BinaryIO,
    program: CompiledProgram,
) -> None:
    file.write(
        _HEADER.pack(
            MAGIC, FORMAT_VERSION, len(program.instructions), len(program.data), len(program.interrupt_handlers)
        )
    )
    for word in program.instructions:
        file.write(_INSTR.pack((word >> 32) & 0xFF, word & 0xFFFFFFFF))
    for word in program.data:
        file.write(_WORD.pack(word & 0xFFFFFFFF))
    for vector, addr in program.interrupt_handlers.items():
        file.write(_IVT_ENTRY.pack(vector, addr))


def read(file: BinaryIO) -> CompiledProgram:
    magic, version, instr_count, data_count, ivt_count = _HEADER.unpack(file.read(_HEADER.size))
    if magic != MAGIC:
        msg = f"Not a CUBE binary (magic={magic!r})"
        raise BinaryFormatError(msg)
    if version != FORMAT_VERSION:
        msg = f"Unsupported format version {version}"
        raise BinaryFormatError(msg)

    instructions: list[int] = []
    for _ in range(instr_count):
        opcode, operand = _INSTR.unpack(file.read(_INSTR.size))
        instructions.append((opcode << 32) | operand)

    data: list[int] = []
    for _ in range(data_count):
        (word,) = _WORD.unpack(file.read(_WORD.size))
        data.append(word)

    interrupt_handlers: dict[int, int] = {}
    for _ in range(ivt_count):
        vector, addr = _IVT_ENTRY.unpack(file.read(_IVT_ENTRY.size))
        interrupt_handlers[vector] = addr

    return CompiledProgram(instructions, data, interrupt_handlers)


class BinaryFormatError(Exception):
    pass

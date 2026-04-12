from enum import IntEnum, unique

OPCODE_LENGTH = 4


@unique
class Opcode(IntEnum):
    # === Math ===
    ADD = 0x01
    SUB = 0x02
    INC = 0x03
    DEC = 0x04
    # === Math ===

    # === Data stack ===
    LOAD = 0x05
    # === Data stack ===

    # === Jumps ===
    JMP = 0x06
    JC  = 0x07
    JZ  = 0x08
    JN  = 0x09
    # === Jumps ===

    HALT = 0x0F

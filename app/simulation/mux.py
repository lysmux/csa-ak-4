from enum import IntEnum, auto


class PCMux(IntEnum):
    NEXT = auto()
    OPERAND = auto()
    R_STACK = auto()
    VECTOR = auto()


class RStackMux(IntEnum):
    PC = auto()
    TOS = auto()
    FLAGS = auto()
    ALU = auto()


class ARMux(IntEnum):
    OPERAND = auto()
    TOS = auto()


class TosMux(IntEnum):
    OPERAND = auto()
    NOS = auto()
    ALU = auto()
    MEMORY = auto()
    R_STACK = auto()


class NosMux(IntEnum):
    TOS = auto()
    D_STACK = auto()


class DSPMux(IntEnum):
    INC = auto()
    DEC = auto()


class RSPMux(IntEnum):
    INC = auto()
    DEC = auto()

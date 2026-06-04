from enum import IntEnum, auto


class PCMux(IntEnum):
    NEXT = auto()
    ADDRESS = auto()
    R_STACK = auto()
    VECTOR = auto()


class RStackMux(IntEnum):
    PC = auto()
    TOS = auto()
    FLAGS = auto()
    ALU = auto()


class ARMux(IntEnum):
    IR_OPERAND = auto()
    TOS = auto()


class DStackMux(IntEnum):
    IR_OPERAND = auto()
    TOS = auto()
    NOS = auto()
    ALU = auto()
    MEMORY = auto()
    R_STACK = auto()


class DSPMux(IntEnum):
    INC = auto()
    DEC = auto()

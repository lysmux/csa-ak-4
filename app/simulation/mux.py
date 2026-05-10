from enum import IntEnum, auto


class PCMux(IntEnum):
    NEXT = auto()
    ADDRESS = auto()
    R_STACK = auto()
    VECTOR = auto()

class RStackMux(IntEnum):
    PC = auto()
    ALU = auto()

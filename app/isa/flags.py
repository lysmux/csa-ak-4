from enum import IntFlag

from app.isa.consts import SIGN_BIT


class Flags(IntFlag):
    N = 1 << 0
    Z = 1 << 1
    V = 1 << 2
    C = 1 << 3

    @classmethod
    def nz(cls, value: int) -> "Flags":
        flags = Flags(0)
        if value == 0:
            flags |= Flags.Z
        if value & SIGN_BIT:
            flags |= Flags.N
        return flags

class ProgramState(IntFlag):
    IE = 1 << 0
    IRQ = 1 << 1

from __future__ import annotations

from enum import IntFlag

from app.isa.consts import SIGN_BIT


class Flag(IntFlag):
    N = 1 << 0
    Z = 1 << 1
    V = 1 << 2
    C = 1 << 3

    @classmethod
    def nz(cls, value: int) -> Flag:
        flags = Flag(0)
        if value == 0:
            flags |= Flag.Z
        if value & SIGN_BIT:
            flags |= Flag.N
        return flags

    def has(self, flag: Flag) -> bool:
        return bool(self & flag)

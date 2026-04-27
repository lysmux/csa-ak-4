from enum import IntFlag


class Flags(IntFlag):
    N = 1 << 0
    Z = 1 << 1
    V = 1 << 2
    C = 1 << 3

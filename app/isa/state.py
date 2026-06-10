from enum import StrEnum, auto


class State(StrEnum):
    HALT = auto()

    INTERRUPT = auto()
    FETCH = auto()
    EXECUTE = auto()
    CHECK_IRQ = auto()

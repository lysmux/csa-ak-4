from enum import StrEnum, auto


class State(StrEnum):
    HALT = auto()

    START = auto()
    INTERRUPT = auto()
    FETCH = auto()
    EXECUTE = auto()
    DONE = auto()

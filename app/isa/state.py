from enum import StrEnum, auto


class State(StrEnum):
    HALT = auto()
    FETCH = auto()
    EXECUTE = auto()

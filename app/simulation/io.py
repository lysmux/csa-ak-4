from typing import Protocol


class Device(Protocol):
    def read(self) -> int: ...
    def write(self, value: int) -> None: ...

class CharOutput(Device):
    def __init__(self) -> None:
        self.buffer: list[int] = []

    @property
    def string(self) -> str:
        result = ""
        for char in self.buffer:
            if char == 0:
                break
            result += chr(char)
        return result

    def read(self) -> int: ...
    def write(self, value: int) -> None:
        self.buffer.append(value)

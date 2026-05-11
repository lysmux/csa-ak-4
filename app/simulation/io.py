from typing import Protocol


class Device(Protocol):
    def read(self) -> int: ...
    def write(self, value: int) -> None: ...
    def tick(self, current_tick: int) -> int | None: ...


class CharOutput(Device):
    def __init__(self) -> None:
        self.buffer: list[int] = []

    @property
    def string(self) -> str:
        result = ""
        for char in self.buffer:
            result += chr(char)
        return result

    def read(self) -> int: ...
    def write(self, value: int) -> None:
        self.buffer.append(value)

    def tick(self, current_tick: int) -> int | None:
        return None


class CharInput(Device):
    def __init__(self, schedule: list[tuple[int, str]], vector: int) -> None:
        self._schedule: list[tuple[int, str]] = sorted(schedule, key=lambda p: p[0])
        self._vector = vector
        self._port: int | None = None

    def tick(self, current_tick: int) -> int | None:
        while self._schedule and self._schedule[0][0] <= current_tick:
            _, ch = self._schedule.pop(0)
            self._port = ord(ch)
        return self._vector if self._port is not None else None

    def read(self) -> int:
        if self._port is None:
            return 0
        value, self._port = self._port, None
        return value

    def write(self, value: int) -> None: ...

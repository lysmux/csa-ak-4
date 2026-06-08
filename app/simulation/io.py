from typing import Literal


class Device:
    def read(self) -> int:
        msg = f"{type(self).__name__} does not support read"
        raise NotImplementedError(msg)

    def write(self, value: int) -> None:
        msg = f"{type(self).__name__} does not support write"
        raise NotImplementedError(msg)

    def tick(self, current_tick: int) -> int | None:
        return None

    def as_string(self) -> str:
        return ""


class Output(Device):
    def __init__(self, mode: Literal["string", "raw"]) -> None:
        self.mode = mode
        self.buffer: list[int] = []

    def write(self, value: int) -> None:
        self.buffer.append(value)

    def as_string(self) -> str:
        if self.mode == "string":
            return "".join(map(chr, self.buffer))
        return " ".join(str(v) for v in self.buffer)


class Input(Device):
    def __init__(self, schedule: list[tuple[int, int | str]], vector: int) -> None:
        normalized = [(t, ord(v) if isinstance(v, str) else v) for t, v in schedule]
        self._schedule: list[tuple[int, int]] = sorted(normalized, key=lambda p: p[0])
        self._vector = vector
        self._port: int | None = None

    def tick(self, current_tick: int) -> int | None:
        while self._schedule and self._schedule[0][0] <= current_tick:
            _, value = self._schedule.pop(0)
            self._port = value
        return self._vector if self._port is not None else None

    def read(self) -> int:
        if self._port is None:
            return 0
        value, self._port = self._port, None
        return value

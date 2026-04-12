import logging

from app.simulation.trigger import DTrigger

logger = logging.getLogger(__name__)

class Memory:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity

        self.addr = DTrigger()

        self._memory = [0] * capacity

        self._in: int = 0
        self._out: int = 0

    def get_signal(self) -> None:
        self._validate_address()

        self._out = self._memory[self.addr.current]

    def write_signal(self) -> None:
        self._validate_address()

        self._memory[self.addr.current] = self._in

    @property
    def out(self) -> int:
        return self._out

    @property
    def in_(self) -> int:
        return self._in

    def set_in(self, in_: int) -> None:
        self._in = in_

    def fill(self, data: list[int]) -> None:
        if len(data) > self.capacity:
            logger.warning("Data size exceeds the memory capacity. Excess will be discarded")

        self._memory = data[:self.capacity]


    def _validate_address(self) -> None:
        if self.addr.current < 0 or self.addr.current > self.capacity:
            raise IndexError("Memory address out of range")

    def __str__(self) -> str:
        dump = "\n".join(f"{i:#010x} - {data:#010x}" for i, data in enumerate(self._memory))

        return f"Memory({self.capacity})\n{dump}"

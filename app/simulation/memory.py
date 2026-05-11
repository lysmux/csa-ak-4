import logging

logger = logging.getLogger(__name__)


class Memory:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity

        self._memory = [0] * capacity

    def read(self, address: int) -> int:
        self._validate_address(address)

        return self._memory[address]

    def write(self, address: int, value: int) -> None:
        self._validate_address(address)

        self._memory[address] = value

    def fill(self, data: list[int]) -> None:
        if len(data) > self.capacity:
            logger.warning("Data size exceeds the memory capacity %d. Excess will be discarded", self.capacity)

        self._memory[: min(self.capacity, len(data))] = data[: self.capacity]

    def _validate_address(self, address: int) -> None:
        if address < 0 or address > self.capacity:
            msg = f"Memory address out of range [0, {self.capacity - 1}]"
            raise IndexError(msg)

    def __str__(self) -> str:
        dump = "\n".join(f"{i:#010x} - {data:#010x}" for i, data in enumerate(self._memory))
        return f"Memory({self.capacity})\n{dump}"

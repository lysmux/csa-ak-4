import logging

from app.isa.consts import INSTR_BYTES, WORD_BYTES

logger = logging.getLogger(__name__)


class Memory:
    def __init__(self, capacity: int, word_bytes: int) -> None:
        self.capacity = capacity
        self._word_bytes = word_bytes
        self._mask = (1 << (word_bytes * 8)) - 1

        self._memory = bytearray(capacity)

    def read_byte(self, address: int) -> int:
        self._validate_address(address)
        return self._memory[address]

    def read(self, address: int) -> int:
        self._validate_address(address)
        return int.from_bytes(self._memory[address : address + self._word_bytes], "little")

    def write_byte(self, address: int, value: int) -> None:
        self._validate_address(address)
        self._memory[address] = value & 0xFF

    def write(self, address: int, value: int) -> None:
        self._validate_address(address)
        self._memory[address : address + self._word_bytes] = (value & self._mask).to_bytes(self._word_bytes, "little")

    def fill(self, words: list[int]) -> None:
        max_words = self.capacity // self._word_bytes

        if len(words) > max_words:
            logger.warning(
                "Data size %d words exceeds the memory capacity %d words. Excess will be discarded",
                len(words),
                max_words,
            )

        for index, word in enumerate(words[:max_words]):
            self.write(index * self._word_bytes, word)

    def fill_bytes(self, data: bytes | bytearray) -> None:
        if len(data) > self.capacity:
            logger.warning(
                "Data size %d bytes exceeds the memory capacity %d bytes. Excess will be discarded",
                len(data),
                self.capacity,
            )

        self._memory[: min(len(data), self.capacity)] = data[: self.capacity]

    @property
    def memory(self) -> bytearray:
        return self._memory

    def _validate_address(self, address: int) -> None:
        if address < 0 or address > self.capacity - 1:
            msg = f"Memory address out of range [0, {self.capacity - 1}]"
            raise IndexError(msg)

    def __str__(self) -> str:
        width = WORD_BYTES + 2
        dump = "\n".join(f"{i:#0{width}x} - {data:#0{width}x}" for i, data in enumerate(self.memory))
        return f"Memory({self.capacity})\n{dump}"


class DataMemory(Memory):
    def __init__(self, capacity: int) -> None:
        super().__init__(capacity, WORD_BYTES)


class InstrMemory(Memory):
    def __init__(self, capacity: int) -> None:
        super().__init__(capacity, INSTR_BYTES)

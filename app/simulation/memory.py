import logging

from app.isa.consts import WORD_BYTES

logger = logging.getLogger(__name__)


class Memory:
    """Byte-backed memory addressed by byte address, accessed a whole word at a time.

    `capacity` is the number of word-sized cells (unchanged meaning); the line width
    `word_bytes` is the number of bytes assembled per access (little-endian). A read or
    write of address `a` touches the slice `_bytes[a : a + word_bytes]` — the processor
    reads the whole line in one go.
    """

    def __init__(self, capacity: int, word_bytes: int = WORD_BYTES) -> None:
        self.capacity = capacity
        self._word_bytes = word_bytes
        self._mask = (1 << (word_bytes * 8)) - 1
        self._bytes = bytearray(capacity * word_bytes)

    def read(self, address: int) -> int:
        self._validate_address(address)

        return int.from_bytes(self._bytes[address : address + self._word_bytes], "little")

    def write(self, address: int, value: int) -> None:
        self._validate_address(address)

        self._bytes[address : address + self._word_bytes] = (value & self._mask).to_bytes(self._word_bytes, "little")

    def fill(self, data: list[int]) -> None:
        if len(data) > self.capacity:
            logger.warning("Data size exceeds the memory capacity %d. Excess will be discarded", self.capacity)

        for index, word in enumerate(data[: self.capacity]):
            start = index * self._word_bytes
            self._bytes[start : start + self._word_bytes] = (word & self._mask).to_bytes(self._word_bytes, "little")

    @property
    def _memory(self) -> list[int]:
        return [self.read(i * self._word_bytes) for i in range(self.capacity)]

    def _validate_address(self, address: int) -> None:
        if address < 0 or address + self._word_bytes > self.capacity * self._word_bytes:
            msg = f"Memory address out of range [0, {self.capacity * self._word_bytes - 1}]"
            raise IndexError(msg)

    def __str__(self) -> str:
        dump = "\n".join(f"{i:#010x} - {data:#010x}" for i, data in enumerate(self._memory))
        return f"Memory({self.capacity})\n{dump}"
